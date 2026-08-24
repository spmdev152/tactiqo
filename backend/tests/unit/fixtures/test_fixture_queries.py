from datetime import date

import pytest
from pytest_django.fixtures import DjangoAssertNumQueries

from apps.fixtures.api.schemas import FixtureResponse
from apps.fixtures.application.queries import list_fixtures_on, list_leagues
from apps.fixtures.infrastructure.repositories import upsert_fixtures
from apps.fixtures.models import League
from tests.unit.fixtures.conftest import (
    BARCELONA,
    DAY,
    LA_LIGA,
    SEVILLA,
    SYNCHRONIZED_AT,
    kickoff,
    provider_fixture,
)

NEXT_DAY = date(2026, 8, 30)


@pytest.mark.django_db
def test_list_leagues_orders_the_competitions_alphabetically() -> None:
    """
    GIVEN two stored competitions whose names sort against their insertion order
    WHEN the competitions are listed
    THEN they come back alphabetically by name
    """

    upsert_fixtures(
        [
            provider_fixture(1, kickoff(11, 30)),
            provider_fixture(
                2, kickoff(14), league=LA_LIGA, home_team=BARCELONA, away_team=SEVILLA
            ),
        ],
        SYNCHRONIZED_AT,
    )

    assert [league.name for league in list_leagues()] == ["La Liga", "Premier League"]


@pytest.mark.django_db
def test_list_fixtures_on_includes_a_fixture_kicking_off_at_midnight() -> None:
    """
    GIVEN a fixture kicking off exactly at midnight UTC on the requested day
    WHEN that day is listed
    THEN the fixture is included
    """

    upsert_fixtures([provider_fixture(1, kickoff(0))], SYNCHRONIZED_AT)

    assert [fixture.sportmonks_id for fixture in list_fixtures_on(DAY, None)] == [1]


@pytest.mark.django_db
def test_list_fixtures_on_excludes_a_fixture_kicking_off_at_the_next_midnight() -> None:
    """
    GIVEN a fixture kicking off exactly at midnight UTC on the following day
    WHEN the earlier day is listed
    THEN the fixture is excluded and the following day carries it
    """

    upsert_fixtures([provider_fixture(1, kickoff(0, day=NEXT_DAY))], SYNCHRONIZED_AT)

    assert list_fixtures_on(DAY, None) == []

    assert [fixture.sportmonks_id for fixture in list_fixtures_on(NEXT_DAY, None)] == [1]


@pytest.mark.django_db
def test_list_fixtures_on_narrows_the_day_to_one_competition() -> None:
    """
    GIVEN two fixtures of the same day in different competitions
    WHEN the day is listed for one competition
    THEN only that competition's fixture comes back
    """

    upsert_fixtures(
        [
            provider_fixture(1, kickoff(11, 30)),
            provider_fixture(
                2, kickoff(14), league=LA_LIGA, home_team=BARCELONA, away_team=SEVILLA
            ),
        ],
        SYNCHRONIZED_AT,
    )

    la_liga = League.objects.get(sportmonks_id=LA_LIGA.provider_id)

    listed = list_fixtures_on(DAY, la_liga.pk)

    assert [fixture.sportmonks_id for fixture in listed] == [2]


@pytest.mark.django_db
def test_list_fixtures_on_orders_the_day_by_kick_off() -> None:
    """
    GIVEN three fixtures of one day stored out of chronological order
    WHEN the day is listed
    THEN they come back earliest kick-off first
    """

    upsert_fixtures(
        [
            provider_fixture(1, kickoff(20)),
            provider_fixture(2, kickoff(11, 30)),
            provider_fixture(3, kickoff(14)),
        ],
        SYNCHRONIZED_AT,
    )

    listed = list_fixtures_on(DAY, None)

    assert [fixture.sportmonks_id for fixture in listed] == [2, 3, 1]


@pytest.mark.django_db
def test_list_fixtures_on_breaks_a_shared_kick_off_by_identifier() -> None:
    """
    GIVEN two fixtures of one day kicking off at the same instant
    WHEN the day is listed
    THEN they come back in ascending identifier order
    """

    window = [provider_fixture(1, kickoff(14)), provider_fixture(2, kickoff(14))]

    upsert_fixtures(window, SYNCHRONIZED_AT)

    identifiers = [fixture.pk for fixture in list_fixtures_on(DAY, None)]

    assert len(identifiers) == len(window)
    assert identifiers == sorted(identifiers)


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

    upsert_fixtures(window, SYNCHRONIZED_AT)

    with django_assert_num_queries(1):
        responses = [FixtureResponse.from_orm(fixture) for fixture in list_fixtures_on(DAY, None)]

    assert len(responses) == len(window)
