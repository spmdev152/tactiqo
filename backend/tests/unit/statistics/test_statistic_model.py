import pytest
from django.db import IntegrityError

from apps.fixtures.models import Fixture, Team
from apps.statistics.domain.enums import MatchSide
from apps.statistics.models import POSSESSION_CEILING, MatchTeamStatistic
from tests.unit.fixtures.conftest import LIVERPOOL, NOTTINGHAM_FOREST
from tests.unit.statistics.conftest import (
    BASE_VALUES,
    FIXTURE_PROVIDER_ID,
    SYNCHRONIZED_AT,
    seed_fixture_ids,
)

SMALLEST_STEP = 1


def store_statistic(
    fixture: Fixture,
    team: Team,
    side: MatchSide = MatchSide.HOME,
    **values: int,
) -> MatchTeamStatistic:
    """
    Write one statistic row directly, bypassing the repository upsert.

    The constraints are what the upsert relies on, so they are exercised against
    a plain write: the repository collapses a duplicate natural key, clears a
    displaced side, and clamps nothing, which is exactly why the database has to
    be the one refusing.

    Parameters
    ----------
    fixture : Fixture
        Match the row belongs to.
    team : Team
        Club whose performance the row records.
    side : MatchSide
        Side the club occupied.
    **values : int
        Figures to override in ``BASE_VALUES``, valid or otherwise.

    Returns
    -------
    MatchTeamStatistic
        Stored row.
    """

    return MatchTeamStatistic.objects.create(
        fixture=fixture,
        team=team,
        side=side,
        synchronized_at=SYNCHRONIZED_AT,
        **(BASE_VALUES | values),
    )


@pytest.mark.django_db
def test_the_database_refuses_a_second_performance_for_one_club_in_a_match() -> None:
    """
    GIVEN a stored performance of one club in a match
    WHEN a second row is written for the same match and club
    THEN the database refuses it, which is what makes the upsert idempotent
    """

    fixture = seed_fixture_ids()[FIXTURE_PROVIDER_ID]

    store_statistic(fixture, fixture.home_team)

    with pytest.raises(IntegrityError, match="team_id"):
        store_statistic(fixture, fixture.home_team, MatchSide.AWAY)


@pytest.mark.django_db
def test_the_database_refuses_two_clubs_taking_the_same_side_of_a_match() -> None:
    """
    GIVEN a stored home performance in a match
    WHEN the other club of the match is also written as its home side
    THEN the database refuses it, so no match can hold two home performances
    """

    fixture = seed_fixture_ids()[FIXTURE_PROVIDER_ID]

    store_statistic(fixture, fixture.home_team)

    with pytest.raises(IntegrityError, match=r"\.side"):
        store_statistic(fixture, fixture.away_team)


@pytest.mark.django_db
def test_the_database_accepts_possession_of_exactly_a_hundred() -> None:
    """
    GIVEN a club that never gave the ball away
    WHEN a possession share of exactly a hundred is written
    THEN the row is stored, because the bound is inclusive
    """

    fixture = seed_fixture_ids()[FIXTURE_PROVIDER_ID]

    store_statistic(fixture, fixture.home_team, possession=POSSESSION_CEILING)

    assert MatchTeamStatistic.objects.get().possession == POSSESSION_CEILING


@pytest.mark.django_db
def test_the_database_refuses_possession_above_a_hundred() -> None:
    """
    GIVEN a match whose possession is stored as a whole percentage
    WHEN a share one point above a hundred is written
    THEN the database refuses it rather than storing an unrenderable bar
    """

    fixture = seed_fixture_ids()[FIXTURE_PROVIDER_ID]

    with pytest.raises(IntegrityError, match="match_statistic_possession_range_check"):
        store_statistic(fixture, fixture.home_team, possession=POSSESSION_CEILING + SMALLEST_STEP)


@pytest.mark.django_db
def test_the_database_refuses_a_negative_count() -> None:
    """
    GIVEN a match whose figures are stored as counts of things that happened
    WHEN a shot count one below nought is written
    THEN the database refuses it, which is why every metric column is unsigned
    """

    fixture = seed_fixture_ids()[FIXTURE_PROVIDER_ID]

    with pytest.raises(IntegrityError, match="shots_total"):
        store_statistic(fixture, fixture.home_team, shots_total=-SMALLEST_STEP)


@pytest.mark.django_db
def test_a_statistic_row_reads_as_the_club_the_side_and_the_match() -> None:
    """
    GIVEN a stored away performance
    WHEN the row is rendered as text, as the admin change list does
    THEN it names the club, the side it took, and the match it belongs to
    """

    fixture = seed_fixture_ids()[FIXTURE_PROVIDER_ID]

    store_statistic(fixture, fixture.away_team, MatchSide.AWAY)

    stored = MatchTeamStatistic.objects.select_related("team", "fixture").get()

    assert str(stored) == f"{NOTTINGHAM_FOREST.name} {MatchSide.AWAY.value} in {stored.fixture}"


@pytest.mark.django_db
def test_both_clubs_of_a_match_are_stored_as_the_two_rows_of_that_match() -> None:
    """
    GIVEN a match whose two clubs each recorded a performance
    WHEN both rows are written
    THEN the table holds one row a side, which is the shape every form read averages
    """

    fixture = seed_fixture_ids()[FIXTURE_PROVIDER_ID]

    store_statistic(fixture, fixture.home_team)
    store_statistic(fixture, fixture.away_team, MatchSide.AWAY)

    stored = {
        (row.team.sportmonks_id, row.side)
        for row in MatchTeamStatistic.objects.select_related("team")
    }

    assert stored == {
        (LIVERPOOL.provider_id, MatchSide.HOME),
        (NOTTINGHAM_FOREST.provider_id, MatchSide.AWAY),
    }
