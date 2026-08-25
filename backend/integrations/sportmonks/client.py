import logging
import time
from collections.abc import Iterator
from typing import Any

import httpx
from django.conf import settings

from integrations.sportmonks.exceptions import SportmonksError

logger = logging.getLogger(__name__)

type ProviderPayload = dict[str, Any]

type QueryParameters = dict[str, str | int]

REQUEST_TIMEOUT_SECONDS = 10.0

CALL_BUDGET_SECONDS = 600.0

MAX_ATTEMPTS = 3

BACKOFF_BASE_SECONDS = 0.25

MAX_RETRY_DELAY_SECONDS = 1.0

# Pages, so a resource read with the fixtures boundary's fifty-row page size cannot exceed two
# thousand rows: an order of magnitude above the fixtures five leagues schedule in a fortnight.
MAX_PAGE_COUNT = 40

LOW_QUOTA_CALLS = 200

CURSOR_PARAMETER = "cursor"

PAGE_SIZE_PARAMETER = "per_page"


class SportmonksClient:
    """
    Authenticated, retrying, pagination-aware reader of the Sportmonks API.

    The client owns every concern the resource modules must not repeat:
    presenting the API token, bounding the request with a timeout and the whole
    call with a deadline, retrying a throttled or failing response, following
    the pagination cursor, and mapping every failure to
    :class:`SportmonksError`.

    The HTTP connection pool is opened per call rather than held on the
    instance, because the Celery worker forks after import and a pool inherited
    across a fork would be shared by processes that each believe they own it.

    The token travels in the ``Authorization`` header, never in the query, even
    though the provider accepts both. ``httpx`` logs the full request URL at
    info level, and every standard-library record reaches the Loguru sink, so a
    token in the query string would be written verbatim into the serialized
    logs of every deployed environment. That is also why the payload only ever
    contributes a scalar to the next request: a page the provider advertises
    contributes its ``cursor`` token alone, and the absolute URL that token was
    published inside is discarded, so neither a host the payload chooses nor a
    credential it echoes back can reach the wire.

    A truncated read is a failure, not a short window. Whenever the provider
    still reports a further page that this client cannot ask for, the call
    raises rather than returning the pages it already has, because a caller
    cannot tell a prefix of a window from the whole of it and would store the
    prefix as if it were complete.

    ``REQUEST_TIMEOUT_SECONDS`` bounds one attempt, which bounds nothing about
    a paginated read: forty pages of three attempts each can outlast any lock
    protecting the caller. ``CALL_BUDGET_SECONDS`` therefore bounds the call as
    a whole, from the moment the pool opens, and is set to ten minutes so that
    the two reads a fixture window performs still finish inside the thirty
    minutes of ``FIXTURE_SYNCHRONIZATION_LOCK_SECONDS`` with a third of that
    lock left over.

    Parameters
    ----------
    transport : httpx.BaseTransport or None
        Transport to send requests through, or ``None`` to let the HTTP library
        build its default one. Supplying one is how a caller substitutes
        recorded responses for the network.

    Raises
    ------
    SportmonksError
        When no API token is configured. Failing here is deliberate: an
        unauthenticated call would spend a request to be told the same thing,
        and the provider answers it with a status the retry policy would treat
        as worth repeating.

    Methods
    -------
    __init__(transport=None) -> None
        Read the configured credential and base URL, opening no connection.
    get_pages(path, params) -> Iterator[list[ProviderPayload]]
        Yield the entries of every page of a paginated resource.
    """

    def __init__(self, transport: httpx.BaseTransport | None = None) -> None:
        token = str(settings.SPORTMONKS_API_TOKEN)

        if not token:
            raise SportmonksError(
                "No Sportmonks API token is configured, so no provider request can be made."
            )

        self._token = token
        self._base_url = str(settings.SPORTMONKS_BASE_URL).rstrip("/")
        self._transport = transport

    def get_pages(self, path: str, params: QueryParameters) -> Iterator[list[ProviderPayload]]:
        """
        Yield the entries of every page of a paginated resource.

        Pages after the first are asked for with the cursor the provider
        advertises, merged onto the URL this client built rather than onto the
        one the payload named. The page size is dropped at the same time: the
        cursor encodes it, and the provider rejects a request carrying both.

        Parameters
        ----------
        path : str
            Resource path relative to the configured base URL, with or without
            a leading slash.
        params : dict of str to str or int
            Query parameters of the first request. The API token is added here
            and must not be supplied by the caller.

        Yields
        ------
        list of ProviderPayload
            Entries of one page, in the order the provider returned them.

        Raises
        ------
        SportmonksError
            When a page cannot be retrieved within the retry budget, when the
            overall call budget elapses, when a body does not carry the
            documented envelope, or when the provider reports a further page
            that cannot be asked for, whether because it named no readable
            cursor or because the page cap was reached.
        """

        url = httpx.URL(f"{self._base_url}/{path.lstrip('/')}").copy_merge_params(dict(params))

        deadline = time.monotonic() + CALL_BUDGET_SECONDS

        with httpx.Client(
            timeout=REQUEST_TIMEOUT_SECONDS,
            transport=self._transport,
            headers={"Authorization": self._token, "accept": "application/json"},
        ) as connection:
            for _ in range(MAX_PAGE_COUNT):
                envelope = self._read_page(connection, url, deadline)

                _log_remaining_budget(envelope)

                yield _entries_of(envelope, url)

                cursor = _next_cursor(envelope, url)

                if cursor is None:
                    return

                url = url.copy_remove_param(PAGE_SIZE_PARAMETER).copy_set_param(
                    CURSOR_PARAMETER, cursor
                )

        raise SportmonksError(
            f"Sportmonks still reports a further page of {url.path} after {MAX_PAGE_COUNT} pages, "
            "so the read would be a truncated window rather than a complete one."
        )

    def _read_page(
        self, connection: httpx.Client, url: httpx.URL, deadline: float
    ) -> ProviderPayload:
        """
        Return the decoded envelope of one page, retrying a repeatable failure.

        Parameters
        ----------
        connection : httpx.Client
            Open connection pool the request is sent through.
        url : httpx.URL
            Fully built page URL, carrying no credential of any kind: the token
            travels in the header the connection pool was opened with.
        deadline : float
            Monotonic instant the whole call must finish by, checked before
            every attempt so a slow provider cannot outlast it.

        Returns
        -------
        ProviderPayload
            Decoded response envelope.

        Raises
        ------
        SportmonksError
            When the attempt budget is exhausted, when the overall call budget
            elapses, when the status is not worth retrying, or when the body is
            not a JSON object.
        """

        failure = "no attempt was made"

        for attempt in range(1, MAX_ATTEMPTS + 1):
            _refuse_past_deadline(deadline, url)

            is_last_attempt = attempt == MAX_ATTEMPTS

            try:
                response = connection.get(url)
            except httpx.HTTPError as error:
                failure = f"the request failed with {type(error).__name__}"

                if is_last_attempt:
                    break

                time.sleep(_backoff(attempt))

                continue

            if response.is_success:
                return _decoded(response, url)

            failure = f"the provider answered HTTP {response.status_code}"

            delay = _retry_delay(response, attempt)

            if delay is None or is_last_attempt:
                break

            logger.debug("Retrying %s in %.2fs: %s.", url.path, delay, failure)

            time.sleep(delay)

        raise SportmonksError(f"Sportmonks request to {url.path} was abandoned: {failure}.")


def _refuse_past_deadline(deadline: float, url: httpx.URL) -> None:
    """
    Raise once the overall budget of a call has elapsed.

    Parameters
    ----------
    deadline : float
        Monotonic instant the call must finish by.
    url : httpx.URL
        URL that would have been requested, used to name the resource.

    Raises
    ------
    SportmonksError
        When the deadline has passed.
    """

    if time.monotonic() < deadline:
        return

    raise SportmonksError(
        f"Sportmonks request to {url.path} was abandoned: the {CALL_BUDGET_SECONDS:.0f} second "
        "budget of this call elapsed before the read finished."
    )


def _decoded(response: httpx.Response, url: httpx.URL) -> ProviderPayload:
    """
    Return the JSON object a successful response carries.

    Parameters
    ----------
    response : httpx.Response
        Successful response whose body is being read.
    url : httpx.URL
        URL the response answers, used to name the failing resource.

    Returns
    -------
    ProviderPayload
        Decoded response body.

    Raises
    ------
    SportmonksError
        When the body is not decodable JSON or is not a JSON object.
    """

    try:
        payload = response.json()
    except ValueError as error:
        raise SportmonksError(
            f"Sportmonks answered {url.path} with a body that is not JSON."
        ) from error

    if not isinstance(payload, dict):
        raise SportmonksError(
            f"Sportmonks answered {url.path} with {type(payload).__name__} instead of an envelope."
        )

    return payload


def _entries_of(envelope: ProviderPayload, url: httpx.URL) -> list[ProviderPayload]:
    """
    Return the entries of a page, dropping anything that is not an object.

    Parameters
    ----------
    envelope : ProviderPayload
        Decoded response envelope of one page.
    url : httpx.URL
        URL the envelope answers, used to name the failing resource.

    Returns
    -------
    list of ProviderPayload
        Entries the page carries.

    Raises
    ------
    SportmonksError
        When the envelope carries no ``data`` list.
    """

    data = envelope.get("data")

    if not isinstance(data, list):
        raise SportmonksError(f"Sportmonks answered {url.path} without a data list.")

    return [entry for entry in data if isinstance(entry, dict)]


def _next_cursor(envelope: ProviderPayload, url: httpx.URL) -> str | None:
    """
    Return the cursor token of the page following the one an envelope describes.

    Parameters
    ----------
    envelope : ProviderPayload
        Decoded response envelope of the current page.
    url : httpx.URL
        URL the envelope answers, used to name the failing resource.

    Returns
    -------
    str or None
        Cursor token to ask the next page with, or ``None`` when the provider
        reports that this page was the last.

    Raises
    ------
    SportmonksError
        When the provider reports a further page it does not name a readable
        cursor for. Returning the pages already read would hand the caller a
        prefix of the window it could not distinguish from the whole of it.
    """

    pagination = envelope.get("pagination")

    if not isinstance(pagination, dict) or not pagination.get("has_more"):
        return None

    advertised = pagination.get("next_cursor")

    if not isinstance(advertised, str) or not advertised:
        raise SportmonksError(
            f"Sportmonks reports a further page of {url.path} without naming a cursor, so the "
            "read cannot be completed and must not be reported as complete."
        )

    return _cursor_token(advertised, url)


def _cursor_token(advertised: str, url: httpx.URL) -> str:
    """
    Return the cursor an advertised next page carries, and nothing else of it.

    The provider publishes the next page as an absolute URL. Everything about
    that URL except the ``cursor`` parameter is discarded, because the payload
    would otherwise choose the host the credential is presented to.

    Parameters
    ----------
    advertised : str
        Value of the ``next_cursor`` field of a pagination block.
    url : httpx.URL
        URL the envelope answers, used to name the failing resource.

    Returns
    -------
    str
        Cursor token to merge onto the URL this client built.

    Raises
    ------
    SportmonksError
        When the advertised value cannot be read as a URL, or carries no
        cursor. ``httpx.InvalidURL`` is not an ``httpx.HTTPError``, so mapping
        it here is what keeps it from escaping the boundary.
    """

    try:
        target = httpx.URL(advertised)
    except httpx.InvalidURL as error:
        raise SportmonksError(
            f"Sportmonks advertised the next page of {url.path} as a value that cannot be read "
            "as a URL, so the read cannot be completed."
        ) from error

    token = str(target.params.get(CURSOR_PARAMETER, ""))

    if not token:
        raise SportmonksError(
            f"Sportmonks advertised a further page of {url.path} that carries no cursor, so the "
            "read cannot be completed and must not be reported as complete."
        )

    return token


def _log_remaining_budget(envelope: ProviderPayload) -> None:
    """
    Report how much of the hourly entity quota the provider says is left.

    The subscription meters calls per entity per hour, so the envelope's own
    accounting is the only place a quota problem becomes visible before the
    provider starts refusing requests. The routine record stays at debug level,
    but a budget close to spent is escalated to warning: the deployed settings
    clamp the sink above debug, and a number parsed into a suppressed line
    would tell nobody anything.

    Parameters
    ----------
    envelope : ProviderPayload
        Decoded response envelope of one page.
    """

    rate_limit = envelope.get("rate_limit")

    if not isinstance(rate_limit, dict):
        return

    remaining = _count(rate_limit.get("remaining"))

    entity = rate_limit.get("requested_entity")

    resets_in_seconds = rate_limit.get("resets_in_seconds")

    if remaining is not None and remaining < LOW_QUOTA_CALLS:
        logger.warning(
            "Sportmonks has only %d calls left for entity %s, resetting in %s seconds.",
            remaining,
            entity,
            resets_in_seconds,
        )

        return

    logger.debug(
        "Sportmonks reports %s calls left for entity %s, resetting in %s seconds.",
        rate_limit.get("remaining"),
        entity,
        resets_in_seconds,
    )


def _retry_delay(response: httpx.Response, attempt: int) -> float | None:
    """
    Return how long to wait before repeating a failed request.

    Parameters
    ----------
    response : httpx.Response
        Unsuccessful response that was received.
    attempt : int
        One-based number of the attempt that produced the response.

    Returns
    -------
    float or None
        Delay in seconds, or ``None`` when the status will not change by being
        asked again inside this call.
    """

    if response.status_code == httpx.codes.TOO_MANY_REQUESTS:
        return _throttled_delay(response, attempt)

    if response.status_code >= httpx.codes.INTERNAL_SERVER_ERROR:
        return _backoff(attempt)

    return None


def _throttled_delay(response: httpx.Response, attempt: int) -> float | None:
    """
    Return how long to wait after a throttled response, or nothing to abandon.

    The subscription meters per hour and the provider reports the whole hour as
    the reset, so a retry a second later would spend the remaining attempts to
    be refused again by the same exhausted bucket. A reset longer than the
    retry ceiling is therefore reported at warning level and abandoned, while a
    genuinely short one is still waited out.

    Parameters
    ----------
    response : httpx.Response
        Throttled response that was received.
    attempt : int
        One-based number of the attempt that produced the response.

    Returns
    -------
    float or None
        Delay in seconds, or ``None`` when the quota cannot return inside this
        call and retrying it would only spend attempts.
    """

    reported = _reported_reset(response)

    if reported is None:
        return _backoff(attempt)

    if reported > MAX_RETRY_DELAY_SECONDS:
        logger.warning(
            "Abandoning a Sportmonks request: the hourly quota is spent and the provider reports "
            "it resetting in %.0f seconds, which no retry inside this call can outlast.",
            reported,
        )

        return None

    return reported


def _reported_reset(response: httpx.Response) -> float | None:
    """
    Return the delay a throttled response states before its quota returns.

    Three carriers are read, in the order of how precisely each is known to
    state this provider's quota: the ``rate_limit`` accounting a successful
    envelope carries too, the top-level ``retry_after`` the documented
    throttled body carries instead, and the standard ``Retry-After`` header.
    The first one present wins. A header expressed as an HTTP date rather than
    a number of seconds is read as absent.

    Parameters
    ----------
    response : httpx.Response
        Throttled response whose envelope and headers are being inspected.

    Returns
    -------
    float or None
        Seconds the provider says remain of the window, or ``None`` when none of
        the three carriers states it.
    """

    payload = _body_of(response)

    rate_limit = payload.get("rate_limit")

    accounted = rate_limit.get("resets_in_seconds") if isinstance(rate_limit, dict) else None

    for stated in (accounted, payload.get("retry_after"), response.headers.get("Retry-After")):
        seconds = _seconds(stated)

        if seconds is not None:
            return seconds

    return None


def _body_of(response: httpx.Response) -> ProviderPayload:
    """
    Return the JSON object a response carries, or an empty one.

    Parameters
    ----------
    response : httpx.Response
        Response whose body is being inspected rather than consumed.

    Returns
    -------
    ProviderPayload
        Decoded body, or ``{}`` when it is not a JSON object.
    """

    try:
        payload = response.json()
    except ValueError:
        return {}

    return payload if isinstance(payload, dict) else {}


def _count(value: object) -> int | None:
    """
    Return a non-negative integer a provider accounting field states.

    Parameters
    ----------
    value : object
        Value a counting field of the rate-limit block carried.

    Returns
    -------
    int or None
        The count, or ``None`` when the value does not denote one.
    """

    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None

    return value


def _seconds(value: object) -> float | None:
    """
    Return a non-negative delay in seconds from a value that states one.

    Parameters
    ----------
    value : object
        Value a delay field or header carried, as a number or as the digits a
        header can only express it in.

    Returns
    -------
    float or None
        Delay in seconds, or ``None`` when the value does not denote one.
    """

    if isinstance(value, bool):
        return None

    if isinstance(value, int | float):
        return max(float(value), 0.0)

    if not isinstance(value, str):
        return None

    try:
        return max(float(value), 0.0)
    except ValueError:
        return None


def _backoff(attempt: int) -> float:
    """
    Return the exponential delay for an attempt, capped at the ceiling.

    Parameters
    ----------
    attempt : int
        One-based number of the attempt that just failed.

    Returns
    -------
    float
        Delay in seconds.
    """

    return min(BACKOFF_BASE_SECONDS * 2 ** (attempt - 1), MAX_RETRY_DELAY_SECONDS)
