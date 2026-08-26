from datetime import datetime

import pytest
from django.db import OperationalError, connection
from django.db.models import Model, QuerySet
from django.test.utils import CaptureQueriesContext

from apps.statistics.domain.enums import MatchSide
from apps.statistics.infrastructure import repositories
from apps.statistics.models import MatchTeamStatistic
from tests.conftest import CapturedRecord
from tests.unit.fixtures.conftest import LIVERPOOL, NOTTINGHAM_FOREST
from tests.unit.statistics.conftest import (
    FIXTURE_PROVIDER_ID,
    LATER_SYNCHRONIZED_AT,
    METRIC_COLUMNS,
    SPLIT_BATCH_SIZE,
    SYNCHRONIZED_AT,
    fixture_statistics,
    insert_statements,
    seed_fixture_ids,
    store_statistics,
    team_statistics,
)

SECOND_FIXTURE_PROVIDER_ID = 2

UNSTORED_FIXTURE_PROVIDER_ID = 99

THIRD_FIXTURE_PROVIDER_ID = 3

UNSTORED_TEAM_PROVIDER_ID = 999

BOTH_FIXTURES = [FIXTURE_PROVIDER_ID, SECOND_FIXTURE_PROVIDER_ID]

MANY_FIXTURES = 20

# psycopg refuses a statement carrying more than this many placeholders, which is what the batch
# size of the repository exists to stay clear of.
PLACEHOLDER_CEILING = 65535

RECONCILIATION_FAILURE = "The reconciliation delete was cancelled."

HOME_PERFORMANCE = team_statistics(LIVERPOOL.provider_id, MatchSide.HOME)

AWAY_PERFORMANCE = team_statistics(
    NOTTINGHAM_FOREST.provider_id, MatchSide.AWAY, possession=46, shots_total=9
)

REVISED_HOME_PERFORMANCE = team_statistics(
    LIVERPOOL.provider_id, MatchSide.HOME, shots_total=15, corners=8
)

UNSTORED_CLUB_PERFORMANCE = team_statistics(UNSTORED_TEAM_PROVIDER_ID, MatchSide.AWAY)

SWAPPED_HOME_PERFORMANCE = team_statistics(NOTTINGHAM_FOREST.provider_id, MatchSide.HOME)

SWAPPED_AWAY_PERFORMANCE = team_statistics(LIVERPOOL.provider_id, MatchSide.AWAY)

BOTH_SIDES = [HOME_PERFORMANCE, AWAY_PERFORMANCE]

SWAPPED_SIDES = [SWAPPED_HOME_PERFORMANCE, SWAPPED_AWAY_PERFORMANCE]

# One side a match, so a read covering twenty of them still writes a single
# insert on the SQLite the tests run against, whose bound-parameter cap is
# lower than the batch size of the repository. Without it a statement count
# would measure a batch the driver split rather than the queries the
# repository issues.
ONE_SIDE = [HOME_PERFORMANCE]

PerformanceRow = tuple[int, int]

StoredRow = tuple[int, str, tuple[int, ...]]


def performance_key(fixture_provider_id: int, team_provider_id: int) -> PerformanceRow:
    """
    Return the natural key a provider performance is stored under.

    Parameters
    ----------
    fixture_provider_id : int
        Provider identifier of the match the performance belongs to.
    team_provider_id : int
        Provider identifier of the club the performance belongs to.

    Returns
    -------
    PerformanceRow
        Provider match identifier and provider club identifier.
    """

    return (fixture_provider_id, team_provider_id)


def stored_rows() -> dict[PerformanceRow, StoredRow]:
    """
    Return the primary key, side, and every figure of each row, by natural key.

    Returns
    -------
    dict of PerformanceRow to StoredRow
        Primary key, side, and the twenty-two figures of each row, keyed by
        provider match identifier and provider club identifier.
    """

    return {
        (row.fixture.sportmonks_id, row.team.sportmonks_id): (
            row.pk,
            row.side,
            tuple(getattr(row, column) for column in METRIC_COLUMNS),
        )
        for row in MatchTeamStatistic.objects.select_related("fixture", "team")
    }


def stored_performances() -> set[PerformanceRow]:
    """
    Return the natural key of every stored row.

    Returns
    -------
    set of PerformanceRow
        Provider match identifier and provider club identifier of each row.
    """

    return set(stored_rows())


def stored_sides() -> dict[PerformanceRow, str]:
    """
    Return the side each stored row records, by natural key.

    Returns
    -------
    dict of PerformanceRow to str
        Side of each row, keyed by provider match and provider club identifier.
    """

    return {
        (row.fixture.sportmonks_id, row.team.sportmonks_id): row.side
        for row in MatchTeamStatistic.objects.select_related("fixture", "team")
    }


def insertion_order() -> list[PerformanceRow]:
    """
    Return the natural key of every stored row in primary-key order.

    Returns
    -------
    list of PerformanceRow
        Natural keys ordered by the primary key the insert assigned.
    """

    return [
        (row.fixture.sportmonks_id, row.team.sportmonks_id)
        for row in MatchTeamStatistic.objects.select_related("fixture", "team").order_by("pk")
    ]


def stored_stamps() -> set[datetime]:
    """
    Return the distinct synchronization stamps the stored rows carry.

    Returns
    -------
    set of datetime
        Every stamp present in the table, which a run leaves as a single value.
    """

    return {row.synchronized_at for row in MatchTeamStatistic.objects.all()}


def reported_skips(records: list[CapturedRecord]) -> list[str]:
    """
    Return the messages the repository reported at information level.

    Parameters
    ----------
    records : list of CapturedRecord
        Records the Loguru sink collected during the test.

    Returns
    -------
    list of str
        Messages of every information record, in emission order.
    """

    return [message for level, message, _ in records if level == "INFO"]


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
    Make the delete the upsert reaches after its write fail, as a lock timeout does.

    Parameters
    ----------
    monkeypatch : MonkeyPatch
        Patcher replacing the queryset delete for the duration of the test.
    """

    def delete(_self: QuerySet[MatchTeamStatistic]) -> tuple[int, dict[str, int]]:
        raise OperationalError(RECONCILIATION_FAILURE)

    monkeypatch.setattr(QuerySet, "delete", delete)


@pytest.mark.django_db
def test_upsert_statistics_reports_how_many_rows_it_wrote() -> None:
    """
    GIVEN a read carrying both sides of one stored match
    WHEN the read is stored
    THEN both rows are written and the call reports as many as it received
    """

    seed_fixture_ids()

    written_count = store_statistics([fixture_statistics(FIXTURE_PROVIDER_ID, BOTH_SIDES)])

    assert written_count == len(BOTH_SIDES)

    assert stored_performances() == {
        performance_key(FIXTURE_PROVIDER_ID, LIVERPOOL.provider_id),
        performance_key(FIXTURE_PROVIDER_ID, NOTTINGHAM_FOREST.provider_id),
    }


@pytest.mark.django_db
def test_upsert_statistics_stores_every_figure_of_the_read() -> None:
    """
    GIVEN a read whose away side is published with its own possession and shot count
    WHEN the read is stored
    THEN the row carries the figures of that side rather than the other side's
    """

    seed_fixture_ids()

    store_statistics([fixture_statistics(FIXTURE_PROVIDER_ID, BOTH_SIDES)])

    stored = MatchTeamStatistic.objects.get(side=MatchSide.AWAY)

    assert (stored.possession, stored.shots_total) == (
        AWAY_PERFORMANCE.values["possession"],
        AWAY_PERFORMANCE.values["shots_total"],
    )


@pytest.mark.django_db
def test_upsert_statistics_writes_nothing_for_a_match_carrying_no_performance() -> None:
    """
    GIVEN a read covering a stored match the provider published no figure for
    WHEN the read is stored
    THEN no row is written and no row is reported, which an abandoned match looks like
    """

    seed_fixture_ids()

    written_count = store_statistics([fixture_statistics(FIXTURE_PROVIDER_ID, [])])

    assert written_count == 0
    assert MatchTeamStatistic.objects.exists() is False


@pytest.mark.django_db
def test_upsert_statistics_changes_only_the_stamp_on_a_second_identical_run() -> None:
    """
    GIVEN a read that has already been stored once
    WHEN the identical read is stored again
    THEN every row keeps its primary key, its side, and its figures, and only the stamp moves
    """

    seed_fixture_ids()

    read = [fixture_statistics(FIXTURE_PROVIDER_ID, BOTH_SIDES)]

    store_statistics(read)

    rows_before = stored_rows()

    written_count = store_statistics(read, LATER_SYNCHRONIZED_AT)

    assert written_count == len(BOTH_SIDES)
    assert stored_rows() == rows_before
    assert stored_stamps() == {LATER_SYNCHRONIZED_AT}


@pytest.mark.django_db
def test_upsert_statistics_moves_a_revised_figure_instead_of_duplicating_it() -> None:
    """
    GIVEN a stored performance whose figures the provider later revised
    WHEN the read is stored again
    THEN the single row carries the new figures under the same primary key
    """

    seed_fixture_ids()
    store_statistics([fixture_statistics(FIXTURE_PROVIDER_ID, [HOME_PERFORMANCE])])

    original_key = MatchTeamStatistic.objects.get().pk

    store_statistics(
        [fixture_statistics(FIXTURE_PROVIDER_ID, [REVISED_HOME_PERFORMANCE])],
        LATER_SYNCHRONIZED_AT,
    )

    stored = MatchTeamStatistic.objects.get()

    assert stored.pk == original_key

    assert (stored.shots_total, stored.corners) == (
        REVISED_HOME_PERFORMANCE.values["shots_total"],
        REVISED_HOME_PERFORMANCE.values["corners"],
    )


@pytest.mark.django_db
def test_upsert_statistics_deletes_a_side_the_provider_stopped_publishing() -> None:
    """
    GIVEN a stored match whose next read omits one of its two sides
    WHEN that read is stored
    THEN the withdrawn row is gone, deleted by carrying the earlier stamp
    """

    seed_fixture_ids()
    store_statistics([fixture_statistics(FIXTURE_PROVIDER_ID, BOTH_SIDES)])

    store_statistics(
        [fixture_statistics(FIXTURE_PROVIDER_ID, [HOME_PERFORMANCE])], LATER_SYNCHRONIZED_AT
    )

    assert stored_performances() == {performance_key(FIXTURE_PROVIDER_ID, LIVERPOOL.provider_id)}


@pytest.mark.django_db
def test_upsert_statistics_empties_a_match_the_provider_stopped_publishing() -> None:
    """
    GIVEN a stored match the next read covers without a single figure
    WHEN that read is stored
    THEN both rows of the match are gone, because the read was authoritative
    """

    seed_fixture_ids()
    store_statistics([fixture_statistics(FIXTURE_PROVIDER_ID, BOTH_SIDES)])

    written_count = store_statistics(
        [fixture_statistics(FIXTURE_PROVIDER_ID, [])], LATER_SYNCHRONIZED_AT
    )

    assert written_count == 0
    assert MatchTeamStatistic.objects.exists() is False


@pytest.mark.django_db
def test_upsert_statistics_leaves_a_match_the_read_did_not_cover_alone() -> None:
    """
    GIVEN two stored matches whose rows were written by the same read
    WHEN a later read covering only the first one is stored
    THEN the second match keeps its rows, because the run learned nothing about it
    """

    seed_fixture_ids(BOTH_FIXTURES)

    store_statistics(
        [
            fixture_statistics(FIXTURE_PROVIDER_ID, BOTH_SIDES),
            fixture_statistics(SECOND_FIXTURE_PROVIDER_ID, BOTH_SIDES),
        ]
    )

    store_statistics(
        [fixture_statistics(FIXTURE_PROVIDER_ID, [HOME_PERFORMANCE])], LATER_SYNCHRONIZED_AT
    )

    assert stored_performances() == {
        performance_key(FIXTURE_PROVIDER_ID, LIVERPOOL.provider_id),
        performance_key(SECOND_FIXTURE_PROVIDER_ID, LIVERPOOL.provider_id),
        performance_key(SECOND_FIXTURE_PROVIDER_ID, NOTTINGHAM_FOREST.provider_id),
    }


@pytest.mark.django_db
def test_upsert_statistics_leaves_the_whole_table_alone_for_an_empty_read() -> None:
    """
    GIVEN a stored match carrying both sides and a later read covering no match at all
    WHEN that read is stored
    THEN nothing is written and every row survives, because an empty read scopes nothing
    """

    seed_fixture_ids()
    store_statistics([fixture_statistics(FIXTURE_PROVIDER_ID, BOTH_SIDES)])

    written_count = store_statistics([], LATER_SYNCHRONIZED_AT)

    assert written_count == 0

    assert stored_performances() == {
        performance_key(FIXTURE_PROVIDER_ID, LIVERPOOL.provider_id),
        performance_key(FIXTURE_PROVIDER_ID, NOTTINGHAM_FOREST.provider_id),
    }


@pytest.mark.django_db
def test_upsert_statistics_skips_a_match_that_is_not_stored_yet(
    loguru_records: list[CapturedRecord],
) -> None:
    """
    GIVEN a read mentioning a match the fixture pass of the chunk did not store
    WHEN the read is stored
    THEN the known match is written, the unknown one is skipped, and the skip is reported
    """

    seed_fixture_ids()

    written_count = store_statistics(
        [
            fixture_statistics(FIXTURE_PROVIDER_ID, [HOME_PERFORMANCE]),
            fixture_statistics(UNSTORED_FIXTURE_PROVIDER_ID, BOTH_SIDES),
        ]
    )

    assert written_count == 1
    assert stored_performances() == {performance_key(FIXTURE_PROVIDER_ID, LIVERPOOL.provider_id)}

    assert reported_skips(loguru_records) == [
        "Skipped 1 match(es) of a statistics read that are not stored yet."
    ]


@pytest.mark.django_db
def test_upsert_statistics_reports_every_unstored_match_of_a_read_in_one_line(
    loguru_records: list[CapturedRecord],
) -> None:
    """
    GIVEN a read mentioning two matches the fixture table has not got
    WHEN the read is stored
    THEN a single line reports both, rather than one line per identifier
    """

    seed_fixture_ids()

    store_statistics(
        [
            fixture_statistics(UNSTORED_FIXTURE_PROVIDER_ID, BOTH_SIDES),
            fixture_statistics(THIRD_FIXTURE_PROVIDER_ID, BOTH_SIDES),
        ]
    )

    assert reported_skips(loguru_records) == [
        "Skipped 2 match(es) of a statistics read that are not stored yet."
    ]


@pytest.mark.django_db
def test_upsert_statistics_skips_a_club_that_is_not_stored_yet(
    loguru_records: list[CapturedRecord],
) -> None:
    """
    GIVEN a read attributing a performance to a club that is not playing the match
    WHEN the read is stored
    THEN the known side is written, the anomalous one is skipped, and the skip is reported
    """

    seed_fixture_ids()

    written_count = store_statistics(
        [fixture_statistics(FIXTURE_PROVIDER_ID, [HOME_PERFORMANCE, UNSTORED_CLUB_PERFORMANCE])]
    )

    assert written_count == 1
    assert stored_performances() == {performance_key(FIXTURE_PROVIDER_ID, LIVERPOOL.provider_id)}

    assert reported_skips(loguru_records) == [
        "Skipped 1 club(s) of a statistics read that are not stored yet."
    ]


@pytest.mark.django_db
def test_upsert_statistics_collapses_a_read_repeating_a_natural_key() -> None:
    """
    GIVEN a read publishing two performances for one club in one match
    WHEN the read is stored
    THEN one row is written, carrying the last figures rather than raising
    """

    seed_fixture_ids()

    written_count = store_statistics(
        [fixture_statistics(FIXTURE_PROVIDER_ID, [HOME_PERFORMANCE, REVISED_HOME_PERFORMANCE])]
    )

    assert written_count == 1

    assert (
        MatchTeamStatistic.objects.get().shots_total
        == REVISED_HOME_PERFORMANCE.values["shots_total"]
    )


@pytest.mark.django_db
def test_upsert_statistics_presents_every_row_in_natural_key_order() -> None:
    """
    GIVEN a read whose matches and whose sides within a match both arrive out of order
    WHEN the read is stored
    THEN the keys ascend with the natural key, so the lock order cannot vary between runs
    """

    seed_fixture_ids(BOTH_FIXTURES)

    store_statistics(
        [
            fixture_statistics(SECOND_FIXTURE_PROVIDER_ID, [AWAY_PERFORMANCE, HOME_PERFORMANCE]),
            fixture_statistics(FIXTURE_PROVIDER_ID, [AWAY_PERFORMANCE, HOME_PERFORMANCE]),
        ]
    )

    assert insertion_order() == [
        performance_key(FIXTURE_PROVIDER_ID, LIVERPOOL.provider_id),
        performance_key(FIXTURE_PROVIDER_ID, NOTTINGHAM_FOREST.provider_id),
        performance_key(SECOND_FIXTURE_PROVIDER_ID, LIVERPOOL.provider_id),
        performance_key(SECOND_FIXTURE_PROVIDER_ID, NOTTINGHAM_FOREST.provider_id),
    ]


@pytest.mark.django_db
def test_upsert_statistics_resolves_every_match_of_a_read_in_one_query() -> None:
    """
    GIVEN two reads of the same shape differing only in how many matches they cover
    WHEN each read is stored
    THEN both writes cost the same number of statements
    """

    provider_ids = list(range(1, MANY_FIXTURES + 1))

    seed_fixture_ids(provider_ids)

    small_read = [fixture_statistics(provider_id, ONE_SIDE) for provider_id in BOTH_FIXTURES]
    large_read = [fixture_statistics(provider_id, ONE_SIDE) for provider_id in provider_ids]

    with CaptureQueriesContext(connection) as small_statements:
        store_statistics(small_read, SYNCHRONIZED_AT)

    with CaptureQueriesContext(connection) as large_statements:
        store_statistics(large_read, LATER_SYNCHRONIZED_AT)

    assert len(large_statements.captured_queries) == len(small_statements.captured_queries)


@pytest.mark.django_db
def test_upsert_statistics_deletes_a_withdrawn_side_stamped_after_the_run() -> None:
    """
    GIVEN a stored side stamped later than the run withdrawing it, as a clock step leaves it
    WHEN a read omitting that side is stored under the earlier stamp
    THEN the row is gone, because the reconciliation compares the stamp rather than ordering it
    """

    seed_fixture_ids()

    store_statistics([fixture_statistics(FIXTURE_PROVIDER_ID, BOTH_SIDES)], LATER_SYNCHRONIZED_AT)

    store_statistics([fixture_statistics(FIXTURE_PROVIDER_ID, [HOME_PERFORMANCE])], SYNCHRONIZED_AT)

    assert stored_performances() == {performance_key(FIXTURE_PROVIDER_ID, LIVERPOOL.provider_id)}
    assert stored_stamps() == {SYNCHRONIZED_AT}


@pytest.mark.django_db
def test_upsert_statistics_stores_a_match_whose_clubs_swapped_sides() -> None:
    """
    GIVEN a stored match the provider later republishes with its two clubs the other way round
    WHEN that read is stored
    THEN both rows carry their new side, rather than the write failing on the side uniqueness
    """

    seed_fixture_ids()
    store_statistics([fixture_statistics(FIXTURE_PROVIDER_ID, BOTH_SIDES)])

    written_count = store_statistics(
        [fixture_statistics(FIXTURE_PROVIDER_ID, SWAPPED_SIDES)], LATER_SYNCHRONIZED_AT
    )

    assert written_count == len(SWAPPED_SIDES)

    assert stored_sides() == {
        performance_key(FIXTURE_PROVIDER_ID, LIVERPOOL.provider_id): MatchSide.AWAY,
        performance_key(FIXTURE_PROVIDER_ID, NOTTINGHAM_FOREST.provider_id): MatchSide.HOME,
    }


@pytest.mark.django_db
def test_upsert_statistics_leaves_the_rows_of_a_match_whose_sides_did_not_move() -> None:
    """
    GIVEN two stored matches of which only the first republishes its clubs the other way round
    WHEN that read is stored
    THEN the second match keeps its primary keys, so a swap clears only what it displaces
    """

    seed_fixture_ids(BOTH_FIXTURES)

    store_statistics(
        [
            fixture_statistics(FIXTURE_PROVIDER_ID, BOTH_SIDES),
            fixture_statistics(SECOND_FIXTURE_PROVIDER_ID, BOTH_SIDES),
        ]
    )

    untouched_before = {
        key: row for key, row in stored_rows().items() if key[0] == SECOND_FIXTURE_PROVIDER_ID
    }

    store_statistics(
        [
            fixture_statistics(FIXTURE_PROVIDER_ID, SWAPPED_SIDES),
            fixture_statistics(SECOND_FIXTURE_PROVIDER_ID, BOTH_SIDES),
        ],
        LATER_SYNCHRONIZED_AT,
    )

    untouched_after = {
        key: row for key, row in stored_rows().items() if key[0] == SECOND_FIXTURE_PROVIDER_ID
    }

    assert untouched_after == untouched_before


@pytest.mark.django_db
def test_upsert_statistics_splits_its_write_at_the_batch_size(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    GIVEN a batch of one row and a read carrying both sides of a match
    WHEN the read is stored
    THEN one insert is issued per row, so no chunk can grow into a single oversized statement
    """

    monkeypatch.setattr(repositories, "WRITE_BATCH_SIZE", SPLIT_BATCH_SIZE)

    seed_fixture_ids()

    with CaptureQueriesContext(connection) as statements:
        store_statistics([fixture_statistics(FIXTURE_PROVIDER_ID, BOTH_SIDES)])

    assert len(insert_statements(statements)) == len(BOTH_SIDES)


def test_the_batch_size_keeps_the_write_inside_the_placeholder_ceiling() -> None:
    """
    GIVEN the batch size the upsert writes under and the columns one of its rows places
    WHEN a full batch is priced in placeholders
    THEN it stays inside the ceiling the driver enforces
    """

    row_width = written_column_count(MatchTeamStatistic)

    assert repositories.WRITE_BATCH_SIZE * row_width <= PLACEHOLDER_CEILING


@pytest.mark.django_db
def test_upsert_statistics_rolls_its_write_back_when_the_reconciliation_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    GIVEN a reconciliation delete that fails after the figures of a read were written
    WHEN the read is stored
    THEN the failure surfaces and no row survives, so a reader never sees a half-refreshed match
    """

    seed_fixture_ids()

    fail_the_reconciliation(monkeypatch)

    with pytest.raises(OperationalError, match=RECONCILIATION_FAILURE):
        store_statistics([fixture_statistics(FIXTURE_PROVIDER_ID, BOTH_SIDES)])

    assert MatchTeamStatistic.objects.exists() is False
