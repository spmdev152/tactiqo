from django.http import HttpRequest
from ninja.throttling import SimpleRateThrottle

from config.client_address import resolve_client_address


class SignInRateThrottle(SimpleRateThrottle):
    """
    Rate of sign-in attempts a single client may make.

    The scope is sign-in alone rather than the whole API, so the bucket a
    rejected password consumes can never deny a read endpoint, and a future
    throttle elsewhere cannot spend this one. Attempts are counted before the
    view runs, so a successful sign-in counts too: the throttle cannot know the
    outcome, and a client legitimately signing in more than a handful of times
    per window is not a shape this product has.

    Attributes
    ----------
    scope : str
        Bucket name the cache key carries, ``"sign-in"``.

    Methods
    -------
    get_cache_key(request) -> str
        Return the bucket the request is counted against.
    """

    scope = "sign-in"

    def get_cache_key(self, request: HttpRequest) -> str:
        """
        Return the bucket the request is counted against.

        Parameters
        ----------
        request : HttpRequest
            Inbound sign-in request.

        Returns
        -------
        str
            Cache key naming the scope and the identified client.
        """

        return self.cache_format % {
            "scope": self.scope,
            "ident": resolve_client_address(request),
        }
