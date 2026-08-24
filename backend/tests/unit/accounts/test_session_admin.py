import pytest
from django.contrib import admin
from django.contrib.messages.middleware import MessageMiddleware
from django.contrib.sessions.middleware import SessionMiddleware
from django.http import HttpRequest, HttpResponse
from django.test import RequestFactory

from apps.accounts.admin import AuthSessionAdmin
from apps.accounts.application.services import issue_session, revoke_session
from apps.accounts.models import AuthSession, User
from tests.conftest import CapturedRecord, UserFactory

SESSION_FIELDS = ("user", "token_digest", "created_at", "expires_at", "revoked_at")


@pytest.fixture
def session_admin() -> AuthSessionAdmin:
    """
    Return the session admin surface bound to the default admin site.

    Returns
    -------
    AuthSessionAdmin
        Admin surface under test.
    """

    return AuthSessionAdmin(AuthSession, admin.site)


@pytest.fixture
def operator(user: UserFactory) -> User:
    """
    Return a staff account standing in for an admin operator.

    Parameters
    ----------
    user : UserFactory
        Factory persisting accounts for the test.

    Returns
    -------
    User
        Account allowed into the admin.
    """

    account = user(email="operator@example.com")
    account.is_staff = True

    account.save(update_fields=["is_staff"])

    return account


@pytest.fixture
def admin_request(operator: User) -> HttpRequest:
    """
    Return an admin request carrying an operator and a message store.

    Parameters
    ----------
    operator : User
        Staff account the request is attributed to.

    Returns
    -------
    HttpRequest
        Request the admin surface can be exercised with.
    """

    request = RequestFactory().post("/admin/accounts/authsession/")
    request.user = operator

    SessionMiddleware(lambda _request: HttpResponse()).process_request(request)
    MessageMiddleware(lambda _request: HttpResponse()).process_request(request)

    return request


@pytest.mark.django_db
def test_a_session_cannot_be_added_through_the_admin(
    session_admin: AuthSessionAdmin, admin_request: HttpRequest
) -> None:
    """
    GIVEN an operator inside the session admin
    WHEN the add permission is evaluated
    THEN it is refused, because a session is issued by signing in
    """

    assert session_admin.has_add_permission(admin_request) is False


@pytest.mark.django_db
def test_every_session_field_is_read_only_in_the_admin(
    session_admin: AuthSessionAdmin, admin_request: HttpRequest
) -> None:
    """
    GIVEN an operator opening the change form of a session
    WHEN the form is built
    THEN every field is read-only and the form exposes none of them
    """

    assert set(session_admin.get_readonly_fields(admin_request)) == set(SESSION_FIELDS)
    assert not session_admin.get_form(admin_request).base_fields


@pytest.mark.django_db
def test_the_admin_action_revokes_current_sessions_and_keeps_the_first_instant(
    session_admin: AuthSessionAdmin, admin_request: HttpRequest, user: UserFactory
) -> None:
    """
    GIVEN a current session and a session revoked earlier
    WHEN an operator runs the revoke action over both
    THEN the current one is revoked and the earlier instant is left untouched
    """

    account = user()

    issue_session(account)
    revoke_session(issue_session(account).token)

    revoked_session = AuthSession.objects.get(revoked_at__isnull=False)
    current_session = AuthSession.objects.get(revoked_at__isnull=True)
    first_revocation = revoked_session.revoked_at

    session_admin.revoke_selected_sessions(admin_request, AuthSession.objects.all())

    revoked_session.refresh_from_db()
    current_session.refresh_from_db()

    assert current_session.revoked_at is not None
    assert revoked_session.revoked_at == first_revocation


@pytest.mark.django_db
def test_the_admin_action_records_the_operator_and_the_locked_out_accounts(
    session_admin: AuthSessionAdmin,
    admin_request: HttpRequest,
    operator: User,
    user: UserFactory,
    loguru_records: list[CapturedRecord],
) -> None:
    """
    GIVEN an operator revoking the two sessions of an account
    WHEN the operator trail is read
    THEN it names the count, the account locked out, and the operator
    """

    account = user()

    issue_session(account)
    issue_session(account)

    session_admin.revoke_selected_sessions(admin_request, AuthSession.objects.all())

    trail = [message for level, message, _ in loguru_records if level == "INFO"]
    revocation = (
        f"Revoked 2 authentication session(s) of account(s) [{account.pk}] "
        f"for operator {operator.pk}"
    )

    assert revocation in trail
