from ipaddress import ip_network

import pytest
from django.test import RequestFactory, override_settings

from config.client_address import resolve_client_address

BACKEND_FOR_FRONTEND_ADDRESS = "192.0.2.10"

CLIENT_ADDRESS = "198.51.100.7"

EDGE_PROXY_ADDRESS = "192.0.2.20"

TRUSTED_NETWORKS = [ip_network(BACKEND_FOR_FRONTEND_ADDRESS), ip_network(EDGE_PROXY_ADDRESS)]


@pytest.fixture
def requests() -> RequestFactory:
    """
    Return a factory building requests without touching the URL configuration.

    Returns
    -------
    RequestFactory
        Factory used to state a peer address and a forwarding chain.
    """

    return RequestFactory()


@override_settings(TRUSTED_PROXY_NETWORKS=TRUSTED_NETWORKS)
def test_the_forwarded_client_is_used_when_the_peer_is_trusted(
    requests: RequestFactory,
) -> None:
    """
    GIVEN a request from the trusted backend-for-frontend carrying a chain
    WHEN its client is identified
    THEN the forwarded address is used rather than the peer address
    """

    request = requests.post(
        "/",
        REMOTE_ADDR=BACKEND_FOR_FRONTEND_ADDRESS,
        headers={"X-Forwarded-For": CLIENT_ADDRESS},
    )

    assert resolve_client_address(request) == CLIENT_ADDRESS


@override_settings(TRUSTED_PROXY_NETWORKS=TRUSTED_NETWORKS)
def test_the_forwarded_chain_is_ignored_when_the_peer_is_not_trusted(
    requests: RequestFactory,
) -> None:
    """
    GIVEN a request from an untrusted peer that forwards a chain anyway
    WHEN its client is identified
    THEN the peer address is used, so the header cannot buy a fresh bucket
    """

    request = requests.post(
        "/", REMOTE_ADDR=CLIENT_ADDRESS, headers={"X-Forwarded-For": "203.0.113.99"}
    )

    assert resolve_client_address(request) == CLIENT_ADDRESS


@override_settings(TRUSTED_PROXY_NETWORKS=TRUSTED_NETWORKS)
def test_the_rightmost_untrusted_entry_of_a_chain_wins(requests: RequestFactory) -> None:
    """
    GIVEN a chain whose left entries were chosen by the client
    WHEN its client is identified
    THEN the rightmost entry no trusted network contains is used
    """

    request = requests.post(
        "/",
        REMOTE_ADDR=BACKEND_FOR_FRONTEND_ADDRESS,
        headers={"X-Forwarded-For": f"203.0.113.99, {CLIENT_ADDRESS}, {EDGE_PROXY_ADDRESS}"},
    )

    assert resolve_client_address(request) == CLIENT_ADDRESS


@override_settings(TRUSTED_PROXY_NETWORKS=TRUSTED_NETWORKS)
def test_a_malformed_forwarded_entry_is_refused(requests: RequestFactory) -> None:
    """
    GIVEN a trusted peer forwarding a chain whose closest entry is not an address
    WHEN its client is identified
    THEN the entry is skipped, so no header value can reach a cache key
    """

    request = requests.post(
        "/",
        REMOTE_ADDR=BACKEND_FOR_FRONTEND_ADDRESS,
        headers={"X-Forwarded-For": f"{CLIENT_ADDRESS}, not-an-address"},
    )

    assert resolve_client_address(request) == CLIENT_ADDRESS


@override_settings(TRUSTED_PROXY_NETWORKS=TRUSTED_NETWORKS)
def test_a_chain_of_only_trusted_entries_falls_back_to_the_peer(
    requests: RequestFactory,
) -> None:
    """
    GIVEN a trusted peer forwarding a chain that names only trusted hops
    WHEN its client is identified
    THEN the peer address is used rather than one of our own addresses
    """

    request = requests.post(
        "/",
        REMOTE_ADDR=BACKEND_FOR_FRONTEND_ADDRESS,
        headers={"X-Forwarded-For": EDGE_PROXY_ADDRESS},
    )

    assert resolve_client_address(request) == BACKEND_FOR_FRONTEND_ADDRESS


@override_settings(TRUSTED_PROXY_NETWORKS=[ip_network("192.0.2.0/24")])
def test_a_trusted_network_covers_its_addresses(requests: RequestFactory) -> None:
    """
    GIVEN a trust list declared as a network rather than as single addresses
    WHEN a request arrives from an address inside it
    THEN the forwarded client is used, so a dynamic proxy address needs no entry
    """

    request = requests.post(
        "/", REMOTE_ADDR="192.0.2.77", headers={"X-Forwarded-For": CLIENT_ADDRESS}
    )

    assert resolve_client_address(request) == CLIENT_ADDRESS


@override_settings(TRUSTED_PROXY_NETWORKS=[])
def test_no_trusted_network_keys_every_request_to_its_peer(requests: RequestFactory) -> None:
    """
    GIVEN an empty trust list, which is the default
    WHEN a request forwards a chain
    THEN the peer address is used, so the safe default needs no configuration
    """

    request = requests.post(
        "/",
        REMOTE_ADDR=BACKEND_FOR_FRONTEND_ADDRESS,
        headers={"X-Forwarded-For": CLIENT_ADDRESS},
    )

    assert resolve_client_address(request) == BACKEND_FOR_FRONTEND_ADDRESS
