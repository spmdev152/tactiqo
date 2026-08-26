from collections.abc import Sequence
from datetime import UTC, date, datetime

from apps.fixtures.domain.enums import FixtureStatus
from apps.fixtures.infrastructure.repositories import upsert_fixtures
from integrations.sportmonks.fixtures import (
    ProviderFixture,
    ProviderLeague,
    ProviderTeam,
    ProviderWindow,
)

DAY = date(2026, 8, 29)

SYNCHRONIZED_AT = datetime(2026, 8, 25, 6, 0, tzinfo=UTC)

WINDOW_START = date(2026, 8, 23)

WINDOW_END = date(2026, 9, 8)

SEASON_ID = 25583

PREMIER_LEAGUE = ProviderLeague(
    provider_id=8,
    name="Premier League",
    short_code="UK PL",
    logo_url="https://cdn.example.test/leagues/8.png",
    country_name="England",
    country_flag_url="https://cdn.example.test/countries/en.png",
)

LA_LIGA = ProviderLeague(
    provider_id=564,
    name="La Liga",
    short_code="ES LL",
    logo_url="https://cdn.example.test/leagues/564.png",
    country_name="Spain",
    country_flag_url="https://cdn.example.test/countries/es.png",
)

LIVERPOOL = ProviderTeam(
    provider_id=8,
    name="Liverpool",
    short_code="LIV",
    crest_url="https://cdn.example.test/teams/8.png",
)

NOTTINGHAM_FOREST = ProviderTeam(
    provider_id=63,
    name="Nottingham Forest",
    short_code="NFO",
    crest_url="https://cdn.example.test/teams/63.png",
)

BARCELONA = ProviderTeam(
    provider_id=83,
    name="Barcelona",
    short_code="BAR",
    crest_url="https://cdn.example.test/teams/83.png",
)

SEVILLA = ProviderTeam(
    provider_id=1,
    name="Sevilla",
    short_code="SEV",
    crest_url="https://cdn.example.test/teams/1.png",
)


def kickoff(hour: int, minute: int = 0, day: date = DAY) -> datetime:
    """
    Return a UTC kick-off instant on a calendar day.

    Parameters
    ----------
    hour : int
        Hour of the kick-off in UTC.
    minute : int
        Minute of the kick-off in UTC.
    day : date
        Calendar day the match is played on.

    Returns
    -------
    datetime
        Timezone-aware UTC instant.
    """

    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=UTC)


def provider_fixture(
    provider_id: int,
    kickoff_at: datetime,
    *,
    season_provider_id: int | None = SEASON_ID,
    league: ProviderLeague = PREMIER_LEAGUE,
    home_team: ProviderTeam = LIVERPOOL,
    away_team: ProviderTeam = NOTTINGHAM_FOREST,
    status: FixtureStatus = FixtureStatus.SCHEDULED,
    home_goals: int | None = None,
    away_goals: int | None = None,
) -> ProviderFixture:
    """
    Build a provider fixture without contacting the provider.

    Parameters
    ----------
    provider_id : int
        Provider identifier of the match, which is its natural key.
    kickoff_at : datetime
        Timezone-aware UTC instant the match starts.
    season_provider_id : int or None
        Provider identifier of the season the match is played in, ``None`` for a
        match the provider states no season for.
    league : ProviderLeague
        Competition the match belongs to.
    home_team : ProviderTeam
        Club playing at home.
    away_team : ProviderTeam
        Club playing away.
    status : FixtureStatus
        Lifecycle stage the boundary read the match at.
    home_goals : int or None
        Goals the home club has scored, ``None`` for a match with no score.
    away_goals : int or None
        Goals the away club has scored, ``None`` for a match with no score.

    Returns
    -------
    ProviderFixture
        Fixture shaped exactly as the Sportmonks boundary yields one.
    """

    return ProviderFixture(
        provider_id=provider_id,
        season_provider_id=season_provider_id,
        kickoff_at=kickoff_at,
        league=league,
        home_team=home_team,
        away_team=away_team,
        status=status,
        home_goals=home_goals,
        away_goals=away_goals,
    )


def provider_window(
    provider_fixtures: Sequence[ProviderFixture],
    leagues: Sequence[ProviderLeague] | None = None,
) -> ProviderWindow:
    """
    Build a provider window without contacting the provider.

    Parameters
    ----------
    provider_fixtures : Sequence of ProviderFixture
        Fixtures the window carries, in the order the provider listed them.
    leagues : Sequence of ProviderLeague or None
        Subscribed competitions the window carries. ``None`` derives them from
        the fixtures, which is what a window whose every subscribed competition
        schedules a match looks like.

    Returns
    -------
    ProviderWindow
        Window shaped exactly as the Sportmonks boundary yields one.
    """

    if leagues is None:
        leagues = [provider_fixture.league for provider_fixture in provider_fixtures]

    return ProviderWindow(
        leagues={league.provider_id: league for league in leagues},
        fixtures=list(provider_fixtures),
    )


def store_window(
    provider_fixtures: Sequence[ProviderFixture],
    synchronized_at: datetime = SYNCHRONIZED_AT,
    *,
    leagues: Sequence[ProviderLeague] | None = None,
    start: date = WINDOW_START,
    end: date = WINDOW_END,
) -> int:
    """
    Store a provider window over the range a scheduled run reads.

    Parameters
    ----------
    provider_fixtures : Sequence of ProviderFixture
        Fixtures the window carries.
    synchronized_at : datetime
        Instant stamped on every fixture the call writes.
    leagues : Sequence of ProviderLeague or None
        Subscribed competitions the window carries, derived from the fixtures
        when ``None``.
    start : date
        First calendar day the window covers.
    end : date
        Last calendar day the window covers, included in the range.

    Returns
    -------
    int
        Number of distinct fixtures written.
    """

    return upsert_fixtures(provider_window(provider_fixtures, leagues), start, end, synchronized_at)
