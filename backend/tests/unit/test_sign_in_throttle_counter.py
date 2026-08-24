from concurrent.futures import ThreadPoolExecutor
from time import sleep

import pytest
from django.core.cache import cache
from django.core.cache.backends.base import BaseCache
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpRequest
from django.test import RequestFactory

from apps.accounts.api.throttling import SignInRateThrottle

CLIENT_ADDRESS = "198.51.100.7"

PERMITTED_ATTEMPTS = 5

CONCURRENT_ATTEMPTS = 20

SLOW_READ_SECONDS = 0.005


class SlowReadCache:
    """
    Cache delegate answering a read as a network cache does, a round trip late.

    A sliding-window counter reads the history, mutates it and writes it back,
    so every concurrent attempt acts on the same pre-state once the read takes
    as long as a Redis round trip. The delay is applied to ``get`` alone, which
    an atomically counting throttle never calls, so this double costs the
    passing test nothing and fails a counter that regresses to reading before
    writing.

    Attributes
    ----------
    delegate : BaseCache
        Real cache every operation is forwarded to.

    Methods
    -------
    get(key, default=None) -> object
        Read a value and return it a round trip later.
    add(key, value, timeout=None) -> bool
        Store a value only when the key is absent.
    incr(key, delta=1) -> int
        Increment an existing value.
    set(key, value, timeout=None) -> None
        Store a value unconditionally.
    """

    def __init__(self, delegate: BaseCache) -> None:
        """
        Wrap a cache.

        Parameters
        ----------
        delegate : BaseCache
            Real cache every operation is forwarded to.
        """

        self.delegate = delegate

    def get(self, key: str, default: object = None) -> object:
        """
        Read a value and return it a round trip later.

        The value is read first and delayed afterwards, which is how a network
        cache behaves: the answer describes the state at the moment of the read,
        and the caller acts on it once the round trip is over.

        Parameters
        ----------
        key : str
            Cache key to read.
        default : object
            Value returned when the key is absent.

        Returns
        -------
        object
            Stored value, or the default.
        """

        value = self.delegate.get(key, default)

        sleep(SLOW_READ_SECONDS)

        return value

    def add(self, key: str, value: object, timeout: float | None = None) -> bool:
        """
        Store a value only when the key is absent.

        Parameters
        ----------
        key : str
            Cache key to seed.
        value : object
            Value to store.
        timeout : float or None
            Lifetime of the entry in seconds.

        Returns
        -------
        bool
            ``True`` when this call created the entry.
        """

        return self.delegate.add(key, value, timeout)

    def incr(self, key: str, delta: int = 1) -> int:
        """
        Increment an existing value.

        Parameters
        ----------
        key : str
            Cache key to increment.
        delta : int
            Amount to add.

        Returns
        -------
        int
            Value after the increment.
        """

        return self.delegate.incr(key, delta)

    def set(self, key: str, value: object, timeout: float | None = None) -> None:
        """
        Store a value unconditionally.

        Parameters
        ----------
        key : str
            Cache key to write.
        value : object
            Value to store.
        timeout : float or None
            Lifetime of the entry in seconds.
        """

        self.delegate.set(key, value, timeout)


class FailingCache:
    """
    Cache delegate that refuses every operation the way an unreachable Redis does.

    Methods
    -------
    get(*_args, **_kwargs) -> object
        Raise as an unreachable cache does.
    add(*_args, **_kwargs) -> bool
        Raise as an unreachable cache does.
    incr(*_args, **_kwargs) -> int
        Raise as an unreachable cache does.
    """

    def get(self, *_args: object, **_kwargs: object) -> object:
        """
        Raise as an unreachable cache does.

        Parameters
        ----------
        *_args : object
            Ignored positional arguments of the replaced operation.
        **_kwargs : object
            Ignored keyword arguments of the replaced operation.

        Raises
        ------
        ConnectionError
            Always.
        """

        raise ConnectionError("Error 111 connecting to redis:6379")

    def add(self, *_args: object, **_kwargs: object) -> bool:
        """
        Raise as an unreachable cache does.

        Parameters
        ----------
        *_args : object
            Ignored positional arguments of the replaced operation.
        **_kwargs : object
            Ignored keyword arguments of the replaced operation.

        Raises
        ------
        ConnectionError
            Always.
        """

        raise ConnectionError("Error 111 connecting to redis:6379")

    def incr(self, *_args: object, **_kwargs: object) -> int:
        """
        Raise as an unreachable cache does.

        Parameters
        ----------
        *_args : object
            Ignored positional arguments of the replaced operation.
        **_kwargs : object
            Ignored keyword arguments of the replaced operation.

        Raises
        ------
        ConnectionError
            Always.
        """

        raise ConnectionError("Error 111 connecting to redis:6379")


class ResurrectingCache:
    """
    Cache delegate reproducing what Redis does to a counter that expires mid-increment.

    Django implements ``incr`` as an existence check followed by ``INCRBY``, and
    ``INCRBY`` recreates a key that expired between the two commands with no
    lifetime at all. A counter left in that state never resets, so the client it
    belongs to is refused forever.

    Attributes
    ----------
    delegate : BaseCache
        Real cache every operation is forwarded to.
    touched_timeouts : list of float
        Lifetime each ``touch`` asked for, recorded for assertion.

    Methods
    -------
    add(*_args, **_kwargs) -> bool
        Report the key as already present, as a live counter does.
    incr(key, delta=1) -> int
        Recreate the key without a lifetime and report the first count.
    touch(key, timeout=None) -> bool
        Record the requested lifetime and apply it.
    """

    def __init__(self, delegate: BaseCache) -> None:
        """
        Wrap a cache.

        Parameters
        ----------
        delegate : BaseCache
            Real cache every operation is forwarded to.
        """

        self.delegate = delegate
        self.touched_timeouts: list[float] = []

    def add(self, *_args: object, **_kwargs: object) -> bool:
        """
        Report the key as already present, as a live counter does.

        Parameters
        ----------
        *_args : object
            Ignored positional arguments of the replaced operation.
        **_kwargs : object
            Ignored keyword arguments of the replaced operation.

        Returns
        -------
        bool
            Always ``False``.
        """

        return False

    def incr(self, key: str, delta: int = 1) -> int:
        """
        Recreate the key without a lifetime and report the first count.

        Parameters
        ----------
        key : str
            Cache key to recreate.
        delta : int
            Amount the recreated counter starts at.

        Returns
        -------
        int
            The recreated count, which is ``delta``.
        """

        self.delegate.set(key, delta, None)

        return delta

    def touch(self, key: str, timeout: float | None = None) -> bool:
        """
        Record the requested lifetime and apply it.

        Parameters
        ----------
        key : str
            Cache key whose lifetime is being set.
        timeout : float or None
            Lifetime in seconds.

        Returns
        -------
        bool
            ``True`` when the key was still present.
        """

        if timeout is not None:
            self.touched_timeouts.append(timeout)

        return self.delegate.touch(key, timeout)


@pytest.fixture
def throttle() -> SignInRateThrottle:
    """
    Return a throttle permitting a known number of attempts per minute.

    Returns
    -------
    SignInRateThrottle
        Throttle under test, counting against the test cache.
    """

    return SignInRateThrottle(f"{PERMITTED_ATTEMPTS}/m")


@pytest.fixture
def sign_in_request() -> HttpRequest:
    """
    Return a request from one client, reused for every attempt.

    Returns
    -------
    HttpRequest
        Request carrying the client address the attempts are keyed on.
    """

    return RequestFactory().post("/", REMOTE_ADDR=CLIENT_ADDRESS)


def test_a_concurrent_burst_never_exceeds_the_permitted_attempts(
    throttle: SignInRateThrottle,
    sign_in_request: HttpRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    GIVEN one client firing far more simultaneous attempts than it may make
    WHEN each attempt is counted against a cache that answers a round trip late
    THEN exactly the permitted number are allowed, so counting is atomic
    """

    monkeypatch.setattr(throttle, "cache", SlowReadCache(cache))

    with ThreadPoolExecutor(max_workers=CONCURRENT_ATTEMPTS) as pool:
        outcomes = list(
            pool.map(
                lambda _attempt: throttle.allow_request(sign_in_request), range(CONCURRENT_ATTEMPTS)
            )
        )

    assert outcomes.count(True) == PERMITTED_ATTEMPTS


def test_an_unreachable_cache_allows_the_attempt(
    throttle: SignInRateThrottle,
    sign_in_request: HttpRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    GIVEN a cache that refuses every operation
    WHEN an attempt is counted
    THEN it is allowed, because a degraded cache must not deny every sign-in
    """

    monkeypatch.setattr(throttle, "cache", FailingCache())

    assert throttle.allow_request(sign_in_request) is True


def test_a_counter_recreated_by_the_increment_is_given_a_lifetime(
    throttle: SignInRateThrottle,
    sign_in_request: HttpRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    GIVEN a counter whose key expires between the existence check and the increment
    WHEN the attempt is counted
    THEN the recreated key is given a lifetime, so the client is not refused forever
    """

    resurrecting_cache = ResurrectingCache(cache)

    monkeypatch.setattr(throttle, "cache", resurrecting_cache)

    assert throttle.allow_request(sign_in_request) is True
    assert resurrecting_cache.touched_timeouts == [throttle.window_seconds]


@pytest.mark.parametrize("rate", ["0/m", "-1/m", "5/0m", "5/-1m"])
def test_a_degenerate_rate_is_refused(rate: str) -> None:
    """
    GIVEN a configured rate that parses but permits no attempt or spans no time
    WHEN the throttle is built from it
    THEN construction fails loudly instead of bricking or disabling sign-in silently
    """

    with pytest.raises(ImproperlyConfigured, match=rate):
        SignInRateThrottle(rate)
