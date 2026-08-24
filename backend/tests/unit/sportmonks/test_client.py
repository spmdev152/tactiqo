import logging

import httpx
import pytest
from django.test import override_settings

from integrations.sportmonks.client import (
    MAX_ATTEMPTS,
    MAX_PAGE_COUNT,
    MAX_RETRY_DELAY_SECONDS,
    ProviderPayload,
    SportmonksClient,
)
from integrations.sportmonks.exceptions import SportmonksError

type ProviderAnswer = tuple[int, ProviderPayload | str]

FIRST_ENTRY: ProviderPayload = {"id": 1}

SECOND_ENTRY: ProviderPayload = {"id": 2}

REPORTED_RESET_SECONDS = 3600

REMAINING_CALLS = 7


def envelope(
    entries: list[ProviderPayload],
    *,
    next_page: str | None = None,
    remaining: int | None = None,
) -> ProviderPayload:
    """
    Build a provider envelope trimmed to the fields the client reads.

    Parameters
    ----------
    entries : list of ProviderPayload
        Entries the page carries.
    next_page : str or None
        Cursor the provider advertises, or ``None`` for a final page.
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
        "pagination": {"has_more": next_page is not None, "next_page": next_page},
    }

    if remaining is not None:
        body["rate_limit"] = {
            "entity": "fixtures",
            "remaining": remaining,
            "resets_in_seconds": REPORTED_RESET_SECONDS,
        }

    return body


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


def test_a_page_is_read_with_the_configured_credential(
    provider_base_url: str, api_token: str
) -> None:
    """
    GIVEN a provider answering one page of entries
    WHEN the pages of a resource are read
    THEN the entries are yielded and the token travelled in the header, not the query
    """

    transport, requests = transport_of((200, envelope([FIRST_ENTRY])))

    pages = list(SportmonksClient(transport).get_pages("/leagues", {"per_page": 100}))

    assert pages == [[FIRST_ENTRY]]
    assert str(requests[0].url).startswith(f"{provider_base_url}/leagues")
    assert requests[0].url.params["per_page"] == "100"
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


def test_pagination_follows_the_advertised_cursor_and_yields_every_page(
    provider_base_url: str,
) -> None:
    """
    GIVEN a provider whose first page advertises a next page
    WHEN the pages of a resource are read
    THEN both pages are yielded in order and the cursor was requested
    """

    cursor = f"{provider_base_url}/fixtures?page=2"

    transport, requests = transport_of(
        (200, envelope([FIRST_ENTRY], next_page=cursor)), (200, envelope([SECOND_ENTRY]))
    )

    pages = list(SportmonksClient(transport).get_pages("/fixtures", {}))

    assert pages == [[FIRST_ENTRY], [SECOND_ENTRY]]
    assert requests[1].url.params["page"] == "2"


def test_a_cursor_carrying_a_stale_credential_is_stripped(
    provider_base_url: str, api_token: str
) -> None:
    """
    GIVEN a next-page cursor that already carries an API token of its own
    WHEN the cursor is followed
    THEN the token is removed from the URL and the header still authenticates
    """

    cursor = f"{provider_base_url}/fixtures?page=2&api_token=expired"

    transport, requests = transport_of(
        (200, envelope([FIRST_ENTRY], next_page=cursor)), (200, envelope([]))
    )

    list(SportmonksClient(transport).get_pages("/fixtures", {}))

    assert "api_token" not in str(requests[1].url)
    assert requests[1].headers["Authorization"] == api_token


def test_a_cursor_that_never_ends_is_abandoned_at_the_page_cap(provider_base_url: str) -> None:
    """
    GIVEN a provider that advertises a next page on every page it returns
    WHEN the pages of a resource are read
    THEN reading stops at the page cap rather than looping forever
    """

    cursor = f"{provider_base_url}/fixtures?page=2"

    transport, requests = transport_of((200, envelope([FIRST_ENTRY], next_page=cursor)))

    pages = list(SportmonksClient(transport).get_pages("/fixtures", {}))

    assert len(pages) == MAX_PAGE_COUNT
    assert len(requests) == MAX_PAGE_COUNT


@pytest.mark.usefixtures("provider_base_url")
def test_a_throttled_request_is_retried_and_then_succeeds(sleeps: list[float]) -> None:
    """
    GIVEN a provider that throttles the first request and then answers it
    WHEN the pages of a resource are read
    THEN the page is returned after a wait clamped to the retry ceiling
    """

    throttled: ProviderAnswer = (429, {"rate_limit": {"resets_in_seconds": REPORTED_RESET_SECONDS}})

    transport, requests = transport_of(throttled, (200, envelope([FIRST_ENTRY])))

    pages = list(SportmonksClient(transport).get_pages("/fixtures", {}))

    assert pages == [[FIRST_ENTRY]]
    assert sleeps == [MAX_RETRY_DELAY_SECONDS]
    assert len(requests) == len(sleeps) + 1


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
    GIVEN a provider reporting how much of the hourly entity quota is left
    WHEN the pages of a resource are read
    THEN the remaining budget is recorded at debug level
    """

    caplog.set_level(logging.DEBUG, logger="integrations.sportmonks.client")

    transport, _ = transport_of((200, envelope([], remaining=REMAINING_CALLS)))

    list(SportmonksClient(transport).get_pages("/fixtures", {}))

    assert f"{REMAINING_CALLS} calls left for entity fixtures" in caplog.text
