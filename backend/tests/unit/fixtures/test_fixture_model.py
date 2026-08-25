import pytest
from django.db import IntegrityError

from apps.fixtures.domain.enums import FixtureStatus
from apps.fixtures.infrastructure.repositories import upsert_fixtures
from apps.fixtures.models import Fixture, League, Team
from tests.unit.fixtures.conftest import SYNCHRONIZED_AT, kickoff, provider_fixture


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

    upsert_fixtures([provider_fixture(1, kickoff(11, 30))], SYNCHRONIZED_AT)

    stored = Fixture.objects.get()

    stored.home_goals = 2

    with pytest.raises(IntegrityError, match="fixture_goals_pair_check"):
        stored.save(update_fields=["home_goals"])
