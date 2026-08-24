from datetime import UTC, date, datetime, time, timedelta

from apps.fixtures.models import Fixture, League


def list_leagues() -> list[League]:
    """
    Return every stored competition.

    The five subscribed competitions are reference data rather than a growing
    table, so the listing is unpaginated and ordered by name through the model
    default.

    Returns
    -------
    list of League
        Competitions ordered alphabetically by name.
    """

    return list(League.objects.all())


def list_fixtures_on(day: date, league_id: int | None) -> list[Fixture]:
    """
    Return the fixtures kicking off on a UTC calendar day.

    Parameters
    ----------
    day : date
        Calendar day, interpreted in UTC, whose fixtures are wanted. A fixture
        kicking off exactly at midnight belongs to the day that opens, not to
        the one that closes.
    league_id : int or None
        Primary key of a competition to narrow the day to, or ``None`` for every
        competition.

    Returns
    -------
    list of Fixture
        Fixtures ordered by kick-off then primary key, each with its competition
        and both clubs already loaded so serializing the list costs one query.
    """

    day_starts_at = datetime.combine(day, time.min, tzinfo=UTC)

    fixtures = Fixture.objects.select_related("league", "home_team", "away_team").filter(
        kickoff_at__gte=day_starts_at, kickoff_at__lt=day_starts_at + timedelta(days=1)
    )

    if league_id is not None:
        fixtures = fixtures.filter(league_id=league_id)

    return list(fixtures)
