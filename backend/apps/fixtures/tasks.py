import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from apps.fixtures.infrastructure.repositories import upsert_fixtures
from integrations.sportmonks.exceptions import SportmonksError
from integrations.sportmonks.fixtures import fetch_fixtures_between

logger = logging.getLogger(__name__)

SYNCHRONIZATION_LOCK_KEY = "fixtures:synchronize-fixtures"


@shared_task(name="fixtures.synchronize_fixtures")
def synchronize_fixtures() -> int:
    """
    Refresh the stored fixture window from the provider.

    Beat runs this every six hours and a deployment or an operator may run it by
    hand, so two runs can overlap. ``cache.add`` is the guard because it is a
    single atomic Redis command that both tests and sets, where a read followed
    by a write leaves a window in which both runs believe they hold the lock. A
    run that finds the lock taken returns without writing rather than waiting,
    since the run holding it is fetching the same window.

    Returns
    -------
    int
        Number of fixtures this run wrote, or ``0`` when another run held the
        lock.

    Raises
    ------
    SportmonksError
        When the provider cannot be read. It is re-raised so Celery records the
        failure; the repository transaction has already discarded whatever the
        run had written.
    """

    today = timezone.now().date()

    start = today - timedelta(days=settings.FIXTURE_SYNCHRONIZATION_PAST_DAYS)
    end = today + timedelta(days=settings.FIXTURE_SYNCHRONIZATION_FUTURE_DAYS)

    lock_acquired = cache.add(
        SYNCHRONIZATION_LOCK_KEY, True, timeout=settings.FIXTURE_SYNCHRONIZATION_LOCK_SECONDS
    )

    if not lock_acquired:
        logger.info("Skipped fixture synchronization for %s to %s: already running.", start, end)

        return 0

    try:
        provider_fixtures = fetch_fixtures_between(start, end, settings.SPORTMONKS_LEAGUE_IDS)

        written_count = upsert_fixtures(provider_fixtures, timezone.now())
    except SportmonksError:
        logger.exception("Failed to synchronize fixtures for %s to %s.", start, end)

        raise
    finally:
        cache.delete(SYNCHRONIZATION_LOCK_KEY)

    logger.info("Synchronized %d fixture(s) for %s to %s.", written_count, start, end)

    return written_count
