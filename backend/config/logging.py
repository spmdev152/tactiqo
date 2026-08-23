import inspect
import logging
import sys
from logging.config import dictConfig
from typing import Any

from loguru import logger

HUMAN_READABLE_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> "
    "<level>{level: <8}</level> "
    "<cyan>{name}</cyan> - <level>{message}</level>"
)

DEPLOYED_MINIMUM_LEVEL = "INFO"


def deployed_log_level(requested: str) -> str:
    """
    Clamp a requested level so a deployed environment never emits debug records.

    Debug records can carry request payloads and configuration values, so the
    guarantee that they stay out of preproduction and production is enforced here
    rather than left to whoever sets ``DJANGO_LOG_LEVEL``. A quieter level than
    the minimum is honoured, and an unknown name falls back to the minimum.

    Parameters
    ----------
    requested : str
        Level name asked for by the environment.

    Returns
    -------
    str
        ``requested`` when it is at least as quiet as the deployed minimum,
        otherwise the deployed minimum.
    """

    names_to_values = logging.getLevelNamesMapping()
    minimum_value = names_to_values[DEPLOYED_MINIMUM_LEVEL]
    requested_value = names_to_values.get(requested)

    if requested_value is None or requested_value < minimum_value:
        return DEPLOYED_MINIMUM_LEVEL

    return requested


class InterceptHandler(logging.Handler):
    """
    Standard-library handler forwarding every record to Loguru.

    Django, Celery, and third-party packages all emit through the standard
    library, so intercepting at the handler level is what makes Loguru the single
    sink for the whole process. Application code keeps calling
    ``logging.getLogger(__name__)`` and stays independent of the sink.

    Methods
    -------
    emit(record) -> None
        Re-emit a standard-library record through Loguru.
    """

    def emit(self, record: logging.LogRecord) -> None:
        """
        Re-emit a standard-library record through Loguru.

        Parameters
        ----------
        record : logging.LogRecord
            Record produced by the standard-library logging machinery.
        """

        try:
            level: str | int = logger.level(record.levelname).name

        except ValueError:
            level = record.levelno

        frame, depth = inspect.currentframe(), 0

        while frame and (depth == 0 or frame.f_code.co_filename == logging.__file__):
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def build_logging(
    level: str,
    *,
    serialize: bool = False,
    colorize: bool = False,
    diagnose: bool = False,
) -> dict[str, Any]:
    """
    Build the Django ``LOGGING`` dictionary for one environment.

    Parameters
    ----------
    level : str
        Minimum level emitted by the root logger and by the Loguru sink.
    serialize : bool, optional
        Emit one JSON object per record, for log collectors in deployed
        environments.
    colorize : bool, optional
        Colourize the human-readable output, useful only on a terminal.
    diagnose : bool, optional
        Include variable values in tracebacks. Never enable this outside local
        development: it prints the surrounding values, which can contain
        credentials.

    Returns
    -------
    dict of str to Any
        Django ``LOGGING`` dictionary consumed by :func:`configure`.
    """

    return {
        "version": 1,
        "disable_existing_loggers": False,
        "loguru": {
            "level": level,
            "serialize": serialize,
            "colorize": colorize,
            "diagnose": diagnose,
        },
        "handlers": {
            "loguru": {
                "class": "config.logging.InterceptHandler",
            },
        },
        "root": {
            "handlers": ["loguru"],
            "level": level,
        },
        "loggers": {
            "django.db.backends": {
                "handlers": ["loguru"],
                "level": "WARNING",
                "propagate": False,
            },
        },
    }


def configure(logging_settings: dict[str, Any]) -> None:
    """
    Install Loguru as the process sink and apply the Django logging dictionary.

    Django calls this through the ``LOGGING_CONFIG`` setting, which guarantees it
    runs exactly once per process and before application code emits anything.

    Parameters
    ----------
    logging_settings : dict of str to Any
        Value of the Django ``LOGGING`` setting, carrying the Loguru sink options
        under the ``loguru`` key.
    """

    options = logging_settings.get("loguru", {})

    standard_library_settings = {
        key: value for key, value in logging_settings.items() if key != "loguru"
    }

    logger.remove()

    logger.add(
        sys.stdout,
        level=options.get("level", "INFO"),
        serialize=options.get("serialize", False),
        colorize=options.get("colorize", False),
        diagnose=options.get("diagnose", False),
        format=HUMAN_READABLE_FORMAT,
        backtrace=True,
    )

    dictConfig(standard_library_settings)
