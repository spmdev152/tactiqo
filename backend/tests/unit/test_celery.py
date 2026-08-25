from celery.schedules import crontab
from django.conf import settings

from config.celery import app

PURGE_ENTRY = "accounts-purge-expired-sessions"
SYNCHRONIZATION_ENTRY = "fixtures-synchronize"
HOUR_IN_SECONDS = 3600
SIX_HOURS_IN_SECONDS = 6 * HOUR_IN_SECONDS
REDIS_VISIBILITY_TIMEOUT_SECONDS = 3600


def test_every_scheduled_task_is_registered() -> None:
    """
    GIVEN the Celery Beat schedule of the project
    WHEN a process imports the task modules the way a worker does
    THEN every scheduled task name is registered and the schedule is not empty
    """

    app.loader.import_default_modules()

    scheduled_names = {entry["task"] for entry in settings.CELERY_BEAT_SCHEDULE.values()}

    assert scheduled_names
    assert scheduled_names <= set(app.tasks)


def test_the_session_purge_runs_hourly_and_expires_within_its_slot() -> None:
    """
    GIVEN the scheduled entry purging expired sessions
    WHEN its cadence and its options are read
    THEN it runs at minute 15 of every hour and expires before the next run
    """

    entry = settings.CELERY_BEAT_SCHEDULE[PURGE_ENTRY]

    assert entry["schedule"] == crontab(minute="15")
    assert 0 < entry["options"]["expires"] < HOUR_IN_SECONDS


def test_the_fixture_synchronization_runs_every_six_hours_and_expires_within_its_slot() -> None:
    """
    GIVEN the scheduled entry refreshing the fixture window
    WHEN its cadence and its options are read
    THEN it runs at minute 5 every six hours and stays valid for most of that slot
    """

    entry = settings.CELERY_BEAT_SCHEDULE[SYNCHRONIZATION_ENTRY]

    assert entry["schedule"] == crontab(minute="5", hour="*/6")

    assert (
        SIX_HOURS_IN_SECONDS - HOUR_IN_SECONDS <= entry["options"]["expires"] < SIX_HOURS_IN_SECONDS
    )


def test_the_synchronization_lease_expires_before_the_broker_redelivers() -> None:
    """
    GIVEN the fixture synchronization lease and the broker visibility timeout
    WHEN the two are compared
    THEN the lease expires first, so a redelivered run never skips itself
    """

    visibility_timeout = app.conf.broker_transport_options.get(
        "visibility_timeout", REDIS_VISIBILITY_TIMEOUT_SECONDS
    )

    assert visibility_timeout > settings.FIXTURE_SYNCHRONIZATION_LOCK_SECONDS
