from datetime import UTC, datetime
from decimal import Decimal
from http import HTTPStatus
from typing import cast

import pytest

from apps.fixtures.domain.enums import FixtureStatus
from apps.fixtures.models import Fixture, League, Team
from apps.predictions.domain.enums import PredictionMarket, PredictionSelection
from apps.predictions.models import FixturePrediction
from tests.conftest import ApiGet, ApiPost, UserFactory

LOGIN_URL = "/api/v1/auth/login"
LEAGUES_URL = "/api/v1/leagues"
FIXTURES_URL = "/api/v1/fixtures"

DAY = "2026-08-29"
NEXT_DAY = "2026-08-30"

SYNCHRONIZED_AT = datetime(2026, 8, 25, 6, 0, tzinfo=UTC)


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


def json_list(payload: object) -> list[dict[str, object]]:
    """
    Narrow a decoded response body to the list of objects the contract promises.

    Parameters
    ----------
    payload : object
        Decoded response body.

    Returns
    -------
    list of dict of str to object
        Response body as a list of JSON objects.
    """

    return cast(list[dict[str, object]], payload)


def store_premier_league() -> League:
    """
    Persist the Premier League with every field the contract exposes populated.

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


def store_la_liga() -> League:
    """
    Persist La Liga, the second competition the filtering tests need.

    Returns
    -------
    League
        Stored competition.
    """

    return League.objects.create(
        sportmonks_id=564,
        name="La Liga",
        short_code="ES LL",
        logo_url="https://cdn.example.test/leagues/564.png",
        country_name="Spain",
        country_flag_url="https://cdn.example.test/countries/es.png",
    )


def store_serie_a() -> League:
    """
    Persist Serie A, the third competition the multi-select tests need.

    Returns
    -------
    League
        Stored competition.
    """

    return League.objects.create(
        sportmonks_id=384,
        name="Serie A",
        short_code="IT SA",
        logo_url="https://cdn.example.test/leagues/384.png",
        country_name="Italy",
        country_flag_url="https://cdn.example.test/countries/it.png",
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


def store_fixture(
    sportmonks_id: int,
    league: League,
    home_team: Team,
    away_team: Team,
    kickoff_at: datetime,
    *,
    status: FixtureStatus = FixtureStatus.SCHEDULED,
    home_goals: int | None = None,
    away_goals: int | None = None,
) -> Fixture:
    """
    Persist a fixture.

    Parameters
    ----------
    sportmonks_id : int
        Provider identifier of the match.
    league : League
        Competition the match belongs to.
    home_team : Team
        Club playing at home.
    away_team : Team
        Club playing away.
    kickoff_at : datetime
        Timezone-aware UTC instant the match starts.
    status : FixtureStatus
        Lifecycle stage of the match.
    home_goals : int or None
        Goals the home club has scored, ``None`` for a match with no score.
    away_goals : int or None
        Goals the away club has scored, ``None`` for a match with no score.

    Returns
    -------
    Fixture
        Stored fixture.
    """

    return Fixture.objects.create(
        sportmonks_id=sportmonks_id,
        league=league,
        home_team=home_team,
        away_team=away_team,
        kickoff_at=kickoff_at,
        status=status,
        home_goals=home_goals,
        away_goals=away_goals,
        synchronized_at=SYNCHRONIZED_AT,
    )


def store_three_competitions() -> list[Fixture]:
    """
    Persist one fixture of the requested day in each of three competitions.

    The three kick off in ascending order, so the returned order is the order
    the endpoint lists them in and a narrowed listing keeps the same relative
    order.

    Returns
    -------
    list of Fixture
        Stored fixtures, each carrying the competition it belongs to.
    """

    premier_league = store_premier_league()
    la_liga = store_la_liga()
    serie_a = store_serie_a()

    liverpool = store_team(8, "Liverpool", "LIV")
    nottingham_forest = store_team(63, "Nottingham Forest", "NFO")
    barcelona = store_team(83, "Barcelona", "BAR")
    sevilla = store_team(1, "Sevilla", "SEV")
    juventus = store_team(625, "Juventus", "JUV")
    napoli = store_team(268, "Napoli", "NAP")

    english = store_fixture(
        1, premier_league, liverpool, nottingham_forest, datetime(2026, 8, 29, 11, 30, tzinfo=UTC)
    )

    spanish = store_fixture(2, la_liga, barcelona, sevilla, datetime(2026, 8, 29, 14, tzinfo=UTC))

    italian = store_fixture(3, serie_a, juventus, napoli, datetime(2026, 8, 29, 17, tzinfo=UTC))

    return [english, spanish, italian]


@pytest.mark.django_db
def test_leagues_returns_every_competition_ordered_by_name(
    api_get: ApiGet, api_post: ApiPost, user: UserFactory, user_password: str
) -> None:
    """
    GIVEN two stored competitions and an authenticated client
    WHEN the league listing is requested
    THEN both competitions come back alphabetically in the contracted shape
    """

    premier_league = store_premier_league()
    la_liga = store_la_liga()

    token = bearer_token(api_post, user, user_password)

    response = api_get(LEAGUES_URL, token=token)

    assert response.status_code == HTTPStatus.OK

    assert json_list(response.json()) == [
        {
            "id": la_liga.pk,
            "name": "La Liga",
            "short_code": "ES LL",
            "logo_url": "https://cdn.example.test/leagues/564.png",
            "country_name": "Spain",
            "country_flag_url": "https://cdn.example.test/countries/es.png",
        },
        {
            "id": premier_league.pk,
            "name": "Premier League",
            "short_code": "UK PL",
            "logo_url": "https://cdn.example.test/leagues/8.png",
            "country_name": "England",
            "country_flag_url": "https://cdn.example.test/countries/en.png",
        },
    ]


@pytest.mark.django_db
def test_leagues_rejects_a_request_without_a_credential(api_get: ApiGet) -> None:
    """
    GIVEN a client presenting no bearer token
    WHEN the league listing is requested
    THEN the API answers unauthorized
    """

    response = api_get(LEAGUES_URL)

    assert response.status_code == HTTPStatus.UNAUTHORIZED


@pytest.mark.django_db
def test_fixtures_returns_the_day_in_the_contracted_shape(
    api_get: ApiGet, api_post: ApiPost, user: UserFactory, user_password: str
) -> None:
    """
    GIVEN one stored fixture of the requested day
    WHEN that day is requested
    THEN it comes back scheduled, without a score, and with its clubs embedded
    """

    premier_league = store_premier_league()

    liverpool = store_team(8, "Liverpool", "LIV")
    nottingham_forest = store_team(63, "Nottingham Forest", "NFO")

    fixture = store_fixture(
        1,
        premier_league,
        liverpool,
        nottingham_forest,
        datetime(2026, 8, 29, 11, 30, tzinfo=UTC),
    )

    token = bearer_token(api_post, user, user_password)

    response = api_get(f"{FIXTURES_URL}?date={DAY}", token=token)

    assert response.status_code == HTTPStatus.OK

    assert json_list(response.json()) == [
        {
            "id": fixture.pk,
            "kickoff_at": "2026-08-29T11:30:00Z",
            "status": "scheduled",
            "home_goals": None,
            "away_goals": None,
            "league": {
                "id": premier_league.pk,
                "name": "Premier League",
                "short_code": "UK PL",
                "logo_url": "https://cdn.example.test/leagues/8.png",
                "country_name": "England",
                "country_flag_url": "https://cdn.example.test/countries/en.png",
            },
            "home_team": {
                "id": liverpool.pk,
                "name": "Liverpool",
                "short_code": "LIV",
                "crest_url": "https://cdn.example.test/teams/8.png",
            },
            "away_team": {
                "id": nottingham_forest.pk,
                "name": "Nottingham Forest",
                "short_code": "NFO",
                "crest_url": "https://cdn.example.test/teams/63.png",
            },
            "has_predictions": False,
        }
    ]


@pytest.mark.django_db
def test_fixtures_returns_the_result_of_a_played_fixture(
    api_get: ApiGet, api_post: ApiPost, user: UserFactory, user_password: str
) -> None:
    """
    GIVEN a stored fixture that has been played to a two-nil home win
    WHEN its day is requested
    THEN it comes back finished and carrying both halves of the score
    """

    premier_league = store_premier_league()

    liverpool = store_team(8, "Liverpool", "LIV")
    nottingham_forest = store_team(63, "Nottingham Forest", "NFO")

    store_fixture(
        1,
        premier_league,
        liverpool,
        nottingham_forest,
        datetime(2026, 8, 29, 11, 30, tzinfo=UTC),
        status=FixtureStatus.FINISHED,
        home_goals=2,
        away_goals=0,
    )

    token = bearer_token(api_post, user, user_password)

    response = api_get(f"{FIXTURES_URL}?date={DAY}", token=token)

    assert response.status_code == HTTPStatus.OK

    played = json_list(response.json())[0]

    assert (played["status"], played["home_goals"], played["away_goals"]) == ("finished", 2, 0)


@pytest.mark.django_db
def test_fixtures_flags_only_the_rows_that_carry_a_prediction(
    api_get: ApiGet, api_post: ApiPost, user: UserFactory, user_password: str
) -> None:
    """
    GIVEN two fixtures of one day, one of which carries a stored prediction
    WHEN that day is requested
    THEN only the predicted fixture is flagged, so a toggle is offered once
    """

    premier_league = store_premier_league()

    liverpool = store_team(8, "Liverpool", "LIV")
    nottingham_forest = store_team(63, "Nottingham Forest", "NFO")

    predicted = store_fixture(
        1, premier_league, liverpool, nottingham_forest, datetime(2026, 8, 29, 11, 30, tzinfo=UTC)
    )

    unpredicted = store_fixture(
        2, premier_league, nottingham_forest, liverpool, datetime(2026, 8, 29, 14, tzinfo=UTC)
    )

    FixturePrediction.objects.create(
        fixture=predicted,
        market=PredictionMarket.FULLTIME_RESULT,
        selection=PredictionSelection.HOME,
        probability=Decimal("26.96"),
        synchronized_at=SYNCHRONIZED_AT,
    )

    token = bearer_token(api_post, user, user_password)

    response = api_get(f"{FIXTURES_URL}?date={DAY}", token=token)

    assert response.status_code == HTTPStatus.OK

    listed = json_list(response.json())

    assert [(fixture["id"], fixture["has_predictions"]) for fixture in listed] == [
        (predicted.pk, True),
        (unpredicted.pk, False),
    ]


@pytest.mark.django_db
def test_fixtures_orders_the_day_by_kick_off(
    api_get: ApiGet, api_post: ApiPost, user: UserFactory, user_password: str
) -> None:
    """
    GIVEN three fixtures of one day stored out of chronological order
    WHEN that day is requested
    THEN they come back earliest kick-off first
    """

    premier_league = store_premier_league()

    liverpool = store_team(8, "Liverpool", "LIV")
    nottingham_forest = store_team(63, "Nottingham Forest", "NFO")

    late = store_fixture(
        1, premier_league, liverpool, nottingham_forest, datetime(2026, 8, 29, 20, tzinfo=UTC)
    )

    early = store_fixture(
        2, premier_league, nottingham_forest, liverpool, datetime(2026, 8, 29, 11, 30, tzinfo=UTC)
    )

    middle = store_fixture(
        3, premier_league, liverpool, nottingham_forest, datetime(2026, 8, 29, 14, tzinfo=UTC)
    )

    token = bearer_token(api_post, user, user_password)

    response = api_get(f"{FIXTURES_URL}?date={DAY}", token=token)

    listed = json_list(response.json())

    assert [fixture["id"] for fixture in listed] == [early.pk, middle.pk, late.pk]


@pytest.mark.django_db
def test_fixtures_narrows_the_day_to_one_league(
    api_get: ApiGet, api_post: ApiPost, user: UserFactory, user_password: str
) -> None:
    """
    GIVEN two fixtures of the same day in different competitions
    WHEN the day is requested for one competition
    THEN only that competition's fixture comes back
    """

    premier_league = store_premier_league()
    la_liga = store_la_liga()

    liverpool = store_team(8, "Liverpool", "LIV")
    nottingham_forest = store_team(63, "Nottingham Forest", "NFO")
    barcelona = store_team(83, "Barcelona", "BAR")
    sevilla = store_team(1, "Sevilla", "SEV")

    store_fixture(
        1, premier_league, liverpool, nottingham_forest, datetime(2026, 8, 29, 11, 30, tzinfo=UTC)
    )

    spanish_fixture = store_fixture(
        2, la_liga, barcelona, sevilla, datetime(2026, 8, 29, 19, tzinfo=UTC)
    )

    token = bearer_token(api_post, user, user_password)

    response = api_get(f"{FIXTURES_URL}?date={DAY}&league_id={la_liga.pk}", token=token)

    listed = json_list(response.json())

    assert [fixture["id"] for fixture in listed] == [spanish_fixture.pk]


@pytest.mark.django_db
def test_fixtures_returns_every_competition_without_a_league_filter(
    api_get: ApiGet, api_post: ApiPost, user: UserFactory, user_password: str
) -> None:
    """
    GIVEN one fixture of the requested day in each of three competitions
    WHEN the day is requested with no competition
    THEN every competition's fixture comes back
    """

    english, spanish, italian = store_three_competitions()

    token = bearer_token(api_post, user, user_password)

    response = api_get(f"{FIXTURES_URL}?date={DAY}", token=token)

    assert response.status_code == HTTPStatus.OK

    listed = json_list(response.json())

    assert [fixture["id"] for fixture in listed] == [english.pk, spanish.pk, italian.pk]


@pytest.mark.django_db
def test_fixtures_narrows_the_day_to_several_leagues(
    api_get: ApiGet, api_post: ApiPost, user: UserFactory, user_password: str
) -> None:
    """
    GIVEN one fixture of the requested day in each of three competitions
    WHEN the day is requested for two of them
    THEN exactly those two fixtures come back and the third is left out
    """

    _english, spanish, italian = store_three_competitions()

    token = bearer_token(api_post, user, user_password)

    response = api_get(
        f"{FIXTURES_URL}?date={DAY}&league_id={spanish.league.pk}&league_id={italian.league.pk}",
        token=token,
    )

    assert response.status_code == HTTPStatus.OK

    listed = json_list(response.json())

    assert [fixture["id"] for fixture in listed] == [spanish.pk, italian.pk]


@pytest.mark.django_db
def test_fixtures_collapses_a_repeated_league(
    api_get: ApiGet, api_post: ApiPost, user: UserFactory, user_password: str
) -> None:
    """
    GIVEN one fixture of the requested day in each of three competitions
    WHEN the day is requested for one competition named twice
    THEN the listing matches the one that competition named once produces
    """

    _english, spanish, _italian = store_three_competitions()

    token = bearer_token(api_post, user, user_password)

    repeated = api_get(
        f"{FIXTURES_URL}?date={DAY}&league_id={spanish.league.pk}&league_id={spanish.league.pk}",
        token=token,
    )

    assert repeated.status_code == HTTPStatus.OK

    assert [fixture["id"] for fixture in json_list(repeated.json())] == [spanish.pk]


@pytest.mark.django_db
def test_fixtures_returns_an_empty_day_for_an_unknown_league(
    api_get: ApiGet, api_post: ApiPost, user: UserFactory, user_password: str
) -> None:
    """
    GIVEN a stored fixture of the requested day and an unused competition key
    WHEN the day is requested for that competition
    THEN the API answers with an empty list rather than an error
    """

    premier_league = store_premier_league()

    liverpool = store_team(8, "Liverpool", "LIV")
    nottingham_forest = store_team(63, "Nottingham Forest", "NFO")

    store_fixture(
        1, premier_league, liverpool, nottingham_forest, datetime(2026, 8, 29, 11, 30, tzinfo=UTC)
    )

    token = bearer_token(api_post, user, user_password)

    response = api_get(f"{FIXTURES_URL}?date={DAY}&league_id={premier_league.pk + 1}", token=token)

    assert response.status_code == HTTPStatus.OK
    assert json_list(response.json()) == []


@pytest.mark.django_db
def test_fixtures_selects_the_day_by_its_utc_calendar_boundary(
    api_get: ApiGet, api_post: ApiPost, user: UserFactory, user_password: str
) -> None:
    """
    GIVEN two fixtures kicking off at midnight UTC on consecutive days
    WHEN the earlier day is requested
    THEN only the fixture opening that day comes back
    """

    premier_league = store_premier_league()

    liverpool = store_team(8, "Liverpool", "LIV")
    nottingham_forest = store_team(63, "Nottingham Forest", "NFO")

    opening = store_fixture(
        1, premier_league, liverpool, nottingham_forest, datetime(2026, 8, 29, tzinfo=UTC)
    )

    following = store_fixture(
        2, premier_league, nottingham_forest, liverpool, datetime(2026, 8, 30, tzinfo=UTC)
    )

    token = bearer_token(api_post, user, user_password)

    requested_day = json_list(api_get(f"{FIXTURES_URL}?date={DAY}", token=token).json())
    following_day = json_list(api_get(f"{FIXTURES_URL}?date={NEXT_DAY}", token=token).json())

    assert [fixture["id"] for fixture in requested_day] == [opening.pk]
    assert [fixture["id"] for fixture in following_day] == [following.pk]


@pytest.mark.django_db
def test_fixtures_returns_an_empty_day(
    api_get: ApiGet, api_post: ApiPost, user: UserFactory, user_password: str
) -> None:
    """
    GIVEN a day carrying no stored fixture
    WHEN that day is requested
    THEN the API answers with an empty list rather than an error
    """

    token = bearer_token(api_post, user, user_password)

    response = api_get(f"{FIXTURES_URL}?date={DAY}", token=token)

    assert response.status_code == HTTPStatus.OK
    assert json_list(response.json()) == []


@pytest.mark.django_db
def test_fixtures_rejects_an_unparseable_day(
    api_get: ApiGet, api_post: ApiPost, user: UserFactory, user_password: str
) -> None:
    """
    GIVEN an authenticated client asking for a day that is not a date
    WHEN the fixture listing is requested
    THEN the API answers unprocessable entity
    """

    token = bearer_token(api_post, user, user_password)

    response = api_get(f"{FIXTURES_URL}?date=not-a-date", token=token)

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


@pytest.mark.django_db
def test_fixtures_rejects_a_league_that_is_not_an_integer(
    api_get: ApiGet, api_post: ApiPost, user: UserFactory, user_password: str
) -> None:
    """
    GIVEN an authenticated client asking for a competition that is not a number
    WHEN the fixture listing is requested
    THEN the API answers unprocessable entity instead of ignoring the value
    """

    token = bearer_token(api_post, user, user_password)

    response = api_get(f"{FIXTURES_URL}?date={DAY}&league_id=not-a-number", token=token)

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


@pytest.mark.django_db
def test_fixtures_rejects_a_request_without_a_credential(api_get: ApiGet) -> None:
    """
    GIVEN a client presenting no bearer token
    WHEN the fixture listing is requested
    THEN the API answers unauthorized
    """

    response = api_get(f"{FIXTURES_URL}?date={DAY}")

    assert response.status_code == HTTPStatus.UNAUTHORIZED
