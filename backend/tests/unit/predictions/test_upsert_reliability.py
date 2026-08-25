from datetime import datetime
from decimal import Decimal

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.predictions.domain.enums import PredictionMarket, PredictionReliability
from apps.predictions.infrastructure import repositories
from apps.predictions.models import LeagueMarketReliability
from integrations.sportmonks.predictions import ProviderReliability
from tests.conftest import CapturedRecord
from tests.unit.fixtures.conftest import LA_LIGA, PREMIER_LEAGUE
from tests.unit.predictions.conftest import (
    LATER_SYNCHRONIZED_AT,
    SPLIT_BATCH_SIZE,
    SYNCHRONIZED_AT,
    insert_statements,
    reliability,
    seed_leagues,
    store_reliability,
)

PREMIER_LEAGUE_ID = PREMIER_LEAGUE.provider_id

LA_LIGA_ID = LA_LIGA.provider_id

UNSTORED_LEAGUE_ID = 999

BOTH_LEAGUE_IDS = [PREMIER_LEAGUE_ID, LA_LIGA_ID]

BOTH_LEAGUES = [PREMIER_LEAGUE, LA_LIGA]

PREMIER_FULLTIME = reliability(
    PREMIER_LEAGUE_ID, PredictionMarket.FULLTIME_RESULT, PredictionReliability.MEDIUM, "0.500"
)

PREMIER_BOTH_SCORE = reliability(
    PREMIER_LEAGUE_ID, PredictionMarket.BOTH_TEAMS_TO_SCORE, PredictionReliability.GOOD, "0.612"
)

PREMIER_GRADES = [PREMIER_FULLTIME, PREMIER_BOTH_SCORE]

PREMIER_CORRECT_SCORE = reliability(
    PREMIER_LEAGUE_ID, PredictionMarket.CORRECT_SCORE, PredictionReliability.POOR, "0.118"
)

REVISED_PREMIER_FULLTIME = reliability(
    PREMIER_LEAGUE_ID, PredictionMarket.FULLTIME_RESULT, PredictionReliability.HIGH, "0.734"
)

LA_LIGA_FULLTIME = reliability(
    LA_LIGA_ID, PredictionMarket.FULLTIME_RESULT, PredictionReliability.GOOD, "0.545"
)

UNSTORED_LEAGUE_FULLTIME = reliability(
    UNSTORED_LEAGUE_ID, PredictionMarket.FULLTIME_RESULT, PredictionReliability.POOR, "0.203"
)

GradeRow = tuple[int, str]

StoredGrade = tuple[int, str, Decimal]


def grade_key(grade: ProviderReliability) -> GradeRow:
    """
    Return the natural key a provider grade is stored under.

    Parameters
    ----------
    grade : ProviderReliability
        Grade whose competition and market form the key.

    Returns
    -------
    GradeRow
        Provider competition identifier and market.
    """

    return (grade.league_provider_id, grade.market)


def stored_grades() -> dict[GradeRow, StoredGrade]:
    """
    Return the primary key, grade, and hit ratio of every row, by natural key.

    Returns
    -------
    dict of GradeRow to StoredGrade
        Primary key, published grade, and hit ratio of each row, keyed by
        provider competition identifier and market.
    """

    return {
        (row.league.sportmonks_id, row.market): (row.pk, row.quality, row.hit_ratio)
        for row in LeagueMarketReliability.objects.select_related("league")
    }


def stored_markets() -> set[GradeRow]:
    """
    Return the natural key of every stored grade.

    Returns
    -------
    set of GradeRow
        Provider competition identifier and market of each row.
    """

    return set(stored_grades())


def insertion_order() -> list[GradeRow]:
    """
    Return the natural key of every stored grade in primary-key order.

    Returns
    -------
    list of GradeRow
        Natural keys ordered by the primary key the insert assigned.
    """

    return [
        (row.league.sportmonks_id, row.market)
        for row in LeagueMarketReliability.objects.select_related("league").order_by("pk")
    ]


def stored_stamps() -> set[datetime]:
    """
    Return the distinct synchronization stamps the stored grades carry.

    Returns
    -------
    set of datetime
        Every stamp present in the table, which a run leaves as a single value.
    """

    return {row.synchronized_at for row in LeagueMarketReliability.objects.all()}


@pytest.mark.django_db
def test_upsert_reliability_reports_how_many_rows_it_wrote() -> None:
    """
    GIVEN a read grading two markets of one stored competition
    WHEN the read is stored
    THEN both rows are written and the call reports as many as it received
    """

    seed_leagues()

    written_count = store_reliability(PREMIER_GRADES)

    assert written_count == len(PREMIER_GRADES)

    assert stored_markets() == {grade_key(PREMIER_FULLTIME), grade_key(PREMIER_BOTH_SCORE)}


@pytest.mark.django_db
def test_upsert_reliability_writes_nothing_for_an_empty_read() -> None:
    """
    GIVEN a read that graded no market at all
    WHEN the read is stored
    THEN nothing is written and no row is reported
    """

    seed_leagues()

    written_count = store_reliability([])

    assert written_count == 0
    assert LeagueMarketReliability.objects.exists() is False


@pytest.mark.django_db
def test_upsert_reliability_changes_only_the_stamp_on_a_second_identical_run() -> None:
    """
    GIVEN a read that has already been stored once
    WHEN the identical read is stored again
    THEN every row keeps its primary key, grade, and hit ratio, and only the stamp moves
    """

    seed_leagues()

    store_reliability(PREMIER_GRADES)

    grades_before = stored_grades()

    written_count = store_reliability(PREMIER_GRADES, LATER_SYNCHRONIZED_AT)

    assert written_count == len(PREMIER_GRADES)
    assert stored_grades() == grades_before
    assert stored_stamps() == {LATER_SYNCHRONIZED_AT}


@pytest.mark.django_db
def test_upsert_reliability_moves_a_regraded_market_instead_of_duplicating_it() -> None:
    """
    GIVEN a stored market the provider later regraded and gave a new hit ratio
    WHEN the read is stored again
    THEN the single row carries the new grade under the same primary key
    """

    seed_leagues()
    store_reliability([PREMIER_FULLTIME])

    original_key = LeagueMarketReliability.objects.get().pk

    store_reliability([REVISED_PREMIER_FULLTIME], LATER_SYNCHRONIZED_AT)

    stored = LeagueMarketReliability.objects.get()

    assert stored.pk == original_key

    assert (stored.quality, stored.hit_ratio) == (
        REVISED_PREMIER_FULLTIME.quality,
        REVISED_PREMIER_FULLTIME.hit_ratio,
    )


@pytest.mark.django_db
def test_upsert_reliability_deletes_a_market_the_provider_stopped_grading() -> None:
    """
    GIVEN a competition whose next read omits one of its graded markets
    WHEN that read is stored
    THEN the ungraded row is gone, deleted by carrying the earlier stamp
    """

    seed_leagues()
    store_reliability([PREMIER_FULLTIME, PREMIER_BOTH_SCORE, PREMIER_CORRECT_SCORE])

    store_reliability([PREMIER_FULLTIME, PREMIER_BOTH_SCORE], LATER_SYNCHRONIZED_AT)

    assert stored_markets() == {grade_key(PREMIER_FULLTIME), grade_key(PREMIER_BOTH_SCORE)}


@pytest.mark.django_db
def test_upsert_reliability_leaves_a_competition_the_read_did_not_cover_alone() -> None:
    """
    GIVEN two graded competitions whose rows were written by the same read
    WHEN a later read covering only the first one is stored
    THEN the second competition keeps its grade, because the run learned nothing about it
    """

    seed_leagues(BOTH_LEAGUES)
    store_reliability([PREMIER_FULLTIME, LA_LIGA_FULLTIME])

    store_reliability([PREMIER_FULLTIME], LATER_SYNCHRONIZED_AT)

    assert stored_markets() == {grade_key(PREMIER_FULLTIME), grade_key(LA_LIGA_FULLTIME)}


@pytest.mark.django_db
def test_upsert_reliability_skips_a_competition_that_is_not_stored_yet(
    loguru_records: list[CapturedRecord],
) -> None:
    """
    GIVEN a read grading a competition the fixture synchronization has not stored
    WHEN the read is stored
    THEN the known competition is written, the unknown one is skipped, and the skip is reported
    """

    seed_leagues()

    written_count = store_reliability([PREMIER_FULLTIME, UNSTORED_LEAGUE_FULLTIME])

    assert written_count == 1
    assert stored_markets() == {grade_key(PREMIER_FULLTIME)}

    assert [message for level, message, _ in loguru_records if level == "INFO"] == [
        "Skipped 1 competition(s) of a reliability read that are not stored yet."
    ]


@pytest.mark.django_db
def test_upsert_reliability_collapses_a_read_repeating_a_natural_key() -> None:
    """
    GIVEN a read grading one market of one competition twice
    WHEN the read is stored
    THEN one row is written, carrying the last grade rather than raising
    """

    seed_leagues()

    written_count = store_reliability([PREMIER_FULLTIME, REVISED_PREMIER_FULLTIME])

    assert written_count == 1
    assert LeagueMarketReliability.objects.get().quality == REVISED_PREMIER_FULLTIME.quality


@pytest.mark.django_db
def test_upsert_reliability_presents_every_row_in_natural_key_order() -> None:
    """
    GIVEN a read whose competitions and markets both arrive out of order
    WHEN the read is stored
    THEN the keys ascend with the natural key, so the lock order cannot vary between runs
    """

    seed_leagues(BOTH_LEAGUES)

    store_reliability([LA_LIGA_FULLTIME, PREMIER_FULLTIME, PREMIER_CORRECT_SCORE])

    assert insertion_order() == [
        grade_key(PREMIER_CORRECT_SCORE),
        grade_key(PREMIER_FULLTIME),
        grade_key(LA_LIGA_FULLTIME),
    ]


@pytest.mark.django_db
def test_upsert_reliability_clears_a_competition_the_read_graded_in_nothing() -> None:
    """
    GIVEN two graded competitions and a later read covering both while grading only one
    WHEN that read is stored
    THEN the ungraded competition loses its grades, because the read covered it authoritatively
    """

    seed_leagues(BOTH_LEAGUES)
    store_reliability([PREMIER_FULLTIME, LA_LIGA_FULLTIME])

    store_reliability([PREMIER_FULLTIME], LATER_SYNCHRONIZED_AT, BOTH_LEAGUE_IDS)

    assert stored_markets() == {grade_key(PREMIER_FULLTIME)}


@pytest.mark.django_db
def test_upsert_reliability_deletes_a_stale_grade_stamped_after_the_run() -> None:
    """
    GIVEN a stored grade stamped later than the run withdrawing it, as a clock step leaves it
    WHEN a read omitting that market is stored under the earlier stamp
    THEN the row is gone, because the reconciliation compares the stamp rather than ordering it
    """

    seed_leagues()
    store_reliability([PREMIER_FULLTIME, PREMIER_BOTH_SCORE], LATER_SYNCHRONIZED_AT)

    store_reliability([PREMIER_FULLTIME], SYNCHRONIZED_AT)

    assert stored_markets() == {grade_key(PREMIER_FULLTIME)}
    assert stored_stamps() == {SYNCHRONIZED_AT}


@pytest.mark.django_db
def test_upsert_reliability_resolves_every_competition_of_a_read_in_one_query() -> None:
    """
    GIVEN two reads of the same shape differing only in how many competitions they cover
    WHEN each read is stored
    THEN both writes cost the same number of statements
    """

    seed_leagues(BOTH_LEAGUES)

    with CaptureQueriesContext(connection) as one_competition:
        store_reliability([PREMIER_FULLTIME])

    with CaptureQueriesContext(connection) as two_competitions:
        store_reliability([PREMIER_FULLTIME, LA_LIGA_FULLTIME], LATER_SYNCHRONIZED_AT)

    assert len(two_competitions.captured_queries) == len(one_competition.captured_queries)


@pytest.mark.django_db
def test_upsert_reliability_splits_its_write_at_the_batch_size(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    GIVEN a batch of one row and a read grading two markets of one competition
    WHEN the read is stored
    THEN one insert is issued per row, so no read can grow into a single oversized statement
    """

    monkeypatch.setattr(repositories, "WRITE_BATCH_SIZE", SPLIT_BATCH_SIZE)

    seed_leagues()

    with CaptureQueriesContext(connection) as statements:
        store_reliability(PREMIER_GRADES)

    assert len(insert_statements(statements)) == len(PREMIER_GRADES)
