from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta

import pytest
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from apps.fixtures.domain.enums import FixtureStatus
from apps.fixtures.models import Fixture
from apps.statistics.domain.enums import MatchSide
from apps.statistics.models import MatchTeamStatistic
from apps.statistics.tasks import (
    MAXIMUM_PAST_DAYS,
    SYNCHRONIZATION_LOCK_KEY,
    synchronize_statistics,
)
from integrations.sportmonks.exceptions import SportmonksError
from integrations.sportmonks.fixtures import ProviderFixture, ProviderWindow
from integrations.sportmonks.statistics import (
    ProviderFixtureStatistics,
    ProviderStatisticsWindow,
)
from tests.conftest import CapturedRecord
from tests.unit.fixtures.conftest import (
    LIVERPOOL,
    NOTTINGHAM_FOREST,
    kickoff,
    provider_fixture,
    provider_window,
)
from tests.unit.statistics.conftest import (
    FIXTURE_PROVIDER_ID,
    fixture_statistics,
    statistics_window,
    team_statistics,
)

TODAY = date(2026, 8, 25)

NOW = datetime(2026, 8, 25, 6, 0, tzinfo=UTC)

MATCH_DAY = date(2026, 8, 22)

SUCCESSOR_LEASE = "a-later-run"

CACHE_UNREACHABLE = "The cache went away mid-run."

FIXTURE_CALL = "fixtures"

STATISTICS_CALL = "statistics"

# Five days back from today at the thirty-day chunk size, which is one chunk.
DEFAULT_CHUNKS = [(date(2026, 8, 20), TODAY)]

BACKFILL_DAYS = 75

# Seventy-five days back from today cut into thirty-day pieces, the last of
# which is short because the range ends today rather than on a chunk boundary.
BACKFILL_CHUNKS = [
    (date(2026, 6, 11), date(2026, 7, 10)),
    (date(2026, 7, 11), date(2026, 8, 9)),
    (date(2026, 8, 10), TODAY),
]

SETTLED_CHUNKS_BEFORE_FAILURE = 1

MATCH = provider_fixture(
    FIXTURE_PROVIDER_ID,
    kickoff(12, day=MATCH_DAY),
    status=FixtureStatus.FINISHED,
    home_goals=2,
    away_goals=1,
)

BOTH_SIDES = [
    team_statistics(LIVERPOOL.provider_id, MatchSide.HOME),
    team_statistics(NOTTINGHAM_FOREST.provider_id, MatchSide.AWAY, possession=46),
]

READ_STATISTICS = [fixture_statistics(FIXTURE_PROVIDER_ID, BOTH_SIDES)]

ProviderCall = tuple[str, date, date, Sequence[int]]


def freeze_now(monkeypatch: pytest.MonkeyPatch, instant: datetime = NOW) -> None:
    """
    Pin the clock the task reads so the range and the stamp are deterministic.

    Parameters
    ----------
    monkeypatch : MonkeyPatch
        Patcher replacing ``django.utils.timezone.now`` for the test.
    instant : datetime
        Instant every call returns.
    """

    monkeypatch.setattr(timezone, "now", lambda: instant)


def record_provider_calls(
    monkeypatch: pytest.MonkeyPatch,
    provider_fixtures: Sequence[ProviderFixture] = (),
    entries: Sequence[ProviderFixtureStatistics] = (),
) -> list[ProviderCall]:
    """
    Replace both provider calls with ones recording what they were asked for.

    Both are recorded into a single list, so the order the task performs them in
    is part of what a test can assert: a chunk must bring its fixture parents
    before its statistics, or a historical range writes nothing.

    Parameters
    ----------
    monkeypatch : MonkeyPatch
        Patcher replacing the two provider calls the task imported.
    provider_fixtures : Sequence of ProviderFixture
        Matches the fixture read yields for every chunk.
    entries : Sequence of ProviderFixtureStatistics
        Performances the statistics read yields for every chunk.

    Returns
    -------
    list of ProviderCall
        Which call was made, the range it covered, and the competitions it
        asked for, in the order the task issued them.
    """

    calls: list[ProviderCall] = []

    def fetch_fixtures(start: date, end: date, league_ids: Sequence[int]) -> ProviderWindow:
        calls.append((FIXTURE_CALL, start, end, league_ids))

        return provider_window(provider_fixtures)

    def fetch_statistics(
        start: date, end: date, league_ids: Sequence[int]
    ) -> ProviderStatisticsWindow:
        calls.append((STATISTICS_CALL, start, end, league_ids))

        return statistics_window(entries)

    monkeypatch.setattr("apps.statistics.tasks.fetch_fixtures_between", fetch_fixtures)
    monkeypatch.setattr("apps.statistics.tasks.fetch_match_statistics", fetch_statistics)

    return calls


def forbid_provider_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Replace both provider calls with ones that fail the test if they are reached.

    Parameters
    ----------
    monkeypatch : MonkeyPatch
        Patcher replacing the two provider calls the task imported.
    """

    def fetch(start: date, end: date, league_ids: Sequence[int]) -> ProviderWindow:
        message = f"The provider was called for {start} to {end} with {list(league_ids)}."

        raise AssertionError(message)

    monkeypatch.setattr("apps.statistics.tasks.fetch_fixtures_between", fetch)
    monkeypatch.setattr("apps.statistics.tasks.fetch_match_statistics", fetch)


def fail_the_fixture_call(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Replace the fixture call of a chunk with one that refuses the read.

    Parameters
    ----------
    monkeypatch : MonkeyPatch
        Patcher replacing the provider calls the task imported.
    """

    record_provider_calls(monkeypatch, [MATCH], READ_STATISTICS)

    def fetch(start: date, end: date, league_ids: Sequence[int]) -> ProviderWindow:
        message = f"The provider refused the fixtures of {start} to {end} for {list(league_ids)}."

        raise SportmonksError(message)

    monkeypatch.setattr("apps.statistics.tasks.fetch_fixtures_between", fetch)


def fail_the_statistics_call(
    monkeypatch: pytest.MonkeyPatch, settled_chunks: int = 0
) -> list[ProviderCall]:
    """
    Replace the statistics call with one refusing the read after some chunks.

    Parameters
    ----------
    monkeypatch : MonkeyPatch
        Patcher replacing the two provider calls the task imported.
    settled_chunks : int
        Chunks the replacement serves before refusing, so a test can watch a
        backfill fail part-way and keep what the chunks before it wrote.

    Returns
    -------
    list of ProviderCall
        Calls recorded up to and including the refused one.
    """

    calls = record_provider_calls(monkeypatch, [MATCH], READ_STATISTICS)

    served = statistics_window(READ_STATISTICS)

    def fetch(start: date, end: date, league_ids: Sequence[int]) -> ProviderStatisticsWindow:
        calls.append((STATISTICS_CALL, start, end, league_ids))

        if len([call for call in calls if call[0] == STATISTICS_CALL]) <= settled_chunks:
            return served

        message = f"The provider refused the statistics of {start} to {end}."

        raise SportmonksError(message)

    monkeypatch.setattr("apps.statistics.tasks.fetch_match_statistics", fetch)

    return calls


def traceback_flags(records: list[CapturedRecord], level: str) -> list[bool]:
    """
    Return whether a traceback was attached to each record of one level.

    Parameters
    ----------
    records : list of CapturedRecord
        Records the Loguru sink collected during the test.
    level : str
        Level to narrow the records to.

    Returns
    -------
    list of bool
        One entry per record of that level, in emission order.
    """

    return [
        carries_exception
        for record_level, _message, carries_exception in records
        if record_level == level
    ]


def break_the_cache_read(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Make reading the lock back fail, as a cache restarted mid-run does.

    Parameters
    ----------
    monkeypatch : MonkeyPatch
        Patcher replacing the cache read the lock release performs.
    """

    def get(*_args: object, **_kwargs: object) -> object:
        raise ConnectionError(CACHE_UNREACHABLE)

    monkeypatch.setattr(cache, "get", get)


def expected_calls(chunks: Sequence[tuple[date, date]]) -> list[ProviderCall]:
    """
    Return the calls a run over the given chunks is expected to issue.

    Parameters
    ----------
    chunks : Sequence of tuple of date
        First and last day of each chunk, in the order the run walks them.

    Returns
    -------
    list of ProviderCall
        Fixture read followed by statistics read for each chunk, over the
        subscribed competitions.
    """

    return [
        (call, chunk_start, chunk_end, settings.SPORTMONKS_LEAGUE_IDS)
        for chunk_start, chunk_end in chunks
        for call in (FIXTURE_CALL, STATISTICS_CALL)
    ]


@pytest.mark.django_db
def test_synchronize_statistics_writes_the_default_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    GIVEN a provider publishing both sides of one finished match
    WHEN the scheduled synchronization runs
    THEN both rows are written and the default range was read as a single chunk
    """

    freeze_now(monkeypatch)

    calls = record_provider_calls(monkeypatch, [MATCH], READ_STATISTICS)

    written_count = synchronize_statistics()

    assert written_count == len(BOTH_SIDES)
    assert MatchTeamStatistic.objects.count() == len(BOTH_SIDES)
    assert calls == expected_calls(DEFAULT_CHUNKS)


@pytest.mark.django_db
def test_synchronize_statistics_brings_the_fixture_parents_of_a_chunk_first(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    GIVEN an empty database, as a historical chunk beyond the fixture window finds
    WHEN the synchronization runs
    THEN the match is stored by the chunk's own fixture read and its statistics land
    """

    freeze_now(monkeypatch)

    calls = record_provider_calls(monkeypatch, [MATCH], READ_STATISTICS)

    synchronize_statistics()

    assert Fixture.objects.count() == 1
    assert MatchTeamStatistic.objects.count() == len(BOTH_SIDES)
    assert [call for call, _start, _end, _leagues in calls] == [FIXTURE_CALL, STATISTICS_CALL]


@pytest.mark.django_db
def test_synchronize_statistics_stamps_every_row_it_wrote(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    GIVEN a provider publishing one match and a pinned clock
    WHEN the synchronization runs
    THEN every stored row carries the instant of the run
    """

    freeze_now(monkeypatch)
    record_provider_calls(monkeypatch, [MATCH], READ_STATISTICS)

    synchronize_statistics()

    assert {row.synchronized_at for row in MatchTeamStatistic.objects.all()} == {NOW}


@pytest.mark.django_db
def test_synchronize_statistics_releases_the_lock_after_a_successful_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    GIVEN a synchronization that completed without failing
    WHEN the lock is inspected afterwards
    THEN it is no longer held, so the next scheduled run may proceed
    """

    freeze_now(monkeypatch)
    record_provider_calls(monkeypatch, [MATCH], READ_STATISTICS)

    synchronize_statistics()

    assert cache.get(SYNCHRONIZATION_LOCK_KEY) is None


@pytest.mark.django_db
def test_synchronize_statistics_writes_nothing_while_another_run_holds_the_lock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    GIVEN a concurrent run already holding the statistics lock
    WHEN a second synchronization starts
    THEN it reports no row, writes nothing, and never reaches the provider
    """

    freeze_now(monkeypatch)
    forbid_provider_calls(monkeypatch)

    assert cache.add(SYNCHRONIZATION_LOCK_KEY, SUCCESSOR_LEASE, timeout=60)

    written_count = synchronize_statistics()

    assert written_count == 0
    assert MatchTeamStatistic.objects.exists() is False
    assert Fixture.objects.exists() is False
    assert cache.get(SYNCHRONIZATION_LOCK_KEY) == SUCCESSOR_LEASE


@pytest.mark.django_db
def test_synchronize_statistics_leaves_a_successor_lease_alone_after_losing_its_own(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    GIVEN a run whose lease expires mid-read and is taken by a later run
    WHEN the first run reaches its release
    THEN the later run keeps the lock, so no third run walks in behind it
    """

    freeze_now(monkeypatch)
    record_provider_calls(monkeypatch, [MATCH], READ_STATISTICS)

    def fetch(_start: date, _end: date, _league_ids: Sequence[int]) -> ProviderStatisticsWindow:
        cache.delete(SYNCHRONIZATION_LOCK_KEY)

        assert cache.add(SYNCHRONIZATION_LOCK_KEY, SUCCESSOR_LEASE, timeout=60)

        return statistics_window(READ_STATISTICS)

    monkeypatch.setattr("apps.statistics.tasks.fetch_match_statistics", fetch)

    written_count = synchronize_statistics()

    assert written_count == len(BOTH_SIDES)
    assert cache.get(SYNCHRONIZATION_LOCK_KEY) == SUCCESSOR_LEASE


@pytest.mark.django_db
def test_synchronize_statistics_reraises_a_statistics_failure_and_frees_the_lock(
    monkeypatch: pytest.MonkeyPatch, loguru_records: list[CapturedRecord]
) -> None:
    """
    GIVEN a provider that refuses the statistics read of the only chunk
    WHEN the synchronization runs
    THEN the failure surfaces with its traceback, no statistic row is written, and the lock frees
    """

    freeze_now(monkeypatch)
    fail_the_statistics_call(monkeypatch)

    with pytest.raises(SportmonksError):
        synchronize_statistics()

    assert MatchTeamStatistic.objects.exists() is False
    assert Fixture.objects.count() == 1
    assert cache.get(SYNCHRONIZATION_LOCK_KEY) is None
    assert traceback_flags(loguru_records, "ERROR") == [True]


@pytest.mark.django_db
def test_synchronize_statistics_writes_nothing_for_a_chunk_whose_fixtures_it_cannot_read(
    monkeypatch: pytest.MonkeyPatch, loguru_records: list[CapturedRecord]
) -> None:
    """
    GIVEN a provider that refuses the fixture read a chunk starts with
    WHEN the synchronization runs
    THEN the failure surfaces, and neither a match nor a statistic row is stored
    """

    freeze_now(monkeypatch)
    fail_the_fixture_call(monkeypatch)

    with pytest.raises(SportmonksError):
        synchronize_statistics()

    assert Fixture.objects.exists() is False
    assert MatchTeamStatistic.objects.exists() is False
    assert traceback_flags(loguru_records, "ERROR") == [True]


@pytest.mark.django_db
def test_synchronize_statistics_keeps_the_provider_failure_when_the_lock_cannot_be_freed(
    monkeypatch: pytest.MonkeyPatch, loguru_records: list[CapturedRecord]
) -> None:
    """
    GIVEN a provider refusing the read and a cache that cannot be read back to free the lock
    WHEN the synchronization runs
    THEN the provider failure surfaces and the lock left to expire is reported as a warning
    """

    freeze_now(monkeypatch)
    fail_the_statistics_call(monkeypatch)
    break_the_cache_read(monkeypatch)

    with pytest.raises(SportmonksError):
        synchronize_statistics()

    assert traceback_flags(loguru_records, "ERROR") == [True]
    assert traceback_flags(loguru_records, "WARNING") == [True]


@pytest.mark.django_db
def test_synchronize_statistics_walks_a_backfill_in_consecutive_chunks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    GIVEN an operator asking for seventy-five days of history
    WHEN the synchronization runs
    THEN it reads three inclusive non-overlapping chunks, fixtures first in each
    """

    freeze_now(monkeypatch)

    calls = record_provider_calls(monkeypatch, [MATCH])

    synchronize_statistics(BACKFILL_DAYS)

    assert calls == expected_calls(BACKFILL_CHUNKS)


@pytest.mark.django_db
def test_synchronize_statistics_totals_the_rows_of_every_chunk_of_a_backfill(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    GIVEN a backfill of three chunks whose statistics read yields two rows each time
    WHEN the synchronization runs
    THEN it reports the rows of every chunk while the table holds the distinct ones
    """

    freeze_now(monkeypatch)
    record_provider_calls(monkeypatch, [MATCH], READ_STATISTICS)

    written_count = synchronize_statistics(BACKFILL_DAYS)

    assert written_count == len(BOTH_SIDES) * len(BACKFILL_CHUNKS)
    assert MatchTeamStatistic.objects.count() == len(BOTH_SIDES)


@pytest.mark.django_db
def test_synchronize_statistics_keeps_the_chunks_settled_before_a_failing_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    GIVEN a backfill whose provider refuses the statistics of its second chunk
    WHEN the synchronization runs
    THEN the failure surfaces and the rows the first chunk wrote survive it
    """

    freeze_now(monkeypatch)

    calls = fail_the_statistics_call(monkeypatch, SETTLED_CHUNKS_BEFORE_FAILURE)

    with pytest.raises(SportmonksError):
        synchronize_statistics(BACKFILL_DAYS)

    assert MatchTeamStatistic.objects.count() == len(BOTH_SIDES)

    assert [call for call, _start, _end, _leagues in calls].count(STATISTICS_CALL) == (
        SETTLED_CHUNKS_BEFORE_FAILURE + 1
    )


@pytest.mark.django_db
def test_synchronize_statistics_refuses_a_days_back_of_nought(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    GIVEN an operator invoking the task with no days of history at all
    WHEN the synchronization runs
    THEN it refuses before acquiring the lock, so the scheduled run is not displaced
    """

    freeze_now(monkeypatch)
    forbid_provider_calls(monkeypatch)

    with pytest.raises(ValueError, match=f"between 1 and {MAXIMUM_PAST_DAYS}"):
        synchronize_statistics(0)

    assert cache.get(SYNCHRONIZATION_LOCK_KEY) is None


@pytest.mark.django_db
def test_synchronize_statistics_refuses_an_absurd_days_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    GIVEN an operator invoking the task one day beyond the history it allows
    WHEN the synchronization runs
    THEN it refuses before acquiring the lock, rather than spending the provider budget
    """

    freeze_now(monkeypatch)
    forbid_provider_calls(monkeypatch)

    with pytest.raises(ValueError, match=f"between 1 and {MAXIMUM_PAST_DAYS}"):
        synchronize_statistics(MAXIMUM_PAST_DAYS + 1)

    assert cache.get(SYNCHRONIZATION_LOCK_KEY) is None


@pytest.mark.django_db
def test_synchronize_statistics_accepts_the_widest_history_it_allows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    GIVEN an operator invoking the task with exactly the widest history it allows
    WHEN the synchronization runs
    THEN it is accepted, because the bound is inclusive, and the lock is released
    """

    freeze_now(monkeypatch)

    calls = record_provider_calls(monkeypatch, [MATCH])

    synchronize_statistics(MAXIMUM_PAST_DAYS)

    walked_range = (calls[0][1], calls[-1][2])

    assert walked_range == (TODAY - timedelta(days=MAXIMUM_PAST_DAYS), TODAY)
    assert cache.get(SYNCHRONIZATION_LOCK_KEY) is None
