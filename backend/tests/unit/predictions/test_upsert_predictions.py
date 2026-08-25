from datetime import datetime
from decimal import Decimal

import pytest
from django.db import OperationalError, connection
from django.db.models import Model, QuerySet
from django.test.utils import CaptureQueriesContext

from apps.predictions.domain.enums import PredictionMarket, PredictionSelection
from apps.predictions.infrastructure import repositories
from apps.predictions.models import FixturePrediction, LeagueMarketReliability
from integrations.sportmonks.predictions import ProviderProbability
from tests.conftest import CapturedRecord
from tests.unit.predictions.conftest import (
    FIXTURE_PROVIDER_ID,
    LATER_SYNCHRONIZED_AT,
    SPLIT_BATCH_SIZE,
    SYNCHRONIZED_AT,
    fixture_probabilities,
    insert_statements,
    probability,
    seed_fixtures,
    store_predictions,
)

SECOND_FIXTURE_PROVIDER_ID = 2

UNSTORED_FIXTURE_PROVIDER_ID = 99

BOTH_FIXTURES = [FIXTURE_PROVIDER_ID, SECOND_FIXTURE_PROVIDER_ID]

MANY_FIXTURES = 20

# psycopg refuses a statement carrying more than this many placeholders, which is what the batch
# size of the repository exists to stay clear of.
PLACEHOLDER_CEILING = 65535

RECONCILIATION_FAILURE = "The reconciliation delete was cancelled."

HOME_WIN = probability(PredictionMarket.FULLTIME_RESULT, PredictionSelection.HOME, "26.96")

DRAWN = probability(PredictionMarket.FULLTIME_RESULT, PredictionSelection.DRAW, "24.82")

AWAY_WIN = probability(PredictionMarket.FULLTIME_RESULT, PredictionSelection.AWAY, "48.18")

REVISED_HOME_WIN = probability(PredictionMarket.FULLTIME_RESULT, PredictionSelection.HOME, "31.04")

BOTH_SCORE = probability(PredictionMarket.BOTH_TEAMS_TO_SCORE, PredictionSelection.YES, "51.30")

FULLTIME_SELECTIONS = [HOME_WIN, DRAWN, AWAY_WIN]

SelectionRow = tuple[int, str, str]

StoredRow = tuple[int, Decimal]


def selection_key(provider_id: int, chance: ProviderProbability) -> SelectionRow:
    """
    Return the natural key a provider probability is stored under.

    Parameters
    ----------
    provider_id : int
        Provider identifier of the fixture the probability belongs to.
    chance : ProviderProbability
        Probability whose market and selection complete the key.

    Returns
    -------
    SelectionRow
        Provider fixture identifier, market, and selection.
    """

    return (provider_id, chance.market, chance.selection)


def stored_rows() -> dict[SelectionRow, StoredRow]:
    """
    Return the primary key and probability of every stored row, by natural key.

    Returns
    -------
    dict of SelectionRow to StoredRow
        Primary key and stored percentage of each row, keyed by provider fixture
        identifier, market, and selection.
    """

    return {
        (row.fixture.sportmonks_id, row.market, row.selection): (row.pk, row.probability)
        for row in FixturePrediction.objects.select_related("fixture")
    }


def stored_selections() -> set[SelectionRow]:
    """
    Return the natural key of every stored row.

    Returns
    -------
    set of SelectionRow
        Provider fixture identifier, market, and selection of each row.
    """

    return set(stored_rows())


def insertion_order() -> list[SelectionRow]:
    """
    Return the natural key of every stored row in primary-key order.

    Returns
    -------
    list of SelectionRow
        Natural keys ordered by the primary key the insert assigned.
    """

    return [
        (row.fixture.sportmonks_id, row.market, row.selection)
        for row in FixturePrediction.objects.select_related("fixture").order_by("pk")
    ]


def stored_stamps() -> set[datetime]:
    """
    Return the distinct synchronization stamps the stored rows carry.

    Returns
    -------
    set of datetime
        Every stamp present in the table, which a run leaves as a single value.
    """

    return {row.synchronized_at for row in FixturePrediction.objects.all()}


def written_column_count(model: type[Model]) -> int:
    """
    Return how many columns one row of a model places in an insert statement.

    Parameters
    ----------
    model : type of Model
        Model whose table the upsert writes.

    Returns
    -------
    int
        Concrete columns other than the generated primary key, which is the
        number of placeholders a single row costs.
    """

    return len([field for field in model._meta.concrete_fields if not field.primary_key])


def fail_the_reconciliation(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Make the delete an upsert reaches after its write fail, as a lock timeout does.

    Parameters
    ----------
    monkeypatch : MonkeyPatch
        Patcher replacing the queryset delete for the duration of the test.
    """

    def delete(_self: QuerySet[FixturePrediction]) -> tuple[int, dict[str, int]]:
        raise OperationalError(RECONCILIATION_FAILURE)

    monkeypatch.setattr(QuerySet, "delete", delete)


@pytest.mark.django_db
def test_upsert_predictions_reports_how_many_rows_it_wrote() -> None:
    """
    GIVEN a read carrying the three full-time selections of one stored fixture
    WHEN the read is stored
    THEN all three rows are written and the call reports as many as it received
    """

    seed_fixtures()

    written_count = store_predictions(
        [fixture_probabilities(FIXTURE_PROVIDER_ID, FULLTIME_SELECTIONS)]
    )

    assert written_count == len(FULLTIME_SELECTIONS)

    assert stored_selections() == {
        selection_key(FIXTURE_PROVIDER_ID, HOME_WIN),
        selection_key(FIXTURE_PROVIDER_ID, DRAWN),
        selection_key(FIXTURE_PROVIDER_ID, AWAY_WIN),
    }


@pytest.mark.django_db
def test_upsert_predictions_writes_nothing_for_a_fixture_carrying_no_probability() -> None:
    """
    GIVEN a read covering a stored fixture the provider published nothing for
    WHEN the read is stored
    THEN no row is written and no row is reported, which is the ordinary state
    """

    seed_fixtures()

    written_count = store_predictions([fixture_probabilities(FIXTURE_PROVIDER_ID, [])])

    assert written_count == 0
    assert FixturePrediction.objects.exists() is False


@pytest.mark.django_db
def test_upsert_predictions_changes_only_the_stamp_on_a_second_identical_run() -> None:
    """
    GIVEN a read that has already been stored once
    WHEN the identical read is stored again
    THEN every row keeps its primary key and its probability, and only the stamp moves
    """

    seed_fixtures()

    read = [fixture_probabilities(FIXTURE_PROVIDER_ID, FULLTIME_SELECTIONS)]

    store_predictions(read)

    rows_before = stored_rows()

    written_count = store_predictions(read, LATER_SYNCHRONIZED_AT)

    assert written_count == len(FULLTIME_SELECTIONS)
    assert stored_rows() == rows_before
    assert stored_stamps() == {LATER_SYNCHRONIZED_AT}


@pytest.mark.django_db
def test_upsert_predictions_moves_a_revised_probability_instead_of_duplicating_it() -> None:
    """
    GIVEN a stored selection whose probability the provider later revised
    WHEN the read is stored again
    THEN the single row carries the new percentage under the same primary key
    """

    seed_fixtures()
    store_predictions([fixture_probabilities(FIXTURE_PROVIDER_ID, [HOME_WIN])])

    original_key = FixturePrediction.objects.get().pk

    store_predictions(
        [fixture_probabilities(FIXTURE_PROVIDER_ID, [REVISED_HOME_WIN])], LATER_SYNCHRONIZED_AT
    )

    stored = FixturePrediction.objects.get()

    assert stored.pk == original_key
    assert stored.probability == REVISED_HOME_WIN.probability


@pytest.mark.django_db
def test_upsert_predictions_deletes_a_selection_the_provider_withdrew() -> None:
    """
    GIVEN a stored fixture whose next read omits one of its selections
    WHEN that read is stored
    THEN the withdrawn row is gone, deleted by carrying the earlier stamp
    """

    seed_fixtures()
    store_predictions([fixture_probabilities(FIXTURE_PROVIDER_ID, [HOME_WIN, DRAWN, BOTH_SCORE])])

    store_predictions(
        [fixture_probabilities(FIXTURE_PROVIDER_ID, [HOME_WIN, DRAWN])], LATER_SYNCHRONIZED_AT
    )

    assert stored_selections() == {
        selection_key(FIXTURE_PROVIDER_ID, HOME_WIN),
        selection_key(FIXTURE_PROVIDER_ID, DRAWN),
    }


@pytest.mark.django_db
def test_upsert_predictions_empties_a_fixture_the_provider_stopped_predicting() -> None:
    """
    GIVEN a stored fixture the next read covers without a single probability
    WHEN that read is stored
    THEN every row of the fixture is gone, because the read was authoritative
    """

    seed_fixtures()
    store_predictions([fixture_probabilities(FIXTURE_PROVIDER_ID, [HOME_WIN, DRAWN])])

    written_count = store_predictions(
        [fixture_probabilities(FIXTURE_PROVIDER_ID, [])], LATER_SYNCHRONIZED_AT
    )

    assert written_count == 0
    assert FixturePrediction.objects.exists() is False


@pytest.mark.django_db
def test_upsert_predictions_leaves_a_fixture_the_read_did_not_cover_alone() -> None:
    """
    GIVEN two stored fixtures whose rows were written by the same read
    WHEN a later read covering only the first one is stored
    THEN the second fixture keeps its rows, because the run learned nothing about it
    """

    seed_fixtures(BOTH_FIXTURES)

    store_predictions(
        [
            fixture_probabilities(FIXTURE_PROVIDER_ID, [HOME_WIN]),
            fixture_probabilities(SECOND_FIXTURE_PROVIDER_ID, [BOTH_SCORE]),
        ]
    )

    store_predictions(
        [fixture_probabilities(FIXTURE_PROVIDER_ID, [HOME_WIN])], LATER_SYNCHRONIZED_AT
    )

    assert stored_selections() == {
        selection_key(FIXTURE_PROVIDER_ID, HOME_WIN),
        selection_key(SECOND_FIXTURE_PROVIDER_ID, BOTH_SCORE),
    }


@pytest.mark.django_db
def test_upsert_predictions_skips_a_fixture_that_is_not_stored_yet(
    loguru_records: list[CapturedRecord],
) -> None:
    """
    GIVEN a read mentioning a fixture the fixture synchronization has not stored
    WHEN the read is stored
    THEN the known fixture is written, the unknown one is skipped, and the skip is reported
    """

    seed_fixtures()

    written_count = store_predictions(
        [
            fixture_probabilities(FIXTURE_PROVIDER_ID, [HOME_WIN]),
            fixture_probabilities(UNSTORED_FIXTURE_PROVIDER_ID, [HOME_WIN, DRAWN]),
        ]
    )

    assert written_count == 1
    assert stored_selections() == {selection_key(FIXTURE_PROVIDER_ID, HOME_WIN)}

    assert [message for level, message, _ in loguru_records if level == "INFO"] == [
        "Skipped 1 fixture(s) of a prediction read that are not stored yet."
    ]


@pytest.mark.django_db
def test_upsert_predictions_collapses_a_read_repeating_a_natural_key() -> None:
    """
    GIVEN a read publishing two percentages for one selection of one fixture
    WHEN the read is stored
    THEN one row is written, carrying the last percentage rather than raising
    """

    seed_fixtures()

    written_count = store_predictions(
        [fixture_probabilities(FIXTURE_PROVIDER_ID, [HOME_WIN, REVISED_HOME_WIN])]
    )

    assert written_count == 1
    assert FixturePrediction.objects.get().probability == REVISED_HOME_WIN.probability


@pytest.mark.django_db
def test_upsert_predictions_presents_every_row_in_natural_key_order() -> None:
    """
    GIVEN a read whose fixtures, markets, and selections all arrive out of order
    WHEN the read is stored
    THEN the keys ascend with the natural key, so the lock order cannot vary between runs
    """

    seed_fixtures(BOTH_FIXTURES)

    store_predictions(
        [
            fixture_probabilities(SECOND_FIXTURE_PROVIDER_ID, [DRAWN, HOME_WIN]),
            fixture_probabilities(FIXTURE_PROVIDER_ID, [BOTH_SCORE, AWAY_WIN]),
        ]
    )

    assert insertion_order() == [
        selection_key(FIXTURE_PROVIDER_ID, BOTH_SCORE),
        selection_key(FIXTURE_PROVIDER_ID, AWAY_WIN),
        selection_key(SECOND_FIXTURE_PROVIDER_ID, DRAWN),
        selection_key(SECOND_FIXTURE_PROVIDER_ID, HOME_WIN),
    ]


@pytest.mark.django_db
def test_upsert_predictions_resolves_every_fixture_of_a_read_in_one_query() -> None:
    """
    GIVEN two reads of the same shape differing only in how many fixtures they cover
    WHEN each read is stored
    THEN both writes cost the same number of statements
    """

    provider_ids = list(range(1, MANY_FIXTURES + 1))

    seed_fixtures(provider_ids)

    small_read = [fixture_probabilities(provider_id, [HOME_WIN]) for provider_id in BOTH_FIXTURES]
    large_read = [fixture_probabilities(provider_id, [HOME_WIN]) for provider_id in provider_ids]

    with CaptureQueriesContext(connection) as small_statements:
        store_predictions(small_read, SYNCHRONIZED_AT)

    with CaptureQueriesContext(connection) as large_statements:
        store_predictions(large_read, LATER_SYNCHRONIZED_AT)

    assert len(large_statements.captured_queries) == len(small_statements.captured_queries)


@pytest.mark.django_db
def test_upsert_predictions_leaves_the_whole_table_alone_for_an_empty_read() -> None:
    """
    GIVEN a stored fixture carrying probabilities and a later read covering no fixture at all
    WHEN that read is stored
    THEN nothing is written and every row survives, because an empty read scopes nothing
    """

    seed_fixtures()
    store_predictions([fixture_probabilities(FIXTURE_PROVIDER_ID, FULLTIME_SELECTIONS)])

    written_count = store_predictions([], LATER_SYNCHRONIZED_AT)

    assert written_count == 0

    assert stored_selections() == {
        selection_key(FIXTURE_PROVIDER_ID, HOME_WIN),
        selection_key(FIXTURE_PROVIDER_ID, DRAWN),
        selection_key(FIXTURE_PROVIDER_ID, AWAY_WIN),
    }


@pytest.mark.django_db
def test_upsert_predictions_deletes_a_withdrawn_selection_stamped_after_the_run() -> None:
    """
    GIVEN a stored selection stamped later than the run withdrawing it, as a clock step leaves it
    WHEN a read omitting that selection is stored under the earlier stamp
    THEN the row is gone, because the reconciliation compares the stamp rather than ordering it
    """

    seed_fixtures()

    store_predictions(
        [fixture_probabilities(FIXTURE_PROVIDER_ID, [HOME_WIN, BOTH_SCORE])],
        LATER_SYNCHRONIZED_AT,
    )

    store_predictions([fixture_probabilities(FIXTURE_PROVIDER_ID, [HOME_WIN])], SYNCHRONIZED_AT)

    assert stored_selections() == {selection_key(FIXTURE_PROVIDER_ID, HOME_WIN)}
    assert stored_stamps() == {SYNCHRONIZED_AT}


@pytest.mark.django_db
def test_upsert_predictions_splits_its_write_at_the_batch_size(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    GIVEN a batch of one row and a read carrying the three full-time selections
    WHEN the read is stored
    THEN one insert is issued per row, so no read can grow into a single oversized statement
    """

    monkeypatch.setattr(repositories, "WRITE_BATCH_SIZE", SPLIT_BATCH_SIZE)

    seed_fixtures()

    with CaptureQueriesContext(connection) as statements:
        store_predictions([fixture_probabilities(FIXTURE_PROVIDER_ID, FULLTIME_SELECTIONS)])

    assert len(insert_statements(statements)) == len(FULLTIME_SELECTIONS)


def test_the_batch_size_keeps_both_writes_inside_the_placeholder_ceiling() -> None:
    """
    GIVEN the batch size the two upserts write under and the columns each of their rows places
    WHEN a full batch is priced in placeholders
    THEN it stays inside the ceiling the driver enforces, for both tables the module writes
    """

    widest_row = max(
        written_column_count(FixturePrediction), written_column_count(LeagueMarketReliability)
    )

    assert repositories.WRITE_BATCH_SIZE * widest_row <= PLACEHOLDER_CEILING


@pytest.mark.django_db
def test_upsert_predictions_rolls_its_write_back_when_the_reconciliation_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    GIVEN a reconciliation delete that fails after the probabilities of a read were written
    WHEN the read is stored
    THEN the failure surfaces and no row survives, so a reader never sees a half-refreshed fixture
    """

    seed_fixtures()

    fail_the_reconciliation(monkeypatch)

    with pytest.raises(OperationalError, match=RECONCILIATION_FAILURE):
        store_predictions([fixture_probabilities(FIXTURE_PROVIDER_ID, FULLTIME_SELECTIONS)])

    assert FixturePrediction.objects.exists() is False
