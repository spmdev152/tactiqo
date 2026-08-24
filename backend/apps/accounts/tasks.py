import logging

from celery import shared_task
from django.utils import timezone

from apps.accounts.application.services import delete_expired_sessions

logger = logging.getLogger(__name__)


@shared_task(name="accounts.purge_expired_sessions")
def purge_expired_sessions() -> int:
    """
    Delete the session rows whose expiry has passed.

    Every sign-in inserts a row and nothing else removes one, so the table would
    otherwise grow for the life of the database. A sign-out that fails to reach
    the API, and a second sign-in that orphans the row of the first, both leave a
    row this run collects once its expiry passes.

    Returns
    -------
    int
        Number of sessions this run deleted.
    """

    deleted_count = delete_expired_sessions(timezone.now())

    logger.info("Deleted %d expired authentication session(s).", deleted_count)

    return deleted_count
