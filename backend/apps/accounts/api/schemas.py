from datetime import datetime

from ninja import Schema


class LoginRequest(Schema):
    """
    Credentials submitted to open a session.

    Attributes
    ----------
    email : str
        Address identifying the account, matched case-insensitively.
    password : str
        Raw password, never echoed back in any response.
    """

    email: str
    password: str


class UserResponse(Schema):
    """
    Public projection of an account.

    Attributes
    ----------
    id : int
        Primary key of the account.
    email : str
        Normalized login identifier.
    full_name : str
        Display name, an empty string when the account has none.
    """

    id: int
    email: str
    full_name: str


class LoginResponse(Schema):
    """
    Session handed to a client that presented valid credentials.

    Attributes
    ----------
    token : str
        Opaque bearer token, which the client must not attempt to parse.
    expires_at : datetime
        Instant from which the token stops authenticating, serialized as an
        ISO 8601 UTC timestamp.
    user : UserResponse
        Account the token authenticates.
    """

    token: str
    expires_at: datetime
    user: UserResponse


class ErrorResponse(Schema):
    """
    Body of a failure this API answers with deliberately.

    Attributes
    ----------
    detail : str
        Human-readable reason, identical for every rejected sign-in so the
        endpoint cannot be used to discover which addresses exist.
    """

    detail: str
