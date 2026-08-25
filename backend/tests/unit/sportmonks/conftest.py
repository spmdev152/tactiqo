import secrets
import time
from collections.abc import Iterator

import pytest
from django.test import override_settings

PROVIDER_BASE_URL = "https://provider.test/v3/football"


@pytest.fixture
def api_token() -> str:
    """
    Return a freshly generated provider token, never a literal.

    Returns
    -------
    str
        Token the boundary presents to the stubbed provider.
    """

    return secrets.token_urlsafe(16)


@pytest.fixture
def provider_base_url(api_token: str) -> Iterator[str]:
    """
    Point the boundary at a stub provider reachable only through a transport.

    Parameters
    ----------
    api_token : str
        Generated token the boundary is configured with.

    Yields
    ------
    str
        Base URL the client under test builds its requests from.
    """

    with override_settings(SPORTMONKS_API_TOKEN=api_token, SPORTMONKS_BASE_URL=PROVIDER_BASE_URL):
        yield PROVIDER_BASE_URL


@pytest.fixture
def sleeps(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[float]]:
    """
    Record every backoff delay instead of waiting it out.

    Parameters
    ----------
    monkeypatch : pytest.MonkeyPatch
        Patcher replacing the standard-library sleep for the test.

    Yields
    ------
    list of float
        Delays the client asked to sleep, in order.
    """

    recorded: list[float] = []

    monkeypatch.setattr(time, "sleep", recorded.append)

    yield recorded
