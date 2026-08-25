import logging
from datetime import timedelta
from uuid import uuid4

from celery import shared_task
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from apps.predictions.infrastructure.repositories import (
    upsert_fixture_predictions,
    upsert_market_reliability,
)
from integrations.sportmonks.exceptions import SportmonksError
from integrations.sportmonks.predictions import fetch_market_reliability, fetch_prediction_window

logger = logging.getLogger(__name__)

SYNCHRONIZATION_LOCK_KEY = "predictions:synchronize-predictions"

RELIABILITY_LOCK_KEY = "predictions:synchronize-reliability"


def _release_lock(lock_key: str, lease: str) -> None:
    """
    Free a synchronization lock, but only if this run still holds the lease.

    ``cache.add`` stores the lease of the run that acquired the lock, so a run
    whose lease has expired can tell that the value it reads back belongs to a
    successor and leave it alone. Without that check a run outliving its lock
    timeout frees the lock a second run legitimately acquired, and a third run
    walks straight in.

    The read and the delete are two commands rather than one, so this is not
    exclusion: a lease that expires between them, and is taken by a successor in
    that interval, is still deleted by its predecessor. What the check does is
    shrink the window in which that can happen from the whole remainder of a run
    to a single round trip, and no more should be claimed for it. Correctness
    does not rest on the lock in the first place: both upserts are idempotent and
    reconcile the same rows whichever run writes them, so the lock is there to
    stop two runs spending the same provider budget, not to make a double write
    unrepresentable.

    The two synchronizations of this module hold two different keys, so they may
    run at the same time. That is deliberate: they read different provider
    resources, against separate hourly budgets, and they write different tables,
    so serializing them would only delay the nightly grades behind a six-hourly
    probability refresh.

    Parameters
    ----------
    lock_key : str
        Cache key of the lock the run acquired.
    lease : str
        Token the run wrote when it acquired that lock.
    """

    if cache.get(lock_key) == lease:
        cache.delete(lock_key)


@shared_task(name="predictions.synchronize_predictions")
def synchronize_predictions() -> int:
    """
    Refresh the stored prediction probabilities from the provider.

    The window is the fixture window, read from
    ``FIXTURE_SYNCHRONIZATION_PAST_DAYS`` and
    ``FIXTURE_SYNCHRONIZATION_FUTURE_DAYS`` rather than from a pair of constants
    of its own. Predictions exist for fixtures, so any range narrower than the
    one the listing can show would leave a visible fixture whose panel is
    permanently empty, and any range wider would ask the provider about days no
    fixture is stored for, which the repository then skips. Tying the two
    together makes that class of gap unrepresentable instead of a thing to keep
    two settings in step over. Past days are included because the provider
    revises a probability up to kick-off and a finished fixture keeps the
    probabilities it was played under, which is the only honest thing to show
    beside its result.

    Beat runs this every six hours and a deployment or an operator may run it by
    hand, so two runs can overlap. ``cache.add`` is the guard because it is a
    single atomic Redis command that both tests and sets, where a read followed
    by a write leaves a window in which both runs believe they hold the lock. A
    run that finds the lock taken returns without writing rather than waiting,
    since the run holding it is reading the same window. What the lock stores is
    a per-run lease, not a flag, so releasing it can be conditional: see
    ``_release_lock`` for what that buys and for the residual race it does not
    close.

    Returns
    -------
    int
        Number of probability rows this run wrote, or ``0`` when another run
        held the lock.

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
        SYNCHRONIZATION_LOCK_KEY, lease, timeout=settings.PREDICTION_SYNCHRONIZATION_LOCK_SECONDS
    )

    if not lock_acquired:
        logger.info("Skipped prediction refresh for %s to %s: already running.", start, end)

        return 0

    try:
        window = fetch_prediction_window(start, end, settings.SPORTMONKS_LEAGUE_IDS)

        written_count = upsert_fixture_predictions(window, timezone.now())
    except SportmonksError:
        logger.exception("Failed to synchronize predictions for %s to %s.", start, end)

        raise
    finally:
        _release_lock(SYNCHRONIZATION_LOCK_KEY, lease)

    logger.info("Synchronized %d probability row(s) for %s to %s.", written_count, start, end)

    return written_count


@shared_task(name="predictions.synchronize_reliability")
def synchronize_reliability() -> int:
    """
    Refresh how well the provider's model grades each market per competition.

    There is no window to derive: a grade is a property of a market in a
    competition over a season, so the run reads the subscribed leagues from
    ``SPORTMONKS_LEAGUE_IDS`` and nothing else. That also makes it one provider
    request per league instead of a paginated read, which is why it holds a
    shorter lease than the probabilities do and runs nightly rather than every
    six hours: the grades move over a season, not over an afternoon.

    The lock is the same mechanism as the probability refresh, on its own key,
    so an operator running the two by hand at once does not have one of them
    return without writing.

    Returns
    -------
    int
        Number of reliability rows this run wrote, or ``0`` when another run
        held the lock.

    Raises
    ------
    SportmonksError
        When the provider cannot be read. It is re-raised so Celery records the
        failure; every league is fetched before the repository is entered, so
        nothing has been written.
    """

    lease = uuid4().hex

    lock_acquired = cache.add(
        RELIABILITY_LOCK_KEY, lease, timeout=settings.PREDICTION_RELIABILITY_LOCK_SECONDS
    )

    if not lock_acquired:
        logger.info("Skipped market reliability refresh: already running.")

        return 0

    try:
        grades = fetch_market_reliability(settings.SPORTMONKS_LEAGUE_IDS)

        written_count = upsert_market_reliability(grades, timezone.now())
    except SportmonksError:
        logger.exception("Failed to synchronize market reliability.")

        raise
    finally:
        _release_lock(RELIABILITY_LOCK_KEY, lease)

    logger.info("Synchronized %d market reliability row(s).", written_count)

    return written_count
