import logging
from datetime import date, timedelta
from uuid import uuid4

from celery import shared_task
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from apps.fixtures.infrastructure.repositories import upsert_fixtures
from apps.statistics.infrastructure.repositories import upsert_match_statistics
from integrations.sportmonks.exceptions import SportmonksError
from integrations.sportmonks.fixtures import fetch_fixtures_between
from integrations.sportmonks.statistics import fetch_match_statistics

logger = logging.getLogger(__name__)

SYNCHRONIZATION_LOCK_KEY = "statistics:synchronize-statistics"

# The bound is a typo guard rather than a performance one: ``days_back`` is the
# one argument an operator types by hand, and a slipped digit would otherwise
# walk a decade of calendar days one chunk at a time, spending the hourly budget
# of every entity the read touches before anybody noticed. It is set above what
# the subscription actually serves rather than below it, so the guard never
# refuses a backfill the provider would have answered: reads were verified to
# return complete windows from August 2024, the start of the 2024/2025 season,
# and to be refused for every month before it, so three seasons of calendar days
# plus a summer of headroom is the honest ceiling.
MAXIMUM_PAST_DAYS = 1200


def _release_lock(lease: str) -> None:
    """
    Free the synchronization lock, but only if this run still holds the lease.

    ``cache.add`` stores the lease of the run that acquired the lock, so a run
    whose lease has expired can tell that the value it reads back belongs to a
    successor and leave it alone. Without that check a run outliving
    ``STATISTICS_SYNCHRONIZATION_LOCK_SECONDS`` frees the lock a second run
    legitimately acquired, and a third run walks straight in. A backfill makes
    that more than theoretical: it is the one invocation whose range can outlast
    the lease it was sized for.

    The read and the delete are two commands rather than one, so this is not
    exclusion: a lease that expires between them, and is taken by a successor in
    that interval, is still deleted by its predecessor. What the check does is
    shrink the window in which that can happen from the whole remainder of a run
    to a single round trip, and no more should be claimed for it. Correctness
    does not rest on the lock in the first place: both upserts a chunk performs
    are idempotent and reconcile the same rows whichever run writes them, so the
    lock is there to stop two runs spending the same provider budget, not to
    make a double write unrepresentable.

    Both commands run under a ``try`` because this is called from a bare
    ``finally``, and a cache the run can no longer reach raises there. That
    exception would replace the provider failure that actually ended the run, so
    Celery would record a ``ConnectionError`` and the traceback worth reading
    would be gone. Failing to release is a recoverable outcome, since the lease
    carries a timeout and expires on its own, whereas losing the reason a run
    failed is not, so the release reports and gives up.

    Parameters
    ----------
    lease : str
        Token the run wrote when it acquired the lock.
    """

    try:
        if cache.get(SYNCHRONIZATION_LOCK_KEY) == lease:
            cache.delete(SYNCHRONIZATION_LOCK_KEY)
    except Exception:
        logger.warning(
            "Could not release the %s lock, so it is left to expire.",
            SYNCHRONIZATION_LOCK_KEY,
            exc_info=True,
        )


def _chunk_boundaries(start: date, end: date, chunk_days: int) -> list[tuple[date, date]]:
    """
    Split a range into the consecutive day ranges the provider is read over.

    The chunking is not an optimization. Both reads a chunk performs are
    paginated, and the client refuses a read it cannot finish inside its page
    budget rather than returning the pages it managed to fetch, which the
    fixture reconciliation depends on: a truncated payload is indistinguishable
    from a range that legitimately lost most of its matches. A range wide enough
    to exceed that budget would therefore fail as a whole, so the range is cut
    into pieces each of which comfortably fits, and every piece is written before
    the next is read.

    The ranges are inclusive at both ends and share no day, because each one is
    handed to ``upsert_fixtures`` as an authoritative window: an overlap would
    have the second chunk reconcile days the first had already settled, and a gap
    would leave a day whose departed matches nothing ever removes. They are
    walked oldest first, so a chunk that fails aborts the ones behind it rather
    than the ones already written, and a retry of the whole invocation is free
    because every chunk is idempotent.

    Parameters
    ----------
    start : date
        First calendar day, in UTC, the invocation covers.
    end : date
        Last calendar day, in UTC, the invocation covers, included in the range.
    chunk_days : int
        Calendar days a single chunk spans, counting both of its ends.

    Returns
    -------
    list of tuple of date
        First and last day of each chunk, ascending, covering the range exactly
        once. A range shorter than one chunk yields a single entry holding it.
    """

    boundaries: list[tuple[date, date]] = []

    chunk_start = start

    while chunk_start <= end:
        chunk_end = min(chunk_start + timedelta(days=chunk_days - 1), end)

        boundaries.append((chunk_start, chunk_end))

        chunk_start = chunk_end + timedelta(days=1)

    return boundaries


@shared_task(name="statistics.synchronize_statistics")
def synchronize_statistics(days_back: int | None = None) -> int:
    """
    Refresh the stored match statistics from the provider.

    The range runs from ``days_back`` days ago to today, defaulting to
    ``STATISTICS_SYNCHRONIZATION_PAST_DAYS``. Beat passes nothing and gets the
    default, a handful of days, which is what a six-hourly run needs to pick up
    every match that has finished since the last one and to re-read a match
    whose figures the provider revised after the whistle. An operator seeding a
    fresh database, or repairing a gap a worker outage left, passes a wider
    number. That is one code path rather than a second task, because a backfill
    differs from a scheduled run in the width of its range and in nothing else:
    the chunking, the locking, and the reconciliation are the same, and a
    separate task would be the same body maintained twice.

    Each chunk brings its own fixture parents before its statistics. That
    ordering is required rather than defensive. The fixture beat window reaches
    only ``FIXTURE_SYNCHRONIZATION_PAST_DAYS`` back, so every day this task
    reads beyond that is a day no other job stores matches for, and a statistics
    read whose matches are absent writes nothing at all. Fetching the fixtures
    of the chunk first makes a historical range self-sufficient, and on the
    scheduled range it costs one extra read of days the fixture job already
    holds, which is the same idempotent upsert it performs itself.

    Both provider reads of a chunk are fully materialized before the repository
    they feed is entered, so a failure part-way through a paginated read leaves
    that chunk untouched instead of half written.

    Beat runs this every six hours and a deployment or an operator may run it by
    hand, so two runs can overlap. ``cache.add`` is the guard because it is a
    single atomic Redis command that both tests and sets, where a read followed
    by a write leaves a window in which both runs believe they hold the lock. A
    run that finds the lock taken returns without writing rather than waiting,
    since the run holding it is reading overlapping days. What the lock stores is
    a per-run lease, not a flag, so releasing it can be conditional: see
    ``_release_lock`` for what that buys and for the residual race it does not
    close.

    Parameters
    ----------
    days_back : int or None
        Calendar days of history to refresh, or ``None`` to use
        ``STATISTICS_SYNCHRONIZATION_PAST_DAYS``.

    Returns
    -------
    int
        Number of statistic rows this run wrote across every chunk, or ``0``
        when another run held the lock.

    Raises
    ------
    ValueError
        When ``days_back`` is not a positive number of days inside
        ``MAXIMUM_PAST_DAYS``. It is rejected before the lock is acquired, so a
        mistyped invocation cannot lock out the scheduled run it would otherwise
        have displaced.
    SportmonksError
        When the provider cannot be read. It is re-raised so Celery records the
        failure; the chunks before the failing one keep what they wrote, which
        is sound because each of them read and reconciled its own days. The
        failing chunk writes no statistic row, though it will already have
        refreshed its fixtures when it is the statistics read that failed, which
        is the same idempotent window the fixture task writes itself.
    """

    past_days = settings.STATISTICS_SYNCHRONIZATION_PAST_DAYS if days_back is None else days_back

    if not 1 <= past_days <= MAXIMUM_PAST_DAYS:
        message = f"days_back must be between 1 and {MAXIMUM_PAST_DAYS} days, not {past_days}."

        raise ValueError(message)

    today = timezone.now().date()

    start = today - timedelta(days=past_days)

    chunks = _chunk_boundaries(start, today, settings.STATISTICS_SYNCHRONIZATION_CHUNK_DAYS)

    lease = uuid4().hex

    lock_acquired = cache.add(
        SYNCHRONIZATION_LOCK_KEY, lease, timeout=settings.STATISTICS_SYNCHRONIZATION_LOCK_SECONDS
    )

    if not lock_acquired:
        logger.info(
            "Skipped statistics synchronization for %s to %s: already running.", start, today
        )

        return 0

    written_count = 0

    try:
        for chunk_start, chunk_end in chunks:
            fixture_window = fetch_fixtures_between(
                chunk_start, chunk_end, settings.SPORTMONKS_LEAGUE_IDS
            )

            upsert_fixtures(fixture_window, chunk_start, chunk_end, timezone.now())

            statistics_window = fetch_match_statistics(
                chunk_start, chunk_end, settings.SPORTMONKS_LEAGUE_IDS
            )

            written_count += upsert_match_statistics(statistics_window, timezone.now())
    except SportmonksError:
        logger.exception("Failed to synchronize statistics for %s to %s.", start, today)

        raise
    finally:
        _release_lock(lease)

    logger.info(
        "Synchronized %d statistic row(s) for %s to %s in %d chunk(s).",
        written_count,
        start,
        today,
        len(chunks),
    )

    return written_count
