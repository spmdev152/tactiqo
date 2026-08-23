import logging
from enum import StrEnum

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.http import HttpRequest
from ninja import Router, Schema

logger = logging.getLogger(__name__)

HEALTH_PROBE_CACHE_KEY = "health-probe"
HEALTH_PROBE_CACHE_TIMEOUT_SECONDS = 5
HEALTH_PROBE_VALUE = "probe"


class DependencyStatus(StrEnum):
    """
    Reachability of a single backing service.

    Attributes
    ----------
    OK : str
        Serialized as ``"ok"``, the dependency answered the probe.
    UNAVAILABLE : str
        Serialized as ``"unavailable"``, the probe failed or timed out.
    """

    OK = "ok"
    UNAVAILABLE = "unavailable"


class ServiceStatus(StrEnum):
    """
    Aggregated readiness of the API process.

    Attributes
    ----------
    OK : str
        Serialized as ``"ok"``, every dependency answered its probe.
    DEGRADED : str
        Serialized as ``"degraded"``, the API serves traffic while at least one
        dependency is unavailable.
    """

    OK = "ok"
    DEGRADED = "degraded"


class HealthResponse(Schema):
    """
    Public response contract of the health endpoint.

    Attributes
    ----------
    status : ServiceStatus
        Aggregated readiness, degraded whenever a dependency is unavailable.
    version : str
        API version the process serves, taken from ``settings.API_VERSION``.
    database : DependencyStatus
        Reachability of the relational database.
    cache : DependencyStatus
        Reachability of the cache, verified with a write-then-read round trip.
    """

    status: ServiceStatus
    version: str
    database: DependencyStatus
    cache: DependencyStatus


def check_database() -> DependencyStatus:
    """
    Probe the configured relational database.

    Any failure is reported as an unavailable dependency: a health probe must
    never raise, otherwise orchestration loses the difference between a degraded
    dependency and a crashed process.

    Returns
    -------
    DependencyStatus
        ``OK`` when a connection to the database can be established.
    """

    try:
        connection.ensure_connection()
    except Exception:
        logger.warning("Database health probe failed.", exc_info=True)

        return DependencyStatus.UNAVAILABLE

    return DependencyStatus.OK


def check_cache() -> DependencyStatus:
    """
    Probe the configured cache backend with a write-then-read round trip.

    Returns
    -------
    DependencyStatus
        ``OK`` when the value written to the cache is read back unchanged.
    """

    try:
        cache.set(HEALTH_PROBE_CACHE_KEY, HEALTH_PROBE_VALUE, HEALTH_PROBE_CACHE_TIMEOUT_SECONDS)
        stored_value = cache.get(HEALTH_PROBE_CACHE_KEY)
    except Exception:
        logger.warning("Cache health probe failed.", exc_info=True)

        return DependencyStatus.UNAVAILABLE

    if stored_value != HEALTH_PROBE_VALUE:
        return DependencyStatus.UNAVAILABLE

    return DependencyStatus.OK


router = Router(tags=["system"])


@router.get("/health", response=HealthResponse, summary="Report API and dependency health")
def read_health(request: HttpRequest) -> HealthResponse:
    """
    Return the readiness of the API process and of its backing services.

    The endpoint is consumed by container orchestration and by the web
    application, so it always answers with HTTP 200 and expresses trouble in the
    payload instead of failing the request.

    Parameters
    ----------
    request : HttpRequest
        Inbound HTTP request, logged at debug level so local development can tell
        an orchestration probe apart from a browser or a curl call.

    Returns
    -------
    HealthResponse
        Aggregated status plus the status of each probed dependency.
    """

    database_status = check_database()
    cache_status = check_cache()

    dependencies_are_healthy = (
        database_status is DependencyStatus.OK and cache_status is DependencyStatus.OK
    )

    logger.debug(
        "Health probe from %s reported database=%s cache=%s",
        request.META.get("REMOTE_ADDR", "unknown"),
        database_status,
        cache_status,
    )

    return HealthResponse(
        status=ServiceStatus.OK if dependencies_are_healthy else ServiceStatus.DEGRADED,
        version=settings.API_VERSION,
        database=database_status,
        cache=cache_status,
    )
