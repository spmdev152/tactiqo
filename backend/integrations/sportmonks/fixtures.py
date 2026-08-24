import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime

from integrations.sportmonks.client import ProviderPayload, SportmonksClient
from integrations.sportmonks.exceptions import SportmonksError

logger = logging.getLogger(__name__)

PAGE_SIZE = 100

KICKOFF_FORMAT = "%Y-%m-%d %H:%M:%S"

HOME_LOCATION = "home"

AWAY_LOCATION = "away"


@dataclass(frozen=True, slots=True)
class ProviderTeam:
    """
    One side of a fixture as the provider describes it.

    Attributes
    ----------
    provider_id : int
        Sportmonks team identifier.
    name : str
        Full team name.
    short_code : str
        Three-letter abbreviation, empty when the provider omits it.
    crest_url : str
        Absolute URL of the team crest, empty when the provider omits it.
    """

    provider_id: int
    name: str
    short_code: str
    crest_url: str


@dataclass(frozen=True, slots=True)
class ProviderLeague:
    """
    A competition as the provider describes it, with its country.

    Attributes
    ----------
    provider_id : int
        Sportmonks league identifier.
    name : str
        Full competition name.
    short_code : str
        Abbreviation the provider publishes, empty when it omits one.
    logo_url : str
        Absolute URL of the competition logo, empty when the provider omits it.
    country_name : str
        Name of the country the competition belongs to.
    country_flag_url : str
        Absolute URL of the country flag, empty when the provider omits it.
    """

    provider_id: int
    name: str
    short_code: str
    logo_url: str
    country_name: str
    country_flag_url: str


@dataclass(frozen=True, slots=True)
class ProviderFixture:
    """
    A scheduled match as the provider describes it.

    Attributes
    ----------
    provider_id : int
        Sportmonks fixture identifier.
    kickoff_at : datetime
        Timezone-aware kick-off instant, always expressed in UTC.
    league : ProviderLeague
        Competition the fixture belongs to.
    home_team : ProviderTeam
        Side playing at home.
    away_team : ProviderTeam
        Side playing away.
    """

    provider_id: int
    kickoff_at: datetime
    league: ProviderLeague
    home_team: ProviderTeam
    away_team: ProviderTeam


def fetch_fixtures_between(
    start: date, end: date, league_ids: Sequence[int]
) -> list[ProviderFixture]:
    """
    Return the fixtures the provider schedules in a window, normalized.

    Two provider resources are read. The competitions are fetched first, with
    their country included, because the fixture payload carries a competition
    logo but no country flag; they are reference data for the whole window and
    cost one request rather than one per fixture.

    A row the provider returns malformed is dropped with a warning instead of
    failing the window, so one broken fixture cannot cost a refresh every other
    fixture in the same range.

    Parameters
    ----------
    start : date
        First day of the window, inclusive.
    end : date
        Last day of the window, inclusive.
    league_ids : sequence of int
        Sportmonks league identifiers to restrict the window to.

    Returns
    -------
    list of ProviderFixture
        Fixtures of the window, in provider order.

    Raises
    ------
    SportmonksError
        When no league is requested, or when the provider cannot be read.
    """

    if not league_ids:
        raise SportmonksError("No Sportmonks league was requested, so no window can be read.")

    client = SportmonksClient()

    leagues = _fetch_leagues(client, league_ids)

    params = {
        "filters": f"fixtureLeagues:{_joined(league_ids)}",
        "include": "participants;league;state",
        "per_page": PAGE_SIZE,
    }

    path = f"/fixtures/between/{start.isoformat()}/{end.isoformat()}"

    fixtures: list[ProviderFixture] = []

    for page in client.get_pages(path, params):
        for entry in page:
            fixture = _fixture_of(entry, leagues)

            if fixture is not None:
                fixtures.append(fixture)

    return fixtures


def _fetch_leagues(
    client: SportmonksClient, league_ids: Sequence[int]
) -> dict[int, ProviderLeague]:
    """
    Return the requested competitions, keyed by provider identifier.

    Parameters
    ----------
    client : SportmonksClient
        Client the request is issued through.
    league_ids : sequence of int
        Sportmonks league identifiers to fetch.

    Returns
    -------
    dict of int to ProviderLeague
        Competitions the provider returned for the requested identifiers.

    Raises
    ------
    SportmonksError
        When the provider cannot be read.
    """

    params = {
        "filters": f"leagueIds:{_joined(league_ids)}",
        "include": "country",
        "per_page": PAGE_SIZE,
    }

    leagues: dict[int, ProviderLeague] = {}

    for page in client.get_pages("/leagues", params):
        for entry in page:
            league = _league_of(entry)

            if league is not None:
                leagues[league.provider_id] = league

    return leagues


def _fixture_of(
    entry: ProviderPayload, leagues: dict[int, ProviderLeague]
) -> ProviderFixture | None:
    """
    Normalize one fixture entry, or report it as unusable.

    Parameters
    ----------
    entry : ProviderPayload
        One entry of a fixtures page.
    leagues : dict of int to ProviderLeague
        Competitions resolved for the window, which is also the set of
        competitions a fixture is allowed to belong to.

    Returns
    -------
    ProviderFixture or None
        Normalized fixture, or ``None`` when the entry lacks an identifier, a
        parseable kick-off, a requested competition, or exactly one home and
        one away side.
    """

    provider_id = _identifier(entry.get("id"))

    if provider_id is None:
        logger.warning("Skipping a Sportmonks fixture that carries no usable identifier.")

        return None

    league_id = _league_reference(entry)

    league = leagues.get(league_id) if league_id is not None else None

    if league is None:
        logger.warning(
            "Skipping Sportmonks fixture %d: league %r is not one of the requested competitions.",
            provider_id,
            league_id,
        )

        return None

    kickoff_at = _kickoff_of(entry.get("starting_at"))

    if kickoff_at is None:
        logger.warning(
            "Skipping Sportmonks fixture %d: %r is not a readable kick-off.",
            provider_id,
            entry.get("starting_at"),
        )

        return None

    sides = _sides_of(entry.get("participants"))

    if sides is None:
        logger.warning(
            "Skipping Sportmonks fixture %d: its participants do not name one home and one "
            "away side.",
            provider_id,
        )

        return None

    home_team, away_team = sides

    return ProviderFixture(
        provider_id=provider_id,
        kickoff_at=kickoff_at,
        league=league,
        home_team=home_team,
        away_team=away_team,
    )


def _league_of(entry: ProviderPayload) -> ProviderLeague | None:
    """
    Normalize one competition entry, or report it as unusable.

    Parameters
    ----------
    entry : ProviderPayload
        One entry of a leagues page, with its country included.

    Returns
    -------
    ProviderLeague or None
        Normalized competition, or ``None`` when the entry carries no usable
        identifier.
    """

    provider_id = _identifier(entry.get("id"))

    if provider_id is None:
        logger.warning("Skipping a Sportmonks league that carries no usable identifier.")

        return None

    country = entry.get("country")

    country_payload: ProviderPayload = country if isinstance(country, dict) else {}

    return ProviderLeague(
        provider_id=provider_id,
        name=_text(entry.get("name")),
        short_code=_text(entry.get("short_code")),
        logo_url=_text(entry.get("image_path")),
        country_name=_text(country_payload.get("name")),
        country_flag_url=_text(country_payload.get("image_path")),
    )


def _league_reference(entry: ProviderPayload) -> int | None:
    """
    Return the competition a fixture entry belongs to.

    Parameters
    ----------
    entry : ProviderPayload
        One entry of a fixtures page.

    Returns
    -------
    int or None
        Sportmonks league identifier taken from the entry's own field, or from
        the included competition when the field is absent, or ``None`` when
        neither names one.
    """

    from_field = _identifier(entry.get("league_id"))

    if from_field is not None:
        return from_field

    included = entry.get("league")

    return _identifier(included.get("id")) if isinstance(included, dict) else None


def _sides_of(payload: object) -> tuple[ProviderTeam, ProviderTeam] | None:
    """
    Return the home and away sides a participants list names.

    Parameters
    ----------
    payload : object
        Value the ``participants`` include carried, which the provider
        documents as a two-element list but is not trusted to be one.

    Returns
    -------
    tuple of ProviderTeam or None
        Home side then away side, or ``None`` unless the list names exactly one
        of each.
    """

    if not isinstance(payload, list):
        return None

    sides = [
        side
        for side in (_side_of(entry) for entry in payload if isinstance(entry, dict))
        if side is not None
    ]

    locations = [location for location, _ in sides]

    if locations.count(HOME_LOCATION) != 1 or locations.count(AWAY_LOCATION) != 1:
        return None

    by_location = dict(sides)

    return by_location[HOME_LOCATION], by_location[AWAY_LOCATION]


def _side_of(entry: ProviderPayload) -> tuple[str, ProviderTeam] | None:
    """
    Normalize one participant into the location it plays at and its team.

    Parameters
    ----------
    entry : ProviderPayload
        One entry of the ``participants`` include.

    Returns
    -------
    tuple of str and ProviderTeam or None
        Location, either ``"home"`` or ``"away"``, and the team playing there,
        or ``None`` when the entry names neither location or carries no usable
        identifier.
    """

    provider_id = _identifier(entry.get("id"))

    meta = entry.get("meta")

    location = _text(meta.get("location")) if isinstance(meta, dict) else ""

    if provider_id is None or location not in (HOME_LOCATION, AWAY_LOCATION):
        return None

    team = ProviderTeam(
        provider_id=provider_id,
        name=_text(entry.get("name")),
        short_code=_text(entry.get("short_code")),
        crest_url=_text(entry.get("image_path")),
    )

    return location, team


def _kickoff_of(value: object) -> datetime | None:
    """
    Parse a provider kick-off stamp into a timezone-aware UTC instant.

    Parameters
    ----------
    value : object
        Value the ``starting_at`` field carried, documented as
        ``"YYYY-MM-DD HH:MM:SS"`` in UTC and carrying no offset of its own.

    Returns
    -------
    datetime or None
        Kick-off instant in UTC, or ``None`` when the value is not a stamp in
        that format.
    """

    if not isinstance(value, str):
        return None

    try:
        naive = datetime.strptime(value, KICKOFF_FORMAT)
    except ValueError:
        return None

    return naive.replace(tzinfo=UTC)


def _identifier(value: object) -> int | None:
    """
    Return a provider identifier as an integer.

    Parameters
    ----------
    value : object
        Value an identifier field carried, which the provider sends as a number
        but has been observed to send as a string of digits.

    Returns
    -------
    int or None
        Identifier, or ``None`` when the value does not denote one.
    """

    if isinstance(value, bool):
        return None

    if isinstance(value, int):
        return value

    if isinstance(value, str) and value.isdigit():
        return int(value)

    return None


def _text(value: object) -> str:
    """
    Return a provider string, collapsing an absent one to the empty string.

    Parameters
    ----------
    value : object
        Value an optional text field carried.

    Returns
    -------
    str
        The string, or ``""`` when the provider omitted it or sent something
        else.
    """

    return value if isinstance(value, str) else ""


def _joined(league_ids: Sequence[int]) -> str:
    """
    Render league identifiers as the comma-separated list a filter expects.

    Parameters
    ----------
    league_ids : sequence of int
        Sportmonks league identifiers.

    Returns
    -------
    str
        Identifiers joined by commas.
    """

    return ",".join(str(league_id) for league_id in league_ids)
