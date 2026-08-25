import logging
from collections.abc import Collection
from datetime import datetime

from django.db import transaction

from apps.fixtures.models import Fixture, League
from apps.predictions.models import FixturePrediction, LeagueMarketReliability
from integrations.sportmonks.predictions import ProviderPredictionWindow, ProviderReliabilityRead

logger = logging.getLogger(__name__)

PREDICTION_UPDATE_FIELDS = ["probability", "synchronized_at"]

RELIABILITY_UPDATE_FIELDS = ["quality", "hit_ratio", "synchronized_at"]

# psycopg refuses a statement carrying more than 65,535 placeholders, and PostgreSQL does not
# narrow ``BaseDatabaseOperations.bulk_batch_size``, which is the whole list, so an unbatched
# ``bulk_create`` becomes one statement however many rows it was given. Both tables here are five
# columns a row, putting that ceiling at 13,107 rows, which a congested window over these leagues
# is already within a factor of two of. The batch is an order of magnitude clear of it, and the
# statements of one call still share the transaction below.
WRITE_BATCH_SIZE = 1000

PredictionKey = tuple[int, str, str]

ReliabilityKey = tuple[int, str]


def _resolve_fixture_keys(provider_ids: Collection[int]) -> dict[int, int]:
    """
    Map the fixtures a prediction read covered onto their stored primary keys.

    One query for the whole read rather than one per fixture: a fortnight of
    five leagues is on the order of eight hundred fixtures, and the rows written
    for them all point at primary keys this single lookup already knows.

    A provider identifier with no stored fixture is skipped rather than treated
    as an error. The two synchronizations are scheduled independently, so on a
    fresh database, or on any run that beats the fixture refresh to a newly
    listed match, the prediction read legitimately mentions a fixture the
    fixture table has not got yet. The next run stores its probabilities. The
    count is reported once for the whole read instead of once per identifier,
    because on that fresh database the line would otherwise be printed several
    hundred times and say nothing more.

    Parameters
    ----------
    provider_ids : Collection of int
        Distinct provider identifiers of the fixtures the read covered.

    Returns
    -------
    dict of int to int
        Primary key of each stored fixture, keyed by provider identifier. A
        provider identifier with no stored fixture is absent, so its length is
        also how many fixtures the caller may write for.
    """

    stored_keys: dict[int, int] = dict(
        Fixture.objects.filter(sportmonks_id__in=provider_ids).values_list("sportmonks_id", "pk")
    )

    skipped_count = len(provider_ids) - len(stored_keys)

    if skipped_count:
        logger.info(
            "Skipped %d fixture(s) of a prediction read that are not stored yet.", skipped_count
        )

    return stored_keys


def _resolve_league_keys(provider_ids: Collection[int]) -> dict[int, int]:
    """
    Map the competitions a reliability read covered onto their primary keys.

    The counterpart of ``_resolve_fixture_keys`` over the competitions, and
    absence is ordinary here for the same reason: the grades are read per
    subscribed league straight from the configuration, so a league the fixture
    synchronization has never stored, because it has never appeared in a window,
    is graded before it exists. Five leagues make the report a single line
    whatever happens.

    Parameters
    ----------
    provider_ids : Collection of int
        Distinct provider identifiers of the competitions the read covered,
        whether or not it graded a market for them.

    Returns
    -------
    dict of int to int
        Primary key of each stored competition, keyed by provider identifier.
    """

    stored_keys: dict[int, int] = dict(
        League.objects.filter(sportmonks_id__in=provider_ids).values_list("sportmonks_id", "pk")
    )

    skipped_count = len(provider_ids) - len(stored_keys)

    if skipped_count:
        logger.info(
            "Skipped %d competition(s) of a reliability read that are not stored yet.",
            skipped_count,
        )

    return stored_keys


def _prediction_rows(
    window: ProviderPredictionWindow, fixture_keys: dict[int, int], synchronized_at: datetime
) -> list[FixturePrediction]:
    """
    Collapse a prediction read into the rows to offer the upsert, in key order.

    ``ON CONFLICT DO UPDATE`` refuses to touch the same row twice in one
    statement, so a read repeating a natural key has to collapse here rather
    than reach the database. The rows are then sorted by natural key so the lock
    order is deterministic across runs: offered in the order the provider
    paginated them, two runs over overlapping windows could take the same
    fixtures' row locks in different orders and deadlock, aborting a whole read
    with an ``OperationalError`` nothing catches.

    Parameters
    ----------
    window : ProviderPredictionWindow
        Every fixture the provider read returned, in any order, each with the
        probabilities it published, which may be none.
    fixture_keys : dict of int to int
        Primary key of each stored fixture, keyed by provider identifier. A
        fixture absent from it contributes no row.
    synchronized_at : datetime
        Timezone-aware instant stamped on every row.

    Returns
    -------
    list of FixturePrediction
        Unsaved rows, one per distinct natural key, ascending by that key.
    """

    unique_predictions: dict[PredictionKey, FixturePrediction] = {}

    for entry in window.fixtures:
        fixture_key = fixture_keys.get(entry.fixture_provider_id)

        if fixture_key is None:
            continue

        for provider_probability in entry.probabilities:
            key = (fixture_key, provider_probability.market, provider_probability.selection)

            unique_predictions[key] = FixturePrediction(
                fixture_id=fixture_key,
                market=provider_probability.market,
                selection=provider_probability.selection,
                probability=provider_probability.probability,
                synchronized_at=synchronized_at,
            )

    return [unique_predictions[key] for key in sorted(unique_predictions)]


def upsert_fixture_predictions(window: ProviderPredictionWindow, synchronized_at: datetime) -> int:
    """
    Store the probabilities of a prediction read, updating whatever exists.

    ``(fixture, market, selection)`` is the natural key, so running the same
    read twice leaves every row where it was, with the same primary key, and
    only moves the probability the provider revised and the stamp. A fixture the
    read carried without a single probability, which is every fixture more than
    roughly a fortnight out, writes nothing and is still authoritative: it was
    read, so the reconciliation below is entitled to clear whatever it used to
    have.

    Reconciliation is by stamp identity rather than by enumeration, and both
    halves share one transaction. Every row this call writes carries exactly
    ``synchronized_at``, so a row of a fixture the run read carrying any other
    stamp is a selection the provider has stopped publishing, and deleting on
    that condition removes it without the run ever having to work out which of
    the fifty selections went missing. The alternative, diffing the stored
    selections of every fixture against the payload, is a read per fixture and a
    second place where the market vocabulary would have to be enumerated. The
    delete is scoped to the fixtures actually resolved: a fixture outside the
    read keeps its rows, because this run learned nothing about it, and a
    fixture the fixture table has not got yet contributes no scope at all.

    Identity is what the predicate tests, not order, and that is deliberate.
    Deleting the rows stamped earlier than this run reads the wall clock as
    monotonic, which it is not: an NTP step correction, or a second worker on a
    skewed clock, gives a stale row a stamp later than the current run's, and
    such a row survives every subsequent run until the clock catches up while
    being rendered as current. Comparing for inequality cannot care which
    direction the clock moved.

    Sharing the transaction is what stops a reader seeing a fixture whose old
    selections are gone and whose new ones are not in yet, which for the panel
    would be an empty market where a moment earlier there was a full one. The
    fixture keys are resolved inside it too, which shrinks rather than closes
    the gap against the fixture synchronization deleting a match this run holds
    probabilities for: the foreign key is checked by the insert, so a parent
    ``DELETE`` committing between the resolution and the insert still costs the
    whole call an ``IntegrityError``. What moving it in buys is that the two
    statements are consecutive rather than separated by the collapse of the
    entire payload, and the run remains safe to retry.

    Parameters
    ----------
    window : ProviderPredictionWindow
        Every fixture the provider read returned, in any order, each with the
        probabilities it published, which may be none.
    synchronized_at : datetime
        Timezone-aware instant stamped on every row this call writes, and the
        one stamp the reconciliation spares.

    Returns
    -------
    int
        Number of probability rows written.
    """

    read_provider_ids = {entry.fixture_provider_id for entry in window.fixtures}

    with transaction.atomic():
        fixture_keys = _resolve_fixture_keys(read_provider_ids)

        ordered_predictions = _prediction_rows(window, fixture_keys, synchronized_at)

        FixturePrediction.objects.bulk_create(
            ordered_predictions,
            update_conflicts=True,
            unique_fields=["fixture", "market", "selection"],
            update_fields=PREDICTION_UPDATE_FIELDS,
            batch_size=WRITE_BATCH_SIZE,
        )

        FixturePrediction.objects.filter(fixture_id__in=fixture_keys.values()).exclude(
            synchronized_at=synchronized_at
        ).delete()

    return len(ordered_predictions)


def _reliability_rows(
    read: ProviderReliabilityRead, league_keys: dict[int, int], synchronized_at: datetime
) -> list[LeagueMarketReliability]:
    """
    Collapse a reliability read into the rows to offer the upsert, in key order.

    The same single-statement conflict rule and the same deterministic lock
    order as ``_prediction_rows``, over ``(league, market)``.

    Parameters
    ----------
    read : ProviderReliabilityRead
        Competitions the provider read covered and the grades it published for
        them, in any order.
    league_keys : dict of int to int
        Primary key of each stored competition, keyed by provider identifier. A
        competition absent from it contributes no row.
    synchronized_at : datetime
        Timezone-aware instant stamped on every row.

    Returns
    -------
    list of LeagueMarketReliability
        Unsaved rows, one per distinct natural key, ascending by that key.
    """

    unique_grades: dict[ReliabilityKey, LeagueMarketReliability] = {}

    for grade in read.grades:
        league_key = league_keys.get(grade.league_provider_id)

        if league_key is None:
            continue

        unique_grades[(league_key, grade.market)] = LeagueMarketReliability(
            league_id=league_key,
            market=grade.market,
            quality=grade.quality,
            hit_ratio=grade.hit_ratio,
            synchronized_at=synchronized_at,
        )

    return [unique_grades[key] for key in sorted(unique_grades)]


def upsert_market_reliability(read: ProviderReliabilityRead, synchronized_at: datetime) -> int:
    """
    Store the reliability grades of a read, updating whatever exists.

    The same shape as ``upsert_fixture_predictions`` over a table three orders
    of magnitude smaller: ``(league, market)`` is the natural key, the rows are
    presented sorted by it so the lock order does not depend on the order the
    provider listed the competitions in, the reconciliation deletes the rows in
    scope carrying any stamp but this run's, and the resolution, the write, and
    the delete share one transaction.

    Two of the eleven markets never have a row, because the provider's
    predictability payload has no entry for double chance or for over/under 4.5,
    and the reconciliation is what keeps that honest over time. A market the
    provider stops grading, or one it drops from a competition, leaves the table
    on the next run instead of showing a grade nobody has measured since.

    Scope is ``read.league_provider_ids``, the competitions the provider was
    read for, not the competitions its grades happen to mention. Those two
    differ exactly when a league is read and graded in nothing, which one page
    missing either type in scope is enough to cause, and deriving the scope from
    the grades would then leave that league's stale grades in the table for
    good. A competition outside the read keeps its grades, because this run
    learned nothing about it.

    Parameters
    ----------
    read : ProviderReliabilityRead
        Competitions the provider read covered and the grades it published for
        them, in any order, across any number of competitions.
    synchronized_at : datetime
        Timezone-aware instant stamped on every row this call writes, and the
        one stamp the reconciliation spares.

    Returns
    -------
    int
        Number of reliability rows written.
    """

    with transaction.atomic():
        league_keys = _resolve_league_keys(set(read.league_provider_ids))

        ordered_grades = _reliability_rows(read, league_keys, synchronized_at)

        LeagueMarketReliability.objects.bulk_create(
            ordered_grades,
            update_conflicts=True,
            unique_fields=["league", "market"],
            update_fields=RELIABILITY_UPDATE_FIELDS,
            batch_size=WRITE_BATCH_SIZE,
        )

        LeagueMarketReliability.objects.filter(league_id__in=league_keys.values()).exclude(
            synchronized_at=synchronized_at
        ).delete()

    return len(ordered_grades)
