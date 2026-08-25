import datetime
import logging
from http import HTTPStatus

from ninja import P, QueryEx, Router, Status

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
    request: AuthenticatedRequest,
    date: datetime.date,
    league_id: QueryEx[list[int], P(default_factory=list)],
) -> Status[list[FixtureResponse]]:
    """
    Return the fixtures of one UTC calendar day, optionally within some leagues.

    A competition repeated in the query string is collapsed to one identifier,
    so repeating it cannot widen the ``IN`` clause the listing generates.

    Parameters
    ----------
    request : AuthenticatedRequest
        Inbound HTTP request, whose account is recorded at debug level.
    date : date
        Calendar day, interpreted in UTC, whose fixtures are wanted. An
        unparseable value is rejected with HTTP 422.
    league_id : list of int
        Primary keys of the competitions to narrow the day to, repeated once per
        competition in the query string. An absent parameter binds to the empty
        list and asks for every competition; a value that is not an integer is
        rejected with HTTP 422.

    Returns
    -------
    Status of list of FixtureResponse
        Fixtures ordered by kick-off, then by identifier.
    """

    logger.debug("Listing fixtures on %s for %s.", date.isoformat(), request.auth.email)

    requested_leagues = list(dict.fromkeys(league_id))

    fixtures = [
        FixtureResponse.from_orm(fixture) for fixture in list_fixtures_on(date, requested_leagues)
    ]

    return Status(HTTPStatus.OK, fixtures)
