import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

from apps.statistics.domain.enums import MatchSide
from integrations.sportmonks.client import ProviderPayload, SportmonksClient
from integrations.sportmonks.exceptions import SportmonksError
from integrations.sportmonks.fixtures import PAGE_SIZE, PROVIDER_TIMEZONE

logger = logging.getLogger(__name__)

# Possession is the one type the provider publishes as a percentage rather than as a count, so it
# is the one type read under a ceiling of its own.
POSSESSION_TYPE = 45

# The bounds below mirror the columns of ``apps.statistics.models``, and the identifier range that
# of ``apps.fixtures.models``, rather than importing them, because the provider adapter must not
# depend on the persistence it feeds.
COUNT_CEILING = 32767

POSSESSION_CEILING = 100

IDENTIFIER_MINIMUM = -(2**63)

IDENTIFIER_MAXIMUM = 2**63 - 1

PROVIDER_STATISTICS: dict[int, str] = {
    42: "shots_total",
    86: "shots_on_target",
    49: "shots_inside_box",
    58: "shots_blocked",
    580: "big_chances_created",
    117: "key_passes",
    34: "corners",
    45: "possession",
    80: "passes",
    81: "successful_passes",
    98: "crosses",
    99: "accurate_crosses",
    108: "dribble_attempts",
    109: "successful_dribbles",
    57: "saves",
    78: "tackles",
    100: "interceptions",
    106: "duels_won",
    56: "fouls",
    84: "yellow_cards",
    83: "red_cards",
    51: "offsides",
}

# The provider omits an event-conditional count at nought rather than sending a zero, so absence
# is the reading itself for these eight and not a defect. Measured over the 828 sides of the 414
# fixtures between 2026-03-28 and 2026-08-25: redcards is published on 14.73% of sides, offsides on
# 95.17%, yellowcards on 96.62%, key-passes on 98.07%, big-chances-created on 98.31%,
# accurate-crosses on 99.03%, saves on 99.52% and shots-blocked on 99.76%. Nought is a real value
# for every one of them: a side can create no clear chance, complete no cross of the several it
# attempted, or never test the goalkeeper. The other fourteen types this boundary maps were
# published on 100% of those sides, which is why a side missing one of them is read as a malformed
# record rather than as fourteen figures and a nought. That distinction is what the required set
# buys: possession is a rate whose absence means unknown rather than nought, and passes, crosses
# and dribble-attempts are denominators a ratio would silently read as nought.
#
# Narrowing this set to the three types a one-month sample suggested cost 21 of 413 finished
# matches, because one absent count discards a whole match, so the sample behind it is deliberately
# a full season rather than a single month.
OPTIONAL_STATISTICS: frozenset[int] = frozenset({51, 57, 58, 83, 84, 99, 117, 580})

# Each completion the product turns into an accuracy, mapped to the attempt that bounds it. The
# pairs are named here rather than inferred from the column names, because the boundary refuses a
# record whose completion exceeds its attempt and that refusal has to be a stated rule.
COMPLETION_PAIRS: dict[str, str] = {
    "successful_passes": "passes",
    "accurate_crosses": "crosses",
    "successful_dribbles": "dribble_attempts",
}

PROVIDER_SIDES: dict[str, MatchSide] = {
    "home": MatchSide.HOME,
    "away": MatchSide.AWAY,
}

SIDE_COUNT = len(PROVIDER_SIDES)


@dataclass(frozen=True, slots=True)
class ProviderTeamStatistics:
    """
    Every figure one side of one fixture was read with.

    Attributes
    ----------
    team_provider_id : int
        Sportmonks team identifier of the side, taken from the
        ``participant_id`` the provider tags each of its rows with.
    side : MatchSide
        Side the team played, mapped from the provider's ``location`` string,
        which never leaves this module.
    values : dict of str to int
        Figure of every column of ``apps.statistics.models.MatchTeamStatistic``
        this boundary persists, keyed by column name and complete: a record that
        could not resolve one of them is never built. Keys arrive in
        ``PROVIDER_STATISTICS`` order rather than in the provider's, so two
        records of the same fixture are comparable.
    """

    team_provider_id: int
    side: MatchSide
    values: dict[str, int]


@dataclass(frozen=True, slots=True)
class ProviderFixtureStatistics:
    """
    Both sides of one finished fixture, as the provider published them.

    Attributes
    ----------
    fixture_provider_id : int
        Sportmonks fixture identifier the records belong to.
    teams : list of ProviderTeamStatistics
        Exactly the two records of the fixture, one a side, in provider order.
        Never one and never three: the application layer reads a team's
        conceded figures off its opponent's record, so half a match would make
        every conceded figure of it a fabrication.
    """

    fixture_provider_id: int
    teams: list[ProviderTeamStatistics]


@dataclass(frozen=True, slots=True)
class ProviderStatisticsWindow:
    """
    Everything one complete read of a statistics window resolved.

    Only the fixtures that resolved both of their records are carried, which is
    the one place this window differs from the prediction one. A prediction is
    reconciled by stamp over every fixture the read returned, so an empty
    include has to be carried to be deleted against; a match statistic is
    written once and never withdrawn, because the provider does not unplay a
    match. A fixture the provider has not yet settled therefore carries nothing
    to reconcile against and is simply read again on the next pass.

    Attributes
    ----------
    fixtures : list of ProviderFixtureStatistics
        Fixtures of the window whose two records were both usable, in provider
        order, and empty for a window the provider has settled nothing in.
    """

    fixtures: list[ProviderFixtureStatistics]


def fetch_match_statistics(
    start: date, end: date, league_ids: Sequence[int]
) -> ProviderStatisticsWindow:
    """
    Return the figures every settled fixture of a window was played with, normalized.

    One paginated resource is read, not one request a fixture. The fixtures
    resource accepts ``include=statistics`` and answers a page of fifty
    fixtures carrying every row of each, which a live probe measured at roughly
    eighty-two rows a fixture. A round of five leagues therefore costs a page or
    two against a budget of two thousand calls an hour, where a request a
    fixture would cost fifty.

    No type filter is stated, unlike the prediction window. The include is
    unfiltered because the provider prices this read by fixture rather than by
    row, so narrowing it server-side would save nothing and would move the list
    of types this boundary understands into a request string that no test can
    hold to the mapping. The narrowing happens here instead, against
    ``PROVIDER_STATISTICS``, and a type outside it is ignored at debug level
    because the provider publishing forty-six types when this boundary
    persists twenty-two is the ordinary state rather than a defect.

    A record the provider returns malformed is dropped with a warning instead of
    failing the window, so one broken fixture cannot cost a refresh every other
    fixture in the same range. A window the provider cannot serve completely is
    the opposite case and fails: the client raises rather than returning the
    pages it managed to read, because a caller cannot tell a prefix of a window
    from the whole of it and would reconcile the prefix as if it were complete.

    A figure the column that stores it could not hold makes its own record
    unusable, and with it the fixture, rather than aborting anything larger. The
    record is all-or-nothing because a form average computed over a record with
    a hole in it would silently be an average over a different denominator than
    the one it reports.

    The request states ``timezone=UTC`` even though nothing here parses an
    instant. The resource shifts every stamp it returns by that parameter, so
    leaving it to a provider default would make this read and the fixture
    window read the same range under two different definitions of a day. That
    timezone and the page size are imported from the fixtures boundary rather
    than restated, because this is the same fixtures resource and both
    constants describe the provider rather than either of its callers.

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
    ProviderStatisticsWindow
        Every fixture of the window that resolved both of its records.

    Raises
    ------
    SportmonksError
        When no league is requested, or when the provider cannot be read
        completely.
    """

    if not league_ids:
        raise SportmonksError(
            "No Sportmonks league was requested, so no statistics window can be read."
        )

    client = SportmonksClient()

    params = {
        "filters": f"fixtureLeagues:{_joined(league_ids)}",
        "include": "statistics",
        "per_page": PAGE_SIZE,
        "timezone": PROVIDER_TIMEZONE,
    }

    path = f"/fixtures/between/{start.isoformat()}/{end.isoformat()}"

    fixtures: list[ProviderFixtureStatistics] = []

    for page in client.get_pages(path, params):
        for entry in page:
            fixture = _fixture_statistics_of(entry)

            if fixture is not None:
                fixtures.append(fixture)

    return ProviderStatisticsWindow(fixtures=fixtures)


def _fixture_statistics_of(entry: ProviderPayload) -> ProviderFixtureStatistics | None:
    """
    Normalize the statistics of one fixture entry, or report it as unusable.

    The provider states the rows of both sides in one flat array, tagging each
    with the participant it belongs to, so the array is grouped by participant
    before either side can be read.

    Parameters
    ----------
    entry : ProviderPayload
        One entry of a fixtures page, with its statistics included.

    Returns
    -------
    ProviderFixtureStatistics or None
        Fixture and the records of its two sides, or ``None`` when the entry
        carries no usable identifier, no statistics array, fewer or more than
        two usable records, or two records claiming the same side.
    """

    provider_id = _identifier(entry.get("id"))

    if provider_id is None:
        logger.warning("Skipping a Sportmonks statistics entry that names no usable fixture.")

        return None

    payload = entry.get("statistics")

    if not isinstance(payload, list):
        logger.warning(
            "Skipping Sportmonks fixture %d: %r is not a statistics array.", provider_id, payload
        )

        return None

    grouped: dict[int, list[ProviderPayload]] = {}

    for row in payload:
        participant_id = _identifier(row.get("participant_id")) if isinstance(row, dict) else None

        if participant_id is None:
            logger.warning(
                "Ignoring a statistic of Sportmonks fixture %d: %r names no usable participant.",
                provider_id,
                row,
            )

            continue

        grouped.setdefault(participant_id, []).append(row)

    teams: list[ProviderTeamStatistics] = []

    for participant_id, rows in grouped.items():
        team = _team_statistics_of(rows, participant_id, provider_id)

        if team is not None:
            teams.append(team)

    if len(teams) != SIDE_COUNT:
        logger.warning(
            "Skipping Sportmonks fixture %d: a match needs two usable team records, not %d.",
            provider_id,
            len(teams),
        )

        return None

    if teams[0].side == teams[1].side:
        logger.warning(
            "Skipping Sportmonks fixture %d: teams %d and %d both claim the %s side.",
            provider_id,
            teams[0].team_provider_id,
            teams[1].team_provider_id,
            teams[0].side.value,
        )

        return None

    return ProviderFixtureStatistics(fixture_provider_id=provider_id, teams=teams)


def _team_statistics_of(
    rows: list[ProviderPayload], team_provider_id: int, fixture_provider_id: int
) -> ProviderTeamStatistics | None:
    """
    Normalize the rows one participant of a fixture was tagged with into its record.

    Every column the boundary persists is resolved, so the caller receives a
    record it can write whole or nothing at all. A type in
    ``OPTIONAL_STATISTICS`` that the provider left out reads as nought, which is
    what its absence means; any of the fourteen it always sends being left out
    makes the record unusable.

    Parameters
    ----------
    rows : list of ProviderPayload
        Rows of the statistics array tagged with this participant.
    team_provider_id : int
        Sportmonks team identifier the rows belong to.
    fixture_provider_id : int
        Identifier of the fixture, named whenever a record is discarded.

    Returns
    -------
    ProviderTeamStatistics or None
        Complete record of the side, or ``None`` when the rows state no side
        this boundary recognizes, leave out a required type, or carry a figure
        the column that stores it could not hold.
    """

    side = _side_of(rows, team_provider_id, fixture_provider_id)

    if side is None:
        return None

    published: dict[int, object] = {}

    for row in rows:
        type_id = _identifier(row.get("type_id"))

        if type_id is None or type_id not in PROVIDER_STATISTICS:
            logger.debug(
                "Ignoring statistic type %r of Sportmonks fixture %d: it is not a figure this "
                "boundary persists.",
                type_id,
                fixture_provider_id,
            )

            continue

        data = row.get("data")

        published[type_id] = data.get("value") if isinstance(data, dict) else data

    values: dict[str, int] = {}

    for type_id, column in PROVIDER_STATISTICS.items():
        if type_id not in published:
            if type_id in OPTIONAL_STATISTICS:
                values[column] = 0

                continue

            logger.warning(
                "Skipping team %d of Sportmonks fixture %d: statistic type %d states no %s.",
                team_provider_id,
                fixture_provider_id,
                type_id,
                column,
            )

            return None

        ceiling = POSSESSION_CEILING if type_id == POSSESSION_TYPE else COUNT_CEILING

        count = _count(published[type_id], ceiling)

        if count is None:
            logger.warning(
                "Skipping team %d of Sportmonks fixture %d: %r is not a %s the column that "
                "stores it could hold.",
                team_provider_id,
                fixture_provider_id,
                published[type_id],
                column,
            )

            return None

        values[column] = count

    if not _consistent(values, team_provider_id, fixture_provider_id):
        return None

    return ProviderTeamStatistics(team_provider_id=team_provider_id, side=side, values=values)


def _consistent(values: dict[str, int], team_provider_id: int, fixture_provider_id: int) -> bool:
    """
    Report whether every completion the record states is one of an attempt it also states.

    The three accuracies the product publishes are a summed numerator over a
    summed denominator, so a record claiming more completions than attempts would
    put a share above a hundred on the wire, and the interface refuses that as a
    broken contract rather than rendering a bar wider than its track. No such
    record was found across the 828 sides of the 414 fixtures between 2026-03-28
    and 2026-08-25, so this refuses a shape the provider has not been observed to
    produce; it is here because the cost of being wrong is a blank panel rather
    than one absent figure, and because the check is the only thing standing
    between the provider and that share.

    Parameters
    ----------
    values : dict of str to int
        Resolved figures of one record, keyed by column name.
    team_provider_id : int
        Sportmonks team identifier the figures belong to.
    fixture_provider_id : int
        Identifier of the fixture, named whenever a record is discarded.

    Returns
    -------
    bool
        Whether every completion is bounded by its attempt.
    """

    for completed, attempted in COMPLETION_PAIRS.items():
        if values[completed] > values[attempted]:
            logger.warning(
                "Skipping team %d of Sportmonks fixture %d: %d %s exceeds %d %s.",
                team_provider_id,
                fixture_provider_id,
                values[completed],
                completed,
                values[attempted],
                attempted,
            )

            return False

    return True


def _side_of(
    rows: list[ProviderPayload], team_provider_id: int, fixture_provider_id: int
) -> MatchSide | None:
    """
    Resolve the side a participant played from the location its rows state.

    The provider tags every row of a participant with the same location, so the
    rows are required to agree. A group that disagrees is refused rather than
    resolved by majority: the location is what decides which record a form
    query reads as the home one, and a payload that states both of them for one
    team has not said.

    Parameters
    ----------
    rows : list of ProviderPayload
        Rows of the statistics array tagged with this participant.
    team_provider_id : int
        Sportmonks team identifier the rows belong to, named when they are
        refused.
    fixture_provider_id : int
        Identifier of the fixture, named when the rows are refused.

    Returns
    -------
    MatchSide or None
        Side the participant played, or ``None`` when a row names a location
        this boundary does not recognize or the rows name more than one.
    """

    sides: list[MatchSide] = []

    for row in rows:
        location = row.get("location")

        side = PROVIDER_SIDES.get(location) if isinstance(location, str) else None

        if side is None:
            logger.warning(
                "Skipping team %d of Sportmonks fixture %d: %r names no side.",
                team_provider_id,
                fixture_provider_id,
                location,
            )

            return None

        if side not in sides:
            sides.append(side)

    if len(sides) != 1:
        logger.warning(
            "Skipping team %d of Sportmonks fixture %d: its statistics name %d sides.",
            team_provider_id,
            fixture_provider_id,
            len(sides),
        )

        return None

    return sides[0]


def _count(value: object, ceiling: int) -> int | None:
    """
    Return a figure the column that stores it can hold.

    The decimal is built from the string form of the value, never from the float
    itself, for the reason the prediction boundary parses a percentage that way:
    ``Decimal(0.1)`` is a binary approximation of a figure nobody published. A
    numeric string is accepted because this provider has been observed to
    stringify a number, and a fractional value is refused rather than rounded,
    because every column here is a whole count and rounding one would invent a
    figure the provider never stated. A boolean is refused although Python
    counts it as an integer.

    Parameters
    ----------
    value : object
        Value the ``data`` object of a row carried, documented as a number and
        accepted as a string of one.
    ceiling : int
        Largest value the column accepts, its floor being nought throughout
        because every column this boundary writes is unsigned.

    Returns
    -------
    int or None
        Figure the column accepts, or ``None`` when the value is not a finite
        whole number inside the range. Refusing it here matters because the
        rows of a run are written in one transaction, so a single value the
        column would reject must cost its own record rather than every other
        record of the run.
    """

    if isinstance(value, bool) or not isinstance(value, int | float | str):
        return None

    try:
        parsed = Decimal(str(value))
    except InvalidOperation:
        return None

    if not parsed.is_finite() or parsed < 0 or parsed > ceiling:
        return None

    if parsed != parsed.to_integral_value():
        return None

    return int(parsed)


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


def _joined(values: Sequence[int]) -> str:
    """
    Render numeric identifiers as the comma-separated list a filter expects.

    Parameters
    ----------
    values : sequence of int
        League identifiers.

    Returns
    -------
    str
        Identifiers joined by commas.
    """

    return ",".join(str(value) for value in values)
