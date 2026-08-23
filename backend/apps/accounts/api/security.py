import logging
from typing import cast

from django.http import HttpRequest
from ninja.security import HttpBearer

from apps.accounts.application.services import resolve_session
from apps.accounts.models import User

logger = logging.getLogger(__name__)


class AuthenticatedRequest(HttpRequest):
    """
    Request whose bearer token has already been resolved to an account.

    Django Ninja attaches the value returned by an authentication callable to
    ``request.auth`` at runtime, and no Django class declares that attribute.
    Annotating a handler with this subclass names it, together with the raw
    token the operation needs in order to revoke the very session it was
    presented with.

    Attributes
    ----------
    auth : User
        Account the presented bearer token authenticates.
    auth_token : str
        Raw bearer token that authenticated the request.
    """

    auth: User
    auth_token: str


class SessionTokenAuth(HttpBearer):
    """
    Bearer authentication backed by the server-side session table.

    Methods
    -------
    authenticate(request, token) -> User | None
        Resolve a bearer token to the account it authenticates.
    """

    def authenticate(self, request: HttpRequest, token: str) -> User | None:
        """
        Resolve a bearer token to the account it authenticates.

        Parameters
        ----------
        request : HttpRequest
            Inbound request, whose origin is logged at debug level when the
            token is rejected and which carries the token onwards on success.
        token : str
            Raw bearer token taken from the ``Authorization`` header.

        Returns
        -------
        User or None
            Authenticated account, or ``None`` to answer HTTP 401.
        """

        user = resolve_session(token)

        if user is None:
            logger.debug(
                "Rejected a bearer token from %s", request.META.get("REMOTE_ADDR", "unknown")
            )

            return None

        cast(AuthenticatedRequest, request).auth_token = token

        return user
