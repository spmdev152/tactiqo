import logging
from collections.abc import Collection, Sequence
from datetime import datetime

from django.db import transaction

from apps.fixtures.models import Fixture, League
from apps.predictions.models import FixturePrediction, LeagueMarketReliability
from integrations.sportmonks.predictions import ProviderPredictionWindow, ProviderReliability

logger = logging.getLogger(__name__)

PREDICTION_UPDATE_FIELDS = ["probability", "synchronized_at"]

RELIABILITY_UPDATE_FIELDS = ["quality", "hit_ratio", "synchronized_at"]

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
        Distinct provider identifiers of the competitions the read graded.

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

    Reconciliation is by stamp rather than by enumeration, and both halves share
    one transaction. Every row this call writes carries ``synchronized_at``, so
    a row of a fixture the run read that still carries an earlier stamp is a
    selection the provider has stopped publishing, and deleting on that
    condition removes it without the run ever having to work out which of the
    fifty selections went missing. The alternative, diffing the stored
    selections of every fixture against the payload, is a read per fixture and a
    second place where the market vocabulary would have to be enumerated. The
    delete is scoped to the fixtures actually resolved: a fixture outside the
    read keeps its rows, because this run learned nothing about it, and a
    fixture the fixture table has not got yet contributes no scope at all.

    Sharing the transaction is what stops a reader seeing a fixture whose old
    selections are gone and whose new ones are not in yet, which for the panel
    would be an empty market where a moment earlier there was a full one. The
    rows are presented sorted by natural key so the lock order is deterministic
    across runs: offered in the order the provider paginated them, two runs over
    overlapping windows could take the same fixtures' row locks in different
    orders and deadlock, aborting a whole read with an ``OperationalError``
    nothing catches.

    Parameters
    ----------
    window : ProviderPredictionWindow
        Every fixture the provider read returned, in any order, each with the
        probabilities it published, which may be none.
    synchronized_at : datetime
        Timezone-aware instant stamped on every row this call writes, and the
        threshold the reconciliation deletes below.

    Returns
    -------
    int
        Number of probability rows written.
    """

    read_provider_ids = {entry.fixture_provider_id for entry in window.fixtures}

    fixture_keys = _resolve_fixture_keys(read_provider_ids)

    # ``ON CONFLICT DO UPDATE`` refuses to touch the same row twice in one
    # statement, so a read repeating a natural key must collapse before it
    # reaches the database.
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

    ordered_predictions = [unique_predictions[key] for key in sorted(unique_predictions)]

    with transaction.atomic():
        FixturePrediction.objects.bulk_create(
            ordered_predictions,
            update_conflicts=True,
            unique_fields=["fixture", "market", "selection"],
            update_fields=PREDICTION_UPDATE_FIELDS,
        )

        FixturePrediction.objects.filter(
            fixture_id__in=fixture_keys.values(), synchronized_at__lt=synchronized_at
        ).delete()

    return len(ordered_predictions)


def upsert_market_reliability(
    grades: Sequence[ProviderReliability], synchronized_at: datetime
) -> int:
    """
    Store the reliability grades of a read, updating whatever exists.

    The same shape as ``upsert_fixture_predictions`` over a table three orders
    of magnitude smaller: ``(league, market)`` is the natural key, the rows are
    presented sorted by it so the lock order does not depend on the order the
    provider listed the competitions in, and the stamp reconciliation runs in
    the same transaction as the write.

    Two of the eleven markets never have a row, because the provider's
    predictability payload has no entry for double chance or for over/under 4.5,
    and the reconciliation is what keeps that honest over time. A market the
    provider stops grading, or one it drops from a competition, leaves the table
    on the next run instead of showing a grade nobody has measured since. The
    delete is scoped to the competitions the read resolved, so a league absent
    from this read keeps its grades.

    Parameters
    ----------
    grades : Sequence of ProviderReliability
        Grades the provider published, in any order, across any number of
        competitions.
    synchronized_at : datetime
        Timezone-aware instant stamped on every row this call writes, and the
        threshold the reconciliation deletes below.

    Returns
    -------
    int
        Number of reliability rows written.
    """

    read_provider_ids = {grade.league_provider_id for grade in grades}

    league_keys = _resolve_league_keys(read_provider_ids)

    # The same single-statement conflict rule as the probabilities: a read
    # repeating a natural key has to collapse before the upsert.
    unique_grades: dict[ReliabilityKey, LeagueMarketReliability] = {}

    for grade in grades:
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

    ordered_grades = [unique_grades[key] for key in sorted(unique_grades)]

    with transaction.atomic():
        LeagueMarketReliability.objects.bulk_create(
            ordered_grades,
            update_conflicts=True,
            unique_fields=["league", "market"],
            update_fields=RELIABILITY_UPDATE_FIELDS,
        )

        LeagueMarketReliability.objects.filter(
            league_id__in=league_keys.values(), synchronized_at__lt=synchronized_at
        ).delete()

    return len(ordered_grades)
