import logging
from http import HTTPStatus

from ninja import Router, Status

from apps.accounts.api.schemas import ErrorResponse
from apps.accounts.api.security import AuthenticatedRequest, SessionTokenAuth
from apps.statistics.api.schemas import FixtureFormResponse
from apps.statistics.application.queries import get_fixture_form

logger = logging.getLogger(__name__)

UNKNOWN_FIXTURE_DETAIL = "Fixture not found."

session_token_auth = SessionTokenAuth()

statistics_router = Router(tags=["statistics"])


@statistics_router.get(
    "/{int:fixture_id}/form",
    auth=session_token_auth,
    response={
        HTTPStatus.OK: FixtureFormResponse,
        HTTPStatus.NOT_FOUND: ErrorResponse,
    },
    summary="Read the pre-match form of both clubs of a fixture",
)
def read_fixture_form(
    request: AuthenticatedRequest, fixture_id: int
) -> Status[FixtureFormResponse] | Status[ErrorResponse]:
    """
    Return both clubs' form before one fixture, in the contracted order.

    A fixture whose clubs have no history behind them answers HTTP 200 with
    every sample counting no matches rather than HTTP 404. The two answers say
    different things: a full grid of zeroes means the platform knows the match
    and has nothing behind it yet, which is what a promoted club on the opening
    weekend genuinely looks like, while HTTP 404 means the identifier names no
    match at all.

    Parameters
    ----------
    request : AuthenticatedRequest
        Inbound HTTP request, whose account is recorded at debug level.
    fixture_id : int
        Primary key of the fixture whose form is wanted. A value that is not an
        integer matches no route and is rejected with HTTP 404.

    Returns
    -------
    Status of FixtureFormResponse or Status of ErrorResponse
        Form of both clubs, or the shared failure body with HTTP 404 when no
        fixture carries that key.
    """

    logger.debug("Reading the form before fixture %s for %s.", fixture_id, request.auth.email)

    form = get_fixture_form(fixture_id)

    if form is None:
        return Status(HTTPStatus.NOT_FOUND, ErrorResponse(detail=UNKNOWN_FIXTURE_DETAIL))

    return Status(HTTPStatus.OK, FixtureFormResponse.from_orm(form))
