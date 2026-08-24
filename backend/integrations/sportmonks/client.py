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

MAX_ATTEMPTS = 3

BACKOFF_BASE_SECONDS = 0.25

MAX_RETRY_DELAY_SECONDS = 1.0

MAX_PAGE_COUNT = 25

CREDENTIAL_PARAMETER = "api_token"


class SportmonksClient:
    """
    Authenticated, retrying, pagination-aware reader of the Sportmonks API.

    The client owns every concern the resource modules must not repeat:
    presenting the API token, bounding the request with a timeout, retrying a
    throttled or failing response, following the pagination cursor, and mapping
    every failure to :class:`SportmonksError`.

    The HTTP connection pool is opened per call rather than held on the
    instance, because the Celery worker forks after import and a pool inherited
    across a fork would be shared by processes that each believe they own it.

    The token travels in the ``Authorization`` header, never in the query, even
    though the provider accepts both. ``httpx`` logs the full request URL at
    info level, and every standard-library record reaches the Loguru sink, so a
    token in the query string would be written verbatim into the serialized
    logs of every deployed environment. A pagination cursor the provider echoes
    back with a token of its own is stripped for the same reason.

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
            When a page cannot be retrieved within the retry budget, or when
            its body does not carry the documented envelope.
        """

        url = httpx.URL(f"{self._base_url}/{path.lstrip('/')}").copy_merge_params(dict(params))

        with httpx.Client(
            timeout=REQUEST_TIMEOUT_SECONDS,
            transport=self._transport,
            headers={"Authorization": self._token, "accept": "application/json"},
        ) as connection:
            for _ in range(MAX_PAGE_COUNT):
                envelope = self._read_page(connection, url)

                _log_remaining_budget(envelope)

                yield _entries_of(envelope, url)

                next_page = _next_page(envelope)

                if next_page is None:
                    return

                url = next_page.copy_remove_param(CREDENTIAL_PARAMETER)

            logger.warning(
                "Stopped reading %s after %d pages: the pagination cursor never ended.",
                url.path,
                MAX_PAGE_COUNT,
            )

    def _read_page(self, connection: httpx.Client, url: httpx.URL) -> ProviderPayload:
        """
        Return the decoded envelope of one page, retrying a repeatable failure.

        Parameters
        ----------
        connection : httpx.Client
            Open connection pool the request is sent through.
        url : httpx.URL
            Fully built page URL, already carrying the API token.

        Returns
        -------
        ProviderPayload
            Decoded response envelope.

        Raises
        ------
        SportmonksError
            When the attempt budget is exhausted, when the status is not worth
            retrying, or when the body is not a JSON object.
        """

        failure = "no attempt was made"

        for attempt in range(1, MAX_ATTEMPTS + 1):
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


def _next_page(envelope: ProviderPayload) -> httpx.URL | None:
    """
    Return the URL of the page following the one described by an envelope.

    Parameters
    ----------
    envelope : ProviderPayload
        Decoded response envelope of the current page.

    Returns
    -------
    httpx.URL or None
        Cursor to follow, or ``None`` when the provider reports no further page
        or reports one without naming it.
    """

    pagination = envelope.get("pagination")

    if not isinstance(pagination, dict) or not pagination.get("has_more"):
        return None

    next_page = pagination.get("next_page")

    if not isinstance(next_page, str) or not next_page:
        return None

    return httpx.URL(next_page)


def _log_remaining_budget(envelope: ProviderPayload) -> None:
    """
    Record at debug level how much of the hourly entity quota is left.

    The subscription meters calls per entity per hour, so the envelope's own
    accounting is the only place a quota problem becomes visible before the
    provider starts refusing requests.

    Parameters
    ----------
    envelope : ProviderPayload
        Decoded response envelope of one page.
    """

    rate_limit = envelope.get("rate_limit")

    if not isinstance(rate_limit, dict):
        return

    logger.debug(
        "Sportmonks reports %s calls left for entity %s, resetting in %s seconds.",
        rate_limit.get("remaining"),
        rate_limit.get("entity"),
        rate_limit.get("resets_in_seconds"),
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
        asked again.
    """

    if response.status_code == httpx.codes.TOO_MANY_REQUESTS:
        reported = _reported_reset(response)

        return min(reported if reported is not None else _backoff(attempt), MAX_RETRY_DELAY_SECONDS)

    if response.status_code >= httpx.codes.INTERNAL_SERVER_ERROR:
        return _backoff(attempt)

    return None


def _reported_reset(response: httpx.Response) -> float | None:
    """
    Return the reset delay a throttled response reports for its own quota.

    Parameters
    ----------
    response : httpx.Response
        Throttled response whose envelope is being inspected.

    Returns
    -------
    float or None
        Seconds the provider says remain of the window, or ``None`` when the
        body does not state it.
    """

    try:
        payload = response.json()
    except ValueError:
        return None

    if not isinstance(payload, dict):
        return None

    rate_limit = payload.get("rate_limit")

    if not isinstance(rate_limit, dict):
        return None

    resets_in_seconds = rate_limit.get("resets_in_seconds")

    if not isinstance(resets_in_seconds, int | float) or isinstance(resets_in_seconds, bool):
        return None

    return max(float(resets_in_seconds), 0.0)


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
