import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime

from apps.fixtures.domain.enums import FixtureStatus
from integrations.sportmonks.client import ProviderPayload, SportmonksClient
from integrations.sportmonks.exceptions import SportmonksError

logger = logging.getLogger(__name__)

# Rows a page. The provider honours one to fifty and silently falls back to its own default of
# twenty-five for anything larger, so a hundred would quadruple the pages instead of halving them.
PAGE_SIZE = 50

PROVIDER_TIMEZONE = "UTC"

KICKOFF_FORMAT = "%Y-%m-%d %H:%M:%S"

HOME_LOCATION = "home"

AWAY_LOCATION = "away"

CURRENT_SCORE = "CURRENT"

# The three bounds below mirror the columns of ``apps.fixtures.models`` rather than importing
# them, because the provider adapter must not depend on the persistence it feeds.
NAME_LIMIT = 255

SHORT_CODE_LIMIT = 16

URL_LIMIT = 512

GOALS_LIMIT = 32767

IDENTIFIER_MINIMUM = -(2**63)

IDENTIFIER_MAXIMUM = 2**63 - 1

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
    "ABANDONED": FixtureStatus.LIVE,
    "FT": FixtureStatus.FINISHED,
    "AET": FixtureStatus.FINISHED,
    "FT_PEN": FixtureStatus.FINISHED,
    "WO": FixtureStatus.FINISHED,
    "AWARDED": FixtureStatus.FINISHED,
    "POSTPONED": FixtureStatus.POSTPONED,
    "DELAYED": FixtureStatus.POSTPONED,
    "CANCELLED": FixtureStatus.CANCELLED,
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
    season_provider_id : int or None
        Sportmonks identifier of the season the fixture is played in, ``None``
        when the provider states none this boundary can read. It is the only
        identifier besides the fixture's own that leaves this boundary, because
        a form sample scoped to a season has no other way to tell where the
        season begins.
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
    season_provider_id: int | None
    kickoff_at: datetime
    league: ProviderLeague
    home_team: ProviderTeam
    away_team: ProviderTeam
    status: FixtureStatus
    home_goals: int | None
    away_goals: int | None


@dataclass(frozen=True, slots=True)
class ProviderWindow:
    """
    Everything one complete read of a fixture window resolved.

    The competitions are carried separately from the fixtures because they are
    reference data for the whole subscription rather than a property of the
    window. A competition on its winter break, or one whose season has not
    started, schedules nothing in a fortnight and would otherwise disappear from
    the product for as long as that lasts.

    Attributes
    ----------
    leagues : dict of int to ProviderLeague
        Every subscribed competition the provider returned, keyed by provider
        identifier, whether or not it schedules a fixture inside the window.
    fixtures : list of ProviderFixture
        Fixtures of the window, in provider order.
    """

    leagues: dict[int, ProviderLeague]
    fixtures: list[ProviderFixture]


def fetch_fixtures_between(start: date, end: date, league_ids: Sequence[int]) -> ProviderWindow:
    """
    Return the competitions and the fixtures a window covers, normalized.

    Two provider resources are read. The competitions are fetched first, with
    their country included, because the fixture payload carries a competition
    logo but no country flag; they are reference data for the whole window and
    cost one request rather than one per fixture.

    A row the provider returns malformed is dropped with a warning instead of
    failing the window, so one broken fixture cannot cost a refresh every other
    fixture in the same range. A window the provider cannot serve completely is
    the opposite case and fails: the client raises rather than returning the
    pages it managed to read, because a caller cannot tell a prefix of a window
    from the whole of it.

    Both requests state ``timezone=UTC``, so the instant every stored kick-off
    is derived from is part of the request rather than a provider default that
    nothing checks.

    One read cannot exceed ``PAGE_SIZE`` rows over ``MAX_PAGE_COUNT`` pages, or
    two thousand fixtures. The five subscribed leagues schedule roughly a
    hundred and fifty in the widest window this project synchronizes, so the
    ceiling is an order of magnitude clear of the traffic it bounds.

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
    ProviderWindow
        Subscribed competitions and the normalized fixtures of the window.

    Raises
    ------
    SportmonksError
        When no league is requested, or when the provider cannot be read
        completely.
    """

    if not league_ids:
        raise SportmonksError("No Sportmonks league was requested, so no window can be read.")

    client = SportmonksClient()

    leagues = _fetch_leagues(client, league_ids)

    params = {
        "filters": f"fixtureLeagues:{_joined(league_ids)}",
        "include": "participants;state;scores",
        "per_page": PAGE_SIZE,
        "timezone": PROVIDER_TIMEZONE,
    }

    path = f"/fixtures/between/{start.isoformat()}/{end.isoformat()}"

    fixtures: list[ProviderFixture] = []

    for page in client.get_pages(path, params):
        for entry in page:
            fixture = _fixture_of(entry, leagues)

            if fixture is not None:
                fixtures.append(fixture)

    return ProviderWindow(leagues=leagues, fixtures=fixtures)


def _fetch_leagues(
    client: SportmonksClient, league_ids: Sequence[int]
) -> dict[int, ProviderLeague]:
    """
    Return the subscribed competitions among those requested, keyed by identifier.

    The request states no filter. ``/leagues`` already answers with exactly the
    competitions the subscription covers, ``leagueIds`` is not one of the
    filters that endpoint documents, and the provider has an error of its own
    for a filter it does not recognize. Narrowing against ``league_ids`` here
    instead makes the guarantee true by construction rather than by trusting a
    parameter the provider may ignore.

    Parameters
    ----------
    client : SportmonksClient
        Client the request is issued through.
    league_ids : sequence of int
        Sportmonks league identifiers the window is restricted to.

    Returns
    -------
    dict of int to ProviderLeague
        Competitions the subscription exposes whose identifier was requested.

    Raises
    ------
    SportmonksError
        When the provider cannot be read completely.
    """

    params = {
        "include": "country",
        "per_page": PAGE_SIZE,
        "timezone": PROVIDER_TIMEZONE,
    }

    requested = set(league_ids)

    leagues: dict[int, ProviderLeague] = {}

    for page in client.get_pages("/leagues", params):
        for entry in page:
            league = _league_of(entry)

            if league is not None and league.provider_id in requested:
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

    league_id = _identifier(entry.get("league_id"))

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
        _report_unusable_kickoff(entry.get("starting_at"), provider_id)

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
        season_provider_id=_season_of(entry.get("season_id"), provider_id),
        kickoff_at=kickoff_at,
        league=league,
        home_team=home_team,
        away_team=away_team,
        status=_status_of(entry.get("state"), provider_id),
        home_goals=home_goals,
        away_goals=away_goals,
    )


def _report_unusable_kickoff(value: object, provider_id: int) -> None:
    """
    Record why a fixture without a readable kick-off is being dropped.

    A fixture the provider has not scheduled yet carries no ``starting_at`` at
    all, which is the documented shape of a match announced before its date is
    fixed. That is routine and belongs at debug level; a value that is present
    and still unreadable is a contract the boundary got wrong and warns.

    Parameters
    ----------
    value : object
        Value the ``starting_at`` field carried.
    provider_id : int
        Identifier of the fixture being dropped.
    """

    if value is None:
        logger.debug(
            "Skipping Sportmonks fixture %d: it is not scheduled yet.",
            provider_id,
        )

        return

    logger.warning(
        "Skipping Sportmonks fixture %d: %r is not a readable kick-off.",
        provider_id,
        value,
    )


def _season_of(value: object, provider_id: int) -> int | None:
    """
    Return the season a fixture is played in, or report why it states none.

    Unlike every other unusable field, this one never drops the fixture. The
    listing needs the match whatever season it belongs to, and the only reader
    an absent season degrades is a form sample scoped to one. The two failures
    are still distinguished the way an unusable kick-off is: a fixture the
    provider publishes without a season is routine and belongs at debug level,
    while a season that is present and still unreadable is a contract this
    boundary got wrong and warns.

    Parameters
    ----------
    value : object
        Value the ``season_id`` field carried.
    provider_id : int
        Identifier of the fixture the season was read from.

    Returns
    -------
    int or None
        Season identifier, or ``None`` when the fixture states none or states
        one the column that stores it cannot hold.
    """

    if value is None:
        logger.debug(
            "Sportmonks fixture %d states no season, so its season-scoped form is unavailable.",
            provider_id,
        )

        return None

    season_provider_id = _identifier(value)

    if season_provider_id is None:
        logger.warning(
            "Sportmonks fixture %d: %r is not a readable season identifier.",
            provider_id,
            value,
        )

    return season_provider_id


def _status_of(payload: object, provider_id: int) -> FixtureStatus:
    """
    Map the state a fixture entry reports onto the platform's vocabulary.

    Twenty-five states were observed on a live read of the provider's states
    resource, and that recording is what the test suite compares this table
    against; the published documentation table is stale. The mapping is an
    explicit lookup rather than a test on the shape of a code, because the shape
    carries no meaning: ``FT`` and ``FT_PEN`` are both finished while
    ``INPLAY_PENALTIES`` is not, and a state added later must be reported rather
    than guessed at.

    ``ABANDONED`` maps onto the live stage rather than the cancelled one. The
    provider defines it as abandoned and resuming later, which is the same
    semantics as ``SUSPENDED``, and the opposite of ``CANCELLED``, which it
    defines as not being played and yielding no result.

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
        side = _current_side_of(entry, provider_id) if isinstance(entry, dict) else None

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


def _current_side_of(entry: ProviderPayload, provider_id: int) -> tuple[str, int] | None:
    """
    Normalize one score entry into the side it belongs to and its goal count.

    An entry describing another period is not this function's business and is
    passed over silently. A ``CURRENT`` entry, however, is the score of the
    match, so discarding one is reported: at debug level when the provider has
    simply not filled the count in yet, which it documents, and at warning level
    for any other shape, which the boundary would otherwise lose as quietly as
    a match that has produced no score at all.

    Parameters
    ----------
    entry : ProviderPayload
        One entry of the ``scores`` include.
    provider_id : int
        Identifier of the fixture, named when a current entry is discarded.

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
        logger.warning(
            "Ignoring a current score of Sportmonks fixture %d: %r is not a score object.",
            provider_id,
            score,
        )

        return None

    location = _text(score.get("participant"))

    goals = _goal_count(score.get("goals"))

    if goals is not None and location in (HOME_LOCATION, AWAY_LOCATION):
        return location, goals

    if score.get("goals") is None and location in (HOME_LOCATION, AWAY_LOCATION):
        logger.debug(
            "Sportmonks fixture %d carries no goal count for its %s side yet.",
            provider_id,
            location,
        )

        return None

    logger.warning(
        "Ignoring a current score of Sportmonks fixture %d: %r states no readable count for a "
        "named side.",
        provider_id,
        score,
    )

    return None


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
        identifier, or a text no column could hold.
    """

    provider_id = _identifier(entry.get("id"))

    if provider_id is None:
        logger.warning("Skipping a Sportmonks league that carries no usable identifier.")

        return None

    country = entry.get("country")

    country_payload: ProviderPayload = country if isinstance(country, dict) else {}

    name = _stored_text(entry.get("name"), NAME_LIMIT)
    short_code = _stored_text(entry.get("short_code"), SHORT_CODE_LIMIT)
    logo_url = _stored_text(entry.get("image_path"), URL_LIMIT)
    country_name = _stored_text(country_payload.get("name"), NAME_LIMIT)
    country_flag_url = _stored_text(country_payload.get("image_path"), URL_LIMIT)

    if (
        name is None
        or short_code is None
        or logo_url is None
        or country_name is None
        or country_flag_url is None
    ):
        logger.warning(
            "Skipping Sportmonks league %d: one of its texts is longer than the column that "
            "stores it.",
            provider_id,
        )

        return None

    return ProviderLeague(
        provider_id=provider_id,
        name=name,
        short_code=short_code,
        logo_url=logo_url,
        country_name=country_name,
        country_flag_url=country_flag_url,
    )


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
        or ``None`` when the entry names neither location, carries no usable
        identifier, or carries a text no column could hold.
    """

    provider_id = _identifier(entry.get("id"))

    meta = entry.get("meta")

    location = _text(meta.get("location")) if isinstance(meta, dict) else ""

    if provider_id is None or location not in (HOME_LOCATION, AWAY_LOCATION):
        return None

    name = _stored_text(entry.get("name"), NAME_LIMIT)
    short_code = _stored_text(entry.get("short_code"), SHORT_CODE_LIMIT)
    crest_url = _stored_text(entry.get("image_path"), URL_LIMIT)

    if name is None or short_code is None or crest_url is None:
        logger.warning(
            "Skipping Sportmonks team %d: one of its texts is longer than the column that "
            "stores it.",
            provider_id,
        )

        return None

    team = ProviderTeam(
        provider_id=provider_id,
        name=name,
        short_code=short_code,
        crest_url=crest_url,
    )

    return location, team


def _kickoff_of(value: object) -> datetime | None:
    """
    Parse a provider kick-off stamp into a timezone-aware UTC instant.

    Parameters
    ----------
    value : object
        Value the ``starting_at`` field carried, documented as
        ``"YYYY-MM-DD HH:MM:SS"`` and requested in UTC, so it carries no offset
        of its own.

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
    Return a goal count the column that stores it can hold.

    Parameters
    ----------
    value : object
        Value the ``goals`` field of a score carried, documented as a number and
        published as ``null`` while a match has produced no score.

    Returns
    -------
    int or None
        Goals scored, or ``None`` when the value is not a count, which includes
        the boolean, the negative, and the beyond-``GOALS_LIMIT`` cases the
        column would refuse. Refusing them here matters because the window is
        written in one transaction, so a single unstorable count would discard
        every other fixture of the run.
    """

    if isinstance(value, bool) or not isinstance(value, int):
        return None

    if value < 0 or value > GOALS_LIMIT:
        return None

    return value


def _identifier(value: object) -> int | None:
    """
    Return a provider identifier the column that stores it can hold.

    Parameters
    ----------
    value : object
        Value an identifier field carried, which the provider sends as a number
        but has been observed to send as a string of digits.

    Returns
    -------
    int or None
        Identifier, or ``None`` when the value does not denote one or falls
        outside the signed 64-bit range of the column that stores it.
    """

    if isinstance(value, bool):
        return None

    if isinstance(value, int):
        return value if IDENTIFIER_MINIMUM <= value <= IDENTIFIER_MAXIMUM else None

    if isinstance(value, str) and value.isdigit():
        parsed = int(value)

        return parsed if parsed <= IDENTIFIER_MAXIMUM else None

    return None


def _stored_text(value: object, limit: int) -> str | None:
    """
    Return a provider string short enough for the column that stores it.

    Parameters
    ----------
    value : object
        Value an optional text field carried.
    limit : int
        Characters the column holds, one of ``NAME_LIMIT``,
        ``SHORT_CODE_LIMIT`` or ``URL_LIMIT``.

    Returns
    -------
    str or None
        The string, ``""`` when the provider omitted it or sent something else,
        or ``None`` when it is longer than the column. The caller drops the row
        in that case, because the window is written in one transaction and a
        single overlong value would otherwise discard every other fixture of
        the run.
    """

    if not isinstance(value, str):
        return ""

    return value if len(value) <= limit else None


def _text(value: object) -> str:
    """
    Return a provider string that is read rather than stored.

    Only values compared against a closed vocabulary go through here: a state
    code, a score period, a participant location. None of them reaches a column,
    so none of them is length-bounded; a stored value uses ``_stored_text``.

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
