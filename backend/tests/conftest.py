import secrets
from collections.abc import Iterator
from typing import Protocol, cast

import pytest
from django.core.cache import cache
from django.test import Client

from apps.accounts.models import User


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
    content : bytes
        Raw response body, asserted where the contract demands it be empty.

    Methods
    -------
    json() -> dict[str, object]
        Return the parsed JSON body.
    """

    status_code: int
    content: bytes

    def json(self) -> dict[str, object]:
        """
        Return the parsed JSON body.

        Returns
        -------
        dict of str to object
            Decoded response payload.
        """

        ...


class ApiGet(Protocol):
    """
    Callable issuing GET requests against the project URL configuration.

    Methods
    -------
    __call__(path, token=None) -> ApiResponse
        Request a path, optionally as a bearer-authenticated client.
    """

    def __call__(self, path: str, *, token: str | None = None) -> ApiResponse:
        """
        Request a path, optionally as a bearer-authenticated client.

        Parameters
        ----------
        path : str
            Absolute path to request.
        token : str or None
            Bearer token to present, or ``None`` to send no credential.

        Returns
        -------
        ApiResponse
            Response of the API.
        """

        ...


class ApiPost(Protocol):
    """
    Callable issuing JSON POST requests against the project URL configuration.

    Methods
    -------
    __call__(path, payload=None, token=None) -> ApiResponse
        Post a JSON body to a path, optionally as a bearer-authenticated client.
    """

    def __call__(
        self, path: str, payload: dict[str, object] | None = None, *, token: str | None = None
    ) -> ApiResponse:
        """
        Post a JSON body to a path, optionally as a bearer-authenticated client.

        Parameters
        ----------
        path : str
            Absolute path to request.
        payload : dict of str to object or None
            Body to serialize as JSON, or ``None`` to send an empty object.
        token : str or None
            Bearer token to present, or ``None`` to send no credential.

        Returns
        -------
        ApiResponse
            Response of the API.
        """

        ...


class UserFactory(Protocol):
    """
    Callable persisting an account for a test to authenticate as.

    Methods
    -------
    __call__(email="ada@example.com", full_name="Ada Lovelace", is_active=True) -> User
        Create and store an account with the generated test password.
    """

    def __call__(
        self,
        email: str = ...,
        full_name: str = ...,
        is_active: bool = ...,
    ) -> User:
        """
        Create and store an account with the generated test password.

        Parameters
        ----------
        email : str
            Login identifier of the account.
        full_name : str
            Display name of the account.
        is_active : bool
            Whether the account may authenticate.

        Returns
        -------
        User
            Persisted account.
        """

        ...


def bearer_headers(token: str | None) -> dict[str, str]:
    """
    Return the request headers presenting a bearer token.

    Parameters
    ----------
    token : str or None
        Token to present, or ``None`` to send no credential.

    Returns
    -------
    dict of str to str
        Headers to hand to the Django test client.
    """

    return {"Authorization": f"Bearer {token}"} if token is not None else {}


@pytest.fixture(autouse=True)
def isolated_cache() -> Iterator[None]:
    """
    Empty the cache around every test.

    The test settings back the cache with an in-process locmem store, which
    outlives a single test. The sign-in throttle counts attempts there, so
    without this the tests in a run would share one budget and their order
    would decide which of them sees HTTP 429.
    """

    cache.clear()

    yield

    cache.clear()


@pytest.fixture
def api_get() -> ApiGet:
    """
    Return a callable issuing GET requests against the project URL configuration.

    Returns
    -------
    ApiGet
        Callable that takes a path and an optional bearer token.
    """

    client = Client()

    def get(path: str, *, token: str | None = None) -> ApiResponse:
        return cast(ApiResponse, client.get(path, headers=bearer_headers(token)))

    return get


@pytest.fixture
def api_post() -> ApiPost:
    """
    Return a callable issuing JSON POST requests against the project URL configuration.

    Returns
    -------
    ApiPost
        Callable that takes a path, an optional JSON body, and an optional
        bearer token.
    """

    client = Client()

    def post(
        path: str, payload: dict[str, object] | None = None, *, token: str | None = None
    ) -> ApiResponse:
        response = client.post(
            path,
            data=payload if payload is not None else {},
            content_type="application/json",
            headers=bearer_headers(token),
        )

        return cast(ApiResponse, response)

    return post


@pytest.fixture
def user_password() -> str:
    """
    Return a freshly generated password, never a literal, for the test accounts.

    Returns
    -------
    str
        Random password shared by every account a single test creates.
    """

    return secrets.token_urlsafe(24)


@pytest.fixture
def user(user_password: str) -> UserFactory:
    """
    Return a factory persisting accounts that share the generated password.

    Parameters
    ----------
    user_password : str
        Password every account created by the factory authenticates with.

    Returns
    -------
    UserFactory
        Callable that takes the address, the display name, and whether the
        account may authenticate.
    """

    def create(
        email: str = "ada@example.com",
        full_name: str = "Ada Lovelace",
        is_active: bool = True,
    ) -> User:
        return User.objects.create_user(
            email=email, password=user_password, full_name=full_name, is_active=is_active
        )

    return create
