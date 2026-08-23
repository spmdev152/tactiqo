import logging
from http import HTTPStatus

from django.http import HttpRequest
from ninja import Router, Status

from apps.accounts.api.schemas import ErrorResponse, LoginRequest, LoginResponse, UserResponse
from apps.accounts.api.security import AuthenticatedRequest, SessionTokenAuth
from apps.accounts.application.services import revoke_session, sign_in
from apps.accounts.domain.exceptions import InvalidCredentialsError

logger = logging.getLogger(__name__)

INVALID_CREDENTIALS_DETAIL = "Invalid email or password."

router = Router(tags=["auth"])
session_token_auth = SessionTokenAuth()


@router.post(
    "/login",
    response={HTTPStatus.OK: LoginResponse, HTTPStatus.UNAUTHORIZED: ErrorResponse},
    summary="Open a session from an email address and a password",
)
def login(
    request: HttpRequest, payload: LoginRequest
) -> Status[LoginResponse] | Status[ErrorResponse]:
    """
    Exchange credentials for an opaque bearer token.

    Every rejection answers with the same status and the same detail, whether
    the address is unknown, the password is wrong, or the account is
    deactivated, so the endpoint cannot be used to enumerate accounts.

    Parameters
    ----------
    request : HttpRequest
        Inbound HTTP request, whose origin is logged when an attempt fails so
        that repeated failures can be traced without recording a credential.
    payload : LoginRequest
        Submitted address and password.

    Returns
    -------
    Status of LoginResponse or Status of ErrorResponse
        The issued session, or the shared rejection body with HTTP 401.
    """

    try:
        session = sign_in(payload.email, payload.password)
    except InvalidCredentialsError:
        logger.warning(
            "Rejected a sign-in attempt from %s", request.META.get("REMOTE_ADDR", "unknown")
        )

        return Status(HTTPStatus.UNAUTHORIZED, ErrorResponse(detail=INVALID_CREDENTIALS_DETAIL))

    return Status(
        HTTPStatus.OK,
        LoginResponse(
            token=session.token,
            expires_at=session.expires_at,
            user=UserResponse.from_orm(session.user),
        ),
    )


@router.get(
    "/me",
    auth=session_token_auth,
    response={HTTPStatus.OK: UserResponse},
    summary="Return the account the bearer token authenticates",
)
def read_current_user(request: AuthenticatedRequest) -> Status[UserResponse]:
    """
    Return the authenticated account.

    Parameters
    ----------
    request : AuthenticatedRequest
        Inbound HTTP request carrying the resolved account.

    Returns
    -------
    Status of UserResponse
        Public projection of the authenticated account.
    """

    return Status(HTTPStatus.OK, UserResponse.from_orm(request.auth))


@router.post(
    "/logout",
    auth=session_token_auth,
    response={HTTPStatus.NO_CONTENT: None},
    summary="Revoke the session the bearer token identifies",
)
def logout(request: AuthenticatedRequest) -> Status[None]:
    """
    Revoke the presented session and answer with an empty body.

    Parameters
    ----------
    request : AuthenticatedRequest
        Inbound HTTP request carrying the token to revoke.

    Returns
    -------
    Status of None
        Empty HTTP 204 response.
    """

    revoke_session(request.auth_token)

    return Status(HTTPStatus.NO_CONTENT, None)
