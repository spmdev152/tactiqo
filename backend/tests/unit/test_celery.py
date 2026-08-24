from django.conf import settings

from config.celery import app


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
