import datetime
import logging
from http import HTTPStatus

from ninja import Router, Status

from apps.accounts.api.security import AuthenticatedRequest, SessionTokenAuth
from apps.fixtures.api.schemas import FixtureResponse, LeagueResponse
from apps.fixtures.application.queries import list_fixtures_on, list_leagues

logger = logging.getLogger(__name__)

session_token_auth = SessionTokenAuth()

leagues_router = Router(tags=["fixtures"])
fixtures_router = Router(tags=["fixtures"])


@leagues_router.get(
    "",
    auth=session_token_auth,
    response={HTTPStatus.OK: list[LeagueResponse]},
    summary="List the competitions the platform covers",
)
def read_leagues(request: AuthenticatedRequest) -> Status[list[LeagueResponse]]:
    """
    Return every competition the platform covers, ordered by name.

    Parameters
    ----------
    request : AuthenticatedRequest
        Inbound HTTP request, whose account is recorded at debug level.

    Returns
    -------
    Status of list of LeagueResponse
        Competitions ordered alphabetically by name.
    """

    logger.debug("Listing competitions for %s.", request.auth.email)

    leagues = [LeagueResponse.from_orm(league) for league in list_leagues()]

    return Status(HTTPStatus.OK, leagues)


@fixtures_router.get(
    "",
    auth=session_token_auth,
    response={HTTPStatus.OK: list[FixtureResponse]},
    summary="List the fixtures kicking off on a UTC calendar day",
)
def read_fixtures(
    request: AuthenticatedRequest, date: datetime.date, league_id: int | None = None
) -> Status[list[FixtureResponse]]:
    """
    Return the fixtures of one UTC calendar day, optionally within one league.

    Parameters
    ----------
    request : AuthenticatedRequest
        Inbound HTTP request, whose account is recorded at debug level.
    date : date
        Calendar day, interpreted in UTC, whose fixtures are wanted. An
        unparseable value is rejected with HTTP 422.
    league_id : int or None
        Primary key of a competition to narrow the day to, or ``None`` for every
        competition.

    Returns
    -------
    Status of list of FixtureResponse
        Fixtures ordered by kick-off, then by identifier.
    """

    logger.debug("Listing fixtures on %s for %s.", date.isoformat(), request.auth.email)

    fixtures = [FixtureResponse.from_orm(fixture) for fixture in list_fixtures_on(date, league_id)]

    return Status(HTTPStatus.OK, fixtures)
