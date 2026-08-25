import logging
from time import time

from django.core.exceptions import ImproperlyConfigured
from django.http import HttpRequest
from ninja.throttling import SimpleRateThrottle

from config.client_identity import resolve_client_identity

logger = logging.getLogger(__name__)

KEY_LIFETIME_WINDOWS = 2


class SignInRateThrottle(SimpleRateThrottle):
    """
    Rate of sign-in attempts a single client may make.

    The scope is sign-in alone rather than the whole API, so the bucket a
    rejected password consumes can never deny a read endpoint, and a future
    throttle elsewhere cannot spend this one. Attempts are counted before the
    view runs, so a successful sign-in counts too: the throttle cannot know the
    outcome, and a client legitimately signing in more than a handful of times
    per window is not a shape this product has.

    The counter is a fixed window rather than the sliding window the base class
    implements. That is a correctness requirement, not a preference: the base
    class reads the attempt history, mutates it and writes it back, keeping the
    intermediate state on an instance that every request shares, so concurrent
    attempts all act on the same pre-state and one Redis round trip is enough
    for a client opening several connections to exceed the rate several-fold.
    A fixed window admits up to twice the rate across a window boundary, which
    is the price of counting without a read-modify-write.

    Each window has its own key, named after the window's ordinal, and the key
    outlives its window. Both details are load-bearing. Django implements
    ``incr`` as an existence check followed by ``INCRBY``, and ``INCRBY``
    recreates a key that expired in between without a lifetime, which would
    answer one client HTTP 429 forever and no later attempt could repair it;
    a key that cannot expire while its own window is current makes that race
    unreachable. And should a key end up immortal anyway, the next window uses
    a different key, so the damage expires on its own instead of needing a
    hand-run ``DEL``.

    A cache failure allows the request and logs a warning with its cause.
    Denying every sign-in while Redis is unreachable would turn a degraded
    dependency into a total authentication outage, and ``config/health.py``
    already treats the cache as degradable rather than fatal.

    Attributes
    ----------
    scope : str
        Bucket name the cache key carries, ``"sign-in"``.
    permitted_attempts : int
        Attempts allowed inside one window, validated on construction.
    window_seconds : int
        Length of the window, validated on construction.

    Methods
    -------
    __init__(rate) -> None
        Parse and validate the configured rate.
    allow_request(request) -> bool
        Count the attempt and report whether it may proceed.
    current_window() -> int
        Return the ordinal of the window the current instant falls in.
    get_cache_key(request) -> str
        Return the bucket the request is counted against.
    wait() -> None
        Report no recommended delay, because no history is kept.
    """

    scope = "sign-in"

    def __init__(self, rate: str) -> None:
        """
        Parse and validate the configured rate.

        Parameters
        ----------
        rate : str
            Rate in Django Ninja's ``count/period`` notation, such as ``5/m``.

        Raises
        ------
        ImproperlyConfigured
            If the rate parses but permits no attempt or spans no time, which
            would silently brick sign-in or silently disable the throttle.
        """

        super().__init__(rate)

        if (
            self.num_requests is None
            or self.num_requests < 1
            or self.duration is None
            or self.duration < 1
        ):
            raise ImproperlyConfigured(
                f"Sign-in throttle rate {rate!r} must permit at least one attempt "
                f"in a window of at least one second."
            )

        self.permitted_attempts = self.num_requests
        self.window_seconds = self.duration

    def allow_request(self, request: HttpRequest) -> bool:
        """
        Count the attempt and report whether it may proceed.

        Parameters
        ----------
        request : HttpRequest
            Inbound sign-in request.

        Returns
        -------
        bool
            ``True`` while the client has budget left in the current window.
        """

        key = self.get_cache_key(request)

        try:
            if self.cache.add(key, 1, KEY_LIFETIME_WINDOWS * self.window_seconds):
                return True

            return self.cache.incr(key) <= self.permitted_attempts
        except ValueError:
            return True
        except Exception:
            logger.warning(
                "Allowed a sign-in attempt the cache could not be asked about.", exc_info=True
            )

            return True

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
            Cache key naming the scope, the identified client, and the ordinal
            of the window the attempt falls in.
        """

        window = self.current_window()

        return f"throttle_{self.scope}_{resolve_client_identity(request)}_{window}"

    def current_window(self) -> int:
        """
        Return the ordinal of the window the current instant falls in.

        Returns
        -------
        int
            Count of whole windows since the epoch, which changes exactly when
            one window ends and the next begins.
        """

        return int(time()) // self.window_seconds

    def wait(self) -> None:
        """
        Report no recommended delay.

        The base class derives one from the request history a sliding window
        keeps, and this throttle keeps no history. Django Ninja drops a missing
        recommendation, so the rejection is unaffected.
        """

        return None
