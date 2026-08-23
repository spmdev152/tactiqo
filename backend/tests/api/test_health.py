from http import HTTPStatus

import pytest
from django.core.cache import cache
from django.db import OperationalError, connection

from tests.conftest import ApiGet

HEALTH_URL = "/api/v1/health"
DOCS_URL = "/api/v1/docs"
API_VERSION = "1.0.0"


def raise_operational_error(*_args: object, **_kwargs: object) -> None:
    """
    Simulate a backing service refusing the connection.

    Parameters
    ----------
    *_args : object
        Ignored positional arguments of the replaced callable.
    **_kwargs : object
        Ignored keyword arguments of the replaced callable.

    Raises
    ------
    OperationalError
        Always, to drive the unavailable branch of a health probe.
    """

    raise OperationalError("connection refused")


def return_nothing(*_args: object, **_kwargs: object) -> None:
    """
    Simulate a cache that silently loses the value just written.

    Parameters
    ----------
    *_args : object
        Ignored positional arguments of the replaced callable.
    **_kwargs : object
        Ignored keyword arguments of the replaced callable.
    """

    return None


@pytest.mark.django_db
def test_health_reports_ok_when_every_dependency_is_reachable(api_get: ApiGet) -> None:
    """
    GIVEN a reachable database and a working cache backend
    WHEN the health endpoint is requested
    THEN the API answers HTTP 200 with an ok status for every dependency
    """

    response = api_get(HEALTH_URL)

    assert response.status_code == HTTPStatus.OK

    assert response.json() == {
        "status": "ok",
        "version": API_VERSION,
        "database": "ok",
        "cache": "ok",
    }


def test_health_reports_degraded_when_the_database_is_unreachable(
    api_get: ApiGet, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    GIVEN a database connection that raises an operational error
    WHEN the health endpoint is requested
    THEN the API still answers HTTP 200 and reports the database as unavailable
    """

    monkeypatch.setattr(connection, "ensure_connection", raise_operational_error)

    response = api_get(HEALTH_URL)

    assert response.status_code == HTTPStatus.OK

    assert response.json() == {
        "status": "degraded",
        "version": API_VERSION,
        "database": "unavailable",
        "cache": "ok",
    }


@pytest.mark.django_db
def test_health_reports_degraded_when_the_cache_is_unreachable(
    api_get: ApiGet, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    GIVEN a cache backend that raises when the probe value is written
    WHEN the health endpoint is requested
    THEN the API still answers HTTP 200 and reports the cache as unavailable
    """

    monkeypatch.setattr(cache, "set", raise_operational_error)

    response = api_get(HEALTH_URL)

    assert response.status_code == HTTPStatus.OK

    assert response.json() == {
        "status": "degraded",
        "version": API_VERSION,
        "database": "ok",
        "cache": "unavailable",
    }


@pytest.mark.django_db
def test_health_reports_degraded_when_the_cache_loses_the_probe_value(
    api_get: ApiGet, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    GIVEN a cache backend that accepts the write but reads back nothing
    WHEN the health endpoint is requested
    THEN the overall status is degraded and the cache is reported as unavailable
    """

    monkeypatch.setattr(cache, "get", return_nothing)

    response = api_get(HEALTH_URL)

    assert response.status_code == HTTPStatus.OK

    assert response.json() == {
        "status": "degraded",
        "version": API_VERSION,
        "database": "ok",
        "cache": "unavailable",
    }


def test_openapi_documentation_is_served(api_get: ApiGet) -> None:
    """
    GIVEN the versioned API mounted under its URL prefix
    WHEN the interactive documentation path is requested
    THEN the documentation page is served with HTTP 200
    """

    response = api_get(DOCS_URL)

    assert response.status_code == HTTPStatus.OK
