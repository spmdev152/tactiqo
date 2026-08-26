from collections.abc import Sequence
from datetime import UTC, date, datetime

from django.test.utils import CaptureQueriesContext

from apps.fixtures.infrastructure.repositories import upsert_fixtures
from apps.fixtures.models import Fixture
from apps.statistics.domain.enums import MatchSide
from apps.statistics.infrastructure.repositories import upsert_match_statistics
from integrations.sportmonks.fixtures import ProviderFixture, ProviderLeague
from integrations.sportmonks.statistics import (
    ProviderFixtureStatistics,
    ProviderStatisticsWindow,
    ProviderTeamStatistics,
)
from tests.unit.fixtures.conftest import (
    PREMIER_LEAGUE,
    WINDOW_END,
    WINDOW_START,
    kickoff,
    provider_fixture,
    provider_window,
)

SYNCHRONIZED_AT = datetime(2026, 8, 25, 6, 0, tzinfo=UTC)

LATER_SYNCHRONIZED_AT = SYNCHRONIZED_AT.replace(hour=18)

FIXTURE_PROVIDER_ID = 1

SPLIT_BATCH_SIZE = 1

# One plausible performance, complete in every column, so a test names only the
# figures its assertion is about and the rest still satisfy the model. The
# provider publishes all twenty-two for a settled fixture, so a partial set
# would be a shape the boundary never yields.
BASE_VALUES = {
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

METRIC_COLUMNS = tuple(BASE_VALUES)


def insert_statements(statements: CaptureQueriesContext) -> list[str]:
    """
    Return the insert statements of a captured write, in execution order.

    Parameters
    ----------
    statements : CaptureQueriesContext
        Context the write was captured in.

    Returns
    -------
    list of str
        SQL of every insert issued, so a batched write can be told from one
        statement carrying a whole read.
    """

    return [
        query["sql"] for query in statements.captured_queries if query["sql"].startswith("INSERT")
    ]


def seed_fixtures(
    provider_fixtures: Sequence[ProviderFixture],
    *,
    leagues: Sequence[ProviderLeague] | None = None,
    start: date = WINDOW_START,
    end: date = WINDOW_END,
    synchronized_at: datetime = SYNCHRONIZED_AT,
) -> dict[int, Fixture]:
    """
    Store the matches a statistic points at, through the fixtures repository.

    The rows a test points at are written by the repository that owns them
    rather than by ``objects.create``, so they are shaped exactly as a real
    synchronization leaves them, competitions and clubs included. One call is one
    authoritative window, so ``upsert_fixtures`` reconciles the range and a
    second call replaces the matches the first stored: seed every match a test
    needs in a single call.

    Parameters
    ----------
    provider_fixtures : Sequence of ProviderFixture
        Matches to store, built with ``provider_fixture`` so the kick-off, the
        status, the season, and the score are stated where they matter.
    leagues : Sequence of ProviderLeague or None
        Subscribed competitions the window carries, derived from the matches
        when ``None``.
    start : date
        First calendar day the window covers.
    end : date
        Last calendar day the window covers, included in the range.
    synchronized_at : datetime
        Instant stamped on every match the call writes.

    Returns
    -------
    dict of int to Fixture
        Every stored match, keyed by provider identifier, carrying the primary
        keys the statistic rows point at.
    """

    upsert_fixtures(provider_window(provider_fixtures, leagues), start, end, synchronized_at)

    return {fixture.sportmonks_id: fixture for fixture in Fixture.objects.all()}


def seed_fixture_ids(
    provider_ids: Sequence[int] = (FIXTURE_PROVIDER_ID,),
    *,
    league: ProviderLeague = PREMIER_LEAGUE,
) -> dict[int, Fixture]:
    """
    Store one plainly scheduled match per provider identifier.

    The shorthand for a test that needs matches to hang statistics off and
    nothing else off them. Reach for ``seed_fixtures`` when the kick-off, the
    status, the season, or the score is part of what the test is about.

    Parameters
    ----------
    provider_ids : Sequence of int
        Provider identifiers of the matches to store.
    league : ProviderLeague
        Competition the matches belong to.

    Returns
    -------
    dict of int to Fixture
        Every stored match, keyed by provider identifier.
    """

    return seed_fixtures(
        [provider_fixture(provider_id, kickoff(12), league=league) for provider_id in provider_ids]
    )


def team_statistics(
    team_provider_id: int, side: MatchSide, **values: int
) -> ProviderTeamStatistics:
    """
    Build one side's figures without contacting the provider.

    Parameters
    ----------
    team_provider_id : int
        Provider identifier of the club whose performance this is.
    side : MatchSide
        Side the club occupied in the match.
    **values : int
        Figures to override in ``BASE_VALUES``, keyed by the column that stores
        each one.

    Returns
    -------
    ProviderTeamStatistics
        Record shaped exactly as the Sportmonks boundary yields one.
    """

    return ProviderTeamStatistics(
        team_provider_id=team_provider_id, side=side, values=BASE_VALUES | values
    )


def fixture_statistics(
    fixture_provider_id: int, teams: Sequence[ProviderTeamStatistics]
) -> ProviderFixtureStatistics:
    """
    Build the figures the provider published for one match.

    Parameters
    ----------
    fixture_provider_id : int
        Provider identifier of the match the figures belong to.
    teams : Sequence of ProviderTeamStatistics
        Performances the provider published, empty for a match it read and
        published nothing for.

    Returns
    -------
    ProviderFixtureStatistics
        Entry shaped exactly as the Sportmonks boundary yields one.
    """

    return ProviderFixtureStatistics(fixture_provider_id=fixture_provider_id, teams=list(teams))


def statistics_window(
    entries: Sequence[ProviderFixtureStatistics],
) -> ProviderStatisticsWindow:
    """
    Build a provider statistics read without contacting the provider.

    Parameters
    ----------
    entries : Sequence of ProviderFixtureStatistics
        Matches the read covered, in the order the provider listed them.

    Returns
    -------
    ProviderStatisticsWindow
        Read shaped exactly as the Sportmonks boundary yields one.
    """

    return ProviderStatisticsWindow(fixtures=list(entries))


def store_statistics(
    entries: Sequence[ProviderFixtureStatistics],
    synchronized_at: datetime = SYNCHRONIZED_AT,
) -> int:
    """
    Store a statistics read through the repository under test.

    Parameters
    ----------
    entries : Sequence of ProviderFixtureStatistics
        Matches the read covered, with the performances of each.
    synchronized_at : datetime
        Instant stamped on every row the call writes.

    Returns
    -------
    int
        Number of statistic rows written.
    """

    return upsert_match_statistics(statistics_window(entries), synchronized_at)
