import logging
from ipaddress import IPv4Address, IPv6Address, ip_address, ip_network

from django.conf import settings
from django.http import HttpRequest

logger = logging.getLogger(__name__)

FORWARDED_FOR_HEADER = "HTTP_X_FORWARDED_FOR"

IPV6_CLIENT_PREFIX_LENGTH = 64

type IPAddress = IPv4Address | IPv6Address


def resolve_client_identity(request: HttpRequest) -> str:
    """
    Return the identity a request is attributed to for rate limiting.

    Every request the API serves in a deployed environment arrives from the
    Next.js backend-for-frontend, so ``REMOTE_ADDR`` identifies that one peer
    and would collapse every visitor into a single bucket. The forwarding chain
    is therefore read, but only from a peer listed in
    ``TRUSTED_PROXY_NETWORKS``.

    Which entry of that chain names the visitor is a property of the topology,
    not something the chain itself can prove, so ``TRUSTED_PROXY_HOPS`` states
    how many entries our own infrastructure appended after the visitor's
    address: none for an edge that appends only its peer, as nginx does with
    ``$proxy_add_x_forwarded_for``, and one for an edge that also appends
    itself, as Google Cloud's external Application Load Balancer does. Counting
    from the right is what makes the entries a visitor supplied unreachable,
    since every hop appends after them. A chain too short for the configured
    count, or an entry that is not an address, falls back to the peer rather
    than to a value the visitor may have chosen.

    An IPv6 client is identified by its ``/64`` prefix rather than by its
    address, because a delegated ``/64`` lets one client source from 2**64
    addresses and a per-address bucket would be free to escape.

    Parameters
    ----------
    request : HttpRequest
        Inbound HTTP request whose client is being identified.

    Returns
    -------
    str
        Identity to attribute the request to: a canonical IPv4 address, an
        IPv6 ``/64`` network, or the raw peer value when it is not an address.
    """

    peer = request.META.get("REMOTE_ADDR", "")

    parsed_peer = _parse_address(peer)

    if parsed_peer is None:
        logger.warning(
            "Attributing a request to the unparseable peer %r, so every client shares one bucket.",
            peer,
        )

        return peer

    if not _is_trusted(parsed_peer):
        return _identity_of(parsed_peer)

    forwarded_client = _forwarded_client(request.META.get(FORWARDED_FOR_HEADER, ""))

    return _identity_of(forwarded_client if forwarded_client is not None else parsed_peer)


def _forwarded_client(forwarded_for: str) -> IPAddress | None:
    """
    Return the address a forwarding chain attributes to the visitor.

    Parameters
    ----------
    forwarded_for : str
        Raw ``X-Forwarded-For`` value, a comma-separated chain.

    Returns
    -------
    IPAddress or None
        Entry sitting ``TRUSTED_PROXY_HOPS`` places left of the end of the
        chain, or ``None`` when the chain is shorter than that or that entry is
        not an address.
    """

    entries = [
        stripped for stripped in (entry.strip() for entry in forwarded_for.split(",")) if stripped
    ]

    position = settings.TRUSTED_PROXY_HOPS + 1

    if len(entries) < position:
        return None

    return _parse_address(entries[-position])


def _is_trusted(address: IPAddress) -> bool:
    """
    Report whether an address belongs to the project's own forwarding tier.

    Parameters
    ----------
    address : IPAddress
        Parsed address to test, always a peer address rather than a header
        value, because only a peer address is a fact rather than a claim.

    Returns
    -------
    bool
        ``True`` when a configured network contains the address.
    """

    return any(address in network for network in settings.TRUSTED_PROXY_NETWORKS)


def _identity_of(address: IPAddress) -> str:
    """
    Return the canonical identity of a parsed address.

    Parameters
    ----------
    address : IPAddress
        Address to canonicalize.

    Returns
    -------
    str
        The address itself for IPv4, its ``/64`` network for IPv6. Canonical
        text matters because the identity becomes a cache key, and an address
        with several spellings would otherwise hold several buckets.
    """

    if isinstance(address, IPv4Address):
        return str(address)

    return str(ip_network(f"{address}/{IPV6_CLIENT_PREFIX_LENGTH}", strict=False))


def _parse_address(value: str) -> IPAddress | None:
    """
    Parse an address, refusing anything a header may have carried instead.

    An IPv4-mapped IPv6 address is returned in its IPv4 form, so a dual-stack
    peer is still recognised against an IPv4 trusted network and one client
    cannot hold two buckets by arriving in two notations.

    Parameters
    ----------
    value : str
        Candidate address, from request metadata or a forwarding header.

    Returns
    -------
    IPAddress or None
        Parsed address, or ``None`` when the value is not one. Validating here
        is also what keeps a header value out of a cache key.
    """

    try:
        parsed = ip_address(_without_port(value))
    except ValueError:
        return None

    return parsed.ipv4_mapped or parsed if isinstance(parsed, IPv6Address) else parsed


def _without_port(value: str) -> str:
    """
    Return an address stripped of the port some proxies append to it.

    Azure Front Door writes ``address:port`` and several proxies write the
    bracketed ``[address]:port`` form for IPv6, so refusing both would attribute
    every visitor behind such an edge to the peer, which is one shared bucket.

    Parameters
    ----------
    value : str
        Candidate entry, with or without a port.

    Returns
    -------
    str
        The entry without its port, or the entry unchanged when it carries
        none. A bare IPv6 address is left alone, since its own colons are not
        a port separator.
    """

    if value.startswith("[") and "]" in value:
        return value[1 : value.index("]")]

    host, separator, port = value.rpartition(":")

    if separator and host and ":" not in host and port.isdigit():
        return host

    return value
