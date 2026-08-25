from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta

import pytest
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from apps.predictions.domain.enums import (
    PredictionMarket,
    PredictionReliability,
    PredictionSelection,
)
from apps.predictions.models import FixturePrediction, LeagueMarketReliability
from apps.predictions.tasks import (
    RELIABILITY_LOCK_KEY,
    SYNCHRONIZATION_LOCK_KEY,
    synchronize_predictions,
    synchronize_reliability,
)
from integrations.sportmonks.exceptions import SportmonksError
from integrations.sportmonks.predictions import (
    ProviderPredictionWindow,
    ProviderReliability,
    ProviderReliabilityRead,
)
from tests.conftest import CapturedRecord
from tests.unit.fixtures.conftest import PREMIER_LEAGUE
from tests.unit.predictions.conftest import (
    FIXTURE_PROVIDER_ID,
    fixture_probabilities,
    prediction_window,
    probability,
    reliability,
    reliability_read,
    seed_fixtures,
    seed_leagues,
)

TODAY = date(2026, 8, 25)

NOW = datetime(2026, 8, 25, 6, 0, tzinfo=UTC)

LATER_NOW = NOW.replace(hour=18)

SUCCESSOR_LEASE = "a-later-run"

CACHE_UNREACHABLE = "The cache went away mid-run."

HOME_WIN = probability(PredictionMarket.FULLTIME_RESULT, PredictionSelection.HOME, "26.96")

DRAWN = probability(PredictionMarket.FULLTIME_RESULT, PredictionSelection.DRAW, "24.82")

PREMIER_FULLTIME = reliability(
    PREMIER_LEAGUE.provider_id,
    PredictionMarket.FULLTIME_RESULT,
    PredictionReliability.MEDIUM,
    "0.500",
)

RequestedWindow = tuple[date, date, Sequence[int]]


def freeze_now(monkeypatch: pytest.MonkeyPatch, instant: datetime = NOW) -> None:
    """
    Pin the clock the tasks read so the window and the stamp are deterministic.

    Parameters
    ----------
    monkeypatch : MonkeyPatch
        Patcher replacing ``django.utils.timezone.now`` for the test.
    instant : datetime
        Instant every call returns, which a second call may move so two runs of
        one test carry different stamps.
    """

    monkeypatch.setattr(timezone, "now", lambda: instant)


def record_prediction_read(
    monkeypatch: pytest.MonkeyPatch, window: ProviderPredictionWindow
) -> list[RequestedWindow]:
    """
    Replace the prediction call with one recording the window it was asked for.

    Parameters
    ----------
    monkeypatch : MonkeyPatch
        Patcher replacing the provider call the task imported.
    window : ProviderPredictionWindow
        Read the replacement yields.

    Returns
    -------
    list of RequestedWindow
        Requested windows, appended to on every call.
    """

    requested: list[RequestedWindow] = []

    def fetch(start: date, end: date, league_ids: Sequence[int]) -> ProviderPredictionWindow:
        requested.append((start, end, league_ids))

        return window

    monkeypatch.setattr("apps.predictions.tasks.fetch_prediction_window", fetch)

    return requested


def record_reliability_read(
    monkeypatch: pytest.MonkeyPatch, grades: Sequence[ProviderReliability]
) -> list[Sequence[int]]:
    """
    Replace the reliability call with one recording the leagues it was asked for.

    Parameters
    ----------
    monkeypatch : MonkeyPatch
        Patcher replacing the provider call the task imported.
    grades : Sequence of ProviderReliability
        Grades the replacement yields.

    Returns
    -------
    list of Sequence of int
        Requested competition identifiers, appended to on every call.
    """

    requested: list[Sequence[int]] = []

    def fetch(league_ids: Sequence[int]) -> ProviderReliabilityRead:
        requested.append(league_ids)

        return reliability_read(grades, league_ids)

    monkeypatch.setattr("apps.predictions.tasks.fetch_market_reliability", fetch)

    return requested


def forbid_prediction_call(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Replace the prediction call with one that fails the test if it is reached.

    Parameters
    ----------
    monkeypatch : MonkeyPatch
        Patcher replacing the provider call the task imported.
    """

    def fetch(start: date, end: date, league_ids: Sequence[int]) -> ProviderPredictionWindow:
        message = f"The provider was called for {start} to {end} with {list(league_ids)}."

        raise AssertionError(message)

    monkeypatch.setattr("apps.predictions.tasks.fetch_prediction_window", fetch)


def forbid_reliability_call(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Replace the reliability call with one that fails the test if it is reached.

    Parameters
    ----------
    monkeypatch : MonkeyPatch
        Patcher replacing the provider call the task imported.
    """

    def fetch(league_ids: Sequence[int]) -> ProviderReliabilityRead:
        message = f"The provider was called for {list(league_ids)}."

        raise AssertionError(message)

    monkeypatch.setattr("apps.predictions.tasks.fetch_market_reliability", fetch)


def fail_prediction_call(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Replace the prediction call with one that refuses the read.

    Parameters
    ----------
    monkeypatch : MonkeyPatch
        Patcher replacing the provider call the task imported.
    """

    def fetch(start: date, end: date, league_ids: Sequence[int]) -> ProviderPredictionWindow:
        message = f"The provider refused {start} to {end} for {list(league_ids)}."

        raise SportmonksError(message)

    monkeypatch.setattr("apps.predictions.tasks.fetch_prediction_window", fetch)


def fail_reliability_call(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Replace the reliability call with one that refuses the read.

    Parameters
    ----------
    monkeypatch : MonkeyPatch
        Patcher replacing the provider call the task imported.
    """

    def fetch(league_ids: Sequence[int]) -> ProviderReliabilityRead:
        message = f"The provider refused the grades of {list(league_ids)}."

        raise SportmonksError(message)

    monkeypatch.setattr("apps.predictions.tasks.fetch_market_reliability", fetch)


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
    Make reading a lock back fail, as a cache restarted mid-run does.

    Parameters
    ----------
    monkeypatch : MonkeyPatch
        Patcher replacing the cache read the lock release performs.
    """

    def get(*_args: object, **_kwargs: object) -> object:
        raise ConnectionError(CACHE_UNREACHABLE)

    monkeypatch.setattr(cache, "get", get)


@pytest.mark.django_db
def test_synchronize_predictions_writes_the_fixture_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    GIVEN a provider yielding two probabilities for a stored fixture
    WHEN the synchronization runs
    THEN both rows are written and the fixture window was the one requested
    """

    freeze_now(monkeypatch)
    seed_fixtures()

    published = [HOME_WIN, DRAWN]

    read = prediction_window([fixture_probabilities(FIXTURE_PROVIDER_ID, published)])

    requested = record_prediction_read(monkeypatch, read)

    written_count = synchronize_predictions()

    assert written_count == len(published)
    assert FixturePrediction.objects.count() == len(published)

    assert requested == [
        (
            TODAY - timedelta(days=settings.FIXTURE_SYNCHRONIZATION_PAST_DAYS),
            TODAY + timedelta(days=settings.FIXTURE_SYNCHRONIZATION_FUTURE_DAYS),
            settings.SPORTMONKS_LEAGUE_IDS,
        )
    ]


@pytest.mark.django_db
def test_synchronize_predictions_stamps_every_row_it_wrote(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    GIVEN a provider yielding one probability and a pinned clock
    WHEN the synchronization runs
    THEN the stored row carries the instant of the run
    """

    freeze_now(monkeypatch)
    seed_fixtures()

    record_prediction_read(
        monkeypatch, prediction_window([fixture_probabilities(FIXTURE_PROVIDER_ID, [HOME_WIN])])
    )

    synchronize_predictions()

    assert FixturePrediction.objects.get().synchronized_at == NOW


@pytest.mark.django_db
def test_synchronize_predictions_releases_the_lock_after_a_successful_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    GIVEN a synchronization that completed without failing
    WHEN the lock is inspected afterwards
    THEN it is no longer held, so the next scheduled run may proceed
    """

    freeze_now(monkeypatch)
    seed_fixtures()

    record_prediction_read(
        monkeypatch, prediction_window([fixture_probabilities(FIXTURE_PROVIDER_ID, [HOME_WIN])])
    )

    synchronize_predictions()

    assert cache.get(SYNCHRONIZATION_LOCK_KEY) is None


@pytest.mark.django_db
def test_synchronize_predictions_writes_nothing_while_another_run_holds_the_lock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    GIVEN a concurrent run already holding the prediction lock
    WHEN a second synchronization starts
    THEN it reports no row, writes nothing, and never reaches the provider
    """

    freeze_now(monkeypatch)
    forbid_prediction_call(monkeypatch)
    seed_fixtures()

    assert cache.add(SYNCHRONIZATION_LOCK_KEY, SUCCESSOR_LEASE, timeout=60)

    written_count = synchronize_predictions()

    assert written_count == 0
    assert FixturePrediction.objects.exists() is False
    assert cache.get(SYNCHRONIZATION_LOCK_KEY) == SUCCESSOR_LEASE


@pytest.mark.django_db
def test_synchronize_predictions_leaves_a_successor_lease_alone_after_losing_its_own(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    GIVEN a run whose lease expires mid-read and is taken by a later run
    WHEN the first run reaches its release
    THEN the later run keeps the lock, so no third run walks in behind it
    """

    freeze_now(monkeypatch)
    seed_fixtures()

    def fetch(_start: date, _end: date, _league_ids: Sequence[int]) -> ProviderPredictionWindow:
        cache.delete(SYNCHRONIZATION_LOCK_KEY)

        assert cache.add(SYNCHRONIZATION_LOCK_KEY, SUCCESSOR_LEASE, timeout=60)

        return prediction_window([fixture_probabilities(FIXTURE_PROVIDER_ID, [HOME_WIN])])

    monkeypatch.setattr("apps.predictions.tasks.fetch_prediction_window", fetch)

    written_count = synchronize_predictions()

    assert written_count == 1
    assert cache.get(SYNCHRONIZATION_LOCK_KEY) == SUCCESSOR_LEASE


@pytest.mark.django_db
def test_synchronize_predictions_reraises_a_provider_failure_and_frees_the_lock(
    monkeypatch: pytest.MonkeyPatch, loguru_records: list[CapturedRecord]
) -> None:
    """
    GIVEN a provider that refuses the prediction read
    WHEN the synchronization runs
    THEN the failure surfaces with its traceback, nothing is written, and the lock is released
    """

    freeze_now(monkeypatch)
    fail_prediction_call(monkeypatch)
    seed_fixtures()

    with pytest.raises(SportmonksError):
        synchronize_predictions()

    assert FixturePrediction.objects.exists() is False
    assert cache.get(SYNCHRONIZATION_LOCK_KEY) is None
    assert traceback_flags(loguru_records, "ERROR") == [True]


@pytest.mark.django_db
def test_synchronize_reliability_writes_the_grades_of_the_subscribed_leagues(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    GIVEN a provider grading one market of a stored competition
    WHEN the reliability synchronization runs
    THEN the row is written, stamped with the run, and the subscribed leagues were requested
    """

    freeze_now(monkeypatch)
    seed_leagues()

    requested = record_reliability_read(monkeypatch, [PREMIER_FULLTIME])

    written_count = synchronize_reliability()

    assert written_count == 1
    assert requested == [settings.SPORTMONKS_LEAGUE_IDS]

    stored = LeagueMarketReliability.objects.get()

    assert (stored.quality, stored.synchronized_at) == (PREMIER_FULLTIME.quality, NOW)


@pytest.mark.django_db
def test_synchronize_reliability_releases_the_lock_after_a_successful_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    GIVEN a reliability synchronization that completed without failing
    WHEN the lock is inspected afterwards
    THEN it is no longer held, so the next nightly run may proceed
    """

    freeze_now(monkeypatch)
    seed_leagues()
    record_reliability_read(monkeypatch, [PREMIER_FULLTIME])

    synchronize_reliability()

    assert cache.get(RELIABILITY_LOCK_KEY) is None


@pytest.mark.django_db
def test_synchronize_reliability_writes_nothing_while_another_run_holds_the_lock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    GIVEN a concurrent run already holding the reliability lock
    WHEN a second reliability synchronization starts
    THEN it reports no row, writes nothing, and never reaches the provider
    """

    freeze_now(monkeypatch)
    forbid_reliability_call(monkeypatch)
    seed_leagues()

    assert cache.add(RELIABILITY_LOCK_KEY, SUCCESSOR_LEASE, timeout=60)

    written_count = synchronize_reliability()

    assert written_count == 0
    assert LeagueMarketReliability.objects.exists() is False
    assert cache.get(RELIABILITY_LOCK_KEY) == SUCCESSOR_LEASE


@pytest.mark.django_db
def test_synchronize_reliability_reraises_a_provider_failure_and_frees_the_lock(
    monkeypatch: pytest.MonkeyPatch, loguru_records: list[CapturedRecord]
) -> None:
    """
    GIVEN a provider that refuses the reliability read
    WHEN the reliability synchronization runs
    THEN the failure surfaces with its traceback, nothing is written, and the lock is released
    """

    freeze_now(monkeypatch)
    fail_reliability_call(monkeypatch)
    seed_leagues()

    with pytest.raises(SportmonksError):
        synchronize_reliability()

    assert LeagueMarketReliability.objects.exists() is False
    assert cache.get(RELIABILITY_LOCK_KEY) is None
    assert traceback_flags(loguru_records, "ERROR") == [True]


@pytest.mark.django_db
def test_the_two_synchronizations_do_not_share_a_lock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    GIVEN a prediction run already holding the prediction lock
    WHEN the reliability synchronization starts
    THEN it writes its grades, because the two runs hold two different keys
    """

    freeze_now(monkeypatch)
    seed_leagues()
    record_reliability_read(monkeypatch, [PREMIER_FULLTIME])

    assert cache.add(SYNCHRONIZATION_LOCK_KEY, SUCCESSOR_LEASE, timeout=60)

    written_count = synchronize_reliability()

    assert written_count == 1
    assert cache.get(SYNCHRONIZATION_LOCK_KEY) == SUCCESSOR_LEASE


@pytest.mark.django_db
def test_synchronize_predictions_keeps_the_provider_failure_when_the_lock_cannot_be_freed(
    monkeypatch: pytest.MonkeyPatch, loguru_records: list[CapturedRecord]
) -> None:
    """
    GIVEN a provider refusing the read and a cache that cannot be read back to free the lock
    WHEN the synchronization runs
    THEN the provider failure surfaces and the lock left to expire is reported as a warning
    """

    freeze_now(monkeypatch)
    fail_prediction_call(monkeypatch)
    seed_fixtures()
    break_the_cache_read(monkeypatch)

    with pytest.raises(SportmonksError):
        synchronize_predictions()

    assert traceback_flags(loguru_records, "ERROR") == [True]
    assert traceback_flags(loguru_records, "WARNING") == [True]


@pytest.mark.django_db
def test_synchronize_reliability_clears_the_grades_of_a_competition_it_graded_in_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    GIVEN a stored grade and a provider that grades nothing at all on the following run
    WHEN the reliability synchronization runs again
    THEN the stale grade is gone, because the read covered the competition it graded in nothing
    """

    freeze_now(monkeypatch)
    seed_leagues()
    record_reliability_read(monkeypatch, [PREMIER_FULLTIME])

    synchronize_reliability()

    freeze_now(monkeypatch, LATER_NOW)
    record_reliability_read(monkeypatch, [])

    written_count = synchronize_reliability()

    assert written_count == 0
    assert LeagueMarketReliability.objects.exists() is False
