from concurrent.futures import ThreadPoolExecutor
from time import sleep

import pytest
from django.core.cache import cache
from django.core.cache.backends.base import BaseCache
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpRequest
from django.test import RequestFactory

from apps.accounts.api.throttling import KEY_LIFETIME_WINDOWS, SignInRateThrottle
from tests.conftest import CapturedRecord

CLIENT_ADDRESS = "198.51.100.7"

PERMITTED_ATTEMPTS = 5

CONCURRENT_ATTEMPTS = 20

SLOW_READ_SECONDS = 0.005


class RecordingCache:
    """
    Cache delegate recording the lifetime each counter was seeded with.

    Attributes
    ----------
    delegate : BaseCache
        Real cache every operation is forwarded to.
    added_timeouts : list of float
        Lifetime each ``add`` asked for, in call order.

    Methods
    -------
    add(key, value, timeout=None) -> bool
        Seed a counter, recording the lifetime asked for.
    incr(key, delta=1) -> int
        Increment an existing counter.
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
        self.added_timeouts: list[float] = []

    def add(self, key: str, value: object, timeout: float | None = None) -> bool:
        """
        Seed a counter, recording the lifetime asked for.

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

        if timeout is not None:
            self.added_timeouts.append(timeout)

        return self.delegate.add(key, value, timeout)

    def incr(self, key: str, delta: int = 1) -> int:
        """
        Increment an existing counter.

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


class VanishingCache:
    """
    Cache delegate whose counter is gone by the time the increment reaches it.

    Django implements ``incr`` as an existence check followed by an increment
    and raises when the key is absent, which a cache eviction can produce even
    though the window-keyed counter cannot expire inside its own window.

    Methods
    -------
    add(*_args, **_kwargs) -> bool
        Report the key as already present, as a live counter does.
    incr(*_args, **_kwargs) -> int
        Raise as Django does for a key that is no longer there.
    """

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

    def incr(self, *_args: object, **_kwargs: object) -> int:
        """
        Raise as Django does for a key that is no longer there.

        Parameters
        ----------
        *_args : object
            Ignored positional arguments of the replaced operation.
        **_kwargs : object
            Ignored keyword arguments of the replaced operation.

        Raises
        ------
        ValueError
            Always.
        """

        raise ValueError("Key 'throttle_sign-in' not found.")


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
    loguru_records: list[CapturedRecord],
) -> None:
    """
    GIVEN a cache that refuses every operation
    WHEN an attempt is counted
    THEN it is allowed and the warning carries the cause, not just the fact
    """

    monkeypatch.setattr(throttle, "cache", FailingCache())

    assert throttle.allow_request(sign_in_request) is True

    assert [
        (level, carries_exception) for level, _message, carries_exception in loguru_records
    ] == [("WARNING", True)]


def test_a_counter_the_cache_lost_allows_the_attempt_quietly(
    throttle: SignInRateThrottle,
    sign_in_request: HttpRequest,
    monkeypatch: pytest.MonkeyPatch,
    loguru_records: list[CapturedRecord],
) -> None:
    """
    GIVEN a counter the cache no longer holds when the increment reaches it
    WHEN the attempt is counted
    THEN it is allowed without a warning, because an evicted counter is routine
    """

    monkeypatch.setattr(throttle, "cache", VanishingCache())

    assert throttle.allow_request(sign_in_request) is True
    assert loguru_records == []


def test_a_counter_stuck_without_a_lifetime_stops_being_consulted_next_window(
    throttle: SignInRateThrottle,
    sign_in_request: HttpRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    GIVEN a counter left above the limit and without a lifetime by a failed increment
    WHEN the window rolls over
    THEN the client is allowed again, because each window carries its own key
    """

    monkeypatch.setattr(throttle, "current_window", lambda: 0)

    cache.set(throttle.get_cache_key(sign_in_request), PERMITTED_ATTEMPTS + 99, None)

    assert throttle.allow_request(sign_in_request) is False

    monkeypatch.setattr(throttle, "current_window", lambda: 1)

    assert throttle.allow_request(sign_in_request) is True


def test_a_counter_outlives_the_window_it_counts(
    throttle: SignInRateThrottle,
    sign_in_request: HttpRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    GIVEN an attempt seeding the counter of the current window
    WHEN the lifetime it asks the cache for is inspected
    THEN it is longer than the window, so the counter cannot expire inside it
    """

    recording_cache = RecordingCache(cache)

    monkeypatch.setattr(throttle, "cache", recording_cache)

    assert throttle.allow_request(sign_in_request) is True
    assert recording_cache.added_timeouts == [KEY_LIFETIME_WINDOWS * throttle.window_seconds]
    assert min(recording_cache.added_timeouts) > throttle.window_seconds


@pytest.mark.parametrize("rate", ["0/m", "-1/m", "5/0m", "5/-1m"])
def test_a_degenerate_rate_is_refused(rate: str) -> None:
    """
    GIVEN a configured rate that parses but permits no attempt or spans no time
    WHEN the throttle is built from it
    THEN construction fails loudly instead of bricking or disabling sign-in silently
    """

    with pytest.raises(ImproperlyConfigured, match=rate):
        SignInRateThrottle(rate)
