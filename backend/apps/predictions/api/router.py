import logging
from http import HTTPStatus

from ninja import Router, Status

from apps.accounts.api.schemas import ErrorResponse
from apps.accounts.api.security import AuthenticatedRequest, SessionTokenAuth
from apps.predictions.api.schemas import FixturePredictionsResponse
from apps.predictions.application.queries import get_fixture_predictions

logger = logging.getLogger(__name__)

UNKNOWN_FIXTURE_DETAIL = "Fixture not found."

session_token_auth = SessionTokenAuth()

predictions_router = Router(tags=["predictions"])


@predictions_router.get(
    "/{int:fixture_id}/predictions",
    auth=session_token_auth,
    response={
        HTTPStatus.OK: FixturePredictionsResponse,
        HTTPStatus.NOT_FOUND: ErrorResponse,
    },
    summary="Read the prediction probabilities of a fixture",
)
def read_fixture_predictions(
    request: AuthenticatedRequest, fixture_id: int
) -> Status[FixturePredictionsResponse] | Status[ErrorResponse]:
    """
    Return the markets predicted for one fixture, in the contracted order.

    A fixture nobody has predicted answers HTTP 200 with no markets and no
    timestamp rather than HTTP 404. Prediction availability is
    fixture-dependent, so the two answers say different things: an empty
    payload means the platform knows the match and has nothing to show for it,
    while HTTP 404 means the identifier names no match at all.

    Parameters
    ----------
    request : AuthenticatedRequest
        Inbound HTTP request, whose account is recorded at debug level.
    fixture_id : int
        Primary key of the fixture whose predictions are wanted. A value that
        is not an integer matches no route and is rejected with HTTP 404.

    Returns
    -------
    Status of FixturePredictionsResponse or Status of ErrorResponse
        Predicted markets, or the shared failure body with HTTP 404 when no
        fixture carries that key.
    """

    logger.debug("Reading predictions of fixture %s for %s.", fixture_id, request.auth.email)

    predictions = get_fixture_predictions(fixture_id)

    if predictions is None:
        return Status(HTTPStatus.NOT_FOUND, ErrorResponse(detail=UNKNOWN_FIXTURE_DETAIL))

    return Status(HTTPStatus.OK, FixturePredictionsResponse.from_orm(predictions))
