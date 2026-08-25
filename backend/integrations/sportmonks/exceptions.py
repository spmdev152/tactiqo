class SportmonksError(Exception):
    """
    Raised when the Sportmonks boundary cannot satisfy a request.

    Every failure inside ``integrations.sportmonks`` is mapped to this single
    type: an absent API token, a transport failure, an exhausted retry budget,
    an elapsed call deadline, a non-success status, a body the provider contract
    cannot be read from, a pagination cursor that cannot be read, and a read
    that would otherwise return a truncated window as if it were a complete one.
    Callers therefore depend on this package rather than on the HTTP library it
    happens to use, and a caller that catches this type has covered the whole
    boundary.

    The cursor case is worth naming, because the exception it replaces is easy
    to miss: ``httpx.InvalidURL`` is not an ``httpx.HTTPError``, so a malformed
    cursor would otherwise escape a boundary that catches only the latter.
    """
