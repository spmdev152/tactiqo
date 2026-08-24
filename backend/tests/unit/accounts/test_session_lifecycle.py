import secrets
from datetime import datetime, timedelta

import pytest
from django.contrib.auth.forms import AdminPasswordChangeForm
from django.test import override_settings
from django.utils import timezone

from apps.accounts.application.services import (
    delete_expired_sessions,
    issue_session,
    resolve_session,
    revoke_session,
)
from apps.accounts.models import AuthSession, User
from apps.accounts.tasks import purge_expired_sessions
from tests.conftest import UserFactory

MD5_HASHER = "django.contrib.auth.hashers.MD5PasswordHasher"
PBKDF2_HASHER = "django.contrib.auth.hashers.PBKDF2PasswordHasher"


def store_session(
    account: User, expires_at: datetime, revoked_at: datetime | None = None
) -> AuthSession:
    """
    Persist a session row with an explicit expiry and revocation instant.

    Parameters
    ----------
    account : User
        Account the session authenticates.
    expires_at : datetime
        Instant from which the session stops authenticating.
    revoked_at : datetime or None
        Instant the session was revoked, ``None`` while it is still current.

    Returns
    -------
    AuthSession
        Persisted session, whose digest matches no issued token.
    """

    return AuthSession.objects.create(
        user=account,
        token_digest=secrets.token_hex(32),
        expires_at=expires_at,
        revoked_at=revoked_at,
    )


@pytest.mark.django_db
def test_changing_a_password_revokes_every_session_of_the_account(
    user: UserFactory, user_password: str
) -> None:
    """
    GIVEN an account with two current sessions
    WHEN its password is replaced and the account is saved
    THEN neither session authenticates any more
    """

    account = user()

    first = issue_session(account)
    second = issue_session(account)

    account.set_password(f"{user_password}-rotated")
    account.save()

    assert resolve_session(first.token) is None
    assert resolve_session(second.token) is None


@pytest.mark.django_db
def test_changing_a_password_revokes_the_sessions_when_only_that_column_is_written(
    user: UserFactory, user_password: str
) -> None:
    """
    GIVEN a current session of an account
    WHEN its password is replaced and only that column is written
    THEN the session no longer authenticates
    """

    account = user()

    issued = issue_session(account)

    account.set_password(f"{user_password}-rotated")
    account.save(update_fields=["password"])

    assert resolve_session(issued.token) is None


@pytest.mark.django_db
def test_changing_a_password_through_the_admin_form_revokes_the_sessions(
    user: UserFactory, user_password: str
) -> None:
    """
    GIVEN a current session of an account
    WHEN an administrator sets a new password through the admin form
    THEN the session no longer authenticates
    """

    account = user()

    issued = issue_session(account)
    rotated = f"{user_password}-rotated"
    form = AdminPasswordChangeForm(account, {"password1": rotated, "password2": rotated})

    assert form.is_valid()

    form.save()

    assert resolve_session(issued.token) is None


@pytest.mark.django_db
def test_changing_a_password_leaves_the_sessions_of_another_account_alone(
    user: UserFactory, user_password: str
) -> None:
    """
    GIVEN a current session for each of two accounts
    WHEN the password of one account is replaced
    THEN the session of the other account still authenticates
    """

    rotated_account = user()
    other_account = user(email="grace@example.com")

    rotated = issue_session(rotated_account)
    untouched = issue_session(other_account)

    rotated_account.set_password(f"{user_password}-rotated")
    rotated_account.save()

    assert resolve_session(rotated.token) is None
    assert resolve_session(untouched.token) == other_account


@pytest.mark.django_db
def test_changing_a_password_keeps_the_first_revocation_instant(
    user: UserFactory, user_password: str
) -> None:
    """
    GIVEN an account with one revoked session and one current session
    WHEN its password is replaced
    THEN the current session is revoked and the revoked one keeps its instant
    """

    account = user()

    revoked = issue_session(account)
    current = issue_session(account)

    assert revoke_session(revoked.token) is True

    first_revocation = AuthSession.objects.get(revoked_at__isnull=False).revoked_at

    account.set_password(f"{user_password}-rotated")
    account.save()

    assert resolve_session(current.token) is None
    assert AuthSession.objects.filter(revoked_at=first_revocation).count() == 1


@pytest.mark.django_db
def test_saving_an_account_without_a_new_password_keeps_its_sessions(user: UserFactory) -> None:
    """
    GIVEN a current session of an account
    WHEN another column of the account is written
    THEN the session still authenticates
    """

    account = user()

    issued = issue_session(account)

    account.full_name = "Ada Byron"
    account.save()

    assert resolve_session(issued.token) == account


@pytest.mark.django_db
def test_upgrading_the_hash_of_a_verified_password_keeps_the_sessions(
    user: UserFactory, user_password: str
) -> None:
    """
    GIVEN a current session of an account whose password hash is outdated
    WHEN the password is verified and its hash is upgraded in place
    THEN the stored hash changes and the session still authenticates
    """

    account = user()

    issued = issue_session(account)

    with override_settings(PASSWORD_HASHERS=[MD5_HASHER, PBKDF2_HASHER]):
        assert account.check_password(user_password) is True

    account.refresh_from_db()

    assert account.password.startswith("md5$")
    assert resolve_session(issued.token) == account


@pytest.mark.django_db
def test_purging_deletes_the_sessions_past_their_expiry(user: UserFactory) -> None:
    """
    GIVEN expired sessions, a current one, and a revoked one still unexpired
    WHEN the purge task runs
    THEN only the expired sessions are deleted
    """

    account = user()
    now = timezone.now()

    expired = store_session(account, expires_at=now - timedelta(seconds=1))

    expired_and_revoked = store_session(
        account, expires_at=now - timedelta(days=1), revoked_at=now - timedelta(days=2)
    )

    current = store_session(account, expires_at=now + timedelta(days=1))
    revoked = store_session(account, expires_at=now + timedelta(days=1), revoked_at=now)
    expired_pks = {expired.pk, expired_and_revoked.pk}

    assert purge_expired_sessions() == len(expired_pks)
    assert set(AuthSession.objects.values_list("pk", flat=True)) == {current.pk, revoked.pk}


@pytest.mark.django_db
def test_purging_keeps_the_revocation_instant_of_a_session_it_spares(user: UserFactory) -> None:
    """
    GIVEN a revoked session whose expiry has not passed
    WHEN the purge task runs
    THEN the session survives with its revocation instant untouched
    """

    account = user()
    now = timezone.now()

    revoked = store_session(account, expires_at=now + timedelta(days=1), revoked_at=now)

    assert purge_expired_sessions() == 0
    assert AuthSession.objects.get(pk=revoked.pk).revoked_at == revoked.revoked_at


@pytest.mark.django_db
def test_purging_a_second_time_deletes_nothing_more(user: UserFactory) -> None:
    """
    GIVEN a purge that already deleted every expired session
    WHEN the purge task runs again
    THEN it deletes nothing and the remaining sessions are untouched
    """

    account = user()

    issued = issue_session(account)

    store_session(account, expires_at=timezone.now() - timedelta(seconds=1))

    assert purge_expired_sessions() == 1
    assert purge_expired_sessions() == 0
    assert resolve_session(issued.token) == account


@pytest.mark.django_db
def test_purging_deletes_a_session_expiring_exactly_at_the_evaluated_instant(
    user: UserFactory,
) -> None:
    """
    GIVEN a session whose expiry is the instant the purge evaluates
    WHEN expired sessions are deleted at that instant
    THEN the session is deleted, as it already stopped authenticating
    """

    account = user()
    expiry = timezone.now()

    session = store_session(account, expires_at=expiry)

    assert session.is_usable(expiry) is False
    assert delete_expired_sessions(expiry) == 1
    assert AuthSession.objects.exists() is False
