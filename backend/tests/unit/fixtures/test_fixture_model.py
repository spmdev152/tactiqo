import pytest
from django.db import IntegrityError

from apps.fixtures.domain.enums import FixtureStatus
from apps.fixtures.models import Fixture, League, Team
from tests.unit.fixtures.conftest import (
    SEASON_ID,
    SYNCHRONIZED_AT,
    kickoff,
    provider_fixture,
    store_window,
)


def store_bare_fixture() -> Fixture:
    """
    Persist a fixture stating neither a lifecycle stage nor a score.

    Returns
    -------
    Fixture
        Stored fixture, whose stage and goals are whatever the columns default
        to rather than anything a writer chose.
    """

    league = League.objects.create(sportmonks_id=8, name="Premier League")

    home_team = Team.objects.create(sportmonks_id=1, name="Liverpool")
    away_team = Team.objects.create(sportmonks_id=2, name="Nottingham Forest")

    return Fixture.objects.create(
        sportmonks_id=1,
        league=league,
        home_team=home_team,
        away_team=away_team,
        kickoff_at=kickoff(11, 30),
        synchronized_at=SYNCHRONIZED_AT,
    )


@pytest.mark.django_db
def test_a_fixture_written_without_a_result_is_scheduled_and_scoreless() -> None:
    """
    GIVEN a fixture written with neither a lifecycle stage nor a score stated
    WHEN the row is read back
    THEN it is scheduled and both goal columns are null
    """

    store_bare_fixture()

    stored = Fixture.objects.get()

    assert (stored.status, stored.home_goals, stored.away_goals) == (
        FixtureStatus.SCHEDULED,
        None,
        None,
    )


@pytest.mark.django_db
def test_the_database_refuses_one_goal_column_without_the_other() -> None:
    """
    GIVEN a stored fixture that carries no score on either side
    WHEN the goals of the home club alone are written
    THEN the database refuses the row rather than storing half a score
    """

    store_window([provider_fixture(1, kickoff(11, 30))])

    stored = Fixture.objects.get()

    stored.home_goals = 2

    with pytest.raises(IntegrityError, match="fixture_goals_pair_check"):
        stored.save(update_fields=["home_goals"])


@pytest.mark.django_db
def test_a_stored_fixture_keeps_the_season_the_provider_stated() -> None:
    """
    GIVEN a provider fixture the boundary read a season for
    WHEN the window is stored and the row is read back
    THEN the row carries that season, which is what scopes a form sample to it
    """

    store_window([provider_fixture(1, kickoff(11, 30), season_provider_id=SEASON_ID)])

    assert Fixture.objects.get().season_sportmonks_id == SEASON_ID


@pytest.mark.django_db
def test_a_fixture_the_provider_stated_no_season_for_is_still_stored() -> None:
    """
    GIVEN a provider fixture the boundary could read no season for
    WHEN the window is stored and the row is read back
    THEN the row is stored with a null season rather than refused
    """

    store_window([provider_fixture(1, kickoff(11, 30), season_provider_id=None)])

    assert Fixture.objects.get().season_sportmonks_id is None
