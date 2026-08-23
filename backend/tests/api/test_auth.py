from datetime import UTC, datetime
from http import HTTPStatus

import pytest
from django.test import Client

from apps.accounts.api.router import INVALID_CREDENTIALS_DETAIL
from tests.conftest import ApiGet, ApiPost, UserFactory

LOGIN_URL = "/api/v1/auth/login"
ME_URL = "/api/v1/auth/me"
LOGOUT_URL = "/api/v1/auth/logout"

UNKNOWN_EMAIL = "unknown@example.com"


@pytest.mark.django_db
def test_login_returns_a_token_and_the_signed_in_account(
    api_post: ApiPost, user: UserFactory, user_password: str
) -> None:
    """
    GIVEN an active account and its password
    WHEN they are posted to the login endpoint
    THEN the API answers HTTP 200 with a token, an expiry, and the account
    """

    account = user()

    response = api_post(LOGIN_URL, {"email": account.email, "password": user_password})

    assert response.status_code == HTTPStatus.OK

    body = response.json()

    assert body["token"]
    assert body["expires_at"]

    assert body["user"] == {
        "id": account.pk,
        "email": account.email,
        "full_name": account.full_name,
    }


@pytest.mark.django_db
def test_login_serializes_the_expiry_as_a_zulu_timestamp(
    api_post: ApiPost, user: UserFactory, user_password: str
) -> None:
    """
    GIVEN an active account signing in successfully
    WHEN the expiry of the issued session is read off the wire
    THEN it is a UTC instant suffixed with ``Z`` rather than a numeric offset
    """

    account = user()

    response = api_post(LOGIN_URL, {"email": account.email, "password": user_password})

    expires_at = str(response.json()["expires_at"])

    assert expires_at.endswith("Z")
    assert "+" not in expires_at
    assert datetime.fromisoformat(expires_at).tzinfo == UTC


@pytest.mark.django_db
def test_login_accepts_an_account_without_a_display_name(
    api_post: ApiPost, user: UserFactory, user_password: str
) -> None:
    """
    GIVEN an active account whose display name is empty
    WHEN it signs in
    THEN the account projection carries an empty full name
    """

    account = user(full_name="")

    response = api_post(LOGIN_URL, {"email": account.email, "password": user_password})

    assert response.status_code == HTTPStatus.OK

    assert response.json()["user"] == {
        "id": account.pk,
        "email": account.email,
        "full_name": "",
    }


@pytest.mark.django_db
def test_login_rejects_an_unknown_address_with_the_shared_detail(
    api_post: ApiPost, user_password: str
) -> None:
    """
    GIVEN no account for the submitted address
    WHEN credentials are posted to the login endpoint
    THEN the API answers HTTP 401 with the shared rejection detail
    """

    response = api_post(LOGIN_URL, {"email": UNKNOWN_EMAIL, "password": user_password})

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json() == {"detail": INVALID_CREDENTIALS_DETAIL}


@pytest.mark.django_db
def test_login_rejects_a_wrong_password_with_the_shared_detail(
    api_post: ApiPost, user: UserFactory, user_password: str
) -> None:
    """
    GIVEN an active account
    WHEN another password is posted for it
    THEN the API answers HTTP 401 with the shared rejection detail
    """

    account = user()

    response = api_post(LOGIN_URL, {"email": account.email, "password": f"wrong-{user_password}"})

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json() == {"detail": INVALID_CREDENTIALS_DETAIL}


@pytest.mark.django_db
def test_login_rejects_a_deactivated_account_with_the_shared_detail(
    api_post: ApiPost, user: UserFactory, user_password: str
) -> None:
    """
    GIVEN an account whose active flag is unset
    WHEN its correct credentials are posted
    THEN the API answers HTTP 401 with the shared rejection detail
    """

    account = user(is_active=False)

    response = api_post(LOGIN_URL, {"email": account.email, "password": user_password})

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json() == {"detail": INVALID_CREDENTIALS_DETAIL}


@pytest.mark.django_db
def test_login_rejects_a_body_missing_the_password(api_post: ApiPost) -> None:
    """
    GIVEN a body carrying an address but no password
    WHEN it is posted to the login endpoint
    THEN the API answers HTTP 422 from its own request validation
    """

    response = api_post(LOGIN_URL, {"email": UNKNOWN_EMAIL})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


@pytest.mark.django_db
def test_me_returns_the_account_the_token_authenticates(
    api_get: ApiGet, api_post: ApiPost, user: UserFactory, user_password: str
) -> None:
    """
    GIVEN a token obtained from a successful login
    WHEN it is presented to the current-account endpoint
    THEN the API answers HTTP 200 with the account projection
    """

    account = user()

    token = api_post(LOGIN_URL, {"email": account.email, "password": user_password}).json()["token"]

    response = api_get(ME_URL, token=str(token))

    assert response.status_code == HTTPStatus.OK

    assert response.json() == {
        "id": account.pk,
        "email": account.email,
        "full_name": account.full_name,
    }


@pytest.mark.django_db
def test_me_rejects_a_request_without_a_credential(api_get: ApiGet) -> None:
    """
    GIVEN no Authorization header
    WHEN the current-account endpoint is requested
    THEN the API answers HTTP 401
    """

    response = api_get(ME_URL)

    assert response.status_code == HTTPStatus.UNAUTHORIZED


@pytest.mark.django_db
def test_me_rejects_a_credential_of_another_scheme() -> None:
    """
    GIVEN an Authorization header announcing a scheme the API does not accept
    WHEN the current-account endpoint is requested
    THEN the API answers HTTP 401
    """

    response = Client().get(ME_URL, headers={"Authorization": "Basic bm90LWEtYmVhcmVy"})

    assert response.status_code == HTTPStatus.UNAUTHORIZED


@pytest.mark.django_db
def test_me_rejects_a_revoked_token(
    api_get: ApiGet, api_post: ApiPost, user: UserFactory, user_password: str
) -> None:
    """
    GIVEN a token whose session has been revoked by a logout
    WHEN it is presented to the current-account endpoint
    THEN the API answers HTTP 401
    """

    account = user()

    token = str(
        api_post(LOGIN_URL, {"email": account.email, "password": user_password}).json()["token"]
    )

    api_post(LOGOUT_URL, token=token)

    response = api_get(ME_URL, token=token)

    assert response.status_code == HTTPStatus.UNAUTHORIZED


@pytest.mark.django_db
def test_logout_revokes_the_presented_session(
    api_post: ApiPost, user: UserFactory, user_password: str
) -> None:
    """
    GIVEN a token obtained from a successful login
    WHEN it is presented to the logout endpoint
    THEN the API answers an empty HTTP 204 and the token stops being accepted
    """

    account = user()

    token = str(
        api_post(LOGIN_URL, {"email": account.email, "password": user_password}).json()["token"]
    )

    response = api_post(LOGOUT_URL, token=token)

    assert response.status_code == HTTPStatus.NO_CONTENT
    assert response.content == b""

    assert api_post(LOGOUT_URL, token=token).status_code == HTTPStatus.UNAUTHORIZED


@pytest.mark.django_db
def test_logout_rejects_a_request_without_a_credential(api_post: ApiPost) -> None:
    """
    GIVEN no Authorization header
    WHEN the logout endpoint is requested
    THEN the API answers HTTP 401
    """

    response = api_post(LOGOUT_URL)

    assert response.status_code == HTTPStatus.UNAUTHORIZED
