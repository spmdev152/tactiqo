import os

from celery import Celery
from celery.signals import setup_logging
from django.conf import settings
from django.utils.log import configure_logging

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

app = Celery("tactiqo")

app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


@setup_logging.connect
def keep_django_logging_configuration(**_kwargs: object) -> None:
    """
    Keep Django's logging configuration when Celery starts a worker or the beat.

    Celery installs its own logging unless a receiver is connected to this
    signal, which would give the worker and the beat scheduler a different format
    from the API. Connecting a receiver is what opts out, and re-applying the
    Django configuration here makes that intent explicit instead of relying on an
    empty function body. Re-applying is safe because the Loguru sink is rebuilt
    from scratch on every call.

    Parameters
    ----------
    **_kwargs : object
        Signal arguments, unused because the receiver only restores configuration.
    """

    configure_logging(settings.LOGGING_CONFIG, settings.LOGGING)
