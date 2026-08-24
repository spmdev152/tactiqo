from ipaddress import IPv4Address, IPv6Address, ip_address

from django.conf import settings
from django.http import HttpRequest

FORWARDED_FOR_HEADER = "HTTP_X_FORWARDED_FOR"

type IPAddress = IPv4Address | IPv6Address


def resolve_client_address(request: HttpRequest) -> str:
    """
    Return the address that identifies the client behind a request.

    Every request the API serves in a deployed environment arrives from the
    Next.js backend-for-frontend, so ``REMOTE_ADDR`` alone identifies that one
    peer and would collapse every client into a single bucket. The forwarding
    chain is therefore read, but only from a peer listed in
    ``TRUSTED_PROXY_NETWORKS``, and only its rightmost entry that is neither
    trusted infrastructure nor malformed: entries further left were appended by
    hops closer to the client and may have been chosen by the client itself.
    Anything else falls back to the peer address, which is always truthful.

    Parameters
    ----------
    request : HttpRequest
        Inbound HTTP request whose client is being identified.

    Returns
    -------
    str
        Address to attribute the request to, empty only when the server
        reported no peer at all.
    """

    remote_address = request.META.get("REMOTE_ADDR", "")

    if not _is_trusted_proxy(remote_address):
        return remote_address

    forwarded_address = _rightmost_untrusted_address(request.META.get(FORWARDED_FOR_HEADER, ""))

    return forwarded_address if forwarded_address is not None else remote_address


def _rightmost_untrusted_address(forwarded_for: str) -> str | None:
    """
    Return the closest address in a forwarding chain that is not our own.

    Parameters
    ----------
    forwarded_for : str
        Raw ``X-Forwarded-For`` value, a comma-separated chain.

    Returns
    -------
    str or None
        Rightmost entry that parses as an IP address and belongs to no trusted
        network, or ``None`` when the chain holds no such entry.
    """

    for entry in reversed(forwarded_for.split(",")):
        candidate = entry.strip()
        parsed_candidate = _parse_address(candidate)

        if parsed_candidate is not None and not _is_trusted(parsed_candidate):
            return candidate

    return None


def _is_trusted_proxy(address: str) -> bool:
    """
    Report whether an address belongs to the project's own forwarding tier.

    Parameters
    ----------
    address : str
        Address to test, typically the peer of the request.

    Returns
    -------
    bool
        ``True`` when the address parses and falls inside a trusted network.
    """

    parsed_address = _parse_address(address)

    return parsed_address is not None and _is_trusted(parsed_address)


def _is_trusted(address: IPAddress) -> bool:
    """
    Report whether a parsed address falls inside a configured trusted network.

    Parameters
    ----------
    address : IPAddress
        Parsed address to test.

    Returns
    -------
    bool
        ``True`` when a configured network contains the address.
    """

    return any(address in network for network in settings.TRUSTED_PROXY_NETWORKS)


def _parse_address(value: str) -> IPAddress | None:
    """
    Parse an address, refusing anything a header may have carried instead.

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
        return ip_address(value)
    except ValueError:
        return None
