import os
from collections.abc import Sequence
from ipaddress import IPv4Network, IPv6Network, ip_network
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

TRUTHY_VALUES = frozenset({"1", "true", "t", "yes", "y", "on"})
FALSY_VALUES = frozenset({"0", "false", "f", "no", "n", "off"})

type IPNetwork = IPv4Network | IPv6Network


def load_environment_file(path: Path) -> bool:
    """
    Load a dotenv file without overriding variables already present.

    A missing file is not an error: container deployments inject configuration
    directly and never ship a dotenv file.

    Parameters
    ----------
    path : Path
        Location of the dotenv file to read.

    Returns
    -------
    bool
        ``True`` when the file existed and was parsed.
    """

    return load_dotenv(dotenv_path=path, override=False)


def env_str(name: str, *, default: str) -> str:
    """
    Read a string variable, falling back to a default.

    Parameters
    ----------
    name : str
        Environment variable name.
    default : str
        Value used when the variable is absent.

    Returns
    -------
    str
        Whitespace-stripped value.
    """

    return os.environ.get(name, default).strip()


def require_env_str(name: str) -> str:
    """
    Read a string variable that must be provided by the deployment.

    Parameters
    ----------
    name : str
        Environment variable name.

    Returns
    -------
    str
        Whitespace-stripped value.

    Raises
    ------
    ImproperlyConfigured
        If the variable is missing or empty.
    """

    value = os.environ.get(name, "").strip()

    if not value:
        raise ImproperlyConfigured(
            f"Environment variable {name} is required and must not be empty."
        )

    return value


def env_bool(name: str, *, default: bool) -> bool:
    """
    Read a boolean variable expressed as a common truthy or falsy token.

    Parameters
    ----------
    name : str
        Environment variable name.
    default : bool
        Value used when the variable is absent.

    Returns
    -------
    bool
        Parsed boolean value.

    Raises
    ------
    ImproperlyConfigured
        If the variable is present but not a recognised boolean token.
    """

    raw_value = os.environ.get(name)

    if raw_value is None:
        return default

    normalized_value = raw_value.strip().lower()

    if normalized_value in TRUTHY_VALUES:
        return True

    if normalized_value in FALSY_VALUES:
        return False

    raise ImproperlyConfigured(f"Environment variable {name} must be a boolean, got {raw_value!r}.")


def env_int(name: str, *, default: int, minimum: int) -> int:
    """
    Read an integer variable that must not fall below a bound.

    Parameters
    ----------
    name : str
        Environment variable name.
    default : int
        Value used when the variable is absent.
    minimum : int
        Smallest value the setting accepts.

    Returns
    -------
    int
        Parsed integer value.

    Raises
    ------
    ImproperlyConfigured
        If the variable is present but is not an integer, or is below the bound.
    """

    raw_value = os.environ.get(name)

    if raw_value is None:
        return default

    try:
        value = int(raw_value.strip())
    except ValueError as error:
        raise ImproperlyConfigured(
            f"Environment variable {name} must be an integer, got {raw_value!r}."
        ) from error

    if value < minimum:
        raise ImproperlyConfigured(
            f"Environment variable {name} must be {minimum} or greater, got {value}."
        )

    return value


def env_str_list(name: str, *, default: Sequence[str]) -> list[str]:
    """
    Read a comma-separated list of strings.

    Parameters
    ----------
    name : str
        Environment variable name.
    default : Sequence of str
        Values used when the variable is absent.

    Returns
    -------
    list of str
        Non-empty, whitespace-stripped entries.
    """

    raw_value = os.environ.get(name)

    if raw_value is None:
        return list(default)

    return [entry.strip() for entry in raw_value.split(",") if entry.strip()]


def require_env_str_list(name: str) -> list[str]:
    """
    Read a comma-separated list of strings that must be provided.

    Parameters
    ----------
    name : str
        Environment variable name.

    Returns
    -------
    list of str
        Non-empty, whitespace-stripped entries.

    Raises
    ------
    ImproperlyConfigured
        If the variable is missing, empty, or holds only separators.
    """

    entries = [entry.strip() for entry in require_env_str(name).split(",") if entry.strip()]

    if not entries:
        raise ImproperlyConfigured(f"Environment variable {name} must list at least one entry.")

    return entries


def env_int_list(name: str, *, default: Sequence[int]) -> list[int]:
    """
    Read a comma-separated list of integers.

    Parameters
    ----------
    name : str
        Environment variable name.
    default : Sequence of int
        Values used when the variable is absent.

    Returns
    -------
    list of int
        Parsed integer entries.

    Raises
    ------
    ImproperlyConfigured
        If any entry is not a valid integer.
    """

    entries = env_str_list(name, default=[str(value) for value in default])

    try:
        return [int(entry) for entry in entries]
    except ValueError as error:
        raise ImproperlyConfigured(
            f"Environment variable {name} must be a comma-separated list of integers."
        ) from error


def env_proxy_networks(name: str, *, default: Sequence[str]) -> list[IPNetwork]:
    """
    Read the addresses and CIDR networks a forwarding header may be believed from.

    A bare address is accepted and becomes a single-host network, so an
    operator naming one proxy does not have to write its prefix length.

    Parameters
    ----------
    name : str
        Environment variable name.
    default : Sequence of str
        Entries used when the variable is absent.

    Returns
    -------
    list of IPNetwork
        Parsed networks, in the order they were declared.

    Raises
    ------
    ImproperlyConfigured
        If any entry is not an IP address or CIDR network, host bits included,
        or if an entry is a default route.
    """

    return _parse_proxy_networks(name, env_str_list(name, default=default))


def require_env_proxy_networks(name: str) -> list[IPNetwork]:
    """
    Read a forwarding tier that must be provided.

    Parameters
    ----------
    name : str
        Environment variable name.

    Returns
    -------
    list of IPNetwork
        Parsed networks, in the order they were declared.

    Raises
    ------
    ImproperlyConfigured
        If the variable is missing or empty, or holds an entry that is not an
        IP address or CIDR network, or holds a default route.
    """

    return _parse_proxy_networks(name, require_env_str_list(name))


def _parse_proxy_networks(name: str, entries: Sequence[str]) -> list[IPNetwork]:
    """
    Parse declared forwarding-tier entries into networks.

    Parameters
    ----------
    name : str
        Environment variable name, used in every failure message.
    entries : Sequence of str
        Declared addresses and CIDR networks.

    Returns
    -------
    list of IPNetwork
        Parsed networks, in the order they were declared.

    Raises
    ------
    ImproperlyConfigured
        If an entry is not an IP address or CIDR network, or is a default
        route. A default route would believe a forwarding header from every
        peer, which is the one thing the trust list exists to prevent.
    """

    try:
        networks = [ip_network(entry) for entry in entries]
    except ValueError as error:
        raise ImproperlyConfigured(
            f"Environment variable {name} must be a comma-separated list of "
            f"IP addresses or CIDR networks: {error}"
        ) from error

    for network in networks:
        if network.prefixlen == 0:
            raise ImproperlyConfigured(
                f"Environment variable {name} must not include the default route {network}, "
                f"which would believe a forwarding header from every peer."
            )

    return networks
