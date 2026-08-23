import os
from collections.abc import Sequence
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

TRUTHY_VALUES = frozenset({"1", "true", "t", "yes", "y", "on"})
FALSY_VALUES = frozenset({"0", "false", "f", "no", "n", "off"})


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
