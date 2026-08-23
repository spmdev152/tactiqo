import importlib
import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.core.management.utils import get_random_secret_key

from config.settings import environment

REIMPORTED_SETTINGS_MODULES = (
    "config.settings.base",
    "config.settings.local",
    "config.settings.preproduction",
    "config.settings.production",
    "config.settings.test",
)

DEPLOYED_SETTINGS_MODULES = ["production", "preproduction"]

PROVIDED_SECRET_KEY = get_random_secret_key()
PROVIDED_HOSTS = "tactiqo.example, .example.com"
EXPECTED_HOSTS = ["tactiqo.example", ".example.com"]
EXPECTED_TRUSTED_ORIGINS = ["https://tactiqo.example", "https://*.example.com"]
LOCAL_DEFAULT_HOSTS = ["localhost", "127.0.0.1", "api", "[::1]"]

PROVIDED_DATABASE_PASSWORD = get_random_secret_key()
PROVIDED_DATABASE_HOST = "postgres.internal"

PROVIDED_DATABASE_VARIABLES = {
    "POSTGRES_DB": "tactiqo",
    "POSTGRES_USER": "tactiqo",
    "POSTGRES_PASSWORD": PROVIDED_DATABASE_PASSWORD,
    "POSTGRES_HOST": PROVIDED_DATABASE_HOST,
}

ONE_YEAR_IN_SECONDS = 31_536_000
ONE_HOUR_IN_SECONDS = 3_600

PRODUCTION_HARDENING_SETTINGS = (
    "CSRF_COOKIE_SECURE",
    "CSRF_TRUSTED_ORIGINS",
    "SECURE_HSTS_SECONDS",
    "SECURE_PROXY_SSL_HEADER",
    "SECURE_SSL_REDIRECT",
    "SESSION_COOKIE_SECURE",
)


@contextmanager
def _uncached_settings_modules() -> Iterator[None]:
    """
    Drop the cached settings modules so the next import re-evaluates them.

    The context manager yields no value: entering it is what removes the modules
    from :data:`sys.modules`, and leaving it restores whatever was cached before.
    """

    preserved = {
        name: sys.modules[name] for name in REIMPORTED_SETTINGS_MODULES if name in sys.modules
    }

    for name in preserved:
        del sys.modules[name]

    try:
        yield
    finally:
        for name in REIMPORTED_SETTINGS_MODULES:
            sys.modules.pop(name, None)

        sys.modules.update(preserved)


@dataclass
class SettingsModuleLoader:
    """
    Importer evaluating settings modules against a controlled environment.

    Attributes
    ----------
    dotenv_requests : list of pathlib.Path
        Dotenv files the imported modules asked for, every one of them intercepted.
    dotenv_overrides : list of bool
        Overriding flag each imported module chose, recorded so a settings module
        cannot start clobbering configuration already injected into the process.

    Methods
    -------
    load(module_name, **environment_variables) -> ModuleType
        Import a settings module against the given environment and nothing else.
    """

    dotenv_requests: list[Path] = field(default_factory=list)
    dotenv_overrides: list[bool] = field(default_factory=list)

    def load(self, module_name: str, **environment_variables: str) -> ModuleType:
        """
        Import a settings module with no configuration source other than the given variables.

        Parameters
        ----------
        module_name : str
            Module name inside the ``config.settings`` package.
        **environment_variables : str
            Complete process environment used while the module is evaluated.

        Returns
        -------
        ModuleType
            Freshly evaluated settings module.
        """

        with (
            patch.object(environment, "load_dotenv", self._intercept_dotenv_load),
            patch.dict(os.environ, environment_variables, clear=True),
            _uncached_settings_modules(),
        ):
            return importlib.import_module(f"config.settings.{module_name}")

    def _intercept_dotenv_load(self, dotenv_path: Path, *, override: bool) -> bool:
        """
        Record a dotenv load request and report that nothing was loaded.

        Parameters
        ----------
        dotenv_path : pathlib.Path
            File the settings module asked to load.
        override : bool
            Overriding flag chosen by the settings module, recorded for assertion.

        Returns
        -------
        bool
            Always ``False``, because no value ever reaches the imported module.
        """

        self.dotenv_requests.append(dotenv_path)
        self.dotenv_overrides.append(override)

        return False


@pytest.fixture
def settings_loader() -> SettingsModuleLoader:
    """
    Return a loader importing settings modules in isolation from the developer machine.

    Returns
    -------
    SettingsModuleLoader
        Loader recording the dotenv requests it intercepted.
    """

    return SettingsModuleLoader()


def load_deployed_settings(
    loader: SettingsModuleLoader,
    module_name: str,
    hosts: str = PROVIDED_HOSTS,
    **extra_variables: str,
) -> ModuleType:
    """
    Import a deployed settings module with the mandatory deployment variables provided.

    Parameters
    ----------
    loader : SettingsModuleLoader
        Loader performing the isolated import.
    module_name : str
        Module name inside the ``config.settings`` package.
    hosts : str, optional
        Raw ``DJANGO_ALLOWED_HOSTS`` value.
    **extra_variables : str
        Further variables exported on top of the mandatory ones.

    Returns
    -------
    ModuleType
        Freshly evaluated settings module.
    """

    return loader.load(
        module_name,
        **PROVIDED_DATABASE_VARIABLES,
        DJANGO_SECRET_KEY=PROVIDED_SECRET_KEY,
        DJANGO_DEBUG="true",
        DJANGO_ALLOWED_HOSTS=hosts,
        **extra_variables,
    )


def test_the_repository_dotenv_file_never_reaches_an_imported_settings_module(
    settings_loader: SettingsModuleLoader,
) -> None:
    """
    GIVEN a working copy whose repository dotenv file may hold real developer values
    WHEN a settings module is imported through the isolated loader
    THEN the load of that file is intercepted and contributes no value to the module
    """

    module = settings_loader.load("local")

    assert settings_loader.dotenv_requests == [module.REPOSITORY_ROOT / ".env"]
    assert module.ALLOWED_HOSTS == LOCAL_DEFAULT_HOSTS


def test_settings_modules_load_the_dotenv_file_without_overriding_the_process(
    settings_loader: SettingsModuleLoader,
) -> None:
    """
    GIVEN a settings module that reads the repository dotenv file on import
    WHEN the module is imported
    THEN it never asks to override configuration already injected into the process
    """

    settings_loader.load("local")

    assert settings_loader.dotenv_overrides == [False]


@pytest.mark.parametrize("module_name", DEPLOYED_SETTINGS_MODULES)
def test_deployed_settings_reject_a_missing_secret_key(
    module_name: str, settings_loader: SettingsModuleLoader
) -> None:
    """
    GIVEN a deployment that exports no environment variable at all
    WHEN the environment settings module is imported
    THEN the import fails loudly, naming the missing secret key variable
    """

    with pytest.raises(ImproperlyConfigured, match="DJANGO_SECRET_KEY"):
        settings_loader.load(module_name)


@pytest.mark.parametrize("module_name", DEPLOYED_SETTINGS_MODULES)
def test_deployed_settings_reject_missing_allowed_hosts(
    module_name: str, settings_loader: SettingsModuleLoader
) -> None:
    """
    GIVEN a deployment that exports the secret key but no allowed hosts
    WHEN the environment settings module is imported
    THEN the import fails loudly, naming the missing allowed hosts variable
    """

    with pytest.raises(ImproperlyConfigured, match="DJANGO_ALLOWED_HOSTS"):
        settings_loader.load(module_name, DJANGO_SECRET_KEY=PROVIDED_SECRET_KEY)


@pytest.mark.parametrize("module_name", DEPLOYED_SETTINGS_MODULES)
def test_deployed_settings_reject_a_missing_database_password(
    module_name: str, settings_loader: SettingsModuleLoader
) -> None:
    """
    GIVEN a deployment that exports the Django variables but no database password
    WHEN the environment settings module is imported
    THEN the import fails loudly instead of connecting with a credential from the repository
    """

    with pytest.raises(ImproperlyConfigured, match="POSTGRES_PASSWORD"):
        settings_loader.load(
            module_name,
            DJANGO_SECRET_KEY=PROVIDED_SECRET_KEY,
            DJANGO_ALLOWED_HOSTS=PROVIDED_HOSTS,
            POSTGRES_DB="tactiqo",
            POSTGRES_USER="tactiqo",
            POSTGRES_HOST=PROVIDED_DATABASE_HOST,
        )


def test_production_takes_the_database_credentials_from_the_environment(
    settings_loader: SettingsModuleLoader,
) -> None:
    """
    GIVEN a production deployment exporting its own database credentials
    WHEN the production settings module is imported
    THEN the credentials come from the environment while the shared connection tuning is kept
    """

    module = load_deployed_settings(settings_loader, "production")

    database = module.DATABASES["default"]

    assert database["PASSWORD"] == PROVIDED_DATABASE_PASSWORD
    assert database["HOST"] == PROVIDED_DATABASE_HOST
    assert database["ENGINE"] == "django.db.backends.postgresql"
    assert database["CONN_HEALTH_CHECKS"] is True


def test_production_resolves_when_the_mandatory_variables_are_exported(
    settings_loader: SettingsModuleLoader,
) -> None:
    """
    GIVEN a production deployment exporting the secret key, the hosts, and a debug request
    WHEN the production settings module is imported
    THEN the secret and hosts come from the environment while debug stays off
    """

    module = load_deployed_settings(settings_loader, "production")

    assert module.SECRET_KEY == PROVIDED_SECRET_KEY
    assert module.ALLOWED_HOSTS == EXPECTED_HOSTS
    assert module.DEBUG is False


def test_production_enforces_https_transport(settings_loader: SettingsModuleLoader) -> None:
    """
    GIVEN a production deployment behind a TLS-terminating proxy
    WHEN the production settings module is imported
    THEN plain HTTP is redirected and the forwarded protocol header is trusted
    """

    module = load_deployed_settings(settings_loader, "production")

    assert module.SECURE_SSL_REDIRECT is True
    assert module.SECURE_PROXY_SSL_HEADER == ("HTTP_X_FORWARDED_PROTO", "https")


def test_production_enables_long_lived_hsts_with_preload(
    settings_loader: SettingsModuleLoader,
) -> None:
    """
    GIVEN a production deployment serving a public domain
    WHEN the production settings module is imported
    THEN HSTS lasts a year, covers subdomains, and opts into browser preload lists
    """

    module = load_deployed_settings(settings_loader, "production")

    assert module.SECURE_HSTS_SECONDS == ONE_YEAR_IN_SECONDS
    assert module.SECURE_HSTS_INCLUDE_SUBDOMAINS is True
    assert module.SECURE_HSTS_PRELOAD is True


def test_production_derives_csrf_trusted_origins_from_the_allowed_hosts(
    settings_loader: SettingsModuleLoader,
) -> None:
    """
    GIVEN a production deployment allowing an exact host and a leading-dot wildcard domain
    WHEN the production settings module is imported
    THEN every host becomes an HTTPS origin and the leading dot becomes a wildcard label
    """

    module = load_deployed_settings(settings_loader, "production")

    assert module.CSRF_TRUSTED_ORIGINS == EXPECTED_TRUSTED_ORIGINS


def test_preproduction_shortens_hsts_and_disables_preload(
    settings_loader: SettingsModuleLoader,
) -> None:
    """
    GIVEN a preproduction deployment whose domain must stay reversible
    WHEN the preproduction settings module is imported
    THEN HSTS lasts an hour and preload is disabled
    """

    module = load_deployed_settings(settings_loader, "preproduction")

    assert module.SECURE_HSTS_SECONDS == ONE_HOUR_IN_SECONDS
    assert module.SECURE_HSTS_PRELOAD is False


def test_preproduction_inherits_the_remaining_production_hardening(
    settings_loader: SettingsModuleLoader,
) -> None:
    """
    GIVEN a preproduction deployment exporting the mandatory variables
    WHEN the preproduction settings module is imported
    THEN it keeps the production transport, cookie, and CSRF hardening
    """

    module = load_deployed_settings(settings_loader, "preproduction")

    assert module.DEBUG is False
    assert module.SECURE_SSL_REDIRECT is True
    assert module.SECURE_HSTS_INCLUDE_SUBDOMAINS is True
    assert module.SESSION_COOKIE_SECURE is True
    assert module.CSRF_COOKIE_SECURE is True
    assert module.CSRF_TRUSTED_ORIGINS == EXPECTED_TRUSTED_ORIGINS


def test_local_resolves_with_an_empty_environment(settings_loader: SettingsModuleLoader) -> None:
    """
    GIVEN a developer machine exporting no Django variable
    WHEN the local settings module is imported
    THEN debug is on and the local hostnames are allowed
    """

    module = settings_loader.load("local")

    assert module.DEBUG is True
    assert module.ALLOWED_HOSTS == LOCAL_DEFAULT_HOSTS


def test_no_database_password_is_committed_to_the_repository(
    settings_loader: SettingsModuleLoader,
) -> None:
    """
    GIVEN a developer machine exporting no database password
    WHEN the local settings module is imported
    THEN the password is empty rather than a credential baked into the settings
    """

    module = settings_loader.load("local")

    assert module.DATABASES["default"]["PASSWORD"] == ""


def test_local_takes_the_secret_key_from_the_environment(
    settings_loader: SettingsModuleLoader,
) -> None:
    """
    GIVEN a developer machine exporting a secret key
    WHEN the local settings module is imported
    THEN the exported value becomes the secret key
    """

    module = settings_loader.load("local", DJANGO_SECRET_KEY=PROVIDED_SECRET_KEY)

    assert module.SECRET_KEY == PROVIDED_SECRET_KEY


def test_local_generates_a_secret_key_when_none_is_exported(
    settings_loader: SettingsModuleLoader,
) -> None:
    """
    GIVEN a developer machine exporting no secret key
    WHEN the local settings module is imported twice
    THEN each import yields a freshly generated key rather than a committed literal
    """

    first_import = settings_loader.load("local")
    second_import = settings_loader.load("local")

    assert first_import.SECRET_KEY
    assert first_import.SECRET_KEY != second_import.SECRET_KEY


@pytest.mark.parametrize("module_name", DEPLOYED_SETTINGS_MODULES)
def test_deployed_settings_never_emit_debug_records(
    module_name: str, settings_loader: SettingsModuleLoader
) -> None:
    """
    GIVEN a deployment that exports DJANGO_LOG_LEVEL=DEBUG by mistake
    WHEN the deployed settings module is imported
    THEN the level is clamped to INFO so debug payloads never reach the logs
    """

    module = load_deployed_settings(
        settings_loader, module_name, hosts="api.tactiqo.example", DJANGO_LOG_LEVEL="DEBUG"
    )

    assert module.LOG_LEVEL == "INFO"
    assert module.LOGGING["root"]["level"] == "INFO"
    assert module.LOGGING["loguru"]["level"] == "INFO"


@pytest.mark.parametrize("module_name", DEPLOYED_SETTINGS_MODULES)
def test_deployed_settings_serialize_logs_and_hide_variable_values(
    module_name: str, settings_loader: SettingsModuleLoader
) -> None:
    """
    GIVEN a deployed environment whose logs are consumed by a collector
    WHEN the deployed settings module is imported
    THEN records are serialized and tracebacks never include variable values
    """

    module = load_deployed_settings(settings_loader, module_name, hosts="api.tactiqo.example")

    assert module.LOGGING["loguru"]["serialize"] is True
    assert module.LOGGING["loguru"]["diagnose"] is False


def test_local_emits_debug_records_for_development(
    settings_loader: SettingsModuleLoader,
) -> None:
    """
    GIVEN a developer machine exporting no logging variable
    WHEN the local settings module is imported
    THEN debug records are emitted in human-readable form rather than serialized
    """

    module = settings_loader.load("local")

    assert module.LOG_LEVEL == "DEBUG"
    assert module.LOGGING["root"]["level"] == "DEBUG"
    assert module.LOGGING["loguru"]["serialize"] is False


def test_local_applies_no_production_hardening(settings_loader: SettingsModuleLoader) -> None:
    """
    GIVEN a developer machine serving the application over plain HTTP
    WHEN the local settings module is imported
    THEN none of the production transport, cookie, or CSRF hardening is applied
    """

    module = settings_loader.load("local")

    applied = [name for name in PRODUCTION_HARDENING_SETTINGS if hasattr(module, name)]

    assert applied == []


def test_test_settings_take_the_secret_key_from_the_environment(
    settings_loader: SettingsModuleLoader,
) -> None:
    """
    GIVEN a suite run exporting a secret key
    WHEN the test settings module is imported
    THEN the exported value becomes the secret key
    """

    module = settings_loader.load("test", DJANGO_SECRET_KEY=PROVIDED_SECRET_KEY)

    assert module.SECRET_KEY == PROVIDED_SECRET_KEY


def test_test_settings_generate_a_secret_key_when_none_is_exported(
    settings_loader: SettingsModuleLoader,
) -> None:
    """
    GIVEN a suite run exporting no secret key, as on a clean continuous integration runner
    WHEN the test settings module is imported twice
    THEN each import yields a freshly generated key rather than a committed literal
    """

    first_import = settings_loader.load("test")
    second_import = settings_loader.load("test")

    assert first_import.SECRET_KEY
    assert first_import.SECRET_KEY != second_import.SECRET_KEY


def test_test_settings_ignore_variables_pointing_at_live_services(
    settings_loader: SettingsModuleLoader,
) -> None:
    """
    GIVEN an environment pointing at the PostgreSQL and Redis services of the local stack
    WHEN the test settings module is imported
    THEN the suite still resolves to in-memory SQLite and the local-memory cache
    """

    module = settings_loader.load(
        "test", POSTGRES_HOST="postgres", POSTGRES_DB="tactiqo", REDIS_URL="redis://redis:6379/0"
    )

    database = module.DATABASES["default"]

    assert database["ENGINE"] == "django.db.backends.sqlite3"
    assert database["NAME"] == ":memory:"
    assert not database.get("HOST")
    assert module.CACHES["default"]["BACKEND"] == "django.core.cache.backends.locmem.LocMemCache"
