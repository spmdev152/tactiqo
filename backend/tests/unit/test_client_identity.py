from ipaddress import ip_network

import pytest
from django.test import RequestFactory, override_settings

from config.client_identity import resolve_client_identity
from tests.conftest import CapturedRecord

BACKEND_FOR_FRONTEND_ADDRESS = "192.0.2.10"

CLIENT_ADDRESS = "198.51.100.7"

FORGED_ADDRESS = "203.0.113.99"

EDGE_ADDRESS = "203.0.113.10"

TRUSTED_NETWORKS = [ip_network(BACKEND_FOR_FRONTEND_ADDRESS)]


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

    assert resolve_client_identity(request) == CLIENT_ADDRESS


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
        "/", REMOTE_ADDR=CLIENT_ADDRESS, headers={"X-Forwarded-For": FORGED_ADDRESS}
    )

    assert resolve_client_identity(request) == CLIENT_ADDRESS


@override_settings(TRUSTED_PROXY_NETWORKS=TRUSTED_NETWORKS)
def test_only_the_rightmost_entry_of_a_chain_is_believed(requests: RequestFactory) -> None:
    """
    GIVEN a chain whose left entries were supplied by the client itself
    WHEN its client is identified
    THEN the rightmost entry wins, because the edge appends after the client
    """

    request = requests.post(
        "/",
        REMOTE_ADDR=BACKEND_FOR_FRONTEND_ADDRESS,
        headers={"X-Forwarded-For": f"{FORGED_ADDRESS}, {CLIENT_ADDRESS}"},
    )

    assert resolve_client_identity(request) == CLIENT_ADDRESS


@override_settings(TRUSTED_PROXY_NETWORKS=TRUSTED_NETWORKS)
def test_a_trusted_rightmost_entry_is_believed_like_any_other(
    requests: RequestFactory,
) -> None:
    """
    GIVEN a client whose own address falls inside a trusted network
    WHEN its client is identified
    THEN that address is still used, so no forged entry to its left is promoted
    """

    request = requests.post(
        "/",
        REMOTE_ADDR=BACKEND_FOR_FRONTEND_ADDRESS,
        headers={"X-Forwarded-For": f"{FORGED_ADDRESS}, {BACKEND_FOR_FRONTEND_ADDRESS}"},
    )

    assert resolve_client_identity(request) == BACKEND_FOR_FRONTEND_ADDRESS


@override_settings(TRUSTED_PROXY_NETWORKS=TRUSTED_NETWORKS)
def test_a_malformed_rightmost_entry_falls_back_to_the_peer(requests: RequestFactory) -> None:
    """
    GIVEN a trusted peer forwarding a chain whose closest entry is not an address
    WHEN its client is identified
    THEN the peer is used rather than the client-supplied entry beside it
    """

    request = requests.post(
        "/",
        REMOTE_ADDR=BACKEND_FOR_FRONTEND_ADDRESS,
        headers={"X-Forwarded-For": f"{FORGED_ADDRESS}, unknown"},
    )

    assert resolve_client_identity(request) == BACKEND_FOR_FRONTEND_ADDRESS


@override_settings(TRUSTED_PROXY_NETWORKS=TRUSTED_NETWORKS)
def test_an_empty_chain_falls_back_to_the_peer(requests: RequestFactory) -> None:
    """
    GIVEN a trusted peer forwarding a header that carries no entry
    WHEN its client is identified
    THEN the peer is used and no client shares an empty identity
    """

    request = requests.post(
        "/", REMOTE_ADDR=BACKEND_FOR_FRONTEND_ADDRESS, headers={"X-Forwarded-For": " , "}
    )

    assert resolve_client_identity(request) == BACKEND_FOR_FRONTEND_ADDRESS


@override_settings(TRUSTED_PROXY_NETWORKS=TRUSTED_NETWORKS)
def test_a_port_suffixed_entry_still_identifies_its_client(requests: RequestFactory) -> None:
    """
    GIVEN an edge that appends the client port, as Azure Front Door does
    WHEN its client is identified
    THEN the address is used without its port rather than refused
    """

    request = requests.post(
        "/",
        REMOTE_ADDR=BACKEND_FOR_FRONTEND_ADDRESS,
        headers={"X-Forwarded-For": f"{CLIENT_ADDRESS}:52104"},
    )

    assert resolve_client_identity(request) == CLIENT_ADDRESS


@override_settings(TRUSTED_PROXY_NETWORKS=TRUSTED_NETWORKS)
def test_an_ipv6_client_is_identified_by_its_prefix(requests: RequestFactory) -> None:
    """
    GIVEN an IPv6 client that can source from any address of its delegated prefix
    WHEN two of its addresses are identified
    THEN both resolve to the same ``/64`` identity, so rotating buys no budget
    """

    first = requests.post(
        "/",
        REMOTE_ADDR=BACKEND_FOR_FRONTEND_ADDRESS,
        headers={"X-Forwarded-For": "2001:db8:1:2::5"},
    )

    second = requests.post(
        "/",
        REMOTE_ADDR=BACKEND_FOR_FRONTEND_ADDRESS,
        headers={"X-Forwarded-For": "[2001:0db8:1:2:ffff::abcd]:41234"},
    )

    assert resolve_client_identity(first) == "2001:db8:1:2::/64"
    assert resolve_client_identity(second) == "2001:db8:1:2::/64"


@override_settings(TRUSTED_PROXY_NETWORKS=TRUSTED_NETWORKS)
def test_an_ipv4_mapped_peer_is_recognised_as_trusted(requests: RequestFactory) -> None:
    """
    GIVEN a dual-stack server reporting its peer in IPv4-mapped IPv6 notation
    WHEN its client is identified
    THEN the peer is still matched against the trusted network and the chain is read
    """

    request = requests.post(
        "/",
        REMOTE_ADDR=f"::ffff:{BACKEND_FOR_FRONTEND_ADDRESS}",
        headers={"X-Forwarded-For": f"::ffff:{CLIENT_ADDRESS}"},
    )

    assert resolve_client_identity(request) == CLIENT_ADDRESS


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

    assert resolve_client_identity(request) == CLIENT_ADDRESS


@override_settings(TRUSTED_PROXY_NETWORKS=[])
def test_no_trusted_network_keys_every_request_to_its_peer(requests: RequestFactory) -> None:
    """
    GIVEN an empty trust list, which is what a local environment ships
    WHEN a request forwards a chain
    THEN the peer address is used, so an unverified header changes nothing
    """

    request = requests.post(
        "/",
        REMOTE_ADDR=BACKEND_FOR_FRONTEND_ADDRESS,
        headers={"X-Forwarded-For": CLIENT_ADDRESS},
    )

    assert resolve_client_identity(request) == BACKEND_FOR_FRONTEND_ADDRESS


@override_settings(TRUSTED_PROXY_NETWORKS=TRUSTED_NETWORKS, TRUSTED_PROXY_HOPS=1)
def test_a_configured_hop_is_discarded_from_the_right(requests: RequestFactory) -> None:
    """
    GIVEN an edge that appends its own address after the visitor's, as GCP does
    WHEN a request is identified with one hop configured
    THEN the entry that edge appended is discarded and the visitor is used
    """

    request = requests.post(
        "/",
        REMOTE_ADDR=BACKEND_FOR_FRONTEND_ADDRESS,
        headers={"X-Forwarded-For": f"{CLIENT_ADDRESS}, {EDGE_ADDRESS}"},
    )

    assert resolve_client_identity(request) == CLIENT_ADDRESS


@override_settings(TRUSTED_PROXY_NETWORKS=TRUSTED_NETWORKS, TRUSTED_PROXY_HOPS=1)
def test_a_visitor_supplying_no_chain_cannot_be_promoted(requests: RequestFactory) -> None:
    """
    GIVEN a configured depth deeper than the chain a request carries
    WHEN the request is identified
    THEN the peer is used, so an entry nothing appended to cannot be promoted
    """

    request = requests.post(
        "/", REMOTE_ADDR=BACKEND_FOR_FRONTEND_ADDRESS, headers={"X-Forwarded-For": FORGED_ADDRESS}
    )

    assert resolve_client_identity(request) == BACKEND_FOR_FRONTEND_ADDRESS


@override_settings(TRUSTED_PROXY_NETWORKS=TRUSTED_NETWORKS, TRUSTED_PROXY_HOPS=1)
def test_a_depth_deeper_than_the_topology_believes_a_visitor_entry(
    requests: RequestFactory,
) -> None:
    """
    GIVEN a depth of one configured against an edge that appends only the visitor
    WHEN the visitor supplies an entry of its own
    THEN that entry is believed, which is why the depth is bounded and documented
    """

    request = requests.post(
        "/",
        REMOTE_ADDR=BACKEND_FOR_FRONTEND_ADDRESS,
        headers={"X-Forwarded-For": f"{FORGED_ADDRESS}, {CLIENT_ADDRESS}"},
    )

    assert resolve_client_identity(request) == FORGED_ADDRESS


@override_settings(TRUSTED_PROXY_NETWORKS=TRUSTED_NETWORKS)
def test_an_unparseable_peer_is_reported(
    requests: RequestFactory, loguru_records: list[CapturedRecord]
) -> None:
    """
    GIVEN a server reporting a peer that is not an address
    WHEN the request is identified
    THEN the peer is used and the shared bucket it implies is logged
    """

    request = requests.post("/", REMOTE_ADDR="", headers={"X-Forwarded-For": CLIENT_ADDRESS})

    assert resolve_client_identity(request) == ""

    assert [
        level for level, _message, _carries_exception in loguru_records if level == "WARNING"
    ] == ["WARNING"]


@override_settings(TRUSTED_PROXY_NETWORKS=TRUSTED_NETWORKS, TRUSTED_PROXY_HOPS=2)
def test_a_chain_too_short_for_the_configured_depth_is_reported(
    requests: RequestFactory, loguru_records: list[CapturedRecord]
) -> None:
    """
    GIVEN a chain that arrived with fewer entries than the configured depth
    WHEN the request is identified
    THEN the mismatch is logged, since it is the only signal the depth is wrong
    """

    request = requests.post(
        "/", REMOTE_ADDR=BACKEND_FOR_FRONTEND_ADDRESS, headers={"X-Forwarded-For": CLIENT_ADDRESS}
    )

    assert resolve_client_identity(request) == BACKEND_FOR_FRONTEND_ADDRESS

    assert [
        level for level, _message, _carries_exception in loguru_records if level == "WARNING"
    ] == ["WARNING"]
