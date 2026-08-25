from dataclasses import replace
from datetime import date

import pytest
from django.db import connection
from django.db.models import Model
from django.test.utils import CaptureQueriesContext

from apps.fixtures.domain.enums import FixtureStatus
from apps.fixtures.infrastructure.repositories import upsert_fixtures
from apps.fixtures.models import Fixture, League, Team
from tests.unit.fixtures.conftest import (
    BARCELONA,
    LA_LIGA,
    LIVERPOOL,
    NOTTINGHAM_FOREST,
    PREMIER_LEAGUE,
    SEVILLA,
    SYNCHRONIZED_AT,
    WINDOW_END,
    WINDOW_START,
    kickoff,
    provider_fixture,
    provider_window,
    store_window,
)

LATER_SYNCHRONIZED_AT = SYNCHRONIZED_AT.replace(hour=18)

BOTH_CLUBS = sorted([LIVERPOOL.provider_id, NOTTINGHAM_FOREST.provider_id])

BEYOND_THE_WINDOW = date(2026, 10, 3)


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


def stored_league_identifiers() -> list[int]:
    """
    Return the provider identifiers of every stored competition, ascending.

    Returns
    -------
    list of int
        Sorted provider identifiers of the league table.
    """

    return sorted(league.sportmonks_id for league in League.objects.all())


def provider_identifiers_by_key(model: type[Model]) -> list[int]:
    """
    Return the provider identifiers of a table in primary-key order.

    Parameters
    ----------
    model : type of Model
        Model whose rows are read.

    Returns
    -------
    list of int
        Provider identifiers ordered by the primary key the insert assigned.
    """

    return list(model.objects.order_by("pk").values_list("sportmonks_id", flat=True))


@pytest.mark.django_db
def test_upsert_fixtures_reports_how_many_fixtures_it_wrote() -> None:
    """
    GIVEN two provider fixtures of the same competition
    WHEN the window is stored
    THEN both are written and the call reports as many fixtures as it received
    """

    window = [provider_fixture(1, kickoff(11, 30)), provider_fixture(2, kickoff(14))]

    written_count = store_window(window)

    assert written_count == len(window)
    assert stored_fixture_identifiers() == [1, 2]


@pytest.mark.django_db
def test_upsert_fixtures_writes_nothing_for_an_empty_window() -> None:
    """
    GIVEN a provider window that carried neither a competition nor a fixture
    WHEN the window is stored
    THEN nothing is written and no fixture is reported
    """

    written_count = store_window([], leagues=[])

    assert written_count == 0
    assert Fixture.objects.exists() is False
    assert League.objects.exists() is False
    assert Team.objects.exists() is False


@pytest.mark.django_db
def test_upsert_fixtures_stores_a_competition_with_no_fixture_in_the_window() -> None:
    """
    GIVEN a window whose fixtures name one of its two subscribed competitions
    WHEN the window is stored
    THEN both competitions are stored, so a winter break cannot hide one
    """

    written_count = store_window(
        [provider_fixture(1, kickoff(11, 30))], leagues=[PREMIER_LEAGUE, LA_LIGA]
    )

    assert written_count == 1
    assert stored_league_identifiers() == sorted([PREMIER_LEAGUE.provider_id, LA_LIGA.provider_id])


@pytest.mark.django_db
def test_upsert_fixtures_stores_the_subscribed_competitions_of_a_fixtureless_window() -> None:
    """
    GIVEN an off-season window carrying two subscribed competitions and no fixture
    WHEN the window is stored
    THEN both competitions are stored although no fixture reported was written
    """

    written_count = store_window([], leagues=[PREMIER_LEAGUE, LA_LIGA])

    assert written_count == 0
    assert stored_league_identifiers() == sorted([PREMIER_LEAGUE.provider_id, LA_LIGA.provider_id])


@pytest.mark.django_db
def test_upsert_fixtures_changes_only_the_synchronization_stamp_on_a_second_identical_run() -> None:
    """
    GIVEN a window that has already been stored once
    WHEN the identical window is stored again
    THEN the same rows survive and only their synchronization stamp moves
    """

    window = [provider_fixture(1, kickoff(11, 30)), provider_fixture(2, kickoff(14))]

    store_window(window)

    keys_before = {fixture.sportmonks_id: fixture.pk for fixture in Fixture.objects.all()}

    written_count = store_window(window, LATER_SYNCHRONIZED_AT)

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

    store_window([provider_fixture(1, kickoff(11, 30))])

    original_key = Fixture.objects.get().pk

    postponed_kickoff = kickoff(19, 45, day=date(2026, 8, 30))

    store_window([provider_fixture(1, postponed_kickoff)], LATER_SYNCHRONIZED_AT)

    stored = Fixture.objects.get()

    assert stored.pk == original_key
    assert stored.kickoff_at == postponed_kickoff


@pytest.mark.django_db
def test_upsert_fixtures_deletes_a_fixture_the_window_stopped_carrying() -> None:
    """
    GIVEN a stored fixture inside the range whose identifier the next payload omits
    WHEN that range is stored again
    THEN the row is gone rather than advertising a kick-off that will not happen
    """

    store_window([provider_fixture(1, kickoff(11, 30)), provider_fixture(2, kickoff(14))])

    store_window([provider_fixture(2, kickoff(14))], LATER_SYNCHRONIZED_AT)

    assert stored_fixture_identifiers() == [2]


@pytest.mark.django_db
def test_upsert_fixtures_leaves_a_fixture_outside_the_range_alone() -> None:
    """
    GIVEN a stored fixture kicking off beyond the range the next run reads
    WHEN that shorter range is stored again without it
    THEN the row survives, because the run read no authority over its day
    """

    store_window(
        [provider_fixture(1, kickoff(14)), provider_fixture(2, kickoff(14, day=BEYOND_THE_WINDOW))],
        end=BEYOND_THE_WINDOW,
    )

    store_window([provider_fixture(1, kickoff(14))], LATER_SYNCHRONIZED_AT)

    assert stored_fixture_identifiers() == [1, 2]


@pytest.mark.django_db
def test_upsert_fixtures_empties_a_range_the_provider_stopped_listing_anything_in() -> None:
    """
    GIVEN a stored window and a later complete read of the same range carrying no fixture
    WHEN that read is stored
    THEN the range is emptied while its subscribed competitions stay stored
    """

    store_window([provider_fixture(1, kickoff(11, 30))])

    written_count = store_window([], LATER_SYNCHRONIZED_AT, leagues=[PREMIER_LEAGUE])

    assert written_count == 0
    assert Fixture.objects.exists() is False
    assert stored_league_identifiers() == [PREMIER_LEAGUE.provider_id]


@pytest.mark.django_db
def test_upsert_fixtures_gives_a_finished_fixture_the_result_it_was_inserted_without() -> None:
    """
    GIVEN a fixture stored while it was still scheduled and carried no score
    WHEN the same fixture is stored again as finished and carrying one
    THEN the row that was inserted moved to the result rather than keeping none
    """

    scheduled = provider_fixture(1, kickoff(11, 30))

    store_window([scheduled])

    inserted = Fixture.objects.get()

    assert (inserted.status, inserted.home_goals, inserted.away_goals) == (
        FixtureStatus.SCHEDULED,
        None,
        None,
    )

    finished = replace(scheduled, status=FixtureStatus.FINISHED, home_goals=2, away_goals=0)

    store_window([finished], LATER_SYNCHRONIZED_AT)

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

    store_window([provider_fixture(1, kickoff(11, 30))])

    renamed_league = replace(PREMIER_LEAGUE, name="English Premier League", short_code="EPL")
    renamed_club = replace(LIVERPOOL, name="Liverpool FC", crest_url="")

    store_window(
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
    GIVEN a stored window and two replacements differing only in fixture count
    WHEN each replacement is stored
    THEN both writes cost the same number of statements
    """

    departing_window = [provider_fixture(index, kickoff(12)) for index in range(100, 103)]

    small_window = [provider_fixture(index, kickoff(12)) for index in range(1, 3)]
    large_window = [provider_fixture(index, kickoff(12)) for index in range(10, 40)]

    # Both captures have to reconcile a departure. Since predictions cascade off a
    # fixture, the reconciliation can no longer fast-delete: it selects the
    # departing keys first and only then issues a delete per table. A capture with
    # nothing to delete skips all three statements, so measuring one such write
    # against one that departs would compare the delete path rather than the
    # fixture count this test is about.
    store_window(departing_window)

    with CaptureQueriesContext(connection) as small_statements:
        store_window(small_window)

    with CaptureQueriesContext(connection) as large_statements:
        store_window(large_window)

    assert len(large_statements.captured_queries) == len(small_statements.captured_queries)


@pytest.mark.django_db
def test_upsert_fixtures_presents_every_row_in_ascending_provider_identifier() -> None:
    """
    GIVEN a window whose competitions, clubs, and fixtures all arrive out of identifier order
    WHEN the window is stored
    THEN each table's keys ascend with the provider identifier, whatever order the window used
    """

    window = provider_window(
        [
            provider_fixture(
                9, kickoff(14), league=LA_LIGA, home_team=BARCELONA, away_team=SEVILLA
            ),
            provider_fixture(2, kickoff(11, 30)),
        ],
        [LA_LIGA, PREMIER_LEAGUE],
    )

    upsert_fixtures(window, WINDOW_START, WINDOW_END, SYNCHRONIZED_AT)

    assert provider_identifiers_by_key(League) == [PREMIER_LEAGUE.provider_id, LA_LIGA.provider_id]

    assert provider_identifiers_by_key(Team) == [
        SEVILLA.provider_id,
        LIVERPOOL.provider_id,
        NOTTINGHAM_FOREST.provider_id,
        BARCELONA.provider_id,
    ]

    assert provider_identifiers_by_key(Fixture) == [2, 9]


@pytest.mark.django_db
def test_upsert_fixtures_collapses_a_window_repeating_a_provider_identifier() -> None:
    """
    GIVEN a provider window listing the same fixture identifier twice
    WHEN the window is stored
    THEN one row is written and one fixture is reported
    """

    written_count = store_window(
        [provider_fixture(1, kickoff(11, 30)), provider_fixture(1, kickoff(11, 30))]
    )

    assert written_count == 1
    assert stored_fixture_identifiers() == [1]
