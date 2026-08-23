import logging
from collections.abc import Iterator
from typing import TYPE_CHECKING

import pytest
from loguru import logger

from config import logging as logging_module
from config.logging import (
    DEPLOYED_MINIMUM_LEVEL,
    InterceptHandler,
    build_logging,
    configure,
    deployed_log_level,
)

if TYPE_CHECKING:
    from loguru import Message

CapturedRecord = tuple[str, str, bool]
SinkOptions = dict[str, object]


@pytest.fixture
def loguru_records() -> Iterator[list[CapturedRecord]]:
    """
    Collect the level, message, and exception presence of every Loguru record.

    Loguru bypasses the standard-library handlers that ``caplog`` inspects, so
    assertions have to read from a Loguru sink instead.

    Yields
    ------
    list of CapturedRecord
        Captured records in emission order.
    """

    captured: list[CapturedRecord] = []

    def sink(message: "Message") -> None:
        record = message.record
        captured.append((record["level"].name, record["message"], record["exception"] is not None))

    sink_id = logger.add(sink, level="DEBUG")

    yield captured

    logger.remove(sink_id)


def intercepted_logger(name: str) -> logging.Logger:
    """
    Build a standard-library logger whose only handler is the Loguru interceptor.

    Parameters
    ----------
    name : str
        Logger name, unique per test so handlers never leak between them.

    Returns
    -------
    logging.Logger
        Logger emitting exclusively through :class:`InterceptHandler`.
    """

    intercepted = logging.getLogger(name)

    intercepted.handlers = [InterceptHandler()]
    intercepted.setLevel(logging.DEBUG)
    intercepted.propagate = False

    return intercepted


def test_the_intercept_handler_forwards_standard_library_records_to_loguru(
    loguru_records: list[CapturedRecord],
) -> None:
    """
    GIVEN a standard-library logger whose only handler is the Loguru interceptor
    WHEN application code emits a warning through it
    THEN the record reaches Loguru with its level and message preserved
    """

    intercepted_logger("tactiqo.intercept.probe").warning("database probe failed")

    assert loguru_records == [("WARNING", "database probe failed", False)]


def test_the_intercept_handler_preserves_the_exception_of_a_record(
    loguru_records: list[CapturedRecord],
) -> None:
    """
    GIVEN application code logging inside an exception handler
    WHEN the record carries exception information
    THEN Loguru receives the exception instead of losing it
    """

    intercepted = intercepted_logger("tactiqo.intercept.exception")

    try:
        raise RuntimeError("connection refused")

    except RuntimeError:
        intercepted.warning("cache probe failed", exc_info=True)

    assert loguru_records == [("WARNING", "cache probe failed", True)]


def test_the_intercept_handler_honours_the_standard_library_level(
    loguru_records: list[CapturedRecord],
) -> None:
    """
    GIVEN a standard-library logger raised to the warning threshold
    WHEN application code emits a debug record through it
    THEN nothing reaches Loguru, because the standard library filtered it first
    """

    intercepted = intercepted_logger("tactiqo.intercept.threshold")
    intercepted.setLevel(logging.WARNING)

    intercepted.debug("too verbose for this logger")

    assert loguru_records == []


@pytest.mark.parametrize(
    ("requested", "expected"),
    [
        ("DEBUG", DEPLOYED_MINIMUM_LEVEL),
        ("INFO", "INFO"),
        ("WARNING", "WARNING"),
        ("ERROR", "ERROR"),
        ("NOT-A-LEVEL", DEPLOYED_MINIMUM_LEVEL),
    ],
)
def test_deployed_log_level_never_falls_below_the_minimum(requested: str, expected: str) -> None:
    """
    GIVEN a deployment requesting a log level through the environment
    WHEN the level is resolved for a deployed environment
    THEN anything more verbose than the minimum is clamped and quieter levels pass through
    """

    assert deployed_log_level(requested) == expected


@pytest.fixture
def installed_sinks(monkeypatch: pytest.MonkeyPatch) -> list[SinkOptions]:
    """
    Capture the options every sink installation would apply to Loguru.

    Loguru sinks and the standard-library configuration are process-global, so
    both are replaced here: applying a configuration inside one test must not
    silence the sink another test asserts on.

    Parameters
    ----------
    monkeypatch : pytest.MonkeyPatch
        Fixture replacing the global sink and configuration entry points.

    Returns
    -------
    list of SinkOptions
        Keyword arguments of each installation, in order.
    """

    installations: list[SinkOptions] = []

    def add(_sink: object, **options: object) -> int:
        installations.append(options)

        return len(installations)

    monkeypatch.setattr(logger, "add", add)
    monkeypatch.setattr(logger, "remove", lambda *_args: None)
    monkeypatch.setattr(logging_module, "dictConfig", lambda _settings: None)

    return installations


def test_configure_installs_a_deployed_sink_that_hides_variable_values(
    installed_sinks: list[SinkOptions],
) -> None:
    """
    GIVEN the logging dictionary built for a deployed environment
    WHEN Django applies it through the LOGGING_CONFIG entry point
    THEN the sink serializes records at the requested level with diagnose disabled
    """

    configure(build_logging("INFO", serialize=True))

    assert len(installed_sinks) == 1

    assert installed_sinks[0]["level"] == "INFO"
    assert installed_sinks[0]["serialize"] is True
    assert installed_sinks[0]["diagnose"] is False
    assert installed_sinks[0]["colorize"] is False


def test_configure_installs_a_local_sink_with_readable_diagnostics(
    installed_sinks: list[SinkOptions],
) -> None:
    """
    GIVEN the logging dictionary built for local development
    WHEN Django applies it through the LOGGING_CONFIG entry point
    THEN the sink stays human-readable and keeps the diagnostic traceback values
    """

    configure(build_logging("DEBUG", colorize=True, diagnose=True))

    assert len(installed_sinks) == 1

    assert installed_sinks[0]["level"] == "DEBUG"
    assert installed_sinks[0]["serialize"] is False
    assert installed_sinks[0]["diagnose"] is True
    assert installed_sinks[0]["colorize"] is True
