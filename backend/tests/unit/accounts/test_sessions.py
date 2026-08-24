import hashlib
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.application.services import (
    SESSION_LIFETIME,
    issue_session,
    resolve_session,
    revoke_session,
    sign_in,
)
from apps.accounts.domain.exceptions import InvalidCredentialsError
from apps.accounts.models import AuthSession
from tests.conftest import UserFactory

UNKNOWN_EMAIL = "unknown@example.com"
UNMATCHED_CREDENTIAL = "not-a-session-credential"


@pytest.mark.django_db
def test_signing_in_with_valid_credentials_opens_a_session(
    user: UserFactory, user_password: str
) -> None:
    """
    GIVEN an active account and its password
    WHEN the account signs in
    THEN a session is issued for it with an expiry one lifetime away
    """

    account = user()
    before = timezone.now()

    issued = sign_in(account.email, user_password)

    assert issued.user == account
    assert issued.token
    assert before + SESSION_LIFETIME <= issued.expires_at <= timezone.now() + SESSION_LIFETIME


@pytest.mark.django_db
def test_signing_in_accepts_an_address_typed_in_another_case(
    user: UserFactory, user_password: str
) -> None:
    """
    GIVEN an active account whose stored address is lowercase
    WHEN the same address is submitted in upper case
    THEN the sign-in succeeds because the service normalizes the input
    """

    account = user()

    issued = sign_in(account.email.upper(), user_password)

    assert issued.user == account


@pytest.mark.django_db
def test_signing_in_with_an_unknown_address_is_rejected(user_password: str) -> None:
    """
    GIVEN no account for the submitted address
    WHEN a sign-in is attempted
    THEN the service raises the shared invalid-credentials error
    """

    with pytest.raises(InvalidCredentialsError):
        sign_in(UNKNOWN_EMAIL, user_password)


@pytest.mark.django_db
def test_signing_in_with_a_wrong_password_is_rejected(
    user: UserFactory, user_password: str
) -> None:
    """
    GIVEN an active account
    WHEN a sign-in is attempted with another password
    THEN the service raises the shared invalid-credentials error
    """

    account = user()

    with pytest.raises(InvalidCredentialsError):
        sign_in(account.email, f"wrong-{user_password}")


@pytest.mark.django_db
def test_signing_in_as_a_deactivated_account_is_rejected(
    user: UserFactory, user_password: str
) -> None:
    """
    GIVEN an account whose active flag is unset
    WHEN it signs in with the correct password
    THEN the service raises the shared invalid-credentials error
    """

    account = user(is_active=False)

    with pytest.raises(InvalidCredentialsError):
        sign_in(account.email, user_password)


@pytest.mark.django_db
def test_a_session_stores_only_the_digest_of_its_token(user: UserFactory) -> None:
    """
    GIVEN a session issued for an account
    WHEN the stored row is read back
    THEN it holds the SHA-256 of the token and never the token itself
    """

    issued = issue_session(user())

    session = AuthSession.objects.get()

    assert issued.token not in session.token_digest
    assert session.token_digest == hashlib.sha256(issued.token.encode("utf-8")).hexdigest()


@pytest.mark.django_db
def test_an_issued_session_keeps_its_raw_token_out_of_its_representation(
    user: UserFactory,
) -> None:
    """
    GIVEN a session issued for an account
    WHEN the issued session is rendered by ``repr``
    THEN the raw token does not appear in the rendering
    """

    issued = issue_session(user())

    assert issued.token not in repr(issued)


@pytest.mark.django_db
def test_resolving_a_current_token_returns_its_account(user: UserFactory) -> None:
    """
    GIVEN a session issued for an account
    WHEN its token is resolved
    THEN the account the token authenticates is returned
    """

    account = user()

    issued = issue_session(account)

    assert resolve_session(issued.token) == account


@pytest.mark.django_db
@pytest.mark.parametrize("presented_token", ["", UNMATCHED_CREDENTIAL])
def test_resolving_a_token_no_session_matches_returns_nothing(presented_token: str) -> None:
    """
    GIVEN no session matching the presented token
    WHEN the token is resolved
    THEN nothing is returned and no exception escapes
    """

    assert resolve_session(presented_token) is None


@pytest.mark.django_db
def test_resolving_an_expired_token_returns_nothing(user: UserFactory) -> None:
    """
    GIVEN a session whose expiry has passed
    WHEN its token is resolved
    THEN nothing is returned
    """

    issued = issue_session(user())

    AuthSession.objects.all().update(expires_at=timezone.now() - timedelta(seconds=1))

    assert resolve_session(issued.token) is None


@pytest.mark.django_db
def test_resolving_a_revoked_token_returns_nothing(user: UserFactory) -> None:
    """
    GIVEN a session that has been revoked
    WHEN its token is resolved
    THEN nothing is returned
    """

    issued = issue_session(user())

    revoke_session(issued.token)

    assert resolve_session(issued.token) is None


@pytest.mark.django_db
def test_resolving_a_token_of_a_deactivated_account_returns_nothing(user: UserFactory) -> None:
    """
    GIVEN a current session whose account has since been deactivated
    WHEN its token is resolved
    THEN nothing is returned
    """

    account = user()

    issued = issue_session(account)

    account.is_active = False
    account.save(update_fields=["is_active"])

    assert resolve_session(issued.token) is None


@pytest.mark.django_db
def test_revoking_a_session_twice_keeps_the_first_revocation_instant(user: UserFactory) -> None:
    """
    GIVEN a session revoked once
    WHEN it is revoked again
    THEN the second call reports nothing revoked and the instant is unchanged
    """

    issued = issue_session(user())

    assert revoke_session(issued.token) is True

    first_revocation = AuthSession.objects.get().revoked_at

    assert revoke_session(issued.token) is False
    assert AuthSession.objects.get().revoked_at == first_revocation


@pytest.mark.django_db
@pytest.mark.parametrize("presented_token", ["", UNMATCHED_CREDENTIAL])
def test_revoking_a_token_no_session_matches_reports_nothing_revoked(
    presented_token: str,
) -> None:
    """
    GIVEN no session matching the presented token
    WHEN the token is revoked
    THEN the call reports that nothing was revoked
    """

    assert revoke_session(presented_token) is False
