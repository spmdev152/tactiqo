from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta

import pytest
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from apps.fixtures.models import Fixture
from apps.fixtures.tasks import SYNCHRONIZATION_LOCK_KEY, synchronize_fixtures
from integrations.sportmonks.exceptions import SportmonksError
from integrations.sportmonks.fixtures import ProviderFixture, ProviderWindow
from tests.unit.fixtures.conftest import (
    BARCELONA,
    LA_LIGA,
    SEVILLA,
    kickoff,
    provider_fixture,
    provider_window,
)

TODAY = date(2026, 8, 25)

NOW = datetime(2026, 8, 25, 6, 0, tzinfo=UTC)

SUCCESSOR_LEASE = "a-later-run"

FIRST_PAGE_FIXTURE = provider_fixture(1, kickoff(11, 30))

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


def record_window(monkeypatch: pytest.MonkeyPatch, window: ProviderWindow) -> list[RequestedWindow]:
    """
    Replace the provider call with one recording the window it was asked for.

    Parameters
    ----------
    monkeypatch : MonkeyPatch
        Patcher replacing the provider call the task imported.
    window : ProviderWindow
        Window the replacement yields.

    Returns
    -------
    list of RequestedWindow
        Requested windows, appended to on every call.
    """

    requested: list[RequestedWindow] = []

    def fetch(start: date, end: date, league_ids: Sequence[int]) -> ProviderWindow:
        requested.append((start, end, league_ids))

        return window

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

    def fetch(start: date, end: date, league_ids: Sequence[int]) -> ProviderWindow:
        message = f"The provider was called for {start} to {end} with {list(league_ids)}."

        raise AssertionError(message)

    monkeypatch.setattr("apps.fixtures.tasks.fetch_fixtures_between", fetch)


def fail_after_one_page(monkeypatch: pytest.MonkeyPatch) -> list[ProviderFixture]:
    """
    Replace the provider call with one that reads a page and then gives up.

    The boundary materializes a whole window before returning it, so a failure
    on a later page discards whatever the earlier pages produced rather than
    handing the task a prefix. The returned list is what the replacement had
    normalized when it raised, which is what a test asserting that nothing
    reached the database compares its emptiness against.

    Parameters
    ----------
    monkeypatch : MonkeyPatch
        Patcher replacing the provider call the task imported.

    Returns
    -------
    list of ProviderFixture
        Fixtures the replacement read before failing, appended to as it reads.
    """

    read_fixtures: list[ProviderFixture] = []

    def fetch(start: date, end: date, league_ids: Sequence[int]) -> ProviderWindow:
        read_fixtures.append(FIRST_PAGE_FIXTURE)

        message = f"The provider refused a page of {start} to {end} for {list(league_ids)}."

        raise SportmonksError(message)

    monkeypatch.setattr("apps.fixtures.tasks.fetch_fixtures_between", fetch)

    return read_fixtures


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

    fixtures = [
        provider_fixture(1, kickoff(11, 30)),
        provider_fixture(2, kickoff(14), league=LA_LIGA, home_team=BARCELONA, away_team=SEVILLA),
    ]

    requested = record_window(monkeypatch, provider_window(fixtures))

    written_count = synchronize_fixtures()

    assert written_count == len(fixtures)
    assert Fixture.objects.count() == len(fixtures)

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
    record_window(monkeypatch, provider_window([provider_fixture(1, kickoff(11, 30))]))

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
    record_window(monkeypatch, provider_window([provider_fixture(1, kickoff(11, 30))]))

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

    assert cache.add(SYNCHRONIZATION_LOCK_KEY, SUCCESSOR_LEASE, timeout=60)

    written_count = synchronize_fixtures()

    assert written_count == 0
    assert Fixture.objects.count() == 0
    assert cache.get(SYNCHRONIZATION_LOCK_KEY) == SUCCESSOR_LEASE


@pytest.mark.django_db
def test_synchronize_fixtures_holds_the_lock_against_a_run_starting_mid_fetch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    GIVEN a synchronization whose provider call starts a second one
    WHEN the outer run finishes
    THEN the lease was visibly held, the inner run wrote nothing, and the outer one wrote its window
    """

    freeze_now(monkeypatch)

    held_leases: list[object] = []
    inner_counts: list[int] = []

    def fetch(_start: date, _end: date, _league_ids: Sequence[int]) -> ProviderWindow:
        held_leases.append(cache.get(SYNCHRONIZATION_LOCK_KEY))
        inner_counts.append(synchronize_fixtures())

        return provider_window([provider_fixture(1, kickoff(11, 30))])

    monkeypatch.setattr("apps.fixtures.tasks.fetch_fixtures_between", fetch)

    written_count = synchronize_fixtures()

    assert [lease is not None for lease in held_leases] == [True]
    assert inner_counts == [0]
    assert written_count == 1
    assert Fixture.objects.count() == 1


@pytest.mark.django_db
def test_synchronize_fixtures_leaves_a_successor_lease_alone_after_losing_its_own(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    GIVEN a run whose lease expires mid-fetch and is taken by a later run
    WHEN the first run reaches its release
    THEN the later run keeps the lock, so no third run walks in behind it
    """

    freeze_now(monkeypatch)

    def fetch(_start: date, _end: date, _league_ids: Sequence[int]) -> ProviderWindow:
        cache.delete(SYNCHRONIZATION_LOCK_KEY)

        assert cache.add(SYNCHRONIZATION_LOCK_KEY, SUCCESSOR_LEASE, timeout=60)

        return provider_window([provider_fixture(1, kickoff(11, 30))])

    monkeypatch.setattr("apps.fixtures.tasks.fetch_fixtures_between", fetch)

    written_count = synchronize_fixtures()

    assert written_count == 1
    assert cache.get(SYNCHRONIZATION_LOCK_KEY) == SUCCESSOR_LEASE


@pytest.mark.django_db
def test_synchronize_fixtures_reraises_a_provider_failure_and_frees_the_lock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    GIVEN a provider that reads one fixture and then fails partway through the window
    WHEN the synchronization runs
    THEN the failure surfaces, the fixture it had read is not stored, and the lock is released
    """

    freeze_now(monkeypatch)

    read_fixtures = fail_after_one_page(monkeypatch)

    with pytest.raises(SportmonksError):
        synchronize_fixtures()

    assert read_fixtures == [FIRST_PAGE_FIXTURE]
    assert Fixture.objects.count() == 0
    assert cache.get(SYNCHRONIZATION_LOCK_KEY) is None
