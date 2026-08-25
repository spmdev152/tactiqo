from datetime import UTC, datetime
from decimal import Decimal
from http import HTTPStatus
from typing import cast

import pytest

from apps.fixtures.models import Fixture, League, Team
from apps.predictions.api.router import UNKNOWN_FIXTURE_DETAIL
from apps.predictions.domain.enums import (
    PredictionMarket,
    PredictionReliability,
    PredictionSelection,
)
from apps.predictions.models import FixturePrediction, LeagueMarketReliability
from tests.conftest import ApiGet, ApiPost, UserFactory

LOGIN_URL = "/api/v1/auth/login"
FIXTURES_URL = "/api/v1/fixtures"

SYNCHRONIZED_AT = datetime(2026, 8, 25, 6, 0, tzinfo=UTC)

KICKOFF_AT = datetime(2026, 8, 29, 11, 30, tzinfo=UTC)


def bearer_token(api_post: ApiPost, user: UserFactory, user_password: str) -> str:
    """
    Sign an account in and return the bearer token the API issued.

    Parameters
    ----------
    api_post : ApiPost
        Callable issuing JSON POST requests.
    user : UserFactory
        Factory persisting the account to sign in.
    user_password : str
        Password the factory gave the account.

    Returns
    -------
    str
        Bearer token authenticating the created account.
    """

    account = user()

    response = api_post(LOGIN_URL, {"email": account.email, "password": user_password})

    return str(response.json()["token"])


def json_object(payload: object) -> dict[str, object]:
    """
    Narrow a decoded response body to the object the contract promises.

    Parameters
    ----------
    payload : object
        Decoded response body.

    Returns
    -------
    dict of str to object
        Response body as a JSON object.
    """

    return cast(dict[str, object], payload)


def json_objects(payload: object) -> list[dict[str, object]]:
    """
    Narrow a decoded member of a response body to a list of objects.

    Parameters
    ----------
    payload : object
        Member of a decoded response body.

    Returns
    -------
    list of dict of str to object
        Member as a list of JSON objects.
    """

    return cast(list[dict[str, object]], payload)


def predictions_url(fixture_id: int) -> str:
    """
    Build the prediction endpoint of one fixture.

    Parameters
    ----------
    fixture_id : int
        Primary key the endpoint is addressed with.

    Returns
    -------
    str
        Absolute path of the fixture's prediction endpoint.
    """

    return f"{FIXTURES_URL}/{fixture_id}/predictions"


def store_premier_league() -> League:
    """
    Persist the competition every fixture below belongs to.

    Returns
    -------
    League
        Stored competition.
    """

    return League.objects.create(
        sportmonks_id=8,
        name="Premier League",
        short_code="UK PL",
        logo_url="https://cdn.example.test/leagues/8.png",
        country_name="England",
        country_flag_url="https://cdn.example.test/countries/en.png",
    )


def store_team(sportmonks_id: int, name: str, short_code: str) -> Team:
    """
    Persist a club.

    Parameters
    ----------
    sportmonks_id : int
        Provider identifier of the club.
    name : str
        Club name.
    short_code : str
        Club abbreviation.

    Returns
    -------
    Team
        Stored club.
    """

    return Team.objects.create(
        sportmonks_id=sportmonks_id,
        name=name,
        short_code=short_code,
        crest_url=f"https://cdn.example.test/teams/{sportmonks_id}.png",
    )


def store_fixture(league: League) -> Fixture:
    """
    Persist the single fixture the prediction endpoint is read for.

    Parameters
    ----------
    league : League
        Competition the match belongs to, which is also the competition whose
        reliability grades the endpoint reads.

    Returns
    -------
    Fixture
        Stored fixture.
    """

    return Fixture.objects.create(
        sportmonks_id=1,
        league=league,
        home_team=store_team(8, "Liverpool", "LIV"),
        away_team=store_team(63, "Nottingham Forest", "NFO"),
        kickoff_at=KICKOFF_AT,
        synchronized_at=SYNCHRONIZED_AT,
    )


def store_prediction(
    fixture: Fixture,
    market: PredictionMarket,
    selection: PredictionSelection,
    probability: str,
    synchronized_at: datetime = SYNCHRONIZED_AT,
) -> FixturePrediction:
    """
    Persist the chance one outcome of one market is given.

    Parameters
    ----------
    fixture : Fixture
        Match the prediction belongs to.
    market : PredictionMarket
        Market the outcome belongs to.
    selection : PredictionSelection
        Outcome the chance belongs to.
    probability : str
        Percentage as a decimal string, so the stored scale is written the way
        the contract states it rather than inherited from a float literal.
    synchronized_at : datetime
        Instant the row last agreed with the provider.

    Returns
    -------
    FixturePrediction
        Stored prediction.
    """

    return FixturePrediction.objects.create(
        fixture=fixture,
        market=market,
        selection=selection,
        probability=Decimal(probability),
        synchronized_at=synchronized_at,
    )


def store_reliability(
    league: League, market: PredictionMarket, quality: PredictionReliability, hit_ratio: str
) -> LeagueMarketReliability:
    """
    Persist how much the provider's model for one market is worth in a league.

    Parameters
    ----------
    league : League
        Competition the grade applies to.
    market : PredictionMarket
        Market the grade applies to.
    quality : PredictionReliability
        Graded quality of the model.
    hit_ratio : str
        Share of past predictions the model got right, as a decimal string.

    Returns
    -------
    LeagueMarketReliability
        Stored grade.
    """

    return LeagueMarketReliability.objects.create(
        league=league,
        market=market,
        quality=quality,
        hit_ratio=Decimal(hit_ratio),
        synchronized_at=SYNCHRONIZED_AT,
    )


def store_three_markets() -> Fixture:
    """
    Persist one fixture carrying three markets, none of them stored in order.

    Both the markets and the outcomes inside them are written against the order
    the contract promises, and only two of the three markets are graded, so a
    single read proves the ordering, the grading, and the ungraded market at
    once. Double chance is the ungraded one because the provider publishes no
    predictability entry for it at all.

    Returns
    -------
    Fixture
        Stored fixture, carrying eight predictions across three markets.
    """

    premier_league = store_premier_league()

    fixture = store_fixture(premier_league)

    store_prediction(fixture, PredictionMarket.BOTH_TEAMS_TO_SCORE, PredictionSelection.NO, "46.00")
    store_prediction(
        fixture, PredictionMarket.BOTH_TEAMS_TO_SCORE, PredictionSelection.YES, "54.00"
    )

    store_prediction(
        fixture, PredictionMarket.DOUBLE_CHANCE, PredictionSelection.DRAW_OR_AWAY, "73.00"
    )
    store_prediction(
        fixture, PredictionMarket.DOUBLE_CHANCE, PredictionSelection.HOME_OR_AWAY, "75.14"
    )
    store_prediction(
        fixture, PredictionMarket.DOUBLE_CHANCE, PredictionSelection.HOME_OR_DRAW, "51.78"
    )

    store_prediction(fixture, PredictionMarket.FULLTIME_RESULT, PredictionSelection.AWAY, "48.18")
    store_prediction(fixture, PredictionMarket.FULLTIME_RESULT, PredictionSelection.HOME, "26.96")
    store_prediction(fixture, PredictionMarket.FULLTIME_RESULT, PredictionSelection.DRAW, "24.82")

    store_reliability(
        premier_league,
        PredictionMarket.BOTH_TEAMS_TO_SCORE,
        PredictionReliability.GOOD,
        "0.625",
    )

    store_reliability(
        premier_league, PredictionMarket.FULLTIME_RESULT, PredictionReliability.MEDIUM, "0.500"
    )

    return fixture


@pytest.mark.django_db
def test_predictions_returns_every_market_in_the_contracted_shape(
    api_get: ApiGet, api_post: ApiPost, user: UserFactory, user_password: str
) -> None:
    """
    GIVEN a fixture carrying three markets, stored in neither promised order
    WHEN its predictions are requested
    THEN the markets and their outcomes come back in the promised order
    """

    fixture = store_three_markets()

    token = bearer_token(api_post, user, user_password)

    response = api_get(predictions_url(fixture.pk), token=token)

    assert response.status_code == HTTPStatus.OK

    assert json_object(response.json()) == {
        "fixture_id": fixture.pk,
        "synchronized_at": "2026-08-25T06:00:00Z",
        "markets": [
            {
                "market": "fulltime_result",
                "reliability": "medium",
                "hit_ratio": 0.5,
                "selections": [
                    {"selection": "home", "probability": 26.96},
                    {"selection": "draw", "probability": 24.82},
                    {"selection": "away", "probability": 48.18},
                ],
            },
            {
                "market": "double_chance",
                "reliability": None,
                "hit_ratio": None,
                "selections": [
                    {"selection": "home_or_draw", "probability": 51.78},
                    {"selection": "home_or_away", "probability": 75.14},
                    {"selection": "draw_or_away", "probability": 73.0},
                ],
            },
            {
                "market": "both_teams_to_score",
                "reliability": "good",
                "hit_ratio": 0.625,
                "selections": [
                    {"selection": "yes", "probability": 54.0},
                    {"selection": "no", "probability": 46.0},
                ],
            },
        ],
    }


@pytest.mark.django_db
def test_predictions_renders_a_probability_and_a_hit_ratio_as_json_numbers(
    api_get: ApiGet, api_post: ApiPost, user: UserFactory, user_password: str
) -> None:
    """
    GIVEN a fixture whose graded market stores a percentage and a hit ratio
    WHEN its predictions are requested
    THEN both arrive as JSON numbers rather than as quoted decimal strings
    """

    fixture = store_three_markets()

    token = bearer_token(api_post, user, user_password)

    response = api_get(predictions_url(fixture.pk), token=token)

    graded = json_objects(json_object(response.json())["markets"])[0]

    assert isinstance(graded["hit_ratio"], float)

    assert [
        isinstance(selection["probability"], float)
        for selection in json_objects(graded["selections"])
    ] == [True, True, True]


@pytest.mark.django_db
def test_predictions_leaves_an_ungraded_market_without_a_grade(
    api_get: ApiGet, api_post: ApiPost, user: UserFactory, user_password: str
) -> None:
    """
    GIVEN a fixture whose double chance market the competition has no grade for
    WHEN its predictions are requested
    THEN that market carries neither a reliability nor a hit ratio
    """

    fixture = store_three_markets()

    token = bearer_token(api_post, user, user_password)

    response = api_get(predictions_url(fixture.pk), token=token)

    markets = json_objects(json_object(response.json())["markets"])

    ungraded = next(market for market in markets if market["market"] == "double_chance")

    assert (ungraded["reliability"], ungraded["hit_ratio"]) == (None, None)


@pytest.mark.django_db
def test_predictions_returns_an_empty_payload_for_an_unpredicted_fixture(
    api_get: ApiGet, api_post: ApiPost, user: UserFactory, user_password: str
) -> None:
    """
    GIVEN a stored fixture nothing has ever predicted
    WHEN its predictions are requested
    THEN the API answers with an empty payload rather than a failure
    """

    fixture = store_fixture(store_premier_league())

    token = bearer_token(api_post, user, user_password)

    response = api_get(predictions_url(fixture.pk), token=token)

    assert response.status_code == HTTPStatus.OK

    assert json_object(response.json()) == {
        "fixture_id": fixture.pk,
        "synchronized_at": None,
        "markets": [],
    }


@pytest.mark.django_db
def test_predictions_rejects_an_unknown_fixture(
    api_get: ApiGet, api_post: ApiPost, user: UserFactory, user_password: str
) -> None:
    """
    GIVEN a stored fixture and the identifier that follows its primary key
    WHEN the predictions of that identifier are requested
    THEN the API answers not found with the shared failure body
    """

    fixture = store_fixture(store_premier_league())

    token = bearer_token(api_post, user, user_password)

    response = api_get(predictions_url(fixture.pk + 1), token=token)

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json() == {"detail": UNKNOWN_FIXTURE_DETAIL}


@pytest.mark.django_db
def test_predictions_rejects_a_request_without_a_credential(api_get: ApiGet) -> None:
    """
    GIVEN a client presenting no bearer token
    WHEN the predictions of a fixture are requested
    THEN the API answers unauthorized
    """

    fixture = store_fixture(store_premier_league())

    response = api_get(predictions_url(fixture.pk))

    assert response.status_code == HTTPStatus.UNAUTHORIZED
