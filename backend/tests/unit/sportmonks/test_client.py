import logging

import httpx
import pytest
from django.test import override_settings

from integrations.sportmonks.client import (
    LOW_QUOTA_CALLS,
    MAX_ATTEMPTS,
    MAX_PAGE_COUNT,
    MAX_RETRY_DELAY_SECONDS,
    ProviderPayload,
    SportmonksClient,
)
from integrations.sportmonks.exceptions import SportmonksError
from integrations.sportmonks.fixtures import PAGE_SIZE
from tests.unit.sportmonks.conftest import PROVIDER_BASE_URL

type ProviderAnswer = tuple[int, ProviderPayload | str]

CLIENT_LOGGER = "integrations.sportmonks.client"

FIRST_ENTRY: ProviderPayload = {"id": 1}

SECOND_ENTRY: ProviderPayload = {"id": 2}

PAGE_CURSOR = "eyJmaXh0dXJlIjoxOTQyNzQ1NX0"

FOREIGN_HOST = "attacker.example"

UNREADABLE_CURSOR = f"{PROVIDER_BASE_URL}/fixtures?cursor=\x00"

REPORTED_RESET_SECONDS = 3600

METERED_ENTITY = "Fixture"

HEALTHY_REMAINING_CALLS = 1990

SPENT_REMAINING_CALLS = LOW_QUOTA_CALLS - 1

SHORT_RESET_SECONDS = MAX_RETRY_DELAY_SECONDS / 2

THROTTLE_CARRIERS = [
    pytest.param(
        {"rate_limit": {"resets_in_seconds": REPORTED_RESET_SECONDS}},
        {},
        id="the rate-limit accounting of the envelope",
    ),
    pytest.param({"retry_after": REPORTED_RESET_SECONDS}, {}, id="a top-level retry_after"),
    pytest.param({}, {"Retry-After": str(REPORTED_RESET_SECONDS)}, id="the Retry-After header"),
]

TRUNCATING_PAGINATIONS = [
    pytest.param({"has_more": True}, id="a further page named by no cursor"),
    pytest.param({"has_more": True, "next_cursor": ""}, id="an empty cursor"),
    pytest.param(
        {"has_more": True, "next_cursor": f"{PROVIDER_BASE_URL}/fixtures?page=2"},
        id="a cursor URL carrying no cursor",
    ),
]


def envelope(
    entries: list[ProviderPayload],
    *,
    next_cursor: str | None = None,
    remaining: int | None = None,
) -> ProviderPayload:
    """
    Build a provider envelope trimmed to the fields the client reads.

    Parameters
    ----------
    entries : list of ProviderPayload
        Entries the page carries.
    next_cursor : str or None
        Absolute URL the provider advertises the following page as, in the shape
        it was observed to publish, or ``None`` for a final page.
    remaining : int or None
        Calls the provider says are left of the hourly entity quota, or ``None``
        to omit the accounting entirely.

    Returns
    -------
    ProviderPayload
        Envelope body to answer a request with.
    """

    body: ProviderPayload = {
        "data": entries,
        "pagination": {"has_more": next_cursor is not None, "next_cursor": next_cursor},
    }

    if remaining is not None:
        body["rate_limit"] = {
            "resets_in_seconds": REPORTED_RESET_SECONDS,
            "remaining": remaining,
            "requested_entity": METERED_ENTITY,
        }

    return body


def advertised_page(host_url: str, cursor: str = PAGE_CURSOR) -> str:
    """
    Build the absolute URL a provider advertises its following page as.

    Parameters
    ----------
    host_url : str
        Base the advertised URL is built on, which the test varies to prove the
        payload cannot choose the host a request reaches.
    cursor : str, optional
        Cursor token the advertised URL carries.

    Returns
    -------
    str
        Value to put in the ``next_cursor`` field of a pagination block.
    """

    return f"{host_url}/fixtures?cursor={cursor}&per_page={PAGE_SIZE}"


def transport_of(*answers: ProviderAnswer) -> tuple[httpx.MockTransport, list[httpx.Request]]:
    """
    Build a transport answering with fixed statuses and bodies.

    Parameters
    ----------
    *answers : ProviderAnswer
        Status and body to answer with, in order. The last answer serves every
        further request, which is what makes a permanently failing provider
        expressible without repeating it.

    Returns
    -------
    tuple of httpx.MockTransport and list of httpx.Request
        Transport to hand to the client, and the list its requests land in.
    """

    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)

        status, body = answers[min(len(requests) - 1, len(answers) - 1)]

        if isinstance(body, str):
            return httpx.Response(status, text=body)

        return httpx.Response(status, json=body)

    return httpx.MockTransport(handle), requests


def throttling_transport(
    body: ProviderPayload, headers: dict[str, str]
) -> tuple[httpx.MockTransport, list[httpx.Request]]:
    """
    Build a transport that throttles every request it receives.

    Parameters
    ----------
    body : ProviderPayload
        Envelope the throttled response carries.
    headers : dict of str to str
        Headers the throttled response carries, which is the only place the
        standard ``Retry-After`` can be stated.

    Returns
    -------
    tuple of httpx.MockTransport and list of httpx.Request
        Transport to hand to the client, and the list its requests land in.
    """

    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)

        return httpx.Response(httpx.codes.TOO_MANY_REQUESTS, json=body, headers=headers)

    return httpx.MockTransport(handle), requests


def test_a_page_is_read_with_the_configured_credential(
    provider_base_url: str, api_token: str
) -> None:
    """
    GIVEN a provider answering one page of entries
    WHEN the pages of a resource are read
    THEN the entries are yielded and the token travelled in the header, not the query
    """

    transport, requests = transport_of((200, envelope([FIRST_ENTRY])))

    pages = list(SportmonksClient(transport).get_pages("/leagues", {"per_page": PAGE_SIZE}))

    assert pages == [[FIRST_ENTRY]]
    assert str(requests[0].url).startswith(f"{provider_base_url}/leagues")
    assert requests[0].url.params["per_page"] == str(PAGE_SIZE)
    assert requests[0].headers["Authorization"] == api_token
    assert "api_token" not in str(requests[0].url)


def test_a_path_without_a_leading_slash_reaches_the_same_resource(
    provider_base_url: str,
) -> None:
    """
    GIVEN a resource path written without a leading slash
    WHEN the pages of that resource are read
    THEN the base URL is joined with exactly one separator
    """

    transport, requests = transport_of((200, envelope([])))

    list(SportmonksClient(transport).get_pages("leagues", {}))

    assert requests[0].url.path == f"{httpx.URL(provider_base_url).path}/leagues"


def test_pagination_follows_the_advertised_cursor_and_drops_the_page_size(
    provider_base_url: str,
) -> None:
    """
    GIVEN a provider whose first page advertises a further page as a cursor URL
    WHEN the pages of a resource are read
    THEN both pages are yielded and the second request carries the cursor and no page size
    """

    transport, requests = transport_of(
        (200, envelope([FIRST_ENTRY], next_cursor=advertised_page(provider_base_url))),
        (200, envelope([SECOND_ENTRY])),
    )

    pages = list(SportmonksClient(transport).get_pages("/fixtures", {"per_page": PAGE_SIZE}))

    assert pages == [[FIRST_ENTRY], [SECOND_ENTRY]]
    assert requests[0].url.params["per_page"] == str(PAGE_SIZE)
    assert requests[1].url.params["cursor"] == PAGE_CURSOR
    assert "per_page" not in requests[1].url.params


def test_a_cursor_naming_a_foreign_host_is_never_requested(
    provider_base_url: str, api_token: str
) -> None:
    """
    GIVEN a further page the provider payload advertises on a host of its choosing
    WHEN the cursor is followed
    THEN only the configured host is requested, so the credential never reaches the other one
    """

    transport, requests = transport_of(
        (200, envelope([FIRST_ENTRY], next_cursor=advertised_page(f"https://{FOREIGN_HOST}"))),
        (200, envelope([])),
    )

    list(SportmonksClient(transport).get_pages("/fixtures", {}))

    configured_host = httpx.URL(provider_base_url).host

    assert [request.url.host for request in requests] == [configured_host, configured_host]
    assert requests[1].url.params["cursor"] == PAGE_CURSOR
    assert all(request.headers["Authorization"] == api_token for request in requests)


def test_a_cursor_advertising_a_credential_contributes_only_its_token(
    provider_base_url: str, api_token: str
) -> None:
    """
    GIVEN a further page advertised with an API token and a stale filter of its own
    WHEN the cursor is followed
    THEN only the cursor crosses over and the header still authenticates
    """

    advertised = f"{provider_base_url}/fixtures?cursor={PAGE_CURSOR}&api_token=expired&filters=old"

    transport, requests = transport_of(
        (200, envelope([FIRST_ENTRY], next_cursor=advertised)), (200, envelope([]))
    )

    list(SportmonksClient(transport).get_pages("/fixtures", {}))

    assert "api_token" not in str(requests[1].url)
    assert "filters" not in requests[1].url.params
    assert requests[1].url.params["cursor"] == PAGE_CURSOR
    assert requests[1].headers["Authorization"] == api_token


@pytest.mark.usefixtures("provider_base_url")
def test_a_cursor_that_cannot_be_read_as_a_url_is_reported_as_a_boundary_failure() -> None:
    """
    GIVEN a further page advertised as a value the URL parser refuses outright
    WHEN the pages of a resource are read
    THEN the boundary error is raised rather than the library's own invalid-URL error
    """

    transport, requests = transport_of(
        (200, envelope([FIRST_ENTRY], next_cursor=UNREADABLE_CURSOR))
    )

    with pytest.raises(SportmonksError, match="cannot be read"):
        list(SportmonksClient(transport).get_pages("/fixtures", {}))

    assert len(requests) == 1


@pytest.mark.usefixtures("provider_base_url")
@pytest.mark.parametrize("pagination", TRUNCATING_PAGINATIONS)
def test_a_further_page_that_cannot_be_asked_for_is_reported_rather_than_truncated(
    pagination: ProviderPayload,
) -> None:
    """
    GIVEN a page reporting a further page it names no usable cursor for
    WHEN the pages of a resource are read
    THEN the boundary error is raised rather than the pages already read passing for the whole
    """

    transport, requests = transport_of((200, {"data": [FIRST_ENTRY], "pagination": pagination}))

    with pytest.raises(SportmonksError, match="must not be reported as complete"):
        list(SportmonksClient(transport).get_pages("/fixtures", {}))

    assert len(requests) == 1


def test_a_cursor_that_never_ends_is_reported_rather_than_returned_truncated(
    provider_base_url: str,
) -> None:
    """
    GIVEN a provider that advertises a further page on every page it returns
    WHEN the pages of a resource are read
    THEN the boundary error is raised at the page cap rather than a prefix being returned
    """

    transport, requests = transport_of(
        (200, envelope([FIRST_ENTRY], next_cursor=advertised_page(provider_base_url)))
    )

    with pytest.raises(SportmonksError, match=f"after {MAX_PAGE_COUNT} pages"):
        list(SportmonksClient(transport).get_pages("/fixtures", {}))

    assert len(requests) == MAX_PAGE_COUNT


@pytest.mark.usefixtures("sleeps")
def test_a_failure_on_a_later_page_is_reported_rather_than_a_partial_window(
    provider_base_url: str,
) -> None:
    """
    GIVEN a provider that answers the first page and fails every attempt at the second
    WHEN the pages of a resource are read
    THEN the boundary error is raised, so the page already read cannot pass for a whole window
    """

    transport, _ = transport_of(
        (200, envelope([FIRST_ENTRY], next_cursor=advertised_page(provider_base_url))),
        (500, "upstream failure"),
    )

    read: list[list[ProviderPayload]] = []

    with pytest.raises(SportmonksError, match="HTTP 500"):
        for page in SportmonksClient(transport).get_pages("/fixtures", {}):
            read.append(page)

    assert read == [[FIRST_ENTRY]]


@pytest.mark.usefixtures("provider_base_url")
def test_a_call_whose_budget_is_already_spent_is_abandoned_before_any_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    GIVEN an overall call budget that has elapsed by the time the connection pool opens
    WHEN the pages of a resource are read
    THEN the boundary error names the budget and no request is sent at all
    """

    monkeypatch.setattr("integrations.sportmonks.client.CALL_BUDGET_SECONDS", 0.0)

    transport, requests = transport_of((200, envelope([FIRST_ENTRY])))

    with pytest.raises(SportmonksError, match="budget of this call elapsed"):
        list(SportmonksClient(transport).get_pages("/fixtures", {}))

    assert requests == []


@pytest.mark.usefixtures("provider_base_url")
def test_a_throttled_request_whose_quota_returns_at_once_is_retried(sleeps: list[float]) -> None:
    """
    GIVEN a provider throttling the first request and reporting a reset inside the retry ceiling
    WHEN the pages of a resource are read
    THEN the page is returned after waiting exactly the reported reset
    """

    throttled: ProviderAnswer = (429, {"rate_limit": {"resets_in_seconds": SHORT_RESET_SECONDS}})

    transport, requests = transport_of(throttled, (200, envelope([FIRST_ENTRY])))

    pages = list(SportmonksClient(transport).get_pages("/fixtures", {}))

    assert pages == [[FIRST_ENTRY]]
    assert sleeps == [SHORT_RESET_SECONDS]
    assert len(requests) == len(sleeps) + 1


@pytest.mark.usefixtures("provider_base_url")
@pytest.mark.parametrize(("body", "headers"), THROTTLE_CARRIERS)
def test_a_throttle_resetting_beyond_the_ceiling_is_abandoned_instead_of_retried(
    sleeps: list[float],
    caplog: pytest.LogCaptureFixture,
    body: ProviderPayload,
    headers: dict[str, str],
) -> None:
    """
    GIVEN a throttled response stating a reset far longer than any retry could outlast
    WHEN the pages of a resource are read
    THEN the boundary error is raised at once and the spent quota is reported at warning level
    """

    caplog.set_level(logging.WARNING, logger=CLIENT_LOGGER)

    transport, requests = throttling_transport(body, headers)

    with pytest.raises(SportmonksError, match="HTTP 429"):
        list(SportmonksClient(transport).get_pages("/fixtures", {}))

    assert len(requests) == 1
    assert sleeps == []
    assert "hourly quota is spent" in caplog.text


@pytest.mark.usefixtures("provider_base_url")
def test_a_failing_provider_is_abandoned_once_the_attempt_cap_is_spent(
    sleeps: list[float],
) -> None:
    """
    GIVEN a provider that answers every attempt with a server error
    WHEN the pages of a resource are read
    THEN the boundary error is raised after exactly the permitted attempts
    """

    transport, requests = transport_of((500, "upstream failure"))

    with pytest.raises(SportmonksError, match="HTTP 500"):
        list(SportmonksClient(transport).get_pages("/fixtures", {}))

    assert len(requests) == MAX_ATTEMPTS
    assert len(sleeps) == MAX_ATTEMPTS - 1


@pytest.mark.usefixtures("provider_base_url")
def test_a_rejected_request_is_not_repeated(sleeps: list[float]) -> None:
    """
    GIVEN a provider rejecting a request with a status a repeat cannot change
    WHEN the pages of a resource are read
    THEN the boundary error is raised without spending a second attempt
    """

    transport, requests = transport_of((404, {"message": "not found"}))

    with pytest.raises(SportmonksError, match="HTTP 404"):
        list(SportmonksClient(transport).get_pages("/fixtures", {}))

    assert len(requests) == 1
    assert sleeps == []


@pytest.mark.usefixtures("provider_base_url")
def test_a_transport_failure_is_reported_as_a_boundary_failure(sleeps: list[float]) -> None:
    """
    GIVEN a provider that cannot be reached at all
    WHEN the pages of a resource are read
    THEN the boundary error is raised rather than the transport error
    """

    def unreachable(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("unreachable", request=request)

    with pytest.raises(SportmonksError, match="ConnectTimeout"):
        list(SportmonksClient(httpx.MockTransport(unreachable)).get_pages("/fixtures", {}))

    assert len(sleeps) == MAX_ATTEMPTS - 1


@pytest.mark.usefixtures("provider_base_url")
def test_a_body_that_is_not_json_is_reported_as_a_boundary_failure() -> None:
    """
    GIVEN a provider answering successfully with something that is not JSON
    WHEN the pages of a resource are read
    THEN the boundary error is raised rather than a decoding error
    """

    transport, _ = transport_of((200, "<html>maintenance</html>"))

    with pytest.raises(SportmonksError, match="not JSON"):
        list(SportmonksClient(transport).get_pages("/fixtures", {}))


@pytest.mark.usefixtures("provider_base_url")
def test_an_envelope_without_a_data_list_is_reported_as_a_boundary_failure() -> None:
    """
    GIVEN a provider answering successfully with an envelope carrying no data
    WHEN the pages of a resource are read
    THEN the boundary error is raised rather than a failure further downstream
    """

    transport, _ = transport_of((200, {"message": "no subscription"}))

    with pytest.raises(SportmonksError, match="without a data list"):
        list(SportmonksClient(transport).get_pages("/fixtures", {}))


@override_settings(SPORTMONKS_API_TOKEN="")
def test_an_unconfigured_credential_is_refused_before_any_request() -> None:
    """
    GIVEN a deployment that configured no Sportmonks API token
    WHEN a client is built
    THEN the boundary error is raised instead of an unauthenticated request
    """

    transport, requests = transport_of((200, envelope([])))

    with pytest.raises(SportmonksError, match="No Sportmonks API token"):
        SportmonksClient(transport)

    assert requests == []


@pytest.mark.usefixtures("provider_base_url")
def test_the_remaining_quota_is_recorded_for_diagnosis(caplog: pytest.LogCaptureFixture) -> None:
    """
    GIVEN a provider reporting most of the hourly quota of an entity still available
    WHEN the pages of a resource are read
    THEN the remaining budget and the entity it is metered against are recorded at debug level
    """

    caplog.set_level(logging.DEBUG, logger=CLIENT_LOGGER)

    transport, _ = transport_of((200, envelope([], remaining=HEALTHY_REMAINING_CALLS)))

    list(SportmonksClient(transport).get_pages("/fixtures", {}))

    assert f"{HEALTHY_REMAINING_CALLS} calls left for entity {METERED_ENTITY}" in caplog.text


@pytest.mark.usefixtures("provider_base_url")
def test_a_nearly_spent_quota_is_reported_where_a_deployed_sink_keeps_it(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    GIVEN a provider reporting fewer calls left than the boundary treats as healthy
    WHEN the pages of a resource are read
    THEN the quota is reported at warning level, which the deployed log level does not clamp away
    """

    caplog.set_level(logging.WARNING, logger=CLIENT_LOGGER)

    transport, _ = transport_of((200, envelope([], remaining=SPENT_REMAINING_CALLS)))

    list(SportmonksClient(transport).get_pages("/fixtures", {}))

    assert f"only {SPENT_REMAINING_CALLS} calls left for entity {METERED_ENTITY}" in caplog.text
