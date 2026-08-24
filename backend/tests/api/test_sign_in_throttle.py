from http import HTTPStatus
from ipaddress import ip_network
from typing import Protocol, cast

import pytest
from django.conf import settings
from django.test import Client, override_settings

from apps.accounts.api.router import sign_in_throttle
from tests.conftest import ApiPost, ApiResponse, CapturedRecord, UserFactory

LOGIN_URL = "/api/v1/auth/login"
HEALTH_URL = "/api/v1/health"
OPENAPI_URL = "/api/v1/openapi.json"

UNKNOWN_EMAIL = "unknown@example.com"

CLIENT_ADDRESS = "198.51.100.7"
OTHER_CLIENT_ADDRESS = "198.51.100.8"

PROXY_ADDRESS = "127.0.0.1"

THROTTLED_DETAIL = "Too many requests."

DEFAULT_RATE = "5/m"

PERMITTED_ATTEMPTS = sign_in_throttle.permitted_attempts


class SignInAttempt(Protocol):
    """
    Callable posting one rejected sign-in attempt from a stated origin.

    Methods
    -------
    __call__(email=UNKNOWN_EMAIL, client_address=CLIENT_ADDRESS, forwarded=None) -> ApiResponse
        Post a wrong password as a given client, optionally forwarding a chain.
    """

    def __call__(
        self,
        *,
        email: str = ...,
        client_address: str = ...,
        forwarded: str | None = ...,
    ) -> ApiResponse:
        """
        Post a wrong password as a given client, optionally forwarding a chain.

        Parameters
        ----------
        email : str
            Address to submit.
        client_address : str
            Peer address the request appears to come from.
        forwarded : str or None
            ``X-Forwarded-For`` chain to send, or ``None`` to send none.

        Returns
        -------
        ApiResponse
            Response of the login endpoint.
        """

        ...


@pytest.fixture
def sign_in_attempt(user_password: str) -> SignInAttempt:
    """
    Return a callable posting rejected sign-in attempts from a stated origin.

    Parameters
    ----------
    user_password : str
        Password the accounts of the test authenticate with, submitted here
        with a prefix so that every attempt this callable makes is rejected.

    Returns
    -------
    SignInAttempt
        Callable that takes the address, the peer address, and the forwarding
        chain.
    """

    client = Client()

    def attempt(
        *,
        email: str = UNKNOWN_EMAIL,
        client_address: str = CLIENT_ADDRESS,
        forwarded: str | None = None,
    ) -> ApiResponse:
        response = client.post(
            LOGIN_URL,
            data={"email": email, "password": f"wrong-{user_password}"},
            content_type="application/json",
            headers={"X-Forwarded-For": forwarded} if forwarded is not None else {},
            REMOTE_ADDR=client_address,
        )

        return cast(ApiResponse, response)

    return attempt


def exhaust_budget(sign_in_attempt: SignInAttempt, **origin: str) -> None:
    """
    Spend the whole budget of one client without asserting on the answers.

    Parameters
    ----------
    sign_in_attempt : SignInAttempt
        Callable posting a single attempt.
    **origin : str
        Origin keywords, ``client_address`` and ``forwarded``, identifying the
        client whose budget is spent.
    """

    for _attempt in range(PERMITTED_ATTEMPTS):
        sign_in_attempt(**origin)


def test_the_configured_rate_is_the_one_in_force() -> None:
    """
    GIVEN a settings module configuring a rate other than the shipped default
    WHEN the throttle guarding the login endpoint is inspected
    THEN it enforces that rate rather than one written into the code
    """

    assert sign_in_throttle.rate == settings.SIGN_IN_THROTTLE_RATE
    assert sign_in_throttle.rate != DEFAULT_RATE


@pytest.mark.django_db
def test_the_last_permitted_attempt_is_answered_and_the_next_is_throttled(
    sign_in_attempt: SignInAttempt,
) -> None:
    """
    GIVEN a client that has spent all but one of its permitted attempts
    WHEN it makes that attempt and then one more
    THEN the last permitted attempt is rejected on its merits and the next is throttled
    """

    for _attempt in range(PERMITTED_ATTEMPTS - 1):
        sign_in_attempt()

    assert sign_in_attempt().status_code == HTTPStatus.UNAUTHORIZED

    throttled = sign_in_attempt()

    assert throttled.status_code == HTTPStatus.TOO_MANY_REQUESTS
    assert throttled.json() == {"detail": THROTTLED_DETAIL}


@pytest.mark.django_db
def test_the_budget_is_kept_per_client(sign_in_attempt: SignInAttempt) -> None:
    """
    GIVEN a client that has exhausted its budget
    WHEN another client makes its first attempt
    THEN that attempt is answered on its merits, so the counter is not global
    """

    exhaust_budget(sign_in_attempt, client_address=CLIENT_ADDRESS)

    exhausted = sign_in_attempt(client_address=CLIENT_ADDRESS)
    other = sign_in_attempt(client_address=OTHER_CLIENT_ADDRESS)

    assert exhausted.status_code == HTTPStatus.TOO_MANY_REQUESTS
    assert other.status_code == HTTPStatus.UNAUTHORIZED


@pytest.mark.django_db
@override_settings(TRUSTED_PROXY_NETWORKS=[ip_network(PROXY_ADDRESS)])
def test_the_budget_follows_the_forwarded_client_behind_a_trusted_proxy(
    sign_in_attempt: SignInAttempt,
) -> None:
    """
    GIVEN two clients reaching the API through the same trusted proxy
    WHEN one of them exhausts its budget
    THEN only its own attempts are throttled, so one peer is not one bucket
    """

    exhaust_budget(sign_in_attempt, client_address=PROXY_ADDRESS, forwarded=CLIENT_ADDRESS)

    exhausted = sign_in_attempt(client_address=PROXY_ADDRESS, forwarded=CLIENT_ADDRESS)
    other = sign_in_attempt(client_address=PROXY_ADDRESS, forwarded=OTHER_CLIENT_ADDRESS)

    assert exhausted.status_code == HTTPStatus.TOO_MANY_REQUESTS
    assert other.status_code == HTTPStatus.UNAUTHORIZED


@pytest.mark.django_db
def test_a_throttled_answer_does_not_reveal_whether_the_address_exists(
    sign_in_attempt: SignInAttempt, user: UserFactory
) -> None:
    """
    GIVEN one client guessing an existing address and another an unknown one
    WHEN both exhaust their budget
    THEN both are answered with the same status and the same body
    """

    account = user()

    exhaust_budget(sign_in_attempt, client_address=CLIENT_ADDRESS)
    exhaust_budget(sign_in_attempt, client_address=OTHER_CLIENT_ADDRESS)

    existing = sign_in_attempt(email=account.email, client_address=CLIENT_ADDRESS)
    unknown = sign_in_attempt(email=UNKNOWN_EMAIL, client_address=OTHER_CLIENT_ADDRESS)

    assert existing.status_code == unknown.status_code == HTTPStatus.TOO_MANY_REQUESTS
    assert existing.json() == unknown.json()


@pytest.mark.django_db
def test_a_successful_sign_in_spends_the_budget_too(
    api_post: ApiPost, user: UserFactory, user_password: str
) -> None:
    """
    GIVEN an account signing in successfully on every permitted attempt
    WHEN it makes one attempt beyond the budget
    THEN it is throttled, because the throttle counts attempts and not failures
    """

    account = user()

    credentials: dict[str, object] = {"email": account.email, "password": user_password}

    for _attempt in range(PERMITTED_ATTEMPTS):
        assert api_post(LOGIN_URL, credentials).status_code == HTTPStatus.OK

    assert api_post(LOGIN_URL, credentials).status_code == HTTPStatus.TOO_MANY_REQUESTS


@pytest.mark.django_db
def test_the_throttle_is_scoped_to_sign_in(sign_in_attempt: SignInAttempt) -> None:
    """
    GIVEN a client that has exhausted its sign-in budget
    WHEN the same client requests the health endpoint
    THEN the request is served, so the throttle guards sign-in alone
    """

    exhaust_budget(sign_in_attempt, client_address=CLIENT_ADDRESS)

    exhausted = sign_in_attempt(client_address=CLIENT_ADDRESS)
    health = Client().get(HEALTH_URL, REMOTE_ADDR=CLIENT_ADDRESS)

    assert exhausted.status_code == HTTPStatus.TOO_MANY_REQUESTS
    assert health.status_code == HTTPStatus.OK


@pytest.mark.django_db
@override_settings(TRUSTED_PROXY_NETWORKS=[ip_network(PROXY_ADDRESS)])
def test_a_rejected_attempt_is_logged_against_the_identified_client(
    sign_in_attempt: SignInAttempt, loguru_records: list[CapturedRecord]
) -> None:
    """
    GIVEN a rejected attempt reaching the API through a trusted proxy
    WHEN the operator trail is read
    THEN it names the forwarded client and the peer it arrived from
    """

    sign_in_attempt(client_address=PROXY_ADDRESS, forwarded=CLIENT_ADDRESS)

    warnings = [message for level, message, _ in loguru_records if level == "WARNING"]

    assert any(CLIENT_ADDRESS in message and PROXY_ADDRESS in message for message in warnings)


def test_the_throttled_answer_is_part_of_the_published_contract() -> None:
    """
    GIVEN the OpenAPI document the API publishes
    WHEN the login operation is read from it
    THEN it declares the throttled answer a client has to handle
    """

    document = Client().get(OPENAPI_URL).json()

    responses = document["paths"]["/api/v1/auth/login"]["post"]["responses"]

    assert str(HTTPStatus.TOO_MANY_REQUESTS.value) in responses
