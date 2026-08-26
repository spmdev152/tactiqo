from datetime import UTC, datetime
from http import HTTPStatus
from typing import cast

import pytest

from apps.fixtures.domain.enums import FixtureStatus
from apps.fixtures.models import Fixture, League, Team
from apps.statistics.api.router import UNKNOWN_FIXTURE_DETAIL
from apps.statistics.domain.enums import MatchSide
from apps.statistics.models import MatchTeamStatistic
from tests.conftest import ApiGet, ApiPost, UserFactory

LOGIN_URL = "/api/v1/auth/login"

FIXTURES_URL = "/api/v1/fixtures"

SYNCHRONIZED_AT = datetime(2026, 8, 25, 6, 0, tzinfo=UTC)

KICKOFF_AT = datetime(2026, 8, 29, 11, 30, tzinfo=UTC)

PREVIOUS_KICKOFF_AT = datetime(2026, 8, 22, 14, 0, tzinfo=UTC)

SEASON_PROVIDER_ID = 25583

# One complete performance per side, stated in full rather than overridden from a
# shared default, because every published figure of the body asserted below is
# derived from exactly these numbers. The two differ in the four opposed metrics,
# so a body reading its own figures where it should read the opposition's cannot
# pass.
HOME_FIGURES = {
    "shots_total": 14,
    "shots_on_target": 6,
    "shots_inside_box": 9,
    "shots_blocked": 3,
    "big_chances_created": 2,
    "key_passes": 8,
    "corners": 7,
    "possession": 54,
    "passes": 486,
    "successful_passes": 411,
    "crosses": 18,
    "accurate_crosses": 5,
    "dribble_attempts": 12,
    "successful_dribbles": 7,
    "saves": 3,
    "tackles": 17,
    "interceptions": 9,
    "duels_won": 48,
    "fouls": 11,
    "yellow_cards": 2,
    "red_cards": 0,
    "offsides": 1,
}

AWAY_FIGURES = HOME_FIGURES | {
    "shots_total": 7,
    "shots_on_target": 2,
    "big_chances_created": 1,
    "corners": 3,
    "possession": 46,
}

PUBLISHED_FAMILIES = [
    {"family": "result", "metrics": ["win_share", "draw_share", "loss_share", "goals"]},
    {
        "family": "attacking",
        "metrics": [
            "shots",
            "shots_on_target",
            "shots_inside_box",
            "big_chances_created",
            "key_passes",
            "corners",
        ],
    },
    {
        "family": "possession",
        "metrics": [
            "possession",
            "passes",
            "pass_accuracy",
            "crosses",
            "cross_accuracy",
            "dribble_success",
        ],
    },
    {
        "family": "defending",
        "metrics": ["saves", "tackles", "interceptions", "duels_won", "shots_blocked"],
    },
    {"family": "discipline", "metrics": ["fouls", "yellow_cards", "red_cards", "offsides"]},
]

# Every figure of the one match seeded below, as the contract publishes it: the
# results and the goals from the score, the averages from the stored columns of
# the club itself, the four opposed metrics from the sibling row, and the three
# rates as the completions over the attempts.
PUBLISHED_SAMPLE = [
    {"metric": "win_share", "value": 100.0, "opposed_value": None},
    {"metric": "draw_share", "value": 0.0, "opposed_value": None},
    {"metric": "loss_share", "value": 0.0, "opposed_value": None},
    {"metric": "goals", "value": 2.0, "opposed_value": 1.0},
    {"metric": "shots", "value": 14.0, "opposed_value": 7.0},
    {"metric": "shots_on_target", "value": 6.0, "opposed_value": 2.0},
    {"metric": "shots_inside_box", "value": 9.0, "opposed_value": None},
    {"metric": "big_chances_created", "value": 2.0, "opposed_value": 1.0},
    {"metric": "key_passes", "value": 8.0, "opposed_value": None},
    {"metric": "corners", "value": 7.0, "opposed_value": 3.0},
    {"metric": "possession", "value": 54.0, "opposed_value": None},
    {"metric": "passes", "value": 486.0, "opposed_value": None},
    {"metric": "pass_accuracy", "value": 84.57, "opposed_value": None},
    {"metric": "crosses", "value": 18.0, "opposed_value": None},
    {"metric": "cross_accuracy", "value": 27.78, "opposed_value": None},
    {"metric": "dribble_success", "value": 58.33, "opposed_value": None},
    {"metric": "saves", "value": 3.0, "opposed_value": None},
    {"metric": "tackles", "value": 17.0, "opposed_value": None},
    {"metric": "interceptions", "value": 9.0, "opposed_value": None},
    {"metric": "duels_won", "value": 48.0, "opposed_value": None},
    {"metric": "shots_blocked", "value": 3.0, "opposed_value": None},
    {"metric": "fouls", "value": 11.0, "opposed_value": None},
    {"metric": "yellow_cards", "value": 2.0, "opposed_value": None},
    {"metric": "red_cards", "value": 0.0, "opposed_value": None},
    {"metric": "offsides", "value": 1.0, "opposed_value": None},
]

PUBLISHED_GRID = [
    ("last_3", "overall"),
    ("last_3", "venue"),
    ("last_6", "overall"),
    ("last_6", "venue"),
    ("season", "overall"),
    ("season", "venue"),
]


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


def form_url(fixture_id: int) -> str:
    """
    Build the form endpoint of one fixture.

    Parameters
    ----------
    fixture_id : int
        Primary key the endpoint is addressed with.

    Returns
    -------
    str
        Absolute path of the fixture's form endpoint.
    """

    return f"{FIXTURES_URL}/{fixture_id}/form"


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


def store_fixture(
    league: League,
    sportmonks_id: int,
    home_team: Team,
    away_team: Team,
    kickoff_at: datetime,
    *,
    status: FixtureStatus = FixtureStatus.SCHEDULED,
    home_goals: int | None = None,
    away_goals: int | None = None,
) -> Fixture:
    """
    Persist one match of the competition.

    Parameters
    ----------
    league : League
        Competition the match belongs to.
    sportmonks_id : int
        Provider identifier of the match.
    home_team : Team
        Club playing at home.
    away_team : Team
        Club playing away.
    kickoff_at : datetime
        Instant the match starts.
    status : FixtureStatus
        Lifecycle stage of the match.
    home_goals : int or None
        Goals the home club scored.
    away_goals : int or None
        Goals the away club scored.

    Returns
    -------
    Fixture
        Stored match.
    """

    return Fixture.objects.create(
        sportmonks_id=sportmonks_id,
        season_sportmonks_id=SEASON_PROVIDER_ID,
        league=league,
        home_team=home_team,
        away_team=away_team,
        kickoff_at=kickoff_at,
        status=status,
        home_goals=home_goals,
        away_goals=away_goals,
        synchronized_at=SYNCHRONIZED_AT,
    )


def store_statistics(
    fixture: Fixture, team: Team, side: MatchSide, values: dict[str, int]
) -> MatchTeamStatistic:
    """
    Persist one club's performance in one match.

    Parameters
    ----------
    fixture : Fixture
        Match the performance belongs to.
    team : Team
        Club whose performance it is.
    side : MatchSide
        Side the club occupied.
    values : dict of str to int
        Complete set of stored figures, keyed by column.

    Returns
    -------
    MatchTeamStatistic
        Stored performance.
    """

    return MatchTeamStatistic.objects.create(
        fixture=fixture, team=team, side=side, synchronized_at=SYNCHRONIZED_AT, **values
    )


def store_one_previous_match() -> Fixture:
    """
    Persist the fixture to be read and the single match behind its home club.

    Liverpool has one counted match, a home win over Arsenal with both
    performances stored, so its six samples are the same one match seen through
    six lenses and every published figure follows from one pair of rows. Forest
    has nothing behind it, which is what makes the two halves of the body
    different shapes to draw and the same shape to read.

    Returns
    -------
    Fixture
        Stored fixture whose form is read.
    """

    premier_league = store_premier_league()

    liverpool = store_team(8, "Liverpool", "LIV")
    forest = store_team(63, "Nottingham Forest", "NFO")
    arsenal = store_team(19, "Arsenal", "ARS")

    previous = store_fixture(
        premier_league,
        2,
        liverpool,
        arsenal,
        PREVIOUS_KICKOFF_AT,
        status=FixtureStatus.FINISHED,
        home_goals=2,
        away_goals=1,
    )

    store_statistics(previous, liverpool, MatchSide.HOME, HOME_FIGURES)
    store_statistics(previous, arsenal, MatchSide.AWAY, AWAY_FIGURES)

    return store_fixture(premier_league, 1, liverpool, forest, KICKOFF_AT)


def team_body(body: dict[str, object], side: str) -> dict[str, object]:
    """
    Narrow one half of a decoded form body.

    Parameters
    ----------
    body : dict of str to object
        Decoded response body.
    side : str
        ``"home"`` or ``"away"``.

    Returns
    -------
    dict of str to object
        That club's half of the body.
    """

    return json_object(body[side])


def sample_grid(body: dict[str, object], side: str) -> list[tuple[object, object]]:
    """
    Return the range and scope of every sample one club published, in order.

    Parameters
    ----------
    body : dict of str to object
        Decoded response body.
    side : str
        ``"home"`` or ``"away"``.

    Returns
    -------
    list of tuple of (object, object)
        Range and scope of each sample, in the order they were published.
    """

    return [
        (sample["range"], sample["scope"])
        for sample in json_objects(team_body(body, side)["samples"])
    ]


@pytest.mark.django_db
def test_form_returns_the_envelope_and_the_vocabulary_the_contract_promises(
    api_get: ApiGet, api_post: ApiPost, user: UserFactory, user_password: str
) -> None:
    """
    GIVEN a fixture whose home club has one stored match behind it
    WHEN its form is requested
    THEN the envelope names both clubs, the stamp, and the whole vocabulary
    """

    fixture = store_one_previous_match()

    token = bearer_token(api_post, user, user_password)

    response = api_get(form_url(fixture.pk), token=token)

    assert response.status_code == HTTPStatus.OK

    body = json_object(response.json())

    assert (
        body["fixture_id"],
        body["synchronized_at"],
        team_body(body, "home")["team_id"],
        team_body(body, "away")["team_id"],
        body["families"],
    ) == (
        fixture.pk,
        "2026-08-25T06:00:00Z",
        fixture.home_team.pk,
        fixture.away_team.pk,
        PUBLISHED_FAMILIES,
    )


@pytest.mark.django_db
def test_form_publishes_every_metric_of_a_sample_as_a_json_number(
    api_get: ApiGet, api_post: ApiPost, user: UserFactory, user_password: str
) -> None:
    """
    GIVEN a fixture whose home club won its one previous match at home
    WHEN its form is requested
    THEN the sample lists every metric in order, opposed figures included
    """

    fixture = store_one_previous_match()

    token = bearer_token(api_post, user, user_password)

    response = api_get(form_url(fixture.pk), token=token)

    samples = json_objects(team_body(json_object(response.json()), "home")["samples"])

    assert samples[0] == {
        "range": "last_3",
        "scope": "overall",
        "matches_counted": 1,
        "metrics": PUBLISHED_SAMPLE,
    }


@pytest.mark.django_db
def test_form_publishes_the_same_grid_of_samples_for_both_clubs(
    api_get: ApiGet, api_post: ApiPost, user: UserFactory, user_password: str
) -> None:
    """
    GIVEN a fixture one of whose clubs has no counted match behind it at all
    WHEN its form is requested
    THEN both halves carry the same six samples, the empty ones counting nothing
    """

    fixture = store_one_previous_match()

    token = bearer_token(api_post, user, user_password)

    response = api_get(form_url(fixture.pk), token=token)

    body = json_object(response.json())

    counted = [
        sample["matches_counted"] for sample in json_objects(team_body(body, "away")["samples"])
    ]

    assert (sample_grid(body, "home"), sample_grid(body, "away"), counted) == (
        PUBLISHED_GRID,
        PUBLISHED_GRID,
        [0, 0, 0, 0, 0, 0],
    )


@pytest.mark.django_db
def test_form_publishes_a_zeroed_grid_for_a_fixture_with_nothing_behind_it(
    api_get: ApiGet, api_post: ApiPost, user: UserFactory, user_password: str
) -> None:
    """
    GIVEN a stored fixture neither of whose clubs has ever played
    WHEN its form is requested
    THEN the API answers with an unstamped full grid rather than a failure
    """

    premier_league = store_premier_league()

    fixture = store_fixture(
        premier_league,
        1,
        store_team(8, "Liverpool", "LIV"),
        store_team(63, "Nottingham Forest", "NFO"),
        KICKOFF_AT,
    )

    token = bearer_token(api_post, user, user_password)

    response = api_get(form_url(fixture.pk), token=token)

    assert response.status_code == HTTPStatus.OK

    body = json_object(response.json())

    values = {
        figure["value"]
        for sample in json_objects(team_body(body, "home")["samples"])
        for figure in json_objects(sample["metrics"])
    }

    assert (body["synchronized_at"], sample_grid(body, "home"), values) == (
        None,
        PUBLISHED_GRID,
        {0.0},
    )


@pytest.mark.django_db
def test_form_rejects_an_unknown_fixture(
    api_get: ApiGet, api_post: ApiPost, user: UserFactory, user_password: str
) -> None:
    """
    GIVEN a stored fixture and the identifier that follows its primary key
    WHEN the form of that identifier is requested
    THEN the API answers not found with the shared failure body
    """

    fixture = store_one_previous_match()

    token = bearer_token(api_post, user, user_password)

    response = api_get(form_url(fixture.pk + 1), token=token)

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json() == {"detail": UNKNOWN_FIXTURE_DETAIL}


@pytest.mark.django_db
def test_form_rejects_a_request_without_a_credential(api_get: ApiGet) -> None:
    """
    GIVEN a client presenting no bearer token
    WHEN the form of a fixture is requested
    THEN the API answers unauthorized
    """

    fixture = store_one_previous_match()

    response = api_get(form_url(fixture.pk))

    assert response.status_code == HTTPStatus.UNAUTHORIZED
