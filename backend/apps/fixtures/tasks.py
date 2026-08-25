import logging
from datetime import timedelta
from uuid import uuid4

from celery import shared_task
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from apps.fixtures.infrastructure.repositories import upsert_fixtures
from integrations.sportmonks.exceptions import SportmonksError
from integrations.sportmonks.fixtures import fetch_fixtures_between

logger = logging.getLogger(__name__)

SYNCHRONIZATION_LOCK_KEY = "fixtures:synchronize-fixtures"


def _release_lock(lease: str) -> None:
    """
    Free the synchronization lock, but only if this run still holds the lease.

    ``cache.add`` stores the lease of the run that acquired the lock, so a run
    whose lease has expired can tell that the value it reads back belongs to a
    successor and leave it alone. Without that check a run outliving
    ``FIXTURE_SYNCHRONIZATION_LOCK_SECONDS`` frees the lock a second run
    legitimately acquired, and a third run walks straight in.

    The read and the delete are two commands rather than one, so this is not
    exclusion: a lease that expires between them, and is taken by a successor in
    that interval, is still deleted by its predecessor. What the check does is
    shrink the window in which that can happen from the whole remainder of a run
    to a single round trip, and no more should be claimed for it. Correctness
    does not rest on the lock in the first place: the upsert is idempotent and
    reconciles the same range whichever run writes it, so the lock is there to
    stop two runs spending provider calls on one window, not to make a double
    write unrepresentable.

    Parameters
    ----------
    lease : str
        Token the run wrote when it acquired the lock.
    """

    if cache.get(SYNCHRONIZATION_LOCK_KEY) == lease:
        cache.delete(SYNCHRONIZATION_LOCK_KEY)


@shared_task(name="fixtures.synchronize_fixtures")
def synchronize_fixtures() -> int:
    """
    Refresh the stored fixture window from the provider.

    Beat runs this every six hours and a deployment or an operator may run it by
    hand, so two runs can overlap. ``cache.add`` is the guard because it is a
    single atomic Redis command that both tests and sets, where a read followed
    by a write leaves a window in which both runs believe they hold the lock. A
    run that finds the lock taken returns without writing rather than waiting,
    since the run holding it is fetching the same window. What the lock stores
    is a per-run lease, not a flag, so releasing it can be conditional: see
    ``_release_lock`` for what that buys and for the residual race it does not
    close.

    Returns
    -------
    int
        Number of fixtures this run wrote, or ``0`` when another run held the
        lock.

    Raises
    ------
    SportmonksError
        When the provider cannot be read. It is re-raised so Celery records the
        failure; nothing has been written, because the whole window is fetched
        before the repository is entered.
    """

    today = timezone.now().date()

    start = today - timedelta(days=settings.FIXTURE_SYNCHRONIZATION_PAST_DAYS)
    end = today + timedelta(days=settings.FIXTURE_SYNCHRONIZATION_FUTURE_DAYS)

    lease = uuid4().hex

    lock_acquired = cache.add(
        SYNCHRONIZATION_LOCK_KEY, lease, timeout=settings.FIXTURE_SYNCHRONIZATION_LOCK_SECONDS
    )

    if not lock_acquired:
        logger.info("Skipped fixture synchronization for %s to %s: already running.", start, end)

        return 0

    try:
        window = fetch_fixtures_between(start, end, settings.SPORTMONKS_LEAGUE_IDS)

        written_count = upsert_fixtures(window, start, end, timezone.now())
    except SportmonksError:
        logger.exception("Failed to synchronize fixtures for %s to %s.", start, end)

        raise
    finally:
        _release_lock(lease)

    logger.info("Synchronized %d fixture(s) for %s to %s.", written_count, start, end)

    return written_count
