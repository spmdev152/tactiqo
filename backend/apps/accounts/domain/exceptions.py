class InvalidCredentialsError(Exception):
    """
    Raised when a sign-in attempt does not resolve to an authenticated account.

    The same exception covers an unknown address, a wrong password, and a
    deactivated account, so callers cannot turn the endpoint into an
    account-enumeration oracle by telling the three cases apart.
    """
