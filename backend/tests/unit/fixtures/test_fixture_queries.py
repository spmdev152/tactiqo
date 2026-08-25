from datetime import date
from decimal import Decimal

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from pytest_django.fixtures import DjangoAssertNumQueries

from apps.fixtures.api.schemas import FixtureResponse
from apps.fixtures.application.queries import list_fixtures_on, list_leagues
from apps.fixtures.models import Fixture, League
from apps.predictions.domain.enums import PredictionMarket, PredictionSelection
from apps.predictions.models import FixturePrediction
from integrations.sportmonks.fixtures import ProviderLeague, ProviderTeam
from tests.unit.fixtures.conftest import (
    BARCELONA,
    DAY,
    LA_LIGA,
    PREMIER_LEAGUE,
    SEVILLA,
    SYNCHRONIZED_AT,
    kickoff,
    provider_fixture,
    store_window,
)

NEXT_DAY = date(2026, 8, 30)

FIXTURE_TABLE = "fixtures_fixture"

KICKOFF_THEN_KEY_ORDERING = (
    f'ORDER BY "{FIXTURE_TABLE}"."kickoff_at" ASC, "{FIXTURE_TABLE}"."id" ASC'
)

SERIE_A = ProviderLeague(
    provider_id=384,
    name="Serie A",
    short_code="IT SA",
    logo_url="https://cdn.example.test/leagues/384.png",
    country_name="Italy",
    country_flag_url="https://cdn.example.test/countries/it.png",
)

JUVENTUS = ProviderTeam(
    provider_id=625,
    name="Juventus",
    short_code="JUV",
    crest_url="https://cdn.example.test/teams/625.png",
)

NAPOLI = ProviderTeam(
    provider_id=268,
    name="Napoli",
    short_code="NAP",
    crest_url="https://cdn.example.test/teams/268.png",
)


def store_three_competitions() -> dict[int, League]:
    """
    Persist one fixture of the day in each of three competitions.

    The fixtures kick off in ascending order of their provider identifier, one
    in the Premier League, one in La Liga, and one in Serie A, so a test names
    the fixtures it expects as ``1``, ``2``, and ``3``.

    Returns
    -------
    dict of int to League
        Stored competitions keyed by their Sportmonks identifier.
    """

    store_window(
        [
            provider_fixture(1, kickoff(11, 30)),
            provider_fixture(
                2, kickoff(14), league=LA_LIGA, home_team=BARCELONA, away_team=SEVILLA
            ),
            provider_fixture(3, kickoff(17), league=SERIE_A, home_team=JUVENTUS, away_team=NAPOLI),
        ]
    )

    return {league.sportmonks_id: league for league in League.objects.all()}


@pytest.mark.django_db
def test_list_leagues_orders_the_competitions_alphabetically() -> None:
    """
    GIVEN two stored competitions whose names sort against their insertion order
    WHEN the competitions are listed
    THEN they come back alphabetically by name
    """

    store_window(
        [
            provider_fixture(1, kickoff(11, 30)),
            provider_fixture(
                2, kickoff(14), league=LA_LIGA, home_team=BARCELONA, away_team=SEVILLA
            ),
        ]
    )

    assert [league.name for league in list_leagues()] == ["La Liga", "Premier League"]


@pytest.mark.django_db
def test_list_fixtures_on_includes_a_fixture_kicking_off_at_midnight() -> None:
    """
    GIVEN a fixture kicking off exactly at midnight UTC on the requested day
    WHEN that day is listed
    THEN the fixture is included
    """

    store_window([provider_fixture(1, kickoff(0))])

    assert [fixture.sportmonks_id for fixture in list_fixtures_on(DAY, [])] == [1]


@pytest.mark.django_db
def test_list_fixtures_on_excludes_a_fixture_kicking_off_at_the_next_midnight() -> None:
    """
    GIVEN a fixture kicking off exactly at midnight UTC on the following day
    WHEN the earlier day is listed
    THEN the fixture is excluded and the following day carries it
    """

    store_window([provider_fixture(1, kickoff(0, day=NEXT_DAY))])

    assert list_fixtures_on(DAY, []) == []

    assert [fixture.sportmonks_id for fixture in list_fixtures_on(NEXT_DAY, [])] == [1]


@pytest.mark.django_db
def test_list_fixtures_on_returns_every_competition_without_a_filter() -> None:
    """
    GIVEN one fixture of the day in each of three competitions
    WHEN the day is listed with an empty competition sequence
    THEN every competition's fixture comes back
    """

    store_three_competitions()

    listed = list_fixtures_on(DAY, [])

    assert [fixture.sportmonks_id for fixture in listed] == [1, 2, 3]


@pytest.mark.django_db
def test_list_fixtures_on_narrows_the_day_to_one_competition() -> None:
    """
    GIVEN two fixtures of the same day in different competitions
    WHEN the day is listed for one competition
    THEN only that competition's fixture comes back
    """

    store_window(
        [
            provider_fixture(1, kickoff(11, 30)),
            provider_fixture(
                2, kickoff(14), league=LA_LIGA, home_team=BARCELONA, away_team=SEVILLA
            ),
        ]
    )

    la_liga = League.objects.get(sportmonks_id=LA_LIGA.provider_id)

    listed = list_fixtures_on(DAY, [la_liga.pk])

    assert [fixture.sportmonks_id for fixture in listed] == [2]


@pytest.mark.django_db
def test_list_fixtures_on_narrows_the_day_to_several_competitions() -> None:
    """
    GIVEN one fixture of the day in each of three competitions
    WHEN the day is listed for two of them
    THEN exactly those two fixtures come back and the third is left out
    """

    leagues = store_three_competitions()

    listed = list_fixtures_on(
        DAY, [leagues[LA_LIGA.provider_id].pk, leagues[SERIE_A.provider_id].pk]
    )

    assert [fixture.sportmonks_id for fixture in listed] == [2, 3]


@pytest.mark.django_db
def test_list_fixtures_on_collapses_a_repeated_competition() -> None:
    """
    GIVEN one fixture of the day in each of three competitions
    WHEN the day is listed for one competition named twice
    THEN the listing matches the one the competition named once produces
    """

    leagues = store_three_competitions()

    la_liga = leagues[LA_LIGA.provider_id]

    repeated = list_fixtures_on(DAY, [la_liga.pk, la_liga.pk])

    assert [fixture.pk for fixture in repeated] == [
        fixture.pk for fixture in list_fixtures_on(DAY, [la_liga.pk])
    ]


@pytest.mark.django_db
def test_list_fixtures_on_returns_an_empty_day_for_an_unknown_competition() -> None:
    """
    GIVEN a stored fixture of the day and a competition identifier nothing uses
    WHEN the day is listed for that identifier
    THEN an empty list comes back rather than an error
    """

    store_window([provider_fixture(1, kickoff(11, 30))])

    premier_league = League.objects.get(sportmonks_id=PREMIER_LEAGUE.provider_id)

    assert list_fixtures_on(DAY, [premier_league.pk + 1]) == []


@pytest.mark.django_db
def test_list_fixtures_on_orders_the_day_by_kick_off() -> None:
    """
    GIVEN three fixtures of one day stored out of chronological order
    WHEN the day is listed
    THEN they come back earliest kick-off first
    """

    store_window(
        [
            provider_fixture(1, kickoff(20)),
            provider_fixture(2, kickoff(11, 30)),
            provider_fixture(3, kickoff(14)),
        ]
    )

    listed = list_fixtures_on(DAY, [])

    assert [fixture.sportmonks_id for fixture in listed] == [2, 3, 1]


@pytest.mark.django_db
def test_list_fixtures_on_breaks_a_shared_kick_off_by_primary_key() -> None:
    """
    GIVEN two fixtures sharing a kick-off whose keys ascend against their provider identifiers
    WHEN the day is listed
    THEN they come back in primary-key order, which is the tiebreak the model pins
    """

    store_window([provider_fixture(2, kickoff(14))])
    store_window([provider_fixture(1, kickoff(14)), provider_fixture(2, kickoff(14))])

    ascending_keys = list(Fixture.objects.order_by("pk").values_list("sportmonks_id", flat=True))

    # The test database returns equal-key rows in insertion order whatever the
    # statement asked for, so the data alone cannot tell a tiebreak that is
    # present from one that is absent; the emitted ordering can.
    with CaptureQueriesContext(connection) as executed:
        listed = list_fixtures_on(DAY, [])

    assert ascending_keys == [2, 1]
    assert [fixture.sportmonks_id for fixture in listed] == ascending_keys
    assert executed.captured_queries[0]["sql"].endswith(KICKOFF_THEN_KEY_ORDERING)


@pytest.mark.django_db
def test_list_fixtures_on_serializes_a_day_without_a_query_per_fixture(
    django_assert_num_queries: DjangoAssertNumQueries,
) -> None:
    """
    GIVEN a day carrying several fixtures across two competitions
    WHEN the day is listed and every fixture is mapped to its response schema
    THEN a single query answers the whole listing
    """

    window = [
        provider_fixture(1, kickoff(11, 30)),
        provider_fixture(2, kickoff(14)),
        provider_fixture(3, kickoff(17), league=LA_LIGA, home_team=BARCELONA, away_team=SEVILLA),
        provider_fixture(4, kickoff(20), league=LA_LIGA, home_team=SEVILLA, away_team=BARCELONA),
    ]

    store_window(window)

    with django_assert_num_queries(1):
        responses = [FixtureResponse.from_orm(fixture) for fixture in list_fixtures_on(DAY, [])]

    assert len(responses) == len(window)


@pytest.mark.django_db
def test_list_fixtures_on_serializes_several_competitions_in_one_query(
    django_assert_num_queries: DjangoAssertNumQueries,
) -> None:
    """
    GIVEN one fixture of the day in each of three competitions
    WHEN two competitions are listed and every fixture is mapped to its schema
    THEN the same single query answers the narrowed listing
    """

    leagues = store_three_competitions()

    requested = [leagues[LA_LIGA.provider_id].pk, leagues[SERIE_A.provider_id].pk]

    with django_assert_num_queries(1):
        responses = [
            FixtureResponse.from_orm(fixture) for fixture in list_fixtures_on(DAY, requested)
        ]

    assert [response.league.id for response in responses] == requested


@pytest.mark.django_db
def test_list_fixtures_on_flags_a_predicted_fixture_within_the_same_query(
    django_assert_num_queries: DjangoAssertNumQueries,
) -> None:
    """
    GIVEN two fixtures of one day, exactly one of which carries a prediction
    WHEN the day is listed and every fixture is mapped to its response schema
    THEN the flag tells them apart and the same single query answers the day
    """

    store_window([provider_fixture(1, kickoff(11, 30)), provider_fixture(2, kickoff(14))])

    predicted, unpredicted = Fixture.objects.order_by("kickoff_at")

    FixturePrediction.objects.create(
        fixture=predicted,
        market=PredictionMarket.FULLTIME_RESULT,
        selection=PredictionSelection.HOME,
        probability=Decimal("26.96"),
        synchronized_at=SYNCHRONIZED_AT,
    )

    with django_assert_num_queries(1):
        responses = [FixtureResponse.from_orm(fixture) for fixture in list_fixtures_on(DAY, [])]

    assert [(response.id, response.has_predictions) for response in responses] == [
        (predicted.pk, True),
        (unpredicted.pk, False),
    ]
