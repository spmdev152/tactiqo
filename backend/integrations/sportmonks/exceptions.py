class SportmonksError(Exception):
    """
    Raised when the Sportmonks boundary cannot satisfy a request.

    Every failure inside ``integrations.sportmonks`` is mapped to this single
    type: an absent API token, a transport failure, an exhausted retry budget,
    a non-success status, and a body the provider contract cannot be read from.
    Callers therefore depend on this package rather than on the HTTP library it
    happens to use, and a caller that catches this type has covered the whole
    boundary.
    """
