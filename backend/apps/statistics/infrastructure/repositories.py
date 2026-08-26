import logging
from collections.abc import Collection
from datetime import datetime

from django.db import transaction

from apps.fixtures.models import Fixture, Team
from apps.statistics.models import MatchTeamStatistic
from integrations.sportmonks.statistics import ProviderStatisticsWindow

logger = logging.getLogger(__name__)

STATISTIC_UPDATE_FIELDS = [
    "side",
    "shots_total",
    "shots_on_target",
    "shots_inside_box",
    "shots_blocked",
    "big_chances_created",
    "key_passes",
    "corners",
    "possession",
    "passes",
    "successful_passes",
    "crosses",
    "accurate_crosses",
    "dribble_attempts",
    "successful_dribbles",
    "saves",
    "tackles",
    "interceptions",
    "duels_won",
    "fouls",
    "yellow_cards",
    "red_cards",
    "offsides",
    "synchronized_at",
]

# psycopg refuses a statement carrying more than 65,535 placeholders, and PostgreSQL does not
# narrow ``BaseDatabaseOperations.bulk_batch_size``, which is the whole list, so an unbatched
# ``bulk_create`` becomes one statement however many rows it was given. This table is twenty-six
# columns a row, the widest the project writes, putting that ceiling at 2,520 rows, which a single
# chunk of a backfill clears several times over: thirty days of five leagues is on the order of
# four hundred matches and twice as many rows. The batch is comfortably inside it, and the
# statements of one call still share the transaction below.
WRITE_BATCH_SIZE = 1000

StatisticKey = tuple[int, int]


def _resolve_fixture_keys(provider_ids: Collection[int]) -> dict[int, int]:
    """
    Map the matches a statistics read covered onto their stored primary keys.

    One query for the whole read rather than one per match: a chunk of a backfill
    is on the order of four hundred matches, and the rows written for them all
    point at primary keys this single lookup already knows.

    A provider identifier with no stored match is skipped rather than treated as
    an error. The synchronization brings its own fixture parents chunk by chunk,
    so this is not the ordinary path, but a match the provider lists statistics
    for and no longer lists as a fixture is representable and must not abort the
    chunk around it. The count is reported once for the whole read instead of
    once per identifier, because a chunk that arrives before its fixtures would
    otherwise print the line several hundred times and say nothing more.

    Parameters
    ----------
    provider_ids : Collection of int
        Distinct provider identifiers of the matches the read covered.

    Returns
    -------
    dict of int to int
        Primary key of each stored match, keyed by provider identifier. A
        provider identifier with no stored match is absent, so its length is
        also how many matches the caller may write for.
    """

    stored_keys: dict[int, int] = dict(
        Fixture.objects.filter(sportmonks_id__in=provider_ids).values_list("sportmonks_id", "pk")
    )

    skipped_count = len(provider_ids) - len(stored_keys)

    if skipped_count:
        logger.info(
            "Skipped %d match(es) of a statistics read that are not stored yet.", skipped_count
        )

    return stored_keys


def _resolve_team_keys(provider_ids: Collection[int]) -> dict[int, int]:
    """
    Map the clubs a statistics read covered onto their stored primary keys.

    The counterpart of ``_resolve_fixture_keys`` over the clubs. Absence is far
    rarer here, because ``upsert_fixtures`` writes both clubs of every match it
    stores, so a resolved match almost always brings its two clubs with it. What
    it does cover is a payload attributing a performance to a club that is not
    playing in the match it was sent under, which is a provider anomaly rather
    than a schedule this run is early for, and which would otherwise cost the
    whole chunk an ``IntegrityError`` on a foreign key.

    Parameters
    ----------
    provider_ids : Collection of int
        Distinct provider identifiers of the clubs the read covered.

    Returns
    -------
    dict of int to int
        Primary key of each stored club, keyed by provider identifier.
    """

    stored_keys: dict[int, int] = dict(
        Team.objects.filter(sportmonks_id__in=provider_ids).values_list("sportmonks_id", "pk")
    )

    skipped_count = len(provider_ids) - len(stored_keys)

    if skipped_count:
        logger.info(
            "Skipped %d club(s) of a statistics read that are not stored yet.", skipped_count
        )

    return stored_keys


def _statistic_rows(
    window: ProviderStatisticsWindow,
    fixture_keys: dict[int, int],
    team_keys: dict[int, int],
    synchronized_at: datetime,
) -> dict[StatisticKey, MatchTeamStatistic]:
    """
    Collapse a statistics read into the rows to offer the upsert, in key order.

    ``ON CONFLICT DO UPDATE`` refuses to touch the same row twice in one
    statement, so a read repeating a natural key has to collapse here rather
    than reach the database. The rows are then sorted by natural key so the lock
    order is deterministic across runs: offered in the order the provider
    paginated them, two runs over overlapping ranges could take the same
    matches' row locks in different orders and deadlock, aborting a whole chunk
    with an ``OperationalError`` nothing catches.

    Parameters
    ----------
    window : ProviderStatisticsWindow
        Every match the provider read returned, in any order, each with the
        per-club figures it published.
    fixture_keys : dict of int to int
        Primary key of each stored match, keyed by provider identifier. A match
        absent from it contributes no row.
    team_keys : dict of int to int
        Primary key of each stored club, keyed by provider identifier. A club
        absent from it contributes no row.
    synchronized_at : datetime
        Timezone-aware instant stamped on every row.

    Returns
    -------
    dict of StatisticKey to MatchTeamStatistic
        Unsaved rows keyed by the natural key each one is stored under, in
        ascending key order.
    """

    unique_records: dict[StatisticKey, MatchTeamStatistic] = {}

    for entry in window.fixtures:
        fixture_key = fixture_keys.get(entry.fixture_provider_id)

        if fixture_key is None:
            continue

        for provider_team in entry.teams:
            team_key = team_keys.get(provider_team.team_provider_id)

            if team_key is None:
                continue

            unique_records[(fixture_key, team_key)] = MatchTeamStatistic(
                fixture_id=fixture_key,
                team_id=team_key,
                side=provider_team.side,
                synchronized_at=synchronized_at,
                **provider_team.values,
            )

    return {key: unique_records[key] for key in sorted(unique_records)}


def _clear_displaced_sides(records: dict[StatisticKey, MatchTeamStatistic]) -> None:
    """
    Delete the stored rows whose side the incoming rows are about to take over.

    ``match_statistic_side_unique`` is not deferrable, so PostgreSQL checks it as
    each row of the upsert lands rather than at the end of the statement. That
    makes a match whose two clubs swap sides between runs unwritable without
    this: correcting a fixture listed with its clubs the wrong way round leaves
    the home row wanting the side the away row still holds, and whichever of the
    two the statement reaches first violates the constraint against the other,
    aborting a chunk over a single corrected match. Widening the upsert's
    conflict target cannot help, because the collision is between two different
    rows and not between a row and itself.

    Only the displaced rows go, not every row of the match, and a run in which
    nothing moved deletes nothing at all. That is what keeps the ordinary
    idempotent case a pure update, leaving every primary key where it was, and
    the reconciliation in ``upsert_match_statistics`` still owns the rows the
    provider stopped publishing.

    Parameters
    ----------
    records : dict of StatisticKey to MatchTeamStatistic
        Unsaved rows the upsert is about to offer, keyed by the match and club
        each one belongs to and carrying the side that club is to occupy.
    """

    claimed_sides = {
        (fixture_key, record.side): team_key for (fixture_key, team_key), record in records.items()
    }

    stored_sides = MatchTeamStatistic.objects.filter(
        fixture_id__in={fixture_key for fixture_key, _team_key in records}
    ).values_list("pk", "fixture_id", "team_id", "side")

    displaced_keys = [
        stored_key
        for stored_key, fixture_key, team_key, side in stored_sides
        if claimed_sides.get((fixture_key, side), team_key) != team_key
    ]

    if displaced_keys:
        MatchTeamStatistic.objects.filter(pk__in=displaced_keys).delete()


def upsert_match_statistics(window: ProviderStatisticsWindow, synchronized_at: datetime) -> int:
    """
    Store the figures of a statistics read, updating whatever exists.

    ``(fixture, team)`` is the natural key, so running the same read twice
    leaves every row where it was, with the same primary key, and only moves the
    figures the provider revised and the stamp. A match the read carried without
    a single club, which is what an abandoned game or a provider gap looks like,
    writes nothing and is still authoritative: it was read, so the
    reconciliation below is entitled to clear whatever it used to have.

    Reconciliation is by stamp identity rather than by enumeration, and both
    halves share one transaction. Every row this call writes carries exactly
    ``synchronized_at``, so a row of a match the run read carrying any other
    stamp is a performance the provider has stopped publishing, and deleting on
    that condition removes it without the run ever having to work out which side
    went missing. The delete is scoped to the matches actually resolved: a match
    outside the read keeps its rows, because this run learned nothing about it,
    and a match the fixture table has not got yet contributes no scope at all.

    Sharing the transaction is what stops a reader seeing a match whose old
    figures are gone and whose new ones are not in yet, which for the form panel
    would be a sample counting one side of a match and not the other. The keys
    are resolved inside it too, which shrinks rather than closes the gap against
    the fixture synchronization deleting a match this run holds figures for: the
    foreign key is checked by the insert, so a parent ``DELETE`` committing
    between the resolution and the insert still costs the whole call an
    ``IntegrityError``. What moving it in buys is that the statements are
    consecutive rather than separated by the collapse of the entire payload, and
    the run remains safe to retry.

    Parameters
    ----------
    window : ProviderStatisticsWindow
        Every match the provider read returned, in any order, each with the
        per-club figures it published.
    synchronized_at : datetime
        Timezone-aware instant stamped on every row this call writes, and the
        one stamp the reconciliation spares.

    Returns
    -------
    int
        Number of statistic rows written.

    Notes
    -----
    The reconciliation tests the stamp for identity, not for order, and that is
    deliberate. Deleting the rows stamped earlier than this run reads the wall
    clock as monotonic, which it is not: an NTP step correction, or a second
    worker on a skewed clock, gives a stale row a stamp later than the current
    run's, and such a row survives every subsequent run while being averaged
    into a form sample as though it were current. Comparing for inequality
    cannot care which direction the clock moved.

    A club changing sides between two runs is handled before the write rather
    than by it, because ``match_statistic_side_unique`` is checked per row as
    the statement lands: see ``_clear_displaced_sides`` for what that costs and
    why the ordinary run pays nothing for it.
    """

    read_fixture_ids = {entry.fixture_provider_id for entry in window.fixtures}

    read_team_ids = {
        provider_team.team_provider_id for entry in window.fixtures for provider_team in entry.teams
    }

    with transaction.atomic():
        fixture_keys = _resolve_fixture_keys(read_fixture_ids)
        team_keys = _resolve_team_keys(read_team_ids)

        ordered_records = _statistic_rows(window, fixture_keys, team_keys, synchronized_at)

        _clear_displaced_sides(ordered_records)

        MatchTeamStatistic.objects.bulk_create(
            list(ordered_records.values()),
            update_conflicts=True,
            unique_fields=["fixture", "team"],
            update_fields=STATISTIC_UPDATE_FIELDS,
            batch_size=WRITE_BATCH_SIZE,
        )

        MatchTeamStatistic.objects.filter(fixture_id__in=fixture_keys.values()).exclude(
            synchronized_at=synchronized_at
        ).delete()

    return len(ordered_records)
