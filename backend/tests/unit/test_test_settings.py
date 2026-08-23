import os

from django.conf import settings

EXPECTED_SETTINGS_MODULE = "config.settings.test"


def test_the_suite_runs_under_the_test_settings_module() -> None:
    """
    GIVEN a suite started with the settings module pinned in pytest addopts
    WHEN the active settings module is inspected
    THEN the environment variable and Django both resolve to the test settings
    """

    assert os.environ["DJANGO_SETTINGS_MODULE"] == EXPECTED_SETTINGS_MODULE
    assert settings.SETTINGS_MODULE == EXPECTED_SETTINGS_MODULE


def test_the_suite_uses_an_in_memory_database() -> None:
    """
    GIVEN the test settings module in use
    WHEN the default database configuration is inspected
    THEN it is an in-memory SQLite database that needs no PostgreSQL host
    """

    database = settings.DATABASES["default"]

    assert database["ENGINE"] == "django.db.backends.sqlite3"
    assert "memory" in str(database["NAME"])
    assert not database.get("HOST")


def test_the_suite_uses_an_in_memory_cache() -> None:
    """
    GIVEN the test settings module in use
    WHEN the default cache configuration is inspected
    THEN it is the local-memory backend that needs no Redis server
    """

    assert settings.CACHES["default"]["BACKEND"] == "django.core.cache.backends.locmem.LocMemCache"
