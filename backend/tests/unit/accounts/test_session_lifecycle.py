import secrets
from datetime import datetime, timedelta
from io import StringIO

import pytest
from django.contrib.auth.forms import AdminPasswordChangeForm
from django.contrib.auth.management.commands.changepassword import (
    Command as ChangePasswordCommand,
)
from django.core.management import call_command
from django.db import DatabaseError
from django.db.models import QuerySet
from django.test import override_settings
from django.utils import timezone
from pytest_django.fixtures import DjangoAssertNumQueries

from apps.accounts import signals
from apps.accounts.application.services import (
    delete_expired_sessions,
    issue_session,
    resolve_session,
    revoke_session,
)
from apps.accounts.models import AuthSession, User
from apps.accounts.tasks import purge_expired_sessions
from tests.conftest import CapturedRecord, UserFactory

MD5_HASHER = "django.contrib.auth.hashers.MD5PasswordHasher"
PBKDF2_HASHER = "django.contrib.auth.hashers.PBKDF2PasswordHasher"


def fail_to_revoke(sessions: QuerySet[AuthSession]) -> int:
    """
    Stand in for the revocation and fail the way a lost connection would.

    Parameters
    ----------
    sessions : QuerySet of AuthSession
        Sessions the receiver asked to revoke, left untouched.

    Raises
    ------
    DatabaseError
        Always, so a caller can prove the write that triggered it rolls back.
    """

    raise DatabaseError(f"Revoking {sessions.model.__name__} rows failed.")


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
def test_disabling_password_authentication_in_the_admin_form_revokes_the_sessions(
    user: UserFactory,
) -> None:
    """
    GIVEN a current session of an account
    WHEN an administrator disables password-based authentication in the admin form
    THEN the session no longer authenticates
    """

    account = user()

    issued = issue_session(account)
    form = AdminPasswordChangeForm(account, {"usable_password": "false"})

    assert form.is_valid()

    form.save()

    assert account.has_usable_password() is False
    assert resolve_session(issued.token) is None


@pytest.mark.django_db
def test_changing_a_password_with_the_management_command_revokes_the_sessions(
    user: UserFactory, user_password: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    GIVEN a current session of an account
    WHEN an operator changes its password with the changepassword command
    THEN the session no longer authenticates
    """

    account = user()

    issued = issue_session(account)

    monkeypatch.setattr(ChangePasswordCommand, "_get_pass", lambda *_args: f"{user_password}-typed")

    call_command("changepassword", account.email, stdout=StringIO())

    assert resolve_session(issued.token) is None


@pytest.mark.django_db
def test_setting_a_password_without_writing_that_column_keeps_the_sessions(
    user: UserFactory, user_password: str
) -> None:
    """
    GIVEN a current session of an account whose new password is never written
    WHEN a save writes another column only
    THEN the session still authenticates with the stored password
    """

    account = user()

    issued = issue_session(account)

    account.set_password(f"{user_password}-rotated")
    account.save(update_fields=["full_name"])

    assert User.objects.get(pk=account.pk).check_password(user_password) is True
    assert resolve_session(issued.token) == account


@pytest.mark.django_db
def test_a_failed_revocation_rolls_back_the_password_it_was_triggered_by(
    user: UserFactory, user_password: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    GIVEN an account whose session revocation is going to fail
    WHEN its password is replaced
    THEN the failure escapes and the stored password is the one it had
    """

    account = user()

    issue_session(account)
    monkeypatch.setattr(signals, "revoke_sessions", fail_to_revoke)
    account.set_password(f"{user_password}-rotated")

    with pytest.raises(DatabaseError):
        account.save()

    assert User.objects.get(pk=account.pk).check_password(user_password) is True


@pytest.mark.django_db
def test_a_credential_change_reports_how_many_sessions_it_revoked(
    user: UserFactory, user_password: str, loguru_records: list[CapturedRecord]
) -> None:
    """
    GIVEN an account with two current sessions
    WHEN its password is replaced
    THEN one record reports the two sessions the change revoked
    """

    account = user()

    issue_session(account)
    issue_session(account)

    account.set_password(f"{user_password}-rotated")
    account.save()

    assert [message for _, message, _ in loguru_records if message.startswith("Revoked")] == [
        f"Revoked 2 authentication session(s) of account {account.pk} after a credential change."
    ]


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
    original_hash = account.password

    issued = issue_session(account)

    with override_settings(PASSWORD_HASHERS=[MD5_HASHER, PBKDF2_HASHER]):
        assert account.check_password(user_password) is True

    account.refresh_from_db()

    assert account.password != original_hash
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


@pytest.mark.django_db
def test_purging_keeps_a_session_expiring_just_after_the_evaluated_instant(
    user: UserFactory,
) -> None:
    """
    GIVEN a session whose expiry is one microsecond after the evaluated instant
    WHEN expired sessions are deleted at that instant
    THEN the session survives, as it still authenticates
    """

    account = user()
    at = timezone.now()

    session = store_session(account, expires_at=at + timedelta(microseconds=1))

    assert delete_expired_sessions(at) == 0
    assert AuthSession.objects.get(pk=session.pk).is_usable(at) is True


@pytest.mark.django_db
def test_purging_removes_every_expired_session_with_one_statement(
    user: UserFactory, django_assert_num_queries: DjangoAssertNumQueries
) -> None:
    """
    GIVEN three sessions past their expiry
    WHEN expired sessions are deleted
    THEN one statement removes them all, so no run can race a row of another
    """

    account = user()
    at = timezone.now()
    expired_count = 3

    for age in range(1, expired_count + 1):
        store_session(account, expires_at=at - timedelta(days=age))

    with django_assert_num_queries(1):
        assert delete_expired_sessions(at) == expired_count
