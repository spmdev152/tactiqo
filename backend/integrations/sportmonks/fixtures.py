import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime

from apps.fixtures.domain.enums import FixtureStatus
from integrations.sportmonks.client import ProviderPayload, SportmonksClient
from integrations.sportmonks.exceptions import SportmonksError

logger = logging.getLogger(__name__)

PAGE_SIZE = 100

KICKOFF_FORMAT = "%Y-%m-%d %H:%M:%S"

HOME_LOCATION = "home"

AWAY_LOCATION = "away"

CURRENT_SCORE = "CURRENT"

PROVIDER_STATES: dict[str, FixtureStatus] = {
    "NS": FixtureStatus.SCHEDULED,
    "TBA": FixtureStatus.SCHEDULED,
    "PENDING": FixtureStatus.SCHEDULED,
    "AWAITING_UPDATES": FixtureStatus.SCHEDULED,
    "INPLAY_1ST_HALF": FixtureStatus.LIVE,
    "INPLAY_2ND_HALF": FixtureStatus.LIVE,
    "INPLAY_ET": FixtureStatus.LIVE,
    "INPLAY_ET_2ND_HALF": FixtureStatus.LIVE,
    "INPLAY_PENALTIES": FixtureStatus.LIVE,
    "HT": FixtureStatus.LIVE,
    "BREAK": FixtureStatus.LIVE,
    "EXTRA_TIME_BREAK": FixtureStatus.LIVE,
    "PEN_BREAK": FixtureStatus.LIVE,
    "INTERRUPTED": FixtureStatus.LIVE,
    "SUSPENDED": FixtureStatus.LIVE,
    "FT": FixtureStatus.FINISHED,
    "AET": FixtureStatus.FINISHED,
    "FT_PEN": FixtureStatus.FINISHED,
    "WO": FixtureStatus.FINISHED,
    "AWARDED": FixtureStatus.FINISHED,
    "POSTPONED": FixtureStatus.POSTPONED,
    "DELAYED": FixtureStatus.POSTPONED,
    "CANCELLED": FixtureStatus.CANCELLED,
    "ABANDONED": FixtureStatus.CANCELLED,
    "DELETED": FixtureStatus.CANCELLED,
}


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
    A match as the provider describes it, played or still to be played.

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
    status : FixtureStatus
        Lifecycle stage the provider state maps onto, read as scheduled when it
        publishes a state this boundary does not know.
    home_goals : int or None
        Goals the home side has scored, ``None`` when the provider publishes no
        readable current score for both sides.
    away_goals : int or None
        Goals the away side has scored, ``None`` under the same condition.
    """

    provider_id: int
    kickoff_at: datetime
    league: ProviderLeague
    home_team: ProviderTeam
    away_team: ProviderTeam
    status: FixtureStatus
    home_goals: int | None
    away_goals: int | None


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
        "include": "participants;league;state;scores",
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

    home_goals, away_goals = _goals_of(entry.get("scores"), provider_id)

    return ProviderFixture(
        provider_id=provider_id,
        kickoff_at=kickoff_at,
        league=league,
        home_team=home_team,
        away_team=away_team,
        status=_status_of(entry.get("state"), provider_id),
        home_goals=home_goals,
        away_goals=away_goals,
    )


def _status_of(payload: object, provider_id: int) -> FixtureStatus:
    """
    Map the state a fixture entry reports onto the platform's vocabulary.

    The provider publishes twenty-five states and the mapping is an explicit
    lookup rather than a test on the shape of a code, because the shape carries
    no meaning: ``FT`` and ``FT_PEN`` are both finished while
    ``INPLAY_PENALTIES`` is not, and a state added later must be reported rather
    than guessed at.

    Parameters
    ----------
    payload : object
        Value the ``state`` include carried, documented as an object whose
        ``state`` field names the code.
    provider_id : int
        Identifier of the fixture, named in the warning of an unknown state.

    Returns
    -------
    FixtureStatus
        Stage the state maps onto, or ``FixtureStatus.SCHEDULED`` when the
        provider names a state this boundary does not know.
    """

    code = _text(payload.get("state")) if isinstance(payload, dict) else ""

    status = PROVIDER_STATES.get(code)

    if status is None:
        logger.warning(
            "Reading Sportmonks fixture %d as scheduled: %r is not a state this boundary maps.",
            provider_id,
            code,
        )

        return FixtureStatus.SCHEDULED

    return status


def _goals_of(payload: object, provider_id: int) -> tuple[int | None, int | None]:
    """
    Return the current score a fixture entry reports, for both sides or neither.

    The include carries one entry per period, so only the two the provider
    describes as ``"CURRENT"`` state the score of the match; the half-time and
    second-half entries would otherwise overwrite it. A score naming one side
    alone is discarded rather than half-stored, and the fixture itself survives:
    a match with an unreadable score is still a match worth listing.

    Parameters
    ----------
    payload : object
        Value the ``scores`` include carried, documented as a list of period
        entries and empty for a match that has not produced a score.
    provider_id : int
        Identifier of the fixture, named in the warning of a half-written score.

    Returns
    -------
    tuple of int or None
        Home goals then away goals, or ``None`` twice when the entries do not
        state a readable count for both sides.
    """

    if not isinstance(payload, list):
        return None, None

    by_location: dict[str, int] = {}

    for entry in payload:
        side = _current_side_of(entry) if isinstance(entry, dict) else None

        if side is None:
            continue

        location, goals = side

        by_location[location] = goals

    if not by_location:
        return None, None

    if by_location.keys() != {HOME_LOCATION, AWAY_LOCATION}:
        logger.warning(
            "Ignoring the score of Sportmonks fixture %d: its current entries name %r rather "
            "than both sides.",
            provider_id,
            sorted(by_location),
        )

        return None, None

    return by_location[HOME_LOCATION], by_location[AWAY_LOCATION]


def _current_side_of(entry: ProviderPayload) -> tuple[str, int] | None:
    """
    Normalize one score entry into the side it belongs to and its goal count.

    Parameters
    ----------
    entry : ProviderPayload
        One entry of the ``scores`` include.

    Returns
    -------
    tuple of str and int or None
        Location, either ``"home"`` or ``"away"``, and the goals scored there,
        or ``None`` when the entry describes another period, names no side, or
        carries no readable count.
    """

    if _text(entry.get("description")) != CURRENT_SCORE:
        return None

    score = entry.get("score")

    if not isinstance(score, dict):
        return None

    goals = _goal_count(score.get("goals"))

    location = _text(score.get("participant"))

    if goals is None or location not in (HOME_LOCATION, AWAY_LOCATION):
        return None

    return location, goals


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


def _goal_count(value: object) -> int | None:
    """
    Return a goal count as a non-negative integer.

    Parameters
    ----------
    value : object
        Value the ``goals`` field of a score carried, documented as a number and
        published as ``null`` while a match has produced no score.

    Returns
    -------
    int or None
        Goals scored, or ``None`` when the value is not a count, which includes
        the boolean and negative cases the column would refuse anyway.
    """

    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None

    return value


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
