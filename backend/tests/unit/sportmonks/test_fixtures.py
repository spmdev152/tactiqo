from collections.abc import Iterator
from datetime import UTC, date, datetime

import pytest
from django.test import override_settings

from integrations.sportmonks.client import ProviderPayload, QueryParameters, SportmonksClient
from integrations.sportmonks.exceptions import SportmonksError
from integrations.sportmonks.fixtures import (
    PAGE_SIZE,
    ProviderFixture,
    ProviderLeague,
    ProviderTeam,
    fetch_fixtures_between,
)

type Pages = list[list[ProviderPayload]]

type RecordedCalls = list[tuple[str, QueryParameters]]

LEAGUES_PATH = "/leagues"

PREMIER_LEAGUE_ID = 8

BUNDESLIGA_ID = 82

UNREQUESTED_LEAGUE_ID = 271

LIVERPOOL_ID = 1112

FOREST_ID = 63

FIXTURE_ID = 19427455

WINDOW_START = date(2026, 8, 29)

WINDOW_END = date(2026, 9, 5)

WINDOW_PATH = f"/fixtures/between/{WINDOW_START.isoformat()}/{WINDOW_END.isoformat()}"

KICKOFF_STAMP = "2026-08-29 11:30:00"

KICKOFF_INSTANT = datetime(2026, 8, 29, 11, 30, tzinfo=UTC)

PREMIER_LEAGUE = ProviderLeague(
    provider_id=PREMIER_LEAGUE_ID,
    name="Premier League",
    short_code="UK PL",
    logo_url="https://cdn.provider.test/leagues/8.png",
    country_name="England",
    country_flag_url="https://cdn.provider.test/countries/en.png",
)

LIVERPOOL = ProviderTeam(
    provider_id=LIVERPOOL_ID,
    name="Liverpool",
    short_code="LIV",
    crest_url=f"https://cdn.provider.test/teams/{LIVERPOOL_ID}.png",
)

FOREST = ProviderTeam(
    provider_id=FOREST_ID,
    name="Nottingham Forest",
    short_code="NFO",
    crest_url=f"https://cdn.provider.test/teams/{FOREST_ID}.png",
)


def league_payload() -> ProviderPayload:
    """
    Build the leagues entry of the Premier League, with its country included.

    Returns
    -------
    ProviderPayload
        Entry trimmed to the fields the boundary reads.
    """

    return {
        "id": PREMIER_LEAGUE_ID,
        "name": PREMIER_LEAGUE.name,
        "short_code": PREMIER_LEAGUE.short_code,
        "image_path": PREMIER_LEAGUE.logo_url,
        "country": {
            "id": 462,
            "name": PREMIER_LEAGUE.country_name,
            "image_path": PREMIER_LEAGUE.country_flag_url,
        },
    }


def participant(team: ProviderTeam, location: str) -> ProviderPayload:
    """
    Build one entry of the participants include of a fixture.

    Parameters
    ----------
    team : ProviderTeam
        Team the entry describes.
    location : str
        Side the team plays at, either ``"home"`` or ``"away"``.

    Returns
    -------
    ProviderPayload
        Participant entry trimmed to the fields the boundary reads.
    """

    return {
        "id": team.provider_id,
        "name": team.name,
        "short_code": team.short_code,
        "image_path": team.crest_url,
        "meta": {"location": location},
    }


def fixture_payload(
    *,
    provider_id: int = FIXTURE_ID,
    league_id: int = PREMIER_LEAGUE_ID,
    starting_at: str = KICKOFF_STAMP,
    participants: object = None,
) -> ProviderPayload:
    """
    Build a fixtures entry, defaulting to a well-formed one.

    Parameters
    ----------
    provider_id : int, optional
        Provider fixture identifier.
    league_id : int, optional
        Competition the fixture is reported under.
    starting_at : str, optional
        Kick-off stamp as the provider writes it.
    participants : object, optional
        Value of the participants include, or ``None`` to name Liverpool away
        and Nottingham Forest at home. That order is deliberate: it proves the
        location metadata rather than the position decides the sides.

    Returns
    -------
    ProviderPayload
        Entry trimmed to the fields the boundary reads.
    """

    if participants is None:
        participants = [participant(LIVERPOOL, "away"), participant(FOREST, "home")]

    return {
        "id": provider_id,
        "league_id": league_id,
        "starting_at": starting_at,
        "starting_at_timestamp": 1787052600,
        "state": {"id": 1, "state": "NS"},
        "participants": participants,
    }


class StubbedProvider:
    """
    Stand-in for the provider that answers each resource with recorded pages.

    Attributes
    ----------
    calls : list of tuple of str and QueryParameters
        Path and query parameters of every page read, in order.

    Methods
    -------
    serve(leagues, fixtures) -> None
        State the pages each resource answers with.
    get_pages(path, params) -> Iterator[list[ProviderPayload]]
        Answer a page read, standing in for the real client method.
    """

    def __init__(self) -> None:
        self.calls: RecordedCalls = []
        self._pages: dict[str, Pages] = {}

    def serve(self, *, leagues: Pages, fixtures: Pages) -> None:
        """
        State the pages each resource answers with.

        Parameters
        ----------
        leagues : list of list of ProviderPayload
            Pages the competitions resource answers with.
        fixtures : list of list of ProviderPayload
            Pages the fixtures resource of the window answers with.
        """

        self._pages = {LEAGUES_PATH: leagues, WINDOW_PATH: fixtures}

    def get_pages(self, path: str, params: QueryParameters) -> Iterator[list[ProviderPayload]]:
        """
        Answer a page read, standing in for the real client method.

        Parameters
        ----------
        path : str
            Resource path the boundary asked for.
        params : dict of str to str or int
            Query parameters the boundary stated.

        Returns
        -------
        Iterator[list[ProviderPayload]]
            Pages recorded for the path, or none when it was not served.
        """

        self.calls.append((path, params))

        return iter(self._pages.get(path, []))


@pytest.fixture
def provider(monkeypatch: pytest.MonkeyPatch, api_token: str) -> Iterator[StubbedProvider]:
    """
    Replace the provider read with recorded pages for one test.

    Parameters
    ----------
    monkeypatch : pytest.MonkeyPatch
        Patcher replacing the page reader of the client class.
    api_token : str
        Generated token, configured so the client accepts being built.

    Yields
    ------
    StubbedProvider
        Stub to state pages on and to read the recorded calls from.
    """

    stub = StubbedProvider()

    def get_pages(
        _self: SportmonksClient, path: str, params: QueryParameters
    ) -> Iterator[list[ProviderPayload]]:
        return stub.get_pages(path, params)

    monkeypatch.setattr(SportmonksClient, "get_pages", get_pages)

    with override_settings(SPORTMONKS_API_TOKEN=api_token):
        yield stub


def read_window() -> list[ProviderFixture]:
    """
    Read the window and the competitions every test in this module uses.

    Returns
    -------
    list of ProviderFixture
        Normalized fixtures of the window.
    """

    return fetch_fixtures_between(WINDOW_START, WINDOW_END, [PREMIER_LEAGUE_ID, BUNDESLIGA_ID])


def test_a_well_formed_page_normalizes_into_a_provider_fixture(provider: StubbedProvider) -> None:
    """
    GIVEN a provider page carrying one well-formed fixture
    WHEN the window is read
    THEN the fixture carries a UTC kick-off and the sides the metadata names
    """

    provider.serve(leagues=[[league_payload()]], fixtures=[[fixture_payload()]])

    assert read_window() == [
        ProviderFixture(
            provider_id=FIXTURE_ID,
            kickoff_at=KICKOFF_INSTANT,
            league=PREMIER_LEAGUE,
            home_team=FOREST,
            away_team=LIVERPOOL,
        )
    ]


def test_a_fixture_with_broken_participants_is_skipped_and_the_rest_survive(
    provider: StubbedProvider,
) -> None:
    """
    GIVEN a page whose first fixture names two home sides and no away side
    WHEN the window is read
    THEN that fixture alone is dropped rather than the whole window
    """

    broken = fixture_payload(
        provider_id=1, participants=[participant(LIVERPOOL, "home"), participant(FOREST, "home")]
    )

    provider.serve(leagues=[[league_payload()]], fixtures=[[broken, fixture_payload()]])

    assert [fixture.provider_id for fixture in read_window()] == [FIXTURE_ID]


def test_a_fixture_naming_a_single_participant_is_skipped(provider: StubbedProvider) -> None:
    """
    GIVEN a page whose fixture names only the home side
    WHEN the window is read
    THEN the fixture is dropped, because no away side can be inferred
    """

    incomplete = fixture_payload(participants=[participant(FOREST, "home")])

    provider.serve(leagues=[[league_payload()]], fixtures=[[incomplete]])

    assert read_window() == []


def test_a_fixture_of_an_unrequested_competition_is_skipped(provider: StubbedProvider) -> None:
    """
    GIVEN a page carrying a fixture of a competition the window did not request
    WHEN the window is read
    THEN the fixture is dropped rather than referring to an unknown competition
    """

    provider.serve(
        leagues=[[league_payload()]],
        fixtures=[[fixture_payload(league_id=UNREQUESTED_LEAGUE_ID)]],
    )

    assert read_window() == []


def test_an_unreadable_kickoff_is_skipped(provider: StubbedProvider) -> None:
    """
    GIVEN a page carrying a fixture whose kick-off is not a provider stamp
    WHEN the window is read
    THEN the fixture is dropped rather than being scheduled at a guessed time
    """

    provider.serve(leagues=[[league_payload()]], fixtures=[[fixture_payload(starting_at="soon")]])

    assert read_window() == []


def test_every_page_of_the_window_contributes_its_fixtures(provider: StubbedProvider) -> None:
    """
    GIVEN a fixtures resource that answers with more than one page
    WHEN the window is read
    THEN the fixtures of every page are returned in provider order
    """

    provider.serve(
        leagues=[[league_payload()]],
        fixtures=[[fixture_payload(provider_id=1)], [fixture_payload(provider_id=2)]],
    )

    assert [fixture.provider_id for fixture in read_window()] == [1, 2]


def test_an_omitted_optional_string_becomes_empty_rather_than_absent(
    provider: StubbedProvider,
) -> None:
    """
    GIVEN a provider that omits an abbreviation, a crest and a whole country
    WHEN the window is read
    THEN every optional string is empty rather than an absent value
    """

    league = league_payload()

    del league["short_code"]
    del league["country"]

    away = participant(LIVERPOOL, "away")

    del away["short_code"]
    del away["image_path"]

    provider.serve(
        leagues=[[league]],
        fixtures=[[fixture_payload(participants=[away, participant(FOREST, "home")])]],
    )

    fixture = read_window()[0]

    assert fixture.league.short_code == ""
    assert fixture.league.country_name == ""
    assert fixture.league.country_flag_url == ""
    assert fixture.away_team.short_code == ""
    assert fixture.away_team.crest_url == ""


def test_the_window_and_the_competitions_are_stated_to_the_provider(
    provider: StubbedProvider,
) -> None:
    """
    GIVEN a window over two competitions
    WHEN it is read
    THEN the competitions are resolved first and both requests state the filter
    """

    provider.serve(leagues=[[league_payload()]], fixtures=[[fixture_payload()]])

    read_window()

    assert provider.calls == [
        (
            LEAGUES_PATH,
            {
                "filters": f"leagueIds:{PREMIER_LEAGUE_ID},{BUNDESLIGA_ID}",
                "include": "country",
                "per_page": PAGE_SIZE,
            },
        ),
        (
            WINDOW_PATH,
            {
                "filters": f"fixtureLeagues:{PREMIER_LEAGUE_ID},{BUNDESLIGA_ID}",
                "include": "participants;league;state",
                "per_page": PAGE_SIZE,
            },
        ),
    ]


def test_requesting_no_competition_is_refused_before_any_request(
    provider: StubbedProvider,
) -> None:
    """
    GIVEN a configuration that leaves the requested competitions empty
    WHEN a window is read
    THEN the boundary error is raised and no provider request is made
    """

    with pytest.raises(SportmonksError, match="No Sportmonks league"):
        fetch_fixtures_between(WINDOW_START, WINDOW_END, [])

    assert provider.calls == []
