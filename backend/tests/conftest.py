from collections.abc import Callable
from typing import Protocol, cast

import pytest
from django.test import Client


class ApiResponse(Protocol):
    """
    Response surface used by HTTP contract tests.

    The Django test client attaches its JSON helper to response instances at
    runtime, so the response it hands back cannot be described by a single
    Django class. This protocol names the part the tests rely on.

    Attributes
    ----------
    status_code : int
        HTTP status line of the response under assertion.

    Methods
    -------
    json() -> dict[str, object]
        Return the parsed JSON body.
    """

    status_code: int

    def json(self) -> dict[str, object]:
        """
        Return the parsed JSON body.

        Returns
        -------
        dict of str to object
            Decoded response payload.
        """

        ...


ApiGet = Callable[[str], ApiResponse]


@pytest.fixture
def api_get() -> ApiGet:
    """
    Return a callable issuing GET requests against the project URL configuration.

    Returns
    -------
    ApiGet
        Callable that takes a path and returns the API response.
    """

    client = Client()

    def get(path: str) -> ApiResponse:
        return cast(ApiResponse, client.get(path))

    return get
