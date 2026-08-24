from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta

import pytest
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from apps.fixtures.models import Fixture
from apps.fixtures.tasks import SYNCHRONIZATION_LOCK_KEY, synchronize_fixtures
from integrations.sportmonks.exceptions import SportmonksError
from integrations.sportmonks.fixtures import ProviderFixture
from tests.unit.fixtures.conftest import (
    BARCELONA,
    LA_LIGA,
    SEVILLA,
    kickoff,
    provider_fixture,
)

TODAY = date(2026, 8, 25)

NOW = datetime(2026, 8, 25, 6, 0, tzinfo=UTC)

RequestedWindow = tuple[date, date, Sequence[int]]


def freeze_now(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Pin the clock the task reads so the requested window is deterministic.

    Parameters
    ----------
    monkeypatch : MonkeyPatch
        Patcher replacing ``django.utils.timezone.now`` for the test.
    """

    monkeypatch.setattr(timezone, "now", lambda: NOW)


def record_window(
    monkeypatch: pytest.MonkeyPatch, provider_fixtures: Sequence[ProviderFixture]
) -> list[RequestedWindow]:
    """
    Replace the provider call with one recording the window it was asked for.

    Parameters
    ----------
    monkeypatch : MonkeyPatch
        Patcher replacing the provider call the task imported.
    provider_fixtures : Sequence of ProviderFixture
        Fixtures the replacement yields.

    Returns
    -------
    list of RequestedWindow
        Requested windows, appended to on every call.
    """

    requested: list[RequestedWindow] = []

    def fetch(start: date, end: date, league_ids: Sequence[int]) -> list[ProviderFixture]:
        requested.append((start, end, league_ids))

        return list(provider_fixtures)

    monkeypatch.setattr("apps.fixtures.tasks.fetch_fixtures_between", fetch)

    return requested


def forbid_provider_call(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Replace the provider call with one that fails the test if it is reached.

    Parameters
    ----------
    monkeypatch : MonkeyPatch
        Patcher replacing the provider call the task imported.
    """

    def fetch(start: date, end: date, league_ids: Sequence[int]) -> list[ProviderFixture]:
        message = f"The provider was called for {start} to {end} with {list(league_ids)}."

        raise AssertionError(message)

    monkeypatch.setattr("apps.fixtures.tasks.fetch_fixtures_between", fetch)


@pytest.mark.django_db
def test_synchronize_fixtures_writes_the_configured_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    GIVEN a provider yielding two fixtures and no run holding the lock
    WHEN the synchronization runs
    THEN both fixtures are stored and the configured window was requested
    """

    freeze_now(monkeypatch)

    window = [
        provider_fixture(1, kickoff(11, 30)),
        provider_fixture(2, kickoff(14), league=LA_LIGA, home_team=BARCELONA, away_team=SEVILLA),
    ]

    requested = record_window(monkeypatch, window)

    written_count = synchronize_fixtures()

    assert written_count == len(window)
    assert Fixture.objects.count() == len(window)

    assert requested == [
        (
            TODAY - timedelta(days=settings.FIXTURE_SYNCHRONIZATION_PAST_DAYS),
            TODAY + timedelta(days=settings.FIXTURE_SYNCHRONIZATION_FUTURE_DAYS),
            settings.SPORTMONKS_LEAGUE_IDS,
        )
    ]


@pytest.mark.django_db
def test_synchronize_fixtures_stamps_every_fixture_it_wrote(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    GIVEN a provider yielding one fixture and a pinned clock
    WHEN the synchronization runs
    THEN the stored fixture carries the instant of the run
    """

    freeze_now(monkeypatch)
    record_window(monkeypatch, [provider_fixture(1, kickoff(11, 30))])

    synchronize_fixtures()

    assert Fixture.objects.get().synchronized_at == NOW


@pytest.mark.django_db
def test_synchronize_fixtures_releases_the_lock_after_a_successful_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    GIVEN a synchronization that completed without failing
    WHEN the lock is inspected afterwards
    THEN it is no longer held, so the next scheduled run may proceed
    """

    freeze_now(monkeypatch)
    record_window(monkeypatch, [provider_fixture(1, kickoff(11, 30))])

    synchronize_fixtures()

    assert cache.get(SYNCHRONIZATION_LOCK_KEY) is None


@pytest.mark.django_db
def test_synchronize_fixtures_writes_nothing_while_another_run_holds_the_lock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    GIVEN a concurrent run already holding the synchronization lock
    WHEN a second synchronization starts
    THEN it reports no fixture, writes nothing, and never reaches the provider
    """

    freeze_now(monkeypatch)
    forbid_provider_call(monkeypatch)

    assert cache.add(SYNCHRONIZATION_LOCK_KEY, True, timeout=60)

    written_count = synchronize_fixtures()

    assert written_count == 0
    assert Fixture.objects.count() == 0
    assert cache.get(SYNCHRONIZATION_LOCK_KEY) is True


@pytest.mark.django_db
def test_synchronize_fixtures_reraises_a_provider_failure_and_frees_the_lock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    GIVEN a provider that fails partway through the window
    WHEN the synchronization runs
    THEN the failure surfaces, nothing is stored, and the lock is released
    """

    freeze_now(monkeypatch)

    def fetch(start: date, end: date, league_ids: Sequence[int]) -> list[ProviderFixture]:
        message = f"The provider refused {start} to {end} for {list(league_ids)}."

        raise SportmonksError(message)

    monkeypatch.setattr("apps.fixtures.tasks.fetch_fixtures_between", fetch)

    with pytest.raises(SportmonksError):
        synchronize_fixtures()

    assert Fixture.objects.count() == 0
    assert cache.get(SYNCHRONIZATION_LOCK_KEY) is None
