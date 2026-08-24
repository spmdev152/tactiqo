import os
from pathlib import Path

import pytest
from django.core.exceptions import ImproperlyConfigured

from config.settings.environment import (
    env_bool,
    env_int_list,
    env_ip_network_list,
    env_str,
    env_str_list,
    load_environment_file,
    require_env_ip_network_list,
    require_env_str,
    require_env_str_list,
)

VARIABLE_NAME = "TACTIQO_TEST_VARIABLE"


def test_env_str_strips_surrounding_whitespace(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    GIVEN a variable exported with padding around its value
    WHEN it is read as a string setting
    THEN the value is returned without the surrounding whitespace
    """

    monkeypatch.setenv(VARIABLE_NAME, "  tactiqo  ")

    assert env_str(VARIABLE_NAME, default="fallback") == "tactiqo"


def test_env_str_falls_back_when_the_variable_is_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    GIVEN an environment where the variable is not set
    WHEN it is read as a string setting
    THEN the declared default is returned
    """

    monkeypatch.delenv(VARIABLE_NAME, raising=False)

    assert env_str(VARIABLE_NAME, default="fallback") == "fallback"


@pytest.mark.parametrize("raw_value", ["1", "true", "TRUE", " yes ", "on", "y", "t"])
def test_env_bool_accepts_truthy_tokens(raw_value: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    GIVEN a variable holding a truthy token used in dotenv files and compose manifests
    WHEN it is read as a boolean setting with a false default
    THEN the token is parsed as true
    """

    monkeypatch.setenv(VARIABLE_NAME, raw_value)

    assert env_bool(VARIABLE_NAME, default=False) is True


@pytest.mark.parametrize("raw_value", ["0", "false", "FALSE", " no ", "off", "n", "f"])
def test_env_bool_accepts_falsy_tokens(raw_value: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    GIVEN a variable holding a falsy token used in dotenv files and compose manifests
    WHEN it is read as a boolean setting with a true default
    THEN the token is parsed as false instead of as a non-empty string
    """

    monkeypatch.setenv(VARIABLE_NAME, raw_value)

    assert env_bool(VARIABLE_NAME, default=True) is False


def test_env_bool_rejects_an_unrecognised_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    GIVEN a variable holding a token that is neither truthy nor falsy
    WHEN it is read as a boolean setting
    THEN ImproperlyConfigured is raised instead of silently using the default
    """

    monkeypatch.setenv(VARIABLE_NAME, "maybe")

    with pytest.raises(ImproperlyConfigured):
        env_bool(VARIABLE_NAME, default=False)


def test_require_env_str_rejects_a_blank_value(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    GIVEN a required variable set to whitespace only
    WHEN it is read as mandatory configuration
    THEN ImproperlyConfigured is raised as if the variable were missing
    """

    monkeypatch.setenv(VARIABLE_NAME, "   ")

    with pytest.raises(ImproperlyConfigured):
        require_env_str(VARIABLE_NAME)


def test_require_env_str_returns_the_configured_value(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    GIVEN a required variable provided by the deployment
    WHEN it is read as mandatory configuration
    THEN the configured value is returned
    """

    monkeypatch.setenv(VARIABLE_NAME, "production-secret")

    assert require_env_str(VARIABLE_NAME) == "production-secret"


def test_env_str_list_drops_empty_entries(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    GIVEN a comma-separated variable with padding, a repeated separator, and a trailing comma
    WHEN it is read as a string list setting
    THEN only the non-empty stripped entries are returned
    """

    monkeypatch.setenv(VARIABLE_NAME, "localhost, 127.0.0.1 ,,api,")

    assert env_str_list(VARIABLE_NAME, default=[]) == ["localhost", "127.0.0.1", "api"]


def test_env_str_list_copies_the_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    GIVEN an absent variable read with a default list owned by the caller
    WHEN the returned list is mutated
    THEN the caller default is left unchanged
    """

    monkeypatch.delenv(VARIABLE_NAME, raising=False)
    default = ["localhost"]

    result = env_str_list(VARIABLE_NAME, default=default)

    result.append("intruder")

    assert default == ["localhost"]


def test_require_env_str_list_rejects_a_separator_only_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    GIVEN a required variable holding only separators and whitespace
    WHEN it is read as a mandatory string list setting
    THEN ImproperlyConfigured is raised because the value parses to zero entries
    """

    monkeypatch.setenv(VARIABLE_NAME, " , , ")

    with pytest.raises(ImproperlyConfigured):
        require_env_str_list(VARIABLE_NAME)


def test_env_int_list_parses_league_identifiers(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    GIVEN a variable holding the subscribed Sportmonks league identifiers
    WHEN it is read as an integer list setting
    THEN every entry is returned as an integer
    """

    monkeypatch.setenv(VARIABLE_NAME, "8, 82, 301, 384, 564")

    assert env_int_list(VARIABLE_NAME, default=[]) == [8, 82, 301, 384, 564]


def test_env_int_list_rejects_a_non_numeric_entry(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    GIVEN a variable mixing a league identifier with a non-numeric entry
    WHEN it is read as an integer list setting
    THEN ImproperlyConfigured is raised instead of a bare parsing error
    """

    monkeypatch.setenv(VARIABLE_NAME, "8,premier-league")

    with pytest.raises(ImproperlyConfigured):
        env_int_list(VARIABLE_NAME, default=[])


def test_env_ip_network_list_accepts_networks_and_bare_addresses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    GIVEN a variable mixing a CIDR network with a single proxy address
    WHEN it is read as a network list setting
    THEN the bare address becomes a single-host network of its own
    """

    monkeypatch.setenv(VARIABLE_NAME, "172.16.0.0/12, 192.0.2.10")

    networks = env_ip_network_list(VARIABLE_NAME, default=[])

    assert [str(network) for network in networks] == ["172.16.0.0/12", "192.0.2.10/32"]


def test_env_ip_network_list_rejects_an_entry_that_is_not_a_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    GIVEN a variable whose entry carries host bits its prefix cannot hold
    WHEN it is read as a network list setting
    THEN ImproperlyConfigured is raised rather than the trust being widened
    """

    monkeypatch.setenv(VARIABLE_NAME, "192.0.2.10/24")

    with pytest.raises(ImproperlyConfigured):
        env_ip_network_list(VARIABLE_NAME, default=[])


def test_require_env_ip_network_list_reads_the_declared_networks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    GIVEN a deployment naming the addresses its forwarding tier speaks from
    WHEN they are read as a mandatory network list
    THEN every entry is parsed in the order it was declared
    """

    monkeypatch.setenv(VARIABLE_NAME, "10.4.0.0/16, 192.0.2.10")

    networks = require_env_ip_network_list(VARIABLE_NAME)

    assert [str(network) for network in networks] == ["10.4.0.0/16", "192.0.2.10/32"]


def test_require_env_ip_network_list_rejects_an_empty_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    GIVEN a deployment exporting the variable with nothing in it
    WHEN it is read as a mandatory network list
    THEN ImproperlyConfigured is raised rather than silently trusting no peer
    """

    monkeypatch.setenv(VARIABLE_NAME, "  ")

    with pytest.raises(ImproperlyConfigured, match=VARIABLE_NAME):
        require_env_ip_network_list(VARIABLE_NAME)


def test_load_environment_file_reads_values_without_overriding_the_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    GIVEN a dotenv file that also declares a variable already set in the process
    WHEN the dotenv file is loaded
    THEN the missing variable is filled in and the injected value is preserved
    """

    dotenv_path = tmp_path / ".env"

    dotenv_path.write_text(f"TACTIQO_FROM_FILE=file-value\n{VARIABLE_NAME}=file-value\n")
    monkeypatch.setattr(os, "environ", {VARIABLE_NAME: "injected-value"})

    assert load_environment_file(dotenv_path) is True
    assert env_str("TACTIQO_FROM_FILE", default="") == "file-value"
    assert env_str(VARIABLE_NAME, default="") == "injected-value"


def test_load_environment_file_ignores_a_missing_file(tmp_path: Path) -> None:
    """
    GIVEN a path where no dotenv file exists, as in a container deployment
    WHEN the dotenv file is loaded
    THEN loading reports that nothing was read instead of failing
    """

    assert load_environment_file(tmp_path / "absent.env") is False
