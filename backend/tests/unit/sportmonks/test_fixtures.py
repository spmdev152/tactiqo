import json
import logging
from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from django.test import override_settings

from apps.fixtures.domain.enums import FixtureStatus
from integrations.sportmonks.client import ProviderPayload, QueryParameters, SportmonksClient
from integrations.sportmonks.exceptions import SportmonksError
from integrations.sportmonks.fixtures import (
    CURRENT_SCORE,
    GOALS_LIMIT,
    IDENTIFIER_MAXIMUM,
    NAME_LIMIT,
    PAGE_SIZE,
    PROVIDER_STATES,
    PROVIDER_TIMEZONE,
    ProviderFixture,
    ProviderLeague,
    ProviderTeam,
    ProviderWindow,
    fetch_fixtures_between,
)

type Pages = list[list[ProviderPayload]]

type RecordedCalls = list[tuple[str, QueryParameters]]

FIXTURES_LOGGER = "integrations.sportmonks.fixtures"

LEAGUES_PATH = "/leagues"

STATES_RECORDING = Path(__file__).parent / "states.json"

HONOURED_PAGE_SIZES = range(1, 51)

PREMIER_LEAGUE_ID = 8

BUNDESLIGA_ID = 82

UNREQUESTED_LEAGUE_ID = 271

LIVERPOOL_ID = 1112

FOREST_ID = 63

FIXTURE_ID = 19427455

SEASON_ID = 25583

UNREADABLE_SEASON_ID = "later"

WINDOW_START = date(2026, 8, 29)

WINDOW_END = date(2026, 9, 5)

WINDOW_PATH = f"/fixtures/between/{WINDOW_START.isoformat()}/{WINDOW_END.isoformat()}"

KICKOFF_STAMP = "2026-08-29 11:30:00"

KICKOFF_INSTANT = datetime(2026, 8, 29, 11, 30, tzinfo=UTC)

SCHEDULED_STATE = "NS"

FINISHED_STATE = "FT"

UNMAPPED_STATE = "VAR_REVIEW"

STATES_BY_STATUS: dict[FixtureStatus, tuple[str, ...]] = {
    FixtureStatus.SCHEDULED: ("NS", "TBA", "PENDING", "AWAITING_UPDATES"),
    FixtureStatus.LIVE: (
        "INPLAY_1ST_HALF",
        "INPLAY_2ND_HALF",
        "INPLAY_ET",
        "INPLAY_ET_2ND_HALF",
        "INPLAY_PENALTIES",
        "HT",
        "BREAK",
        "EXTRA_TIME_BREAK",
        "PEN_BREAK",
        "INTERRUPTED",
        "SUSPENDED",
        "ABANDONED",
    ),
    FixtureStatus.FINISHED: ("FT", "AET", "FT_PEN", "WO", "AWARDED"),
    FixtureStatus.POSTPONED: ("POSTPONED", "DELAYED"),
    FixtureStatus.CANCELLED: ("CANCELLED", "DELETED"),
}

OBSERVED_STATES = [
    (state, status) for status, states in STATES_BY_STATUS.items() for state in states
]

PREMIER_LEAGUE = ProviderLeague(
    provider_id=PREMIER_LEAGUE_ID,
    name="Premier League",
    short_code="UK PL",
    logo_url="https://cdn.provider.test/leagues/8.png",
    country_name="England",
    country_flag_url="https://cdn.provider.test/countries/en.png",
)

BUNDESLIGA = ProviderLeague(
    provider_id=BUNDESLIGA_ID,
    name="Bundesliga",
    short_code="DE BL",
    logo_url="https://cdn.provider.test/leagues/82.png",
    country_name="Germany",
    country_flag_url="https://cdn.provider.test/countries/de.png",
)

UNREQUESTED_LEAGUE = replace(
    PREMIER_LEAGUE, provider_id=UNREQUESTED_LEAGUE_ID, name="Eredivisie", short_code="NL ED"
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


def recorded_states() -> list[str]:
    """
    Return the state codes a live read of the provider's states resource returned.

    Returns
    -------
    list of str
        Value of the ``state`` field of every recorded entry, which is the field
        the boundary keys its mapping on.
    """

    envelope = json.loads(STATES_RECORDING.read_text(encoding="utf-8"))

    return [entry["state"] for entry in envelope["data"]]


def league_payload(league: ProviderLeague = PREMIER_LEAGUE) -> ProviderPayload:
    """
    Build the leagues entry of a competition, with its country included.

    Parameters
    ----------
    league : ProviderLeague, optional
        Competition the entry describes, defaulting to the Premier League.

    Returns
    -------
    ProviderPayload
        Entry trimmed to the fields the boundary reads.
    """

    return {
        "id": league.provider_id,
        "name": league.name,
        "short_code": league.short_code,
        "image_path": league.logo_url,
        "country": {"name": league.country_name, "image_path": league.country_flag_url},
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


def score_entry(
    goals: int | None, location: str, description: str = CURRENT_SCORE
) -> ProviderPayload:
    """
    Build one entry of the scores include of a fixture.

    Parameters
    ----------
    goals : int or None
        Goals the entry reports, ``None`` as the provider writes an unfilled
        count.
    location : str
        Side the goals belong to, either ``"home"`` or ``"away"``.
    description : str, optional
        Period the entry describes, defaulting to the current score.

    Returns
    -------
    ProviderPayload
        Score entry trimmed to the fields the boundary reads.
    """

    return {
        "description": description,
        "score": {"goals": goals, "participant": location},
    }


def fixture_payload(
    *,
    provider_id: int = FIXTURE_ID,
    league_id: int = PREMIER_LEAGUE_ID,
    season_id: object = SEASON_ID,
    starting_at: str = KICKOFF_STAMP,
    participants: object = None,
    state: str = SCHEDULED_STATE,
    scores: object = None,
) -> ProviderPayload:
    """
    Build a fixtures entry, defaulting to a well-formed one.

    Parameters
    ----------
    provider_id : int, optional
        Provider fixture identifier.
    league_id : int, optional
        Competition the fixture is reported under.
    season_id : object, optional
        Season the fixture is reported under, as the provider states it at the
        top level of the entry rather than inside an include.
    starting_at : str, optional
        Kick-off stamp as the provider writes it.
    participants : object, optional
        Value of the participants include, or ``None`` to name Liverpool away
        and Nottingham Forest at home. That order is deliberate: it proves the
        location metadata rather than the position decides the sides.
    state : str, optional
        Provider state code the fixture is reported under, defaulting to the
        not-started one.
    scores : object, optional
        Value of the scores include, or ``None`` for the empty list a match that
        has produced no score is reported with.

    Returns
    -------
    ProviderPayload
        Entry trimmed to the fields the boundary reads.
    """

    if participants is None:
        participants = [participant(LIVERPOOL, "away"), participant(FOREST, "home")]

    if scores is None:
        scores = []

    return {
        "id": provider_id,
        "league_id": league_id,
        "season_id": season_id,
        "starting_at": starting_at,
        "starting_at_timestamp": 1787052600,
        "state": {"id": 1, "state": state},
        "participants": participants,
        "scores": scores,
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


def read_window() -> ProviderWindow:
    """
    Read the window and the competitions every test in this module uses.

    Returns
    -------
    ProviderWindow
        Competitions of the subscription and the normalized fixtures.
    """

    return fetch_fixtures_between(WINDOW_START, WINDOW_END, [PREMIER_LEAGUE_ID, BUNDESLIGA_ID])


def read_fixtures() -> list[ProviderFixture]:
    """
    Read only the fixtures of the window every test in this module uses.

    Returns
    -------
    list of ProviderFixture
        Normalized fixtures of the window, in provider order.
    """

    return read_window().fixtures


def test_a_well_formed_page_normalizes_into_a_provider_fixture(provider: StubbedProvider) -> None:
    """
    GIVEN a provider page carrying one well-formed fixture
    WHEN the window is read
    THEN the fixture carries a UTC kick-off, its season, the metadata sides, and no score
    """

    provider.serve(leagues=[[league_payload()]], fixtures=[[fixture_payload()]])

    assert read_fixtures() == [
        ProviderFixture(
            provider_id=FIXTURE_ID,
            season_provider_id=SEASON_ID,
            kickoff_at=KICKOFF_INSTANT,
            league=PREMIER_LEAGUE,
            home_team=FOREST,
            away_team=LIVERPOOL,
            status=FixtureStatus.SCHEDULED,
            home_goals=None,
            away_goals=None,
        )
    ]


def test_the_requested_page_size_stays_inside_what_the_provider_honours() -> None:
    """
    GIVEN a provider that honours one to fifty rows a page and falls back to twenty-five above it
    WHEN the page size this boundary asks for is checked
    THEN it is inside that range, so no request silently costs four times the pages it should
    """

    assert PAGE_SIZE in HONOURED_PAGE_SIZES


@pytest.mark.parametrize(("state", "expected_status"), OBSERVED_STATES)
def test_an_observed_state_maps_onto_the_platform_vocabulary(
    provider: StubbedProvider, state: str, expected_status: FixtureStatus
) -> None:
    """
    GIVEN a fixture reported under one of the states the provider was observed to return
    WHEN the window is read
    THEN the fixture carries the platform stage that state stands for
    """

    provider.serve(leagues=[[league_payload()]], fixtures=[[fixture_payload(state=state)]])

    assert read_fixtures()[0].status == expected_status


def test_the_boundary_maps_exactly_the_states_the_recorded_provider_read_returned() -> None:
    """
    GIVEN the twenty-five states recorded from a live read of the provider's states resource
    WHEN the mapping the boundary applies and the mapping the suite asserts are compared to them
    THEN both name every recorded state and invent none
    """

    recorded = sorted(recorded_states())

    assert sorted(PROVIDER_STATES) == recorded
    assert sorted(state for state, _ in OBSERVED_STATES) == recorded


def test_a_state_the_boundary_does_not_map_is_read_as_scheduled(
    provider: StubbedProvider,
) -> None:
    """
    GIVEN a fixture reported under a state the provider added after this mapping
    WHEN the window is read
    THEN the fixture is kept and read as scheduled rather than dropped
    """

    provider.serve(
        leagues=[[league_payload()]],
        fixtures=[[fixture_payload(state=UNMAPPED_STATE)]],
    )

    assert read_fixtures()[0].status == FixtureStatus.SCHEDULED


def test_a_played_fixture_carries_the_current_score(provider: StubbedProvider) -> None:
    """
    GIVEN a fixture the provider reports as finished with a current score
    WHEN the window is read
    THEN the goals are attributed to the sides the score names
    """

    played = fixture_payload(
        state=FINISHED_STATE,
        scores=[score_entry(2, "home"), score_entry(0, "away")],
    )

    provider.serve(leagues=[[league_payload()]], fixtures=[[played]])

    fixture = read_fixtures()[0]

    assert (fixture.status, fixture.home_goals, fixture.away_goals) == (
        FixtureStatus.FINISHED,
        2,
        0,
    )


def test_only_the_current_entries_state_the_score(provider: StubbedProvider) -> None:
    """
    GIVEN a fixture whose scores include the halves as well as the current score
    WHEN the window is read
    THEN the current entries alone are read and the halves do not overwrite them
    """

    played = fixture_payload(
        state=FINISHED_STATE,
        scores=[
            score_entry(1, "home", description="1ST_HALF"),
            score_entry(0, "away", description="1ST_HALF"),
            score_entry(3, "home"),
            score_entry(1, "away"),
            score_entry(2, "home", description="2ND_HALF"),
            score_entry(1, "away", description="2ND_HALF"),
        ],
    )

    provider.serve(leagues=[[league_payload()]], fixtures=[[played]])

    fixture = read_fixtures()[0]

    assert (fixture.home_goals, fixture.away_goals) == (3, 1)


def test_a_score_naming_one_side_alone_is_ignored_and_the_fixture_survives(
    provider: StubbedProvider,
) -> None:
    """
    GIVEN a fixture whose current score names the home side and no away side
    WHEN the window is read
    THEN the fixture is returned carrying neither half of that score
    """

    half_written = fixture_payload(state=FINISHED_STATE, scores=[score_entry(2, "home")])

    provider.serve(leagues=[[league_payload()]], fixtures=[[half_written]])

    fixture = read_fixtures()[0]

    assert (fixture.provider_id, fixture.home_goals, fixture.away_goals) == (
        FIXTURE_ID,
        None,
        None,
    )


def test_a_score_the_provider_has_not_filled_in_leaves_the_fixture_without_one(
    provider: StubbedProvider,
) -> None:
    """
    GIVEN a fixture whose current entries carry no goal count on either side
    WHEN the window is read
    THEN the fixture is returned with no score rather than a guessed nil-nil
    """

    unfilled = fixture_payload(scores=[score_entry(None, "home"), score_entry(None, "away")])

    provider.serve(leagues=[[league_payload()]], fixtures=[[unfilled]])

    fixture = read_fixtures()[0]

    assert (fixture.home_goals, fixture.away_goals) == (None, None)


def test_a_current_score_of_an_unreadable_shape_is_reported_rather_than_lost(
    provider: StubbedProvider, caplog: pytest.LogCaptureFixture
) -> None:
    """
    GIVEN a fixture whose current entry carries no score object at all
    WHEN the window is read
    THEN the discarded score is reported at warning level and the fixture still survives
    """

    caplog.set_level(logging.WARNING, logger=FIXTURES_LOGGER)

    malformed = fixture_payload(
        state=FINISHED_STATE, scores=[{"description": CURRENT_SCORE, "score": None}]
    )

    provider.serve(leagues=[[league_payload()]], fixtures=[[malformed]])

    fixture = read_fixtures()[0]

    assert (fixture.provider_id, fixture.home_goals) == (FIXTURE_ID, None)
    assert "is not a score object" in caplog.text


def test_a_goal_count_beyond_its_column_leaves_the_fixture_without_a_score(
    provider: StubbedProvider,
) -> None:
    """
    GIVEN a fixture whose current score reports more goals than the column that stores it holds
    WHEN the window is read
    THEN the fixture is returned without a score, so the whole window is still writable
    """

    absurd = fixture_payload(
        state=FINISHED_STATE,
        scores=[score_entry(GOALS_LIMIT + 1, "home"), score_entry(0, "away")],
    )

    provider.serve(leagues=[[league_payload()]], fixtures=[[absurd]])

    fixture = read_fixtures()[0]

    assert (fixture.provider_id, fixture.home_goals, fixture.away_goals) == (
        FIXTURE_ID,
        None,
        None,
    )


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

    assert [fixture.provider_id for fixture in read_fixtures()] == [FIXTURE_ID]


def test_a_fixture_naming_a_single_participant_is_skipped(provider: StubbedProvider) -> None:
    """
    GIVEN a page whose fixture names only the home side
    WHEN the window is read
    THEN the fixture is dropped, because no away side can be inferred
    """

    incomplete = fixture_payload(participants=[participant(FOREST, "home")])

    provider.serve(leagues=[[league_payload()]], fixtures=[[incomplete]])

    assert read_fixtures() == []


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

    assert read_fixtures() == []


def test_an_identifier_beyond_its_column_range_skips_only_that_fixture(
    provider: StubbedProvider,
) -> None:
    """
    GIVEN a page whose first fixture carries an identifier beyond the range of its column
    WHEN the window is read
    THEN that fixture alone is dropped, so the whole window is still writable
    """

    provider.serve(
        leagues=[[league_payload()]],
        fixtures=[[fixture_payload(provider_id=IDENTIFIER_MAXIMUM + 1), fixture_payload()]],
    )

    assert [fixture.provider_id for fixture in read_fixtures()] == [FIXTURE_ID]


def test_a_club_name_longer_than_its_column_skips_only_that_fixture(
    provider: StubbedProvider, caplog: pytest.LogCaptureFixture
) -> None:
    """
    GIVEN a page whose first fixture names a club whose name overruns the column storing it
    WHEN the window is read
    THEN that fixture alone is dropped with a warning, so the whole window is still writable
    """

    caplog.set_level(logging.WARNING, logger=FIXTURES_LOGGER)

    oversized = participant(LIVERPOOL, "away")

    oversized["name"] = "x" * (NAME_LIMIT + 1)

    broken = fixture_payload(provider_id=1, participants=[oversized, participant(FOREST, "home")])

    provider.serve(leagues=[[league_payload()]], fixtures=[[broken, fixture_payload()]])

    assert [fixture.provider_id for fixture in read_fixtures()] == [FIXTURE_ID]
    assert "longer than the column" in caplog.text


def test_a_competition_name_longer_than_its_column_skips_only_that_competition(
    provider: StubbedProvider, caplog: pytest.LogCaptureFixture
) -> None:
    """
    GIVEN a leagues page whose first competition has a name overrunning the column storing it
    WHEN the window is read
    THEN that competition and its fixtures are dropped with a warning and the others survive
    """

    caplog.set_level(logging.WARNING, logger=FIXTURES_LOGGER)

    oversized = league_payload()

    oversized["name"] = "x" * (NAME_LIMIT + 1)

    provider.serve(
        leagues=[[oversized, league_payload(BUNDESLIGA)]],
        fixtures=[
            [
                fixture_payload(provider_id=1),
                fixture_payload(provider_id=2, league_id=BUNDESLIGA_ID),
            ]
        ],
    )

    window = read_window()

    assert sorted(window.leagues) == [BUNDESLIGA_ID]
    assert [fixture.provider_id for fixture in window.fixtures] == [2]
    assert "longer than the column" in caplog.text


def test_an_unreadable_kickoff_is_skipped(
    provider: StubbedProvider, caplog: pytest.LogCaptureFixture
) -> None:
    """
    GIVEN a page carrying a fixture whose kick-off is present but not a provider stamp
    WHEN the window is read
    THEN the fixture is dropped with a warning rather than scheduled at a guessed time
    """

    caplog.set_level(logging.WARNING, logger=FIXTURES_LOGGER)

    provider.serve(leagues=[[league_payload()]], fixtures=[[fixture_payload(starting_at="soon")]])

    assert read_fixtures() == []
    assert "not a readable kick-off" in caplog.text


def test_a_fixture_the_provider_has_not_scheduled_is_reported_as_routine(
    provider: StubbedProvider, caplog: pytest.LogCaptureFixture
) -> None:
    """
    GIVEN a fixture the provider announced before fixing its date, so it carries no kick-off
    WHEN the window is read
    THEN it is dropped at debug level, because an unscheduled match is documented rather than broken
    """

    caplog.set_level(logging.DEBUG, logger=FIXTURES_LOGGER)

    announced = fixture_payload()

    del announced["starting_at"]

    provider.serve(leagues=[[league_payload()]], fixtures=[[announced]])

    assert read_fixtures() == []
    assert "not scheduled yet" in caplog.text


def test_the_season_a_fixture_is_played_in_reaches_the_normalized_fixture(
    provider: StubbedProvider,
) -> None:
    """
    GIVEN a page carrying a fixture the provider reports under a season of its own
    WHEN the window is read
    THEN that season is the one the normalized fixture carries
    """

    provider.serve(
        leagues=[[league_payload()]],
        fixtures=[[fixture_payload(season_id=SEASON_ID + 1)]],
    )

    assert [fixture.season_provider_id for fixture in read_fixtures()] == [SEASON_ID + 1]


def test_a_fixture_stating_no_season_is_kept_without_one(
    provider: StubbedProvider, caplog: pytest.LogCaptureFixture
) -> None:
    """
    GIVEN a page carrying a fixture the provider publishes without a season at all
    WHEN the window is read
    THEN the fixture is returned seasonless at debug level, because only its form read suffers
    """

    caplog.set_level(logging.DEBUG, logger=FIXTURES_LOGGER)

    seasonless = fixture_payload()

    del seasonless["season_id"]

    provider.serve(leagues=[[league_payload()]], fixtures=[[seasonless]])

    assert [fixture.season_provider_id for fixture in read_fixtures()] == [None]
    assert "states no season" in caplog.text


def test_an_unreadable_season_is_reported_and_the_fixture_survives(
    provider: StubbedProvider, caplog: pytest.LogCaptureFixture
) -> None:
    """
    GIVEN a page carrying a fixture whose season is present but denotes no identifier
    WHEN the window is read
    THEN the fixture is returned seasonless with a warning rather than dropped
    """

    caplog.set_level(logging.WARNING, logger=FIXTURES_LOGGER)

    provider.serve(
        leagues=[[league_payload()]],
        fixtures=[[fixture_payload(season_id=UNREADABLE_SEASON_ID)]],
    )

    assert [(fixture.provider_id, fixture.season_provider_id) for fixture in read_fixtures()] == [
        (FIXTURE_ID, None)
    ]
    assert "not a readable season identifier" in caplog.text


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

    assert [fixture.provider_id for fixture in read_fixtures()] == [1, 2]


def test_a_competition_without_a_fixture_in_the_window_is_still_returned(
    provider: StubbedProvider,
) -> None:
    """
    GIVEN a subscription whose second competition schedules nothing inside the window
    WHEN the window is read
    THEN both competitions are returned, so neither vanishes from the product during its break
    """

    provider.serve(
        leagues=[[league_payload(), league_payload(BUNDESLIGA)]],
        fixtures=[[fixture_payload()]],
    )

    window = read_window()

    assert window.leagues == {PREMIER_LEAGUE_ID: PREMIER_LEAGUE, BUNDESLIGA_ID: BUNDESLIGA}
    assert [fixture.provider_id for fixture in window.fixtures] == [FIXTURE_ID]


def test_a_competition_outside_the_requested_set_is_narrowed_away_here(
    provider: StubbedProvider,
) -> None:
    """
    GIVEN a leagues resource answering with a competition the window did not request
    WHEN the window is read
    THEN it is dropped by this boundary rather than by a filter the endpoint does not document
    """

    provider.serve(
        leagues=[[league_payload(), league_payload(UNREQUESTED_LEAGUE)]],
        fixtures=[[fixture_payload()]],
    )

    assert sorted(read_window().leagues) == [PREMIER_LEAGUE_ID]


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

    fixture = read_fixtures()[0]

    assert fixture.league.short_code == ""
    assert fixture.league.country_name == ""
    assert fixture.league.country_flag_url == ""
    assert fixture.away_team.short_code == ""
    assert fixture.away_team.crest_url == ""


def test_the_window_is_stated_to_the_provider_and_the_competitions_are_not_filtered(
    provider: StubbedProvider,
) -> None:
    """
    GIVEN a window over two competitions
    WHEN it is read
    THEN the competitions are resolved first without a filter and both requests state UTC
    """

    provider.serve(leagues=[[league_payload()]], fixtures=[[fixture_payload()]])

    read_window()

    assert provider.calls == [
        (
            LEAGUES_PATH,
            {
                "include": "country",
                "per_page": PAGE_SIZE,
                "timezone": PROVIDER_TIMEZONE,
            },
        ),
        (
            WINDOW_PATH,
            {
                "filters": f"fixtureLeagues:{PREMIER_LEAGUE_ID},{BUNDESLIGA_ID}",
                "include": "participants;state;scores",
                "per_page": PAGE_SIZE,
                "timezone": PROVIDER_TIMEZONE,
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
