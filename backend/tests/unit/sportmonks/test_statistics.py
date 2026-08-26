import json
import logging
from collections.abc import Iterator, Mapping
from datetime import date
from pathlib import Path

import pytest
from django.db.models import Model, PositiveSmallIntegerField
from django.test import override_settings

from apps.statistics.domain.enums import MatchSide
from apps.statistics.models import MatchTeamStatistic
from integrations.sportmonks.client import ProviderPayload, QueryParameters, SportmonksClient
from integrations.sportmonks.exceptions import SportmonksError
from integrations.sportmonks.fixtures import PAGE_SIZE, PROVIDER_TIMEZONE
from integrations.sportmonks.statistics import (
    COMPLETION_PAIRS,
    COUNT_CEILING,
    OPTIONAL_STATISTICS,
    POSSESSION_CEILING,
    POSSESSION_TYPE,
    PROVIDER_STATISTICS,
    UNMEASURED_COLUMNS,
    UNMEASURED_STATISTICS,
    ProviderTeamStatistics,
    fetch_match_statistics,
)

COLUMN_TYPES: dict[str, int] = {column: type_id for type_id, column in PROVIDER_STATISTICS.items()}

type Pages = list[list[ProviderPayload]]

type RecordedCalls = list[tuple[str, QueryParameters]]

STATISTICS_LOGGER = "integrations.sportmonks.statistics"

TYPES_RECORDING = Path(__file__).parent / "statistic_types.json"

PREMIER_LEAGUE_ID = 8

BUNDESLIGA_ID = 82

SEASON_ID = 25583

FIXTURE_ID = 19732724

OTHER_FIXTURE_ID = 19732725

HOME_TEAM_ID = 2975

AWAY_TEAM_ID = 8

THIRD_TEAM_ID = 14

FINISHED_STATE_ID = 5

WINDOW_START = date(2026, 8, 20)

WINDOW_END = date(2026, 8, 25)

WINDOW_PATH = f"/fixtures/between/{WINDOW_START.isoformat()}/{WINDOW_END.isoformat()}"

KICKOFF_STAMP = "2026-08-22 14:00:00"

STATISTIC_ROW_ID = 965498851

# Codes the recorded vocabulary publishes each mapped type under. A provider identifier is opaque,
# so this is the only statement in the suite that ties one to the figure it denotes.
MAPPED_CODES: dict[int, str] = {
    34: "corners",
    42: "shots-total",
    45: "ball-possession",
    49: "shots-insidebox",
    51: "offsides",
    56: "fouls",
    57: "saves",
    58: "shots-blocked",
    78: "tackles",
    80: "passes",
    81: "successful-passes",
    83: "redcards",
    84: "yellowcards",
    86: "shots-on-target",
    98: "total-crosses",
    99: "accurate-crosses",
    100: "interceptions",
    106: "duels-won",
    108: "dribble-attempts",
    109: "successful-dribbles",
    117: "key-passes",
    580: "big-chances-created",
}

# Figures of one recorded fixture, keyed by the provider type identifier the row states them
# under. The expectations below are keyed by column name instead, and neither is derived from the
# other, so the mapping itself is what the comparison exercises.
HOME_FIGURES: dict[int, int] = {
    42: 14,
    86: 5,
    49: 9,
    58: 3,
    580: 2,
    117: 8,
    34: 7,
    45: 56,
    80: 512,
    81: 441,
    98: 19,
    99: 6,
    108: 12,
    109: 7,
    57: 4,
    78: 17,
    100: 9,
    106: 48,
    56: 11,
    84: 2,
    83: 1,
    51: 3,
}

AWAY_FIGURES: dict[int, int] = {
    42: 10,
    86: 3,
    49: 6,
    58: 1,
    580: 1,
    117: 5,
    34: 4,
    45: 44,
    80: 398,
    81: 321,
    98: 13,
    99: 2,
    108: 15,
    109: 9,
    57: 6,
    78: 21,
    100: 13,
    106: 52,
    56: 15,
    84: 3,
    83: 0,
    51: 1,
}

HOME_VALUES: dict[str, int | None] = {
    "shots_total": 14,
    "shots_on_target": 5,
    "shots_inside_box": 9,
    "shots_blocked": 3,
    "big_chances_created": 2,
    "key_passes": 8,
    "corners": 7,
    "possession": 56,
    "passes": 512,
    "successful_passes": 441,
    "crosses": 19,
    "accurate_crosses": 6,
    "dribble_attempts": 12,
    "successful_dribbles": 7,
    "saves": 4,
    "tackles": 17,
    "interceptions": 9,
    "duels_won": 48,
    "fouls": 11,
    "yellow_cards": 2,
    "red_cards": 1,
    "offsides": 3,
}

AWAY_VALUES: dict[str, int | None] = {
    "shots_total": 10,
    "shots_on_target": 3,
    "shots_inside_box": 6,
    "shots_blocked": 1,
    "big_chances_created": 1,
    "key_passes": 5,
    "corners": 4,
    "possession": 44,
    "passes": 398,
    "successful_passes": 321,
    "crosses": 13,
    "accurate_crosses": 2,
    "dribble_attempts": 15,
    "successful_dribbles": 9,
    "saves": 6,
    "tackles": 21,
    "interceptions": 13,
    "duels_won": 52,
    "fouls": 15,
    "yellow_cards": 3,
    "red_cards": 0,
    "offsides": 1,
}

# Attacks, dangerous attacks and throw-ins: three of the twenty-four types the provider publishes
# on every side and this boundary persists none of.
UNPERSISTED_TYPE = 43

SHOTS_TOTAL_TYPE = 42

REFUSED_FIGURES: list[object] = [
    -1,
    COUNT_CEILING + 1,
    12.5,
    "12.5",
    True,
    None,
    "many",
    [14],
]

# One figure of the refused set, used where the assertion is about which tier the type belongs to
# rather than about which shapes the boundary refuses.
REFUSED_COUNT = -1

# Tier a missing type falls into when it is neither read as nought nor left unset: the ten the
# provider was never observed to withhold, so an absence of one is a broken record.
REQUIRED_STATISTICS = frozenset(PROVIDER_STATISTICS) - OPTIONAL_STATISTICS - UNMEASURED_STATISTICS


class StubbedProvider:
    """
    Stand-in for the provider that answers each resource with recorded pages.

    Attributes
    ----------
    calls : list of tuple of str and QueryParameters
        Path and query parameters of every page read, in order.

    Methods
    -------
    serve(path, pages) -> None
        State the pages one resource answers with.
    get_pages(path, params) -> Iterator[list[ProviderPayload]]
        Answer a page read, standing in for the real client method.
    """

    def __init__(self) -> None:
        self.calls: RecordedCalls = []
        self._pages: dict[str, Pages] = {}

    def serve(self, path: str, pages: Pages) -> None:
        """
        State the pages one resource answers with.

        Parameters
        ----------
        path : str
            Resource path the pages answer.
        pages : list of list of ProviderPayload
            Pages the resource answers with, in order.
        """

        self._pages[path] = pages

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
        iterator of list of ProviderPayload
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


def reported(caplog: pytest.LogCaptureFixture) -> list[str]:
    """
    Return what the boundary itself reported as broken, ignoring every other logger.

    Parameters
    ----------
    caplog : pytest.LogCaptureFixture
        Capture of the records emitted during the read.

    Returns
    -------
    list of str
        Message of every record the boundary logged at warning or above.
    """

    return [
        record.getMessage()
        for record in caplog.records
        if record.name == STATISTICS_LOGGER and record.levelno >= logging.WARNING
    ]


def recorded_types() -> dict[int, str]:
    """
    Return the statistic types a live read of the provider's types resource returned.

    Returns
    -------
    dict of int to str
        Code of every recorded entry, keyed by the numeric identifier the
        boundary maps its figures on.
    """

    envelope = json.loads(TYPES_RECORDING.read_text(encoding="utf-8"))

    return {entry["id"]: entry["code"] for entry in envelope["data"]}


def count_columns(model: type[Model]) -> list[str]:
    """
    Return every whole-count column a model stores a provider figure in.

    Parameters
    ----------
    model : type of Model
        Model the adapter feeds.

    Returns
    -------
    list of str
        Name of every unsigned small-integer field of the model, which is the
        field class every figure this boundary normalizes is stored in.
    """

    return [
        field.name
        for field in model._meta.get_fields()
        if isinstance(field, PositiveSmallIntegerField)
    ]


def nullable_columns(model: type[Model]) -> set[str]:
    """
    Return every whole-count column a model accepts a null in.

    Parameters
    ----------
    model : type of Model
        Model the adapter feeds.

    Returns
    -------
    set of str
        Name of every unsigned small-integer field of the model the schema lets
        a row leave unset.
    """

    return {
        field.name
        for field in model._meta.get_fields()
        if isinstance(field, PositiveSmallIntegerField) and field.null
    }


def statistic_rows(
    figures: Mapping[int, object],
    participant_id: int,
    location: object,
    fixture_id: int = FIXTURE_ID,
) -> list[ProviderPayload]:
    """
    Build the rows one participant of a fixture is tagged with.

    Parameters
    ----------
    figures : mapping of int to object
        Figure each provider type states, keyed by type identifier.
    participant_id : int
        Team the rows belong to.
    location : object
        Side the provider tags the rows with.
    fixture_id : int, optional
        Fixture the rows belong to.

    Returns
    -------
    list of ProviderPayload
        One row a figure, in the order the figures were stated.
    """

    return [
        {
            "id": STATISTIC_ROW_ID + offset,
            "fixture_id": fixture_id,
            "type_id": type_id,
            "participant_id": participant_id,
            "data": {"value": value},
            "location": location,
        }
        for offset, (type_id, value) in enumerate(figures.items())
    ]


def both_sides(fixture_id: int = FIXTURE_ID) -> list[ProviderPayload]:
    """
    Build the flat statistics array of a settled fixture, both sides complete.

    Parameters
    ----------
    fixture_id : int, optional
        Fixture the rows belong to.

    Returns
    -------
    list of ProviderPayload
        Rows of the home side followed by those of the away side.
    """

    return statistic_rows(HOME_FIGURES, HOME_TEAM_ID, "home", fixture_id) + statistic_rows(
        AWAY_FIGURES, AWAY_TEAM_ID, "away", fixture_id
    )


def fixture_payload(provider_id: int = FIXTURE_ID, statistics: object = None) -> ProviderPayload:
    """
    Build the fixtures entry of a settled match, with its statistics included.

    Parameters
    ----------
    provider_id : int, optional
        Identifier the entry states.
    statistics : object, optional
        Value of the statistics include, defaulting to both complete sides.

    Returns
    -------
    ProviderPayload
        Entry shaped as the recorded provider envelope shapes it.
    """

    return {
        "id": provider_id,
        "league_id": PREMIER_LEAGUE_ID,
        "season_id": SEASON_ID,
        "state_id": FINISHED_STATE_ID,
        "starting_at": KICKOFF_STAMP,
        "result_info": "Liverpool won after full time.",
        "statistics": both_sides(provider_id) if statistics is None else statistics,
    }


def serve_statistics(provider: StubbedProvider, statistics: object) -> None:
    """
    Serve a window of one fixture carrying the given statistics include.

    Parameters
    ----------
    provider : StubbedProvider
        Stub the page is recorded on.
    statistics : object
        Value of the statistics include of the fixture.
    """

    provider.serve(WINDOW_PATH, [[fixture_payload(statistics=statistics)]])


def read_teams() -> list[ProviderTeamStatistics]:
    """
    Read the records of the first fixture of the window under test.

    Returns
    -------
    list of ProviderTeamStatistics
        Records the fixture resolved, or none when the fixture was dropped.
    """

    fixtures = fetch_match_statistics(WINDOW_START, WINDOW_END, [PREMIER_LEAGUE_ID]).fixtures

    return fixtures[0].teams if fixtures else []


def read_values(side: MatchSide) -> dict[str, int | None]:
    """
    Read the figures one side of the fixture under test was normalized with.

    Parameters
    ----------
    side : MatchSide
        Side to read.

    Returns
    -------
    dict of str to (int or None)
        Figures of that side, unset where the provider did not measure one, or
        none at all when the fixture was dropped.
    """

    return next((team.values for team in read_teams() if team.side == side), {})


def without(figures: Mapping[int, object], type_id: int) -> dict[int, object]:
    """
    Return the figures with one provider type left out, as the provider omits one.

    Parameters
    ----------
    figures : mapping of int to object
        Figures of one side.
    type_id : int
        Provider type to omit.

    Returns
    -------
    dict of int to object
        Figures without that type.
    """

    return {mapped: value for mapped, value in figures.items() if mapped != type_id}


def replacing(figures: Mapping[int, object], type_id: int, value: object) -> dict[int, object]:
    """
    Return the figures with one provider type restated as the given value.

    Parameters
    ----------
    figures : mapping of int to object
        Figures of one side.
    type_id : int
        Provider type to restate.
    value : object
        Value the type states instead.

    Returns
    -------
    dict of int to object
        Figures carrying that value.
    """

    return {**figures, type_id: value}


def test_the_window_states_the_league_filter_and_the_statistics_include(
    provider: StubbedProvider,
) -> None:
    """
    GIVEN a statistics window over two competitions
    WHEN it is read
    THEN one paginated read states the league filter, the statistics include, the page size and UTC
    """

    serve_statistics(provider, both_sides())

    fetch_match_statistics(WINDOW_START, WINDOW_END, [PREMIER_LEAGUE_ID, BUNDESLIGA_ID])

    assert provider.calls == [
        (
            WINDOW_PATH,
            {
                "filters": f"fixtureLeagues:{PREMIER_LEAGUE_ID},{BUNDESLIGA_ID}",
                "include": "statistics",
                "per_page": PAGE_SIZE,
                "timezone": PROVIDER_TIMEZONE,
            },
        )
    ]


def test_both_sides_of_a_settled_fixture_land_on_the_columns_that_store_them(
    provider: StubbedProvider,
) -> None:
    """
    GIVEN a settled fixture whose flat array carries every persisted type for both participants
    WHEN the window is read
    THEN each side is grouped onto its own record, named by team and side, with every column filled
    """

    serve_statistics(provider, both_sides())

    assert read_teams() == [
        ProviderTeamStatistics(
            team_provider_id=HOME_TEAM_ID, side=MatchSide.HOME, values=HOME_VALUES
        ),
        ProviderTeamStatistics(
            team_provider_id=AWAY_TEAM_ID, side=MatchSide.AWAY, values=AWAY_VALUES
        ),
    ]


def test_the_columns_of_a_record_arrive_in_the_order_the_boundary_maps_them(
    provider: StubbedProvider,
) -> None:
    """
    GIVEN a fixture whose away rows arrive in a different order from its home rows
    WHEN the window is read
    THEN both records key their figures in the boundary's order rather than in the provider's
    """

    shuffled = dict(reversed(list(AWAY_FIGURES.items())))

    serve_statistics(
        provider,
        statistic_rows(HOME_FIGURES, HOME_TEAM_ID, "home")
        + statistic_rows(shuffled, AWAY_TEAM_ID, "away"),
    )

    assert [list(team.values) for team in read_teams()] == [
        list(PROVIDER_STATISTICS.values()),
        list(PROVIDER_STATISTICS.values()),
    ]


@pytest.mark.parametrize("type_id", sorted(OPTIONAL_STATISTICS))
def test_an_event_conditional_count_the_provider_omits_reads_as_nought(
    provider: StubbedProvider, caplog: pytest.LogCaptureFixture, type_id: int
) -> None:
    """
    GIVEN a side whose rows leave out one of the counts the provider omits rather than zeroes
    WHEN the window is read
    THEN the column reads nought, nothing is reported, and every other column is unaffected
    """

    caplog.set_level(logging.WARNING, logger=STATISTICS_LOGGER)

    serve_statistics(
        provider,
        statistic_rows(without(HOME_FIGURES, type_id), HOME_TEAM_ID, "home")
        + statistic_rows(AWAY_FIGURES, AWAY_TEAM_ID, "away"),
    )

    assert read_values(MatchSide.HOME) == {
        **HOME_VALUES,
        PROVIDER_STATISTICS[type_id]: 0,
    }
    assert reported(caplog) == []


@pytest.mark.parametrize("type_id", sorted(REQUIRED_STATISTICS))
def test_a_required_type_the_provider_omits_costs_the_whole_fixture(
    provider: StubbedProvider, caplog: pytest.LogCaptureFixture, type_id: int
) -> None:
    """
    GIVEN a side whose rows leave out a type the provider publishes on every side of every match
    WHEN the window is read
    THEN the fixture yields nothing and the omission is reported naming the type
    """

    caplog.set_level(logging.WARNING, logger=STATISTICS_LOGGER)

    serve_statistics(
        provider,
        statistic_rows(without(HOME_FIGURES, type_id), HOME_TEAM_ID, "home")
        + statistic_rows(AWAY_FIGURES, AWAY_TEAM_ID, "away"),
    )

    assert read_teams() == []
    assert f"statistic type {type_id} states no {PROVIDER_STATISTICS[type_id]}" in caplog.text


@pytest.mark.parametrize("type_id", sorted(UNMEASURED_STATISTICS))
def test_a_figure_the_provider_did_not_measure_leaves_its_column_unset(
    provider: StubbedProvider, caplog: pytest.LogCaptureFixture, type_id: int
) -> None:
    """
    GIVEN a side whose rows leave out one of the counts the provider publishes no nought for
    WHEN the window is read
    THEN the column is unset, every other column is intact, and nothing is reported as broken
    """

    caplog.set_level(logging.WARNING, logger=STATISTICS_LOGGER)

    serve_statistics(
        provider,
        statistic_rows(without(HOME_FIGURES, type_id), HOME_TEAM_ID, "home")
        + statistic_rows(AWAY_FIGURES, AWAY_TEAM_ID, "away"),
    )

    assert read_values(MatchSide.HOME) == {
        **HOME_VALUES,
        PROVIDER_STATISTICS[type_id]: None,
    }
    assert reported(caplog) == []


@pytest.mark.parametrize("type_id", sorted(UNMEASURED_STATISTICS))
def test_a_figure_the_provider_measured_for_neither_side_still_yields_the_fixture(
    provider: StubbedProvider, caplog: pytest.LogCaptureFixture, type_id: int
) -> None:
    """
    GIVEN a fixture whose two sides both leave out an unmeasured count, as the provider withholds
    WHEN the window is read
    THEN both records are kept with that column unset, which is what 497 real matches look like
    """

    caplog.set_level(logging.WARNING, logger=STATISTICS_LOGGER)

    serve_statistics(
        provider,
        statistic_rows(without(HOME_FIGURES, type_id), HOME_TEAM_ID, "home")
        + statistic_rows(without(AWAY_FIGURES, type_id), AWAY_TEAM_ID, "away"),
    )

    assert [
        values[PROVIDER_STATISTICS[type_id]]
        for values in (
            read_values(MatchSide.HOME),
            read_values(MatchSide.AWAY),
        )
    ] == [None, None]
    assert reported(caplog) == []


@pytest.mark.parametrize("type_id", sorted(UNMEASURED_STATISTICS))
def test_an_unusable_figure_costs_the_fixture_even_where_an_absence_would_not(
    provider: StubbedProvider, caplog: pytest.LogCaptureFixture, type_id: int
) -> None:
    """
    GIVEN a side stating a count the column could not hold for a type it may also leave out
    WHEN the window is read
    THEN the fixture yields nothing, because an unusable value is not an unmeasured one
    """

    caplog.set_level(logging.WARNING, logger=STATISTICS_LOGGER)

    serve_statistics(
        provider,
        statistic_rows(replacing(HOME_FIGURES, type_id, REFUSED_COUNT), HOME_TEAM_ID, "home")
        + statistic_rows(AWAY_FIGURES, AWAY_TEAM_ID, "away"),
    )

    assert read_teams() == []
    assert "the column that stores it could hold" in caplog.text


@pytest.mark.parametrize("value", REFUSED_FIGURES)
def test_a_figure_the_column_could_not_hold_costs_the_whole_fixture(
    provider: StubbedProvider, caplog: pytest.LogCaptureFixture, value: object
) -> None:
    """
    GIVEN a side stating a count that is negative, above the column ceiling, fractional or no number
    WHEN the window is read
    THEN the fixture yields nothing and the refused value is reported
    """

    caplog.set_level(logging.WARNING, logger=STATISTICS_LOGGER)

    serve_statistics(
        provider,
        statistic_rows(replacing(HOME_FIGURES, SHOTS_TOTAL_TYPE, value), HOME_TEAM_ID, "home")
        + statistic_rows(AWAY_FIGURES, AWAY_TEAM_ID, "away"),
    )

    assert read_teams() == []
    assert "the column that stores it could hold" in caplog.text


def test_a_possession_above_a_hundred_is_refused_although_a_count_that_size_would_pass(
    provider: StubbedProvider, caplog: pytest.LogCaptureFixture
) -> None:
    """
    GIVEN a side claiming more possession than a match has, well inside the column's own ceiling
    WHEN the window is read
    THEN the fixture yields nothing, because possession is read as the percentage it is
    """

    caplog.set_level(logging.WARNING, logger=STATISTICS_LOGGER)

    serve_statistics(
        provider,
        statistic_rows(
            replacing(HOME_FIGURES, POSSESSION_TYPE, POSSESSION_CEILING + 1), HOME_TEAM_ID, "home"
        )
        + statistic_rows(AWAY_FIGURES, AWAY_TEAM_ID, "away"),
    )

    assert POSSESSION_CEILING + 1 < COUNT_CEILING
    assert read_teams() == []
    assert "is not a possession" in caplog.text


def test_a_figure_the_provider_stringifies_is_read_as_the_number_it_denotes(
    provider: StubbedProvider,
) -> None:
    """
    GIVEN a side whose shot count arrives as a string of digits rather than as a number
    WHEN the window is read
    THEN the figure is carried as the integer it denotes, so a formatting change costs no record
    """

    serve_statistics(
        provider,
        statistic_rows(replacing(HOME_FIGURES, SHOTS_TOTAL_TYPE, "23"), HOME_TEAM_ID, "home")
        + statistic_rows(AWAY_FIGURES, AWAY_TEAM_ID, "away"),
    )

    assert read_values(MatchSide.HOME) == {**HOME_VALUES, "shots_total": 23}


def test_a_location_the_boundary_does_not_recognize_costs_the_whole_fixture(
    provider: StubbedProvider, caplog: pytest.LogCaptureFixture
) -> None:
    """
    GIVEN a participant whose rows are tagged with a location that names neither side
    WHEN the window is read
    THEN the fixture yields nothing, because the side decides which record a form query reads
    """

    caplog.set_level(logging.WARNING, logger=STATISTICS_LOGGER)

    serve_statistics(
        provider,
        statistic_rows(HOME_FIGURES, HOME_TEAM_ID, "neutral")
        + statistic_rows(AWAY_FIGURES, AWAY_TEAM_ID, "away"),
    )

    assert read_teams() == []
    assert "'neutral' names no side" in caplog.text


def test_a_participant_whose_rows_name_two_locations_is_refused(
    provider: StubbedProvider, caplog: pytest.LogCaptureFixture
) -> None:
    """
    GIVEN a participant whose rows disagree about which side of the match it played
    WHEN the window is read
    THEN the record is refused rather than resolved by majority, and the fixture yields nothing
    """

    caplog.set_level(logging.WARNING, logger=STATISTICS_LOGGER)

    rows = statistic_rows(HOME_FIGURES, HOME_TEAM_ID, "home")
    rows[-1]["location"] = "away"

    serve_statistics(provider, rows + statistic_rows(AWAY_FIGURES, AWAY_TEAM_ID, "away"))

    assert read_teams() == []
    assert "its statistics name 2 sides" in caplog.text


def test_a_fixture_the_provider_settled_one_side_of_yields_nothing_at_all(
    provider: StubbedProvider, caplog: pytest.LogCaptureFixture
) -> None:
    """
    GIVEN a fixture whose array carries the rows of one participant only
    WHEN the window is read
    THEN nothing is carried, because the opponent's record is where conceded figures come from
    """

    caplog.set_level(logging.WARNING, logger=STATISTICS_LOGGER)

    serve_statistics(provider, statistic_rows(HOME_FIGURES, HOME_TEAM_ID, "home"))

    assert fetch_match_statistics(WINDOW_START, WINDOW_END, [PREMIER_LEAGUE_ID]).fixtures == []
    assert "a match needs two usable team records, not 1" in caplog.text


def test_two_records_claiming_the_same_side_are_refused(
    provider: StubbedProvider, caplog: pytest.LogCaptureFixture
) -> None:
    """
    GIVEN a fixture whose two participants are both tagged as the home side
    WHEN the window is read
    THEN nothing is carried and the payload is named, rather than a row the constraint would refuse
    """

    caplog.set_level(logging.WARNING, logger=STATISTICS_LOGGER)

    serve_statistics(
        provider,
        statistic_rows(HOME_FIGURES, HOME_TEAM_ID, "home")
        + statistic_rows(AWAY_FIGURES, AWAY_TEAM_ID, "home"),
    )

    assert read_teams() == []
    assert f"teams {HOME_TEAM_ID} and {AWAY_TEAM_ID} both claim the home side" in caplog.text


def test_a_third_participant_makes_the_fixture_unreadable(
    provider: StubbedProvider, caplog: pytest.LogCaptureFixture
) -> None:
    """
    GIVEN a fixture whose array carries the rows of three participants
    WHEN the window is read
    THEN nothing is carried, because a match has exactly two sides and no rule picks two of three
    """

    caplog.set_level(logging.WARNING, logger=STATISTICS_LOGGER)

    serve_statistics(
        provider,
        both_sides() + statistic_rows(AWAY_FIGURES, THIRD_TEAM_ID, "away"),
    )

    assert read_teams() == []
    assert "a match needs two usable team records, not 3" in caplog.text


def test_a_statistic_type_the_boundary_does_not_persist_is_ignored_without_a_warning(
    provider: StubbedProvider, caplog: pytest.LogCaptureFixture
) -> None:
    """
    GIVEN a settled fixture carrying one of the two dozen types the provider publishes unpersisted
    WHEN the window is read
    THEN both records normalize, the type is noted at debug only, and nothing is reported as broken
    """

    caplog.set_level(logging.DEBUG, logger=STATISTICS_LOGGER)

    serve_statistics(
        provider,
        statistic_rows(replacing(HOME_FIGURES, UNPERSISTED_TYPE, 118), HOME_TEAM_ID, "home")
        + statistic_rows(AWAY_FIGURES, AWAY_TEAM_ID, "away"),
    )

    assert read_values(MatchSide.HOME) == HOME_VALUES
    assert f"Ignoring statistic type {UNPERSISTED_TYPE}" in caplog.text
    assert reported(caplog) == []


def test_a_row_naming_no_participant_is_reported_rather_than_attributed(
    provider: StubbedProvider, caplog: pytest.LogCaptureFixture
) -> None:
    """
    GIVEN a fixture carrying a row whose participant identifier is unusable
    WHEN the window is read
    THEN the row is dropped and reported, so the figure is never charged to the wrong team
    """

    caplog.set_level(logging.WARNING, logger=STATISTICS_LOGGER)

    rows = both_sides()
    rows[0]["participant_id"] = None

    serve_statistics(provider, rows)

    assert read_teams() == []
    assert "names no usable participant" in caplog.text


def test_a_fixture_whose_statistics_are_not_an_array_is_dropped_and_reported(
    provider: StubbedProvider, caplog: pytest.LogCaptureFixture
) -> None:
    """
    GIVEN a fixture whose statistics include arrived as an object rather than as an array
    WHEN the window is read
    THEN the fixture is dropped and the payload is reported
    """

    caplog.set_level(logging.WARNING, logger=STATISTICS_LOGGER)

    serve_statistics(provider, {"value": 7})

    assert fetch_match_statistics(WINDOW_START, WINDOW_END, [PREMIER_LEAGUE_ID]).fixtures == []
    assert "is not a statistics array" in caplog.text


def test_an_entry_naming_no_usable_fixture_is_dropped_and_reported(
    provider: StubbedProvider, caplog: pytest.LogCaptureFixture
) -> None:
    """
    GIVEN a page entry whose fixture identifier is unusable
    WHEN the window is read
    THEN the entry is dropped and reported, because nothing could be written against it
    """

    caplog.set_level(logging.WARNING, logger=STATISTICS_LOGGER)

    provider.serve(WINDOW_PATH, [[{"id": None, "statistics": both_sides()}]])

    assert fetch_match_statistics(WINDOW_START, WINDOW_END, [PREMIER_LEAGUE_ID]).fixtures == []
    assert "names no usable fixture" in caplog.text


def test_one_broken_fixture_costs_only_itself(provider: StubbedProvider) -> None:
    """
    GIVEN a page carrying a settled fixture beside one whose home side omits a required type
    WHEN the window is read
    THEN the sound fixture is carried, so a broken payload cannot cost the rest of the range
    """

    provider.serve(
        WINDOW_PATH,
        [
            [
                fixture_payload(
                    statistics=statistic_rows(
                        without(HOME_FIGURES, SHOTS_TOTAL_TYPE), HOME_TEAM_ID, "home"
                    )
                    + statistic_rows(AWAY_FIGURES, AWAY_TEAM_ID, "away")
                ),
                fixture_payload(provider_id=OTHER_FIXTURE_ID),
            ]
        ],
    )

    window = fetch_match_statistics(WINDOW_START, WINDOW_END, [PREMIER_LEAGUE_ID])

    assert [fixture.fixture_provider_id for fixture in window.fixtures] == [OTHER_FIXTURE_ID]


def test_a_window_the_provider_paginates_carries_the_fixtures_of_every_page(
    provider: StubbedProvider,
) -> None:
    """
    GIVEN a window the provider serves over two pages, each carrying a different settled fixture
    WHEN the window is read
    THEN both fixtures are carried with their two records, in the order the pages arrived
    """

    provider.serve(
        WINDOW_PATH,
        [[fixture_payload()], [fixture_payload(provider_id=OTHER_FIXTURE_ID)]],
    )

    window = fetch_match_statistics(WINDOW_START, WINDOW_END, [PREMIER_LEAGUE_ID])

    assert [
        (fixture.fixture_provider_id, [team.side for team in fixture.teams])
        for fixture in window.fixtures
    ] == [
        (FIXTURE_ID, [MatchSide.HOME, MatchSide.AWAY]),
        (OTHER_FIXTURE_ID, [MatchSide.HOME, MatchSide.AWAY]),
    ]


def test_requesting_no_competition_is_refused_before_any_window_request(
    provider: StubbedProvider,
) -> None:
    """
    GIVEN a configuration that leaves the requested competitions empty
    WHEN a statistics window is read
    THEN the boundary error is raised and no provider request is made
    """

    with pytest.raises(SportmonksError, match="No Sportmonks league"):
        fetch_match_statistics(WINDOW_START, WINDOW_END, [])

    assert provider.calls == []


def test_the_statistic_table_maps_only_types_the_provider_publishes() -> None:
    """
    GIVEN the mapped provider types and the vocabulary a live read of the types resource returned
    WHEN they are compared
    THEN every mapped identifier still exists upstream under the code the mapping was built from
    """

    recorded = recorded_types()

    assert {type_id: recorded.get(type_id) for type_id in PROVIDER_STATISTICS} == MAPPED_CODES


def test_the_types_read_as_nought_when_absent_are_the_ones_the_provider_zeroes() -> None:
    """
    GIVEN the types the boundary reads an absence of as nought
    WHEN they are compared with the mapping and with the codes the provider publishes them under
    THEN they are mapped types, and they are the eight the provider also sends explicit noughts for
    """

    assert set(PROVIDER_STATISTICS) >= OPTIONAL_STATISTICS
    assert {MAPPED_CODES[type_id] for type_id in OPTIONAL_STATISTICS} == {
        "accurate-crosses",
        "big-chances-created",
        "key-passes",
        "offsides",
        "redcards",
        "saves",
        "shots-blocked",
        "yellowcards",
    }


def test_the_types_left_unset_when_absent_are_the_ones_no_match_ever_read_nought() -> None:
    """
    GIVEN the types the boundary leaves unset rather than reading an absence of as nought
    WHEN they are compared with the mapping, the provider codes, and the columns exported for them
    THEN they are the four whose lowest reading over 7,100 sides was above nought
    """

    assert set(PROVIDER_STATISTICS) >= UNMEASURED_STATISTICS
    assert {MAPPED_CODES[type_id] for type_id in UNMEASURED_STATISTICS} == {
        "dribble-attempts",
        "duels-won",
        "successful-dribbles",
        "tackles",
    }
    assert {
        "dribble_attempts",
        "duels_won",
        "successful_dribbles",
        "tackles",
    } == UNMEASURED_COLUMNS


def test_the_types_a_record_cannot_do_without_are_the_ones_the_provider_always_sends() -> None:
    """
    GIVEN the types whose absence discards a record
    WHEN they are compared with the codes measured on every side of two seasons of fixtures
    THEN they are the ten never once withheld, so no absence the provider produces costs a match
    """

    assert {MAPPED_CODES[type_id] for type_id in REQUIRED_STATISTICS} == {
        "ball-possession",
        "corners",
        "fouls",
        "interceptions",
        "passes",
        "shots-insidebox",
        "shots-on-target",
        "shots-total",
        "successful-passes",
        "total-crosses",
    }


def test_the_three_tiers_partition_every_type_the_boundary_maps() -> None:
    """
    GIVEN the three tiers an absent type is read under: required, nought, and unset
    WHEN their union and their sizes are compared with the mapping the whole policy is stated over
    THEN they cover every mapped type exactly once, which is what the policy rests on
    """

    tiers = (REQUIRED_STATISTICS, OPTIONAL_STATISTICS, UNMEASURED_STATISTICS)

    assert frozenset[int]().union(*tiers) == set(PROVIDER_STATISTICS)
    assert sum(len(tier) for tier in tiers) == len(PROVIDER_STATISTICS)


def test_the_columns_left_unset_are_the_ones_the_model_accepts_a_null_in() -> None:
    """
    GIVEN the columns the boundary can leave unset and the columns the model declares nullable
    WHEN they are compared
    THEN they are the same set, so the boundary can only leave unset what the schema stores unset
    """

    assert nullable_columns(MatchTeamStatistic) == UNMEASURED_COLUMNS


def test_the_statistic_table_names_every_column_that_stores_a_figure() -> None:
    """
    GIVEN the mapped column names and the whole-count columns of the model the adapter feeds
    WHEN they are compared
    THEN they name the same columns, so neither the mapping nor the model can drift from the other
    """

    assert sorted(PROVIDER_STATISTICS.values()) == sorted(count_columns(MatchTeamStatistic))


def test_the_percentage_type_is_the_one_the_boundary_bounds_at_a_hundred() -> None:
    """
    GIVEN the type identifier the boundary reads under the percentage ceiling
    WHEN the mapping is consulted
    THEN it is the possession column, so the two constants cannot come to mean different types
    """

    assert PROVIDER_STATISTICS[POSSESSION_TYPE] == "possession"


@pytest.mark.parametrize(("completed", "attempted"), sorted(COMPLETION_PAIRS.items()))
def test_a_record_completing_more_than_it_attempted_costs_the_whole_fixture(
    provider: StubbedProvider,
    caplog: pytest.LogCaptureFixture,
    completed: str,
    attempted: str,
) -> None:
    """
    GIVEN a side stating one more completion than the attempts it also states
    WHEN the window is read
    THEN the fixture yields nothing and the pair is reported, so no share above a hundred is built
    """

    caplog.set_level(logging.WARNING, logger=STATISTICS_LOGGER)

    completed_type = COLUMN_TYPES[completed]

    figures = replacing(HOME_FIGURES, completed_type, HOME_FIGURES[COLUMN_TYPES[attempted]] + 1)

    serve_statistics(
        provider,
        statistic_rows(figures, HOME_TEAM_ID, "home")
        + statistic_rows(AWAY_FIGURES, AWAY_TEAM_ID, "away"),
    )

    assert read_teams() == []
    assert f"exceeds {HOME_FIGURES[COLUMN_TYPES[attempted]]} {attempted}" in caplog.text


def test_a_record_completing_exactly_what_it_attempted_is_kept(
    provider: StubbedProvider, caplog: pytest.LogCaptureFixture
) -> None:
    """
    GIVEN a side whose every completion equals the attempts it states
    WHEN the window is read
    THEN the record is kept and nothing is reported, because a perfect accuracy is not a fault
    """

    caplog.set_level(logging.WARNING, logger=STATISTICS_LOGGER)

    figures = dict(HOME_FIGURES)

    for completed, attempted in COMPLETION_PAIRS.items():
        figures[COLUMN_TYPES[completed]] = figures[COLUMN_TYPES[attempted]]

    serve_statistics(
        provider,
        statistic_rows(figures, HOME_TEAM_ID, "home")
        + statistic_rows(AWAY_FIGURES, AWAY_TEAM_ID, "away"),
    )

    kept = read_values(MatchSide.HOME)

    assert reported(caplog) == []
    assert all(
        kept[completed] == kept[attempted] for completed, attempted in COMPLETION_PAIRS.items()
    )


def test_every_completion_pair_names_columns_the_boundary_actually_maps() -> None:
    """
    GIVEN the completion pairs the guard enforces
    WHEN they are compared with the columns the mapping produces
    THEN both halves of every pair are mapped columns, so the guard cannot read a missing key
    """

    paired = set(COMPLETION_PAIRS) | set(COMPLETION_PAIRS.values())

    assert paired <= set(PROVIDER_STATISTICS.values())
