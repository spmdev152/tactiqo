from collections.abc import Collection
from datetime import UTC, date, datetime, time, timedelta

from django.db import transaction

from apps.fixtures.models import Fixture, League, Team
from integrations.sportmonks.fixtures import (
    ProviderLeague,
    ProviderTeam,
    ProviderWindow,
)

LEAGUE_UPDATE_FIELDS = ["name", "short_code", "logo_url", "country_name", "country_flag_url"]

TEAM_UPDATE_FIELDS = ["name", "short_code", "crest_url"]

FIXTURE_UPDATE_FIELDS = [
    "season_sportmonks_id",
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
    Store the subscribed competitions and return them by provider identifier.

    The rows are presented in ascending provider identifier so that every run
    takes the competition row locks in the same order whatever order the
    provider listed them in.

    Parameters
    ----------
    provider_leagues : dict of int to ProviderLeague
        Every competition the provider returned for the subscription, keyed by
        provider identifier. It is deliberately the whole subscribed set rather
        than the competitions the window's fixtures happen to mention.

    Returns
    -------
    dict of int to League
        Stored competitions keyed by provider identifier, carrying the primary
        keys the fixture rows point at.
    """

    ordered = [provider_leagues[provider_id] for provider_id in sorted(provider_leagues)]

    League.objects.bulk_create(
        [
            League(
                sportmonks_id=provider_league.provider_id,
                name=provider_league.name,
                short_code=provider_league.short_code,
                logo_url=provider_league.logo_url,
                country_name=provider_league.country_name,
                country_flag_url=provider_league.country_flag_url,
            )
            for provider_league in ordered
        ],
        update_conflicts=True,
        unique_fields=["sportmonks_id"],
        update_fields=LEAGUE_UPDATE_FIELDS,
    )

    stored = League.objects.filter(sportmonks_id__in=provider_leagues)

    return {league.sportmonks_id: league for league in stored}


def _upsert_teams(provider_teams: dict[int, ProviderTeam]) -> dict[int, Team]:
    """
    Store every distinct club of a window and return them by provider id.

    The rows are presented in ascending provider identifier for the same reason
    the competitions are: the lock order stops depending on the order the
    provider paginated the window in.

    Parameters
    ----------
    provider_teams : dict of int to ProviderTeam
        Clubs of the window, keyed by provider identifier so each one is written
        once however many fixtures it appears in.

    Returns
    -------
    dict of int to Team
        Stored clubs keyed by provider identifier, carrying the primary keys the
        fixture rows point at.
    """

    ordered = [provider_teams[provider_id] for provider_id in sorted(provider_teams)]

    Team.objects.bulk_create(
        [
            Team(
                sportmonks_id=provider_team.provider_id,
                name=provider_team.name,
                short_code=provider_team.short_code,
                crest_url=provider_team.crest_url,
            )
            for provider_team in ordered
        ],
        update_conflicts=True,
        unique_fields=["sportmonks_id"],
        update_fields=TEAM_UPDATE_FIELDS,
    )

    stored = Team.objects.filter(sportmonks_id__in=provider_teams)

    return {team.sportmonks_id: team for team in stored}


def _delete_departed_fixtures(
    start: date, end: date, retained_provider_ids: Collection[int]
) -> None:
    """
    Remove the fixtures of a window the provider has stopped listing.

    Inside the range the run just read, the payload is the whole truth, so a
    stored row whose provider identifier it did not carry is a match that was
    postponed beyond the window or marked as deleted. Upserting alone would
    leave that row advertising a kick-off that will not happen, for as long as
    the new date stays outside the window, which for an ordinary rescheduling is
    months. Deleting is sound only because the provider boundary raises on a
    truncated read instead of returning the pages it managed to fetch: a prefix
    would be indistinguishable from a window that legitimately lost most of its
    fixtures, so the two changes are load-bearing for each other.

    An empty fixture list is a complete read like any other, the off-season
    being the ordinary case, so it empties the range rather than being taken for
    a failure. ``Fixture`` is the child of all three ``PROTECT`` relations and
    the parent of none, so the delete cascades nowhere.

    Parameters
    ----------
    start : date
        First calendar day, in UTC, the run read from the provider.
    end : date
        Last calendar day, in UTC, the run read from the provider, included in
        the range.
    retained_provider_ids : Collection of int
        Provider identifiers the payload carried, which are the rows the delete
        spares.
    """

    window_opens_at = datetime.combine(start, time.min, tzinfo=UTC)

    window_closes_at = datetime.combine(end + timedelta(days=1), time.min, tzinfo=UTC)

    Fixture.objects.filter(
        kickoff_at__gte=window_opens_at, kickoff_at__lt=window_closes_at
    ).exclude(sportmonks_id__in=retained_provider_ids).delete()


def upsert_fixtures(
    window: ProviderWindow, start: date, end: date, synchronized_at: datetime
) -> int:
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
    eight hundred fixtures sharing a few dozen of them.

    The competitions written are ``window.leagues``, the whole subscribed set,
    rather than the ones the window's fixtures mention. A league on a winter
    break has no fixture in a seventeen-day window, and neither does any league
    during the off-season, so deriving the competitions from the fixtures makes
    the league listing silently lose entries in situations that are ordinary
    rather than exceptional.

    Storing is only half of a synchronization: ``_delete_departed_fixtures``
    reconciles the range the run authoritatively read, so a match the provider
    stopped listing leaves the table instead of lingering on a day it will not
    be played.

    All four writes share one transaction. That does not protect against a
    provider failure part-way through the fetch, which is fully materialized
    before this function is entered; what it gives is that the write is atomic,
    so no fixture can reference a competition or a club a later failure rolls
    back and no reader sees the departed rows gone while the current ones are
    still missing. The three upserts insert in ascending provider identifier,
    which is what makes their row locks deterministic: presented in provider
    pagination order, two runs over different windows could offer the same
    league or club rows in a different order and deadlock, aborting a whole
    window with an ``OperationalError`` nothing catches.

    Parameters
    ----------
    window : ProviderWindow
        Competitions and fixtures the provider returned for the range, the
        fixtures in any order.
    start : date
        First calendar day, in UTC, the run read from the provider.
    end : date
        Last calendar day, in UTC, the run read from the provider, included in
        the range.
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
        provider_fixture.provider_id: provider_fixture for provider_fixture in window.fixtures
    }

    provider_teams: dict[int, ProviderTeam] = {}

    for provider_fixture in unique_fixtures.values():
        provider_teams[provider_fixture.home_team.provider_id] = provider_fixture.home_team
        provider_teams[provider_fixture.away_team.provider_id] = provider_fixture.away_team

    ordered_fixtures = [unique_fixtures[provider_id] for provider_id in sorted(unique_fixtures)]

    with transaction.atomic():
        leagues = _upsert_leagues(window.leagues)
        teams = _upsert_teams(provider_teams)

        Fixture.objects.bulk_create(
            [
                Fixture(
                    sportmonks_id=provider_fixture.provider_id,
                    season_sportmonks_id=provider_fixture.season_provider_id,
                    league=leagues[provider_fixture.league.provider_id],
                    home_team=teams[provider_fixture.home_team.provider_id],
                    away_team=teams[provider_fixture.away_team.provider_id],
                    kickoff_at=provider_fixture.kickoff_at,
                    status=provider_fixture.status,
                    home_goals=provider_fixture.home_goals,
                    away_goals=provider_fixture.away_goals,
                    synchronized_at=synchronized_at,
                )
                for provider_fixture in ordered_fixtures
            ],
            update_conflicts=True,
            unique_fields=["sportmonks_id"],
            update_fields=FIXTURE_UPDATE_FIELDS,
        )

        _delete_departed_fixtures(start, end, unique_fixtures.keys())

    return len(unique_fixtures)
