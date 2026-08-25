from dataclasses import replace
from datetime import date

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.fixtures.domain.enums import FixtureStatus
from apps.fixtures.infrastructure.repositories import upsert_fixtures
from apps.fixtures.models import Fixture, League, Team
from tests.unit.fixtures.conftest import (
    LIVERPOOL,
    NOTTINGHAM_FOREST,
    PREMIER_LEAGUE,
    SYNCHRONIZED_AT,
    kickoff,
    provider_fixture,
)

LATER_SYNCHRONIZED_AT = SYNCHRONIZED_AT.replace(hour=18)

BOTH_CLUBS = sorted([LIVERPOOL.provider_id, NOTTINGHAM_FOREST.provider_id])


def stored_fixture_identifiers() -> list[int]:
    """
    Return the provider identifiers of every stored fixture, in ascending order.

    Returns
    -------
    list of int
        Sorted provider identifiers of the fixture table.
    """

    return sorted(fixture.sportmonks_id for fixture in Fixture.objects.all())


def stored_club_identifiers() -> list[int]:
    """
    Return the provider identifiers of every stored club, in ascending order.

    Returns
    -------
    list of int
        Sorted provider identifiers of the team table.
    """

    return sorted(team.sportmonks_id for team in Team.objects.all())


@pytest.mark.django_db
def test_upsert_fixtures_reports_how_many_fixtures_it_wrote() -> None:
    """
    GIVEN two provider fixtures of the same competition
    WHEN the window is stored
    THEN both are written and the call reports as many fixtures as it received
    """

    window = [provider_fixture(1, kickoff(11, 30)), provider_fixture(2, kickoff(14))]

    written_count = upsert_fixtures(window, SYNCHRONIZED_AT)

    assert written_count == len(window)
    assert stored_fixture_identifiers() == [1, 2]


@pytest.mark.django_db
def test_upsert_fixtures_writes_nothing_for_an_empty_window() -> None:
    """
    GIVEN a provider window that yielded no fixture
    WHEN the window is stored
    THEN nothing is written and no fixture is reported
    """

    written_count = upsert_fixtures([], SYNCHRONIZED_AT)

    assert written_count == 0
    assert Fixture.objects.exists() is False
    assert League.objects.exists() is False
    assert Team.objects.exists() is False


@pytest.mark.django_db
def test_upsert_fixtures_changes_only_the_synchronization_stamp_on_a_second_identical_run() -> None:
    """
    GIVEN a window that has already been stored once
    WHEN the identical window is stored again
    THEN the same rows survive and only their synchronization stamp moves
    """

    window = [provider_fixture(1, kickoff(11, 30)), provider_fixture(2, kickoff(14))]

    upsert_fixtures(window, SYNCHRONIZED_AT)

    keys_before = {fixture.sportmonks_id: fixture.pk for fixture in Fixture.objects.all()}

    written_count = upsert_fixtures(window, LATER_SYNCHRONIZED_AT)

    assert written_count == len(window)
    assert League.objects.count() == 1
    assert stored_club_identifiers() == BOTH_CLUBS

    assert {fixture.sportmonks_id: fixture.pk for fixture in Fixture.objects.all()} == keys_before

    assert {fixture.synchronized_at for fixture in Fixture.objects.all()} == {LATER_SYNCHRONIZED_AT}


@pytest.mark.django_db
def test_upsert_fixtures_moves_a_postponed_fixture_instead_of_duplicating_it() -> None:
    """
    GIVEN a stored fixture whose provider identifier reappears with a later kick-off
    WHEN the window is stored again
    THEN the single row carries the new kick-off
    """

    upsert_fixtures([provider_fixture(1, kickoff(11, 30))], SYNCHRONIZED_AT)

    original_key = Fixture.objects.get().pk

    postponed_kickoff = kickoff(19, 45, day=date(2026, 8, 30))

    upsert_fixtures([provider_fixture(1, postponed_kickoff)], LATER_SYNCHRONIZED_AT)

    stored = Fixture.objects.get()

    assert stored.pk == original_key
    assert stored.kickoff_at == postponed_kickoff


@pytest.mark.django_db
def test_upsert_fixtures_gives_a_finished_fixture_the_result_it_was_inserted_without() -> None:
    """
    GIVEN a fixture stored while it was still scheduled and carried no score
    WHEN the same fixture is stored again as finished and carrying one
    THEN the row that was inserted moved to the result rather than keeping none
    """

    scheduled = provider_fixture(1, kickoff(11, 30))

    upsert_fixtures([scheduled], SYNCHRONIZED_AT)

    inserted = Fixture.objects.get()

    assert (inserted.status, inserted.home_goals, inserted.away_goals) == (
        FixtureStatus.SCHEDULED,
        None,
        None,
    )

    finished = replace(scheduled, status=FixtureStatus.FINISHED, home_goals=2, away_goals=0)

    upsert_fixtures([finished], LATER_SYNCHRONIZED_AT)

    stored = Fixture.objects.get()

    assert stored.pk == inserted.pk

    assert (stored.status, stored.home_goals, stored.away_goals) == (
        FixtureStatus.FINISHED,
        2,
        0,
    )


@pytest.mark.django_db
def test_upsert_fixtures_refreshes_the_competition_and_club_details() -> None:
    """
    GIVEN a stored fixture whose competition and home club were later renamed by the provider
    WHEN the window is stored again
    THEN the stored competition and club carry the new details
    """

    upsert_fixtures([provider_fixture(1, kickoff(11, 30))], SYNCHRONIZED_AT)

    renamed_league = replace(PREMIER_LEAGUE, name="English Premier League", short_code="EPL")
    renamed_club = replace(LIVERPOOL, name="Liverpool FC", crest_url="")

    upsert_fixtures(
        [provider_fixture(1, kickoff(11, 30), league=renamed_league, home_team=renamed_club)],
        LATER_SYNCHRONIZED_AT,
    )

    assert League.objects.count() == 1
    assert stored_club_identifiers() == BOTH_CLUBS

    stored_league = League.objects.get()

    assert (stored_league.name, stored_league.short_code) == ("English Premier League", "EPL")

    stored_club = Team.objects.get(sportmonks_id=LIVERPOOL.provider_id)

    assert (stored_club.name, stored_club.crest_url) == ("Liverpool FC", "")


@pytest.mark.django_db
def test_upsert_fixtures_resolves_a_shared_competition_and_club_once_per_call() -> None:
    """
    GIVEN two windows of the same competition and clubs differing only in fixture count
    WHEN each window is stored
    THEN both writes cost the same number of statements
    """

    small_window = [provider_fixture(index, kickoff(12)) for index in range(1, 3)]
    large_window = [provider_fixture(index, kickoff(12)) for index in range(10, 40)]

    with CaptureQueriesContext(connection) as small_statements:
        upsert_fixtures(small_window, SYNCHRONIZED_AT)

    with CaptureQueriesContext(connection) as large_statements:
        upsert_fixtures(large_window, SYNCHRONIZED_AT)

    assert len(large_statements.captured_queries) == len(small_statements.captured_queries)


@pytest.mark.django_db
def test_upsert_fixtures_collapses_a_window_repeating_a_provider_identifier() -> None:
    """
    GIVEN a provider window listing the same fixture identifier twice
    WHEN the window is stored
    THEN one row is written and one fixture is reported
    """

    written_count = upsert_fixtures(
        [provider_fixture(1, kickoff(11, 30)), provider_fixture(1, kickoff(11, 30))],
        SYNCHRONIZED_AT,
    )

    assert written_count == 1
    assert stored_fixture_identifiers() == [1]
