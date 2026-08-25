from collections.abc import Sequence
from datetime import UTC, date, datetime, time, timedelta

from django.db.models import Exists, OuterRef

from apps.fixtures.models import Fixture, League
from apps.predictions.models import FixturePrediction


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


def list_fixtures_on(day: date, league_ids: Sequence[int]) -> list[Fixture]:
    """
    Return the fixtures kicking off on a UTC calendar day.

    Parameters
    ----------
    day : date
        Calendar day, interpreted in UTC, whose fixtures are wanted. A fixture
        kicking off exactly at midnight belongs to the day that opens, not to
        the one that closes.
    league_ids : sequence of int
        Primary keys of the competitions the day is narrowed to. An empty
        sequence asks for every competition, so no filter is a single state
        rather than one split between an absent value and an empty one.

    Returns
    -------
    list of Fixture
        Fixtures ordered by kick-off then primary key, each with its competition
        and both clubs already loaded and each carrying ``has_predictions``, so
        serializing the list costs one query.

    Notes
    -----
    ``has_predictions`` is a semi-join rather than a second round trip or a
    denormalized column. A second read would either fetch one row per fixture,
    which is the N+1 this listing already goes out of its way to avoid, or fetch
    the day's distinct predicted fixtures and intersect them here, which costs a
    second statement to answer a question the first one can already answer. A
    column on ``Fixture`` would be cheaper still to read and would have to be
    kept true by every writer of the prediction table, including the deletions
    the stamp-based reconciliation performs, so the flag could silently outlive
    the rows it describes. ``EXISTS`` cannot: it is derived from those rows at
    read time, and it stops at the first match instead of counting or joining,
    so a fixture carrying fifty predictions costs what a fixture carrying one
    costs.

    Crossing a slice boundary is the price of that choice, and it is paid
    knowingly: this module imports ``apps.predictions.models`` while the
    predictions slice imports ``apps.fixtures.models``, so the two slices read
    each other's tables even though the foreign key runs one way. Nothing
    cycles, because the prediction models name their fixture and competition
    relations as lazy strings, and the alternative was not a cleaner boundary: a
    denormalized column would move the coupling from one read into every writer
    of the prediction table, and the second round trip would move it into the
    caller. "Does this match have predictions" is a fact about a fixture that
    only the prediction table holds, so a one-way read across two slices of one
    monolith is the lesser cost.
    """

    day_starts_at = datetime.combine(day, time.min, tzinfo=UTC)

    fixtures = (
        Fixture.objects.select_related("league", "home_team", "away_team")
        .annotate(has_predictions=Exists(FixturePrediction.objects.filter(fixture=OuterRef("pk"))))
        .filter(kickoff_at__gte=day_starts_at, kickoff_at__lt=day_starts_at + timedelta(days=1))
    )

    if league_ids:
        fixtures = fixtures.filter(league_id__in=league_ids)

    return list(fixtures)
