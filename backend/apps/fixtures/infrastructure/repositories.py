from collections.abc import Sequence
from datetime import datetime

from django.db import transaction

from apps.fixtures.models import Fixture, League, Team
from integrations.sportmonks.fixtures import ProviderFixture, ProviderLeague, ProviderTeam

LEAGUE_UPDATE_FIELDS = ["name", "short_code", "logo_url", "country_name", "country_flag_url"]

TEAM_UPDATE_FIELDS = ["name", "short_code", "crest_url"]

FIXTURE_UPDATE_FIELDS = [
    "league",
    "home_team",
    "away_team",
    "kickoff_at",
    "status",
    "home_goals",
    "away_goals",
    "synchronized_at",
]


def _upsert_leagues(provider_leagues: dict[int, ProviderLeague]) -> dict[int, League]:
    """
    Store every distinct competition of a batch and return them by provider id.

    Parameters
    ----------
    provider_leagues : dict of int to ProviderLeague
        Competitions of the batch, keyed by provider identifier so each one is
        written once however many fixtures referenced it.

    Returns
    -------
    dict of int to League
        Stored competitions keyed by provider identifier, carrying the primary
        keys the fixture rows point at.
    """

    League.objects.bulk_create(
        [
            League(
                sportmonks_id=provider_id,
                name=provider_league.name,
                short_code=provider_league.short_code,
                logo_url=provider_league.logo_url,
                country_name=provider_league.country_name,
                country_flag_url=provider_league.country_flag_url,
            )
            for provider_id, provider_league in provider_leagues.items()
        ],
        update_conflicts=True,
        unique_fields=["sportmonks_id"],
        update_fields=LEAGUE_UPDATE_FIELDS,
    )

    stored = League.objects.filter(sportmonks_id__in=provider_leagues)

    return {league.sportmonks_id: league for league in stored}


def _upsert_teams(provider_teams: dict[int, ProviderTeam]) -> dict[int, Team]:
    """
    Store every distinct club of a batch and return them by provider id.

    Parameters
    ----------
    provider_teams : dict of int to ProviderTeam
        Clubs of the batch, keyed by provider identifier so each one is written
        once however many fixtures it appears in.

    Returns
    -------
    dict of int to Team
        Stored clubs keyed by provider identifier, carrying the primary keys the
        fixture rows point at.
    """

    Team.objects.bulk_create(
        [
            Team(
                sportmonks_id=provider_id,
                name=provider_team.name,
                short_code=provider_team.short_code,
                crest_url=provider_team.crest_url,
            )
            for provider_id, provider_team in provider_teams.items()
        ],
        update_conflicts=True,
        unique_fields=["sportmonks_id"],
        update_fields=TEAM_UPDATE_FIELDS,
    )

    stored = Team.objects.filter(sportmonks_id__in=provider_teams)

    return {team.sportmonks_id: team for team in stored}


def upsert_fixtures(provider_fixtures: Sequence[ProviderFixture], synchronized_at: datetime) -> int:
    """
    Store a window of provider fixtures, updating whatever already exists.

    The provider identifier is the natural key of all three tables, so running
    the same window twice leaves the rows as they were apart from
    ``synchronized_at``, and a postponed match arriving with a later kick-off
    moves its row rather than adding one. The window a fixture is played in is
    read repeatedly, so the status and the score are updated on conflict like
    everything else: a match inserted as scheduled gains its result on the run
    after it finishes. Competitions and clubs are resolved once per call instead
    of once per fixture, because a fortnight of five leagues is on the order of
    eight hundred fixtures sharing a few dozen of them. The whole write is one
    transaction, so a provider failure part-way through a paginated fetch cannot
    leave half a window behind.

    Parameters
    ----------
    provider_fixtures : Sequence of ProviderFixture
        Fixtures read from the provider, in any order.
    synchronized_at : datetime
        Timezone-aware instant stamped on every fixture this call writes.

    Returns
    -------
    int
        Number of distinct fixtures written.
    """

    # ``ON CONFLICT DO UPDATE`` refuses to touch the same row twice in one
    # statement, so a provider window repeating an identifier must collapse
    # before it reaches the database.
    unique_fixtures = {
        provider_fixture.provider_id: provider_fixture for provider_fixture in provider_fixtures
    }

    if not unique_fixtures:
        return 0

    provider_leagues = {
        provider_fixture.league.provider_id: provider_fixture.league
        for provider_fixture in unique_fixtures.values()
    }

    provider_teams: dict[int, ProviderTeam] = {}

    for provider_fixture in unique_fixtures.values():
        provider_teams[provider_fixture.home_team.provider_id] = provider_fixture.home_team
        provider_teams[provider_fixture.away_team.provider_id] = provider_fixture.away_team

    with transaction.atomic():
        leagues = _upsert_leagues(provider_leagues)
        teams = _upsert_teams(provider_teams)

        Fixture.objects.bulk_create(
            [
                Fixture(
                    sportmonks_id=provider_id,
                    league=leagues[provider_fixture.league.provider_id],
                    home_team=teams[provider_fixture.home_team.provider_id],
                    away_team=teams[provider_fixture.away_team.provider_id],
                    kickoff_at=provider_fixture.kickoff_at,
                    status=provider_fixture.status,
                    home_goals=provider_fixture.home_goals,
                    away_goals=provider_fixture.away_goals,
                    synchronized_at=synchronized_at,
                )
                for provider_id, provider_fixture in unique_fixtures.items()
            ],
            update_conflicts=True,
            unique_fields=["sportmonks_id"],
            update_fields=FIXTURE_UPDATE_FIELDS,
        )

    return len(unique_fixtures)
