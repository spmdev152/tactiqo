import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta

from django.contrib.auth import authenticate
from django.utils import timezone

from apps.accounts.domain.exceptions import InvalidCredentialsError
from apps.accounts.models import AuthSession, User, normalize_email

SESSION_LIFETIME = timedelta(days=14)
TOKEN_BYTES = 32


@dataclass(frozen=True)
class IssuedSession:
    """
    Freshly issued session, the only moment the raw token exists.

    Attributes
    ----------
    token : str
        Opaque bearer token handed to the client and never stored as is.
    expires_at : datetime
        Instant from which the token stops authenticating.
    user : User
        Account the token authenticates.
    """

    token: str
    expires_at: datetime
    user: User


def _digest(token: str) -> str:
    """
    Return the lookup digest of a bearer token.

    Parameters
    ----------
    token : str
        Raw bearer token as issued or as presented by a client.

    Returns
    -------
    str
        Hexadecimal SHA-256 of the token.
    """

    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def issue_session(user: User) -> IssuedSession:
    """
    Issue a bearer token for an account and persist only its digest.

    Parameters
    ----------
    user : User
        Account to authenticate for the lifetime of the session.

    Returns
    -------
    IssuedSession
        Raw token, its expiry, and the account it authenticates.
    """

    token = secrets.token_urlsafe(TOKEN_BYTES)
    expires_at = timezone.now() + SESSION_LIFETIME

    AuthSession.objects.create(user=user, token_digest=_digest(token), expires_at=expires_at)

    return IssuedSession(token=token, expires_at=expires_at, user=user)


def sign_in(email: str, password: str) -> IssuedSession:
    """
    Authenticate an account by email and password and open a session for it.

    Authentication goes through ``django.contrib.auth.authenticate``, whose
    ``ModelBackend`` already rejects a deactivated account and already runs a
    dummy password hash for an unknown address. That constant-work path is the
    timing mitigation that keeps the endpoint from leaking which addresses
    exist, so it is deliberately not reimplemented here.

    Parameters
    ----------
    email : str
        Address submitted by the client, normalized to the stored form.
    password : str
        Raw password submitted by the client.

    Returns
    -------
    IssuedSession
        Session opened for the authenticated account.

    Raises
    ------
    InvalidCredentialsError
        If the address is unknown, the password is wrong, or the account is
        deactivated.
    """

    user = authenticate(username=normalize_email(email), password=password)

    if not isinstance(user, User):
        raise InvalidCredentialsError("Authentication did not resolve to an active account.")

    return issue_session(user)


def resolve_session(token: str) -> User | None:
    """
    Return the account a bearer token authenticates.

    Parameters
    ----------
    token : str
        Raw bearer token as presented by a client, trusted for nothing.

    Returns
    -------
    User or None
        Authenticated account, or ``None`` when the token is empty, unknown,
        expired, revoked, or attached to a deactivated account.
    """

    if not token:
        return None

    session = AuthSession.objects.select_related("user").filter(token_digest=_digest(token)).first()

    if session is None or not session.is_usable(timezone.now()):
        return None

    user: User = session.user

    return user if user.is_active else None


def revoke_session(token: str) -> bool:
    """
    Revoke the session a bearer token identifies.

    Revoking twice is a no-op: the update only matches a session that has not
    been revoked yet, so the first revocation instant is never moved.

    Parameters
    ----------
    token : str
        Raw bearer token whose session must stop authenticating.

    Returns
    -------
    bool
        ``True`` when a current session was revoked by this call.
    """

    if not token:
        return False

    revoked_count = AuthSession.objects.filter(
        token_digest=_digest(token), revoked_at__isnull=True
    ).update(revoked_at=timezone.now())

    return revoked_count > 0
