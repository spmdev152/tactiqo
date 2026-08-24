from celery.schedules import crontab
from django.conf import settings

from config.celery import app

PURGE_ENTRY = "accounts-purge-expired-sessions"
HOUR_IN_SECONDS = 3600


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
