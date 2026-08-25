import logging
from collections.abc import Iterator
from datetime import date
from decimal import Decimal

import pytest
from django.test import override_settings

from apps.predictions.domain.enums import (
    PredictionMarket,
    PredictionReliability,
    PredictionSelection,
)
from apps.predictions.domain.markets import MARKET_SELECTIONS
from integrations.sportmonks.client import ProviderPayload, QueryParameters, SportmonksClient
from integrations.sportmonks.exceptions import SportmonksError
from integrations.sportmonks.fixtures import PAGE_SIZE, PROVIDER_TIMEZONE
from integrations.sportmonks.predictions import (
    PROVIDER_SELECTIONS,
    ProviderFixtureProbabilities,
    ProviderProbability,
    ProviderReliability,
    fetch_market_reliability,
    fetch_prediction_window,
)

type Pages = list[list[ProviderPayload]]

type RecordedCalls = list[tuple[str, QueryParameters]]

type SelectionsByMarket = dict[PredictionMarket, list[PredictionSelection]]

PREDICTIONS_LOGGER = "integrations.sportmonks.predictions"

PREMIER_LEAGUE_ID = 8

BUNDESLIGA_ID = 82

FIXTURE_ID = 19427455

OTHER_FIXTURE_ID = 19427456

WINDOW_START = date(2026, 8, 29)

WINDOW_END = date(2026, 9, 5)

WINDOW_PATH = f"/fixtures/between/{WINDOW_START.isoformat()}/{WINDOW_END.isoformat()}"

KICKOFF_STAMP = "2026-08-29 11:30:00"

# The filter string a live probe of the subscription confirmed the provider honours server-side.
REQUESTED_TYPES = "231,232,233,234,235,236,237,238,239,240,1679"

FULLTIME_RESULT_TYPE = 237

DOUBLE_CHANCE_TYPE = 239

BOTH_TEAMS_TO_SCORE_TYPE = 231

OVER_UNDER_1_5_TYPE = 234

OVER_UNDER_2_5_TYPE = 235

OVER_UNDER_3_5_TYPE = 236

OVER_UNDER_4_5_TYPE = 1679

TEAM_TO_SCORE_FIRST_TYPE = 238

FIRST_HALF_RESULT_TYPE = 233

HALF_TIME_FULL_TIME_TYPE = 232

CORRECT_SCORE_TYPE = 240

# Historical log loss, predictive power and models log loss. The window filter asks for none of
# the three, and the predictability resource returns all three beside the two that are in scope.
LOG_LOSS_TYPE = 241

PREDICTIVE_POWER_TYPE = 244

MODELS_LOG_LOSS_TYPE = 245

QUALITY_TYPE = 243

HIT_RATIO_TYPE = 242

RECORDED_SELECTIONS: dict[int, ProviderPayload] = {
    FULLTIME_RESULT_TYPE: {"home": 26.96, "draw": 24.82, "away": 48.18},
    DOUBLE_CHANCE_TYPE: {"draw_home": 51.78, "home_away": 75.14, "draw_away": 73.04},
    BOTH_TEAMS_TO_SCORE_TYPE: {"yes": 55.5, "no": 44.5},
    OVER_UNDER_1_5_TYPE: {"yes": 74.21, "no": 25.79},
    OVER_UNDER_2_5_TYPE: {"yes": 49.94, "no": 50.06},
    OVER_UNDER_3_5_TYPE: {"yes": 27.35, "no": 72.65},
    OVER_UNDER_4_5_TYPE: {"yes": 13.11, "no": 86.89},
    TEAM_TO_SCORE_FIRST_TYPE: {"home": 40.55, "away": 51.45, "draw": 8.0},
    FIRST_HALF_RESULT_TYPE: {"home": 30.11, "draw": 40.22, "away": 29.67},
    HALF_TIME_FULL_TIME_TYPE: {
        "home_home": 18.44,
        "home_draw": 3.21,
        "home_away": 1.12,
        "draw_home": 9.83,
        "draw_draw": 8.44,
        "draw_away": 6.61,
        "away_home": 3.93,
        "away_draw": 12.21,
        "away_away": 36.21,
    },
    CORRECT_SCORE_TYPE: {
        "scores": {
            "0-0": 5.55,
            "0-1": 6.61,
            "0-2": 4.02,
            "0-3": 1.63,
            "1-0": 7.02,
            "1-1": 8.36,
            "1-2": 5.08,
            "1-3": 2.06,
            "2-0": 4.44,
            "2-1": 5.29,
            "2-2": 3.21,
            "2-3": 1.3,
            "3-0": 1.87,
            "3-1": 2.23,
            "3-2": 1.35,
            "3-3": 0.55,
            "Other_1": 12.14,
            "Other_X": 0.35,
            "Other_2": 26.94,
        }
    },
}

RECORDED_MARKETS = [
    (FULLTIME_RESULT_TYPE, PredictionMarket.FULLTIME_RESULT),
    (DOUBLE_CHANCE_TYPE, PredictionMarket.DOUBLE_CHANCE),
    (BOTH_TEAMS_TO_SCORE_TYPE, PredictionMarket.BOTH_TEAMS_TO_SCORE),
    (OVER_UNDER_1_5_TYPE, PredictionMarket.OVER_UNDER_1_5),
    (OVER_UNDER_2_5_TYPE, PredictionMarket.OVER_UNDER_2_5),
    (OVER_UNDER_3_5_TYPE, PredictionMarket.OVER_UNDER_3_5),
    (OVER_UNDER_4_5_TYPE, PredictionMarket.OVER_UNDER_4_5),
    (TEAM_TO_SCORE_FIRST_TYPE, PredictionMarket.TEAM_TO_SCORE_FIRST),
    (FIRST_HALF_RESULT_TYPE, PredictionMarket.FIRST_HALF_RESULT),
    (HALF_TIME_FULL_TIME_TYPE, PredictionMarket.HALF_TIME_FULL_TIME),
    (CORRECT_SCORE_TYPE, PredictionMarket.CORRECT_SCORE),
]

RECORDED_QUALITIES: ProviderPayload = {
    "fulltime_result": "medium",
    "fulltime_result_1st_half": "poor",
    "ht_ft": "poor",
    "correct_score": "poor",
    "team_to_score_first": "good",
    "both_teams_to_score": "high",
    "over_under_1_5": "good",
    "over_under_2_5": "medium",
    "over_under_3_5": "good",
    "home_over_under_0_5": "high",
    "home_over_under_1_5": "medium",
    "away_over_under_0_5": "high",
    "away_over_under_1_5": "medium",
}

RECORDED_HIT_RATIOS: ProviderPayload = {
    "fulltime_result": 0.5,
    "fulltime_result_1st_half": 0.4737,
    "ht_ft": 0.2106,
    "correct_score": 0.1052,
    "team_to_score_first": 0.6315,
    "both_teams_to_score": 0.7368,
    "over_under_1_5": 0.7894,
    "over_under_2_5": 0.5263,
    "over_under_3_5": 0.6842,
    "home_over_under_0_5": 0.8421,
    "home_over_under_1_5": 0.6842,
    "away_over_under_0_5": 0.7894,
    "away_over_under_1_5": 0.7368,
}

UNSTORABLE_PERCENTAGES = [100.01, -0.01, "26.96", True, None, float("nan")]

UNSTORABLE_HIT_RATIOS = [1.001, -0.001, "0.5", True, None, float("inf")]


def predictability_path(league_id: int) -> str:
    """
    Build the path the predictability resource of one competition is read at.

    Parameters
    ----------
    league_id : int
        Sportmonks league identifier.

    Returns
    -------
    str
        Resource path the boundary is expected to ask for.
    """

    return f"/predictions/predictability/leagues/{league_id}"


def prediction(type_id: int, selections: object = None) -> ProviderPayload:
    """
    Build one entry of the predictions include of a fixture.

    Parameters
    ----------
    type_id : int
        Provider type the entry is published under.
    selections : object, optional
        Value of the nested ``predictions`` field, or ``None`` to use the
        recorded selections of the type.

    Returns
    -------
    ProviderPayload
        Prediction entry trimmed to the fields the boundary reads.
    """

    if selections is None:
        selections = RECORDED_SELECTIONS[type_id]

    return {
        "id": 5170000 + type_id,
        "fixture_id": FIXTURE_ID,
        "type_id": type_id,
        "predictions": selections,
    }


def fixture_payload(
    *, provider_id: int = FIXTURE_ID, predictions: object = None
) -> ProviderPayload:
    """
    Build a fixtures entry with its predictions included.

    Parameters
    ----------
    provider_id : int, optional
        Provider fixture identifier.
    predictions : object, optional
        Value of the predictions include, or ``None`` for the empty list a
        fixture the provider publishes nothing for is returned with.

    Returns
    -------
    ProviderPayload
        Entry trimmed to the fields the boundary reads.
    """

    if predictions is None:
        predictions = []

    return {
        "id": provider_id,
        "league_id": PREMIER_LEAGUE_ID,
        "starting_at": KICKOFF_STAMP,
        "predictions": predictions,
    }


def grade_entry(type_id: int, data: object, league_id: int = PREMIER_LEAGUE_ID) -> ProviderPayload:
    """
    Build one entry of the predictability resource of a competition.

    Parameters
    ----------
    type_id : int
        Provider type the entry grades the competition by.
    data : object
        Value of the ``data`` field, documented as a market-keyed object.
    league_id : int, optional
        Competition the entry grades.

    Returns
    -------
    ProviderPayload
        Predictability entry trimmed to the fields the boundary reads.
    """

    return {"id": 100 + type_id, "league_id": league_id, "type_id": type_id, "data": data}


def grade(
    market: PredictionMarket, quality: PredictionReliability, hit_ratio: str
) -> ProviderReliability:
    """
    Build the grade the boundary is expected to normalize one market into.

    Parameters
    ----------
    market : PredictionMarket
        Market the grade describes.
    quality : PredictionReliability
        Word the provider graded the market with.
    hit_ratio : str
        Share the model achieved, as the exact decimal it is stored to.

    Returns
    -------
    ProviderReliability
        Expected grade of the Premier League.
    """

    return ProviderReliability(
        league_provider_id=PREMIER_LEAGUE_ID,
        market=market,
        quality=quality,
        hit_ratio=Decimal(hit_ratio),
    )


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


def serve_predictions(provider: StubbedProvider, predictions: object) -> None:
    """
    Serve a window of one fixture carrying the given predictions include.

    Parameters
    ----------
    provider : StubbedProvider
        Stub the page is recorded on.
    predictions : object
        Value of the predictions include of the fixture.
    """

    provider.serve(WINDOW_PATH, [[fixture_payload(predictions=predictions)]])


def serve_grades(
    provider: StubbedProvider, entries: list[ProviderPayload], league_id: int = PREMIER_LEAGUE_ID
) -> None:
    """
    Serve the predictability resource of one competition with the given entries.

    Parameters
    ----------
    provider : StubbedProvider
        Stub the page is recorded on.
    entries : list of ProviderPayload
        Entries the resource answers with on its single page.
    league_id : int, optional
        Competition the entries grade.
    """

    provider.serve(predictability_path(league_id), [entries])


def read_probabilities() -> list[ProviderProbability]:
    """
    Read the probabilities of the first fixture of the window under test.

    Returns
    -------
    list of ProviderProbability
        Normalized probabilities of the fixture, in provider order.
    """

    window = fetch_prediction_window(WINDOW_START, WINDOW_END, [PREMIER_LEAGUE_ID, BUNDESLIGA_ID])

    return window.fixtures[0].probabilities


def read_selections(market: PredictionMarket) -> dict[PredictionSelection, Decimal]:
    """
    Read the probability each selection of one market was normalized to.

    Parameters
    ----------
    market : PredictionMarket
        Market to narrow the probabilities to.

    Returns
    -------
    dict of PredictionSelection to Decimal
        Probability of every selection the market was read with.
    """

    return {
        probability.selection: probability.probability
        for probability in read_probabilities()
        if probability.market == market
    }


def selections_by_market(probabilities: list[ProviderProbability]) -> SelectionsByMarket:
    """
    Group normalized probabilities into the selections each market carries.

    Parameters
    ----------
    probabilities : list of ProviderProbability
        Probabilities one fixture was read with.

    Returns
    -------
    dict of PredictionMarket to list of PredictionSelection
        Selections of every market read, sorted so the comparison is about
        coverage rather than about the order the provider listed them in.
    """

    grouped: SelectionsByMarket = {}

    for probability in probabilities:
        grouped.setdefault(probability.market, []).append(probability.selection)

    return {market: sorted(selections) for market, selections in grouped.items()}


def test_a_full_window_normalizes_every_market_of_the_published_vocabulary(
    provider: StubbedProvider,
) -> None:
    """
    GIVEN a fixture carrying one prediction of every type the boundary asks the provider for
    WHEN the window is read
    THEN every published market is normalized with exactly the selections its contract promises
    """

    serve_predictions(provider, [prediction(type_id) for type_id, _ in RECORDED_MARKETS])

    assert selections_by_market(read_probabilities()) == {
        market: sorted(selections) for market, selections in MARKET_SELECTIONS.items()
    }


@pytest.mark.parametrize(("type_id", "expected_market"), RECORDED_MARKETS)
def test_a_recorded_prediction_type_lands_on_the_market_it_denotes(
    provider: StubbedProvider, type_id: int, expected_market: PredictionMarket
) -> None:
    """
    GIVEN a fixture carrying a single prediction of one recorded provider type
    WHEN the window is read
    THEN every probability read belongs to the market that type denotes
    """

    serve_predictions(provider, [prediction(type_id)])

    assert list(selections_by_market(read_probabilities())) == [expected_market]


def test_a_probability_is_carried_as_an_exact_two_place_decimal(
    provider: StubbedProvider,
) -> None:
    """
    GIVEN a market whose percentages arrive as an integer, as two decimals, and as three
    WHEN the window is read
    THEN each is carried as an exact decimal rounded to the two places the column stores
    """

    serve_predictions(
        provider,
        [prediction(FULLTIME_RESULT_TYPE, {"home": 27, "draw": 39.34, "away": 33.336})],
    )

    assert read_selections(PredictionMarket.FULLTIME_RESULT) == {
        PredictionSelection.HOME: Decimal("27.00"),
        PredictionSelection.DRAW: Decimal("39.34"),
        PredictionSelection.AWAY: Decimal("33.34"),
    }


def test_the_correct_score_market_is_read_from_the_object_it_nests_its_selections_in(
    provider: StubbedProvider,
) -> None:
    """
    GIVEN the one market whose payload nests its selections under a scores object
    WHEN the window is read
    THEN the scores are unwrapped, the hyphenated pair naming a side each and the buckets a result
    """

    serve_predictions(provider, [prediction(CORRECT_SCORE_TYPE)])

    selections = read_selections(PredictionMarket.CORRECT_SCORE)

    assert selections[PredictionSelection.SCORE_1_2] == Decimal("5.08")
    assert selections[PredictionSelection.SCORE_3_0] == Decimal("1.87")
    assert selections[PredictionSelection.ANY_OTHER_HOME_WIN] == Decimal("12.14")
    assert selections[PredictionSelection.ANY_OTHER_DRAW] == Decimal("0.35")
    assert selections[PredictionSelection.ANY_OTHER_AWAY_WIN] == Decimal("26.94")


def test_a_correct_score_prediction_stated_flat_is_dropped_and_reported(
    provider: StubbedProvider, caplog: pytest.LogCaptureFixture
) -> None:
    """
    GIVEN a correct-score prediction whose selections are stated flat rather than nested
    WHEN the window is read
    THEN the market is dropped, the drop is reported, and the fixture still belongs to the window
    """

    caplog.set_level(logging.WARNING, logger=PREDICTIONS_LOGGER)

    serve_predictions(provider, [prediction(CORRECT_SCORE_TYPE, {"1-2": 5.08})])

    assert read_probabilities() == []
    assert "states no selection" in caplog.text


def test_the_double_chance_keys_map_onto_the_pairs_they_denote(
    provider: StubbedProvider,
) -> None:
    """
    GIVEN a double-chance prediction, whose keys name the outcome pair they exclude the third of
    WHEN the window is read
    THEN each key lands on its overlapping selection rather than on a single-outcome one
    """

    serve_predictions(provider, [prediction(DOUBLE_CHANCE_TYPE)])

    assert read_selections(PredictionMarket.DOUBLE_CHANCE) == {
        PredictionSelection.HOME_OR_DRAW: Decimal("51.78"),
        PredictionSelection.HOME_OR_AWAY: Decimal("75.14"),
        PredictionSelection.DRAW_OR_AWAY: Decimal("73.04"),
    }


def test_the_half_time_full_time_keys_map_onto_the_ordered_pairs_they_denote(
    provider: StubbedProvider,
) -> None:
    """
    GIVEN a half-time/full-time prediction, which spells two of its keys as double chance does
    WHEN the window is read
    THEN home_away and draw_home read as ordered sequences, not as the pairs of that other market
    """

    serve_predictions(provider, [prediction(HALF_TIME_FULL_TIME_TYPE)])

    selections = read_selections(PredictionMarket.HALF_TIME_FULL_TIME)

    assert selections[PredictionSelection.HOME_THEN_AWAY] == Decimal("1.12")
    assert selections[PredictionSelection.DRAW_THEN_HOME] == Decimal("9.83")
    assert PredictionSelection.HOME_OR_AWAY not in selections
    assert PredictionSelection.HOME_OR_DRAW not in selections


def test_the_team_to_score_first_draw_key_reads_as_neither_side_scoring(
    provider: StubbedProvider,
) -> None:
    """
    GIVEN a team-to-score-first prediction, whose draw key means that nobody scores at all
    WHEN the window is read
    THEN the key lands on the no-goal selection rather than on the draw of a result market
    """

    serve_predictions(provider, [prediction(TEAM_TO_SCORE_FIRST_TYPE)])

    assert read_selections(PredictionMarket.TEAM_TO_SCORE_FIRST) == {
        PredictionSelection.HOME: Decimal("40.55"),
        PredictionSelection.AWAY: Decimal("51.45"),
        PredictionSelection.NO_GOAL: Decimal("8.00"),
    }


def test_a_fixture_the_provider_publishes_no_prediction_for_still_belongs_to_the_window(
    provider: StubbedProvider,
) -> None:
    """
    GIVEN a fixture returned with an empty predictions array, as one a fortnight out always is
    WHEN the window is read
    THEN the fixture is carried without a probability, so reconciliation knows it was read
    """

    provider.serve(WINDOW_PATH, [[fixture_payload()]])

    window = fetch_prediction_window(WINDOW_START, WINDOW_END, [PREMIER_LEAGUE_ID])

    assert window.fixtures == [
        ProviderFixtureProbabilities(fixture_provider_id=FIXTURE_ID, probabilities=[])
    ]


def test_a_fixture_whose_predictions_are_not_an_array_is_dropped_rather_than_read_as_empty(
    provider: StubbedProvider, caplog: pytest.LogCaptureFixture
) -> None:
    """
    GIVEN one fixture whose predictions include is malformed beside one that is well formed
    WHEN the window is read
    THEN only the well-formed fixture is carried and the drop is reported
    """

    caplog.set_level(logging.WARNING, logger=PREDICTIONS_LOGGER)

    malformed = fixture_payload(predictions={"home": 26.96})

    well_formed = fixture_payload(
        provider_id=OTHER_FIXTURE_ID, predictions=[prediction(FULLTIME_RESULT_TYPE)]
    )

    provider.serve(WINDOW_PATH, [[malformed, well_formed]])

    window = fetch_prediction_window(WINDOW_START, WINDOW_END, [PREMIER_LEAGUE_ID])

    assert [fixture.fixture_provider_id for fixture in window.fixtures] == [OTHER_FIXTURE_ID]
    assert "is not a predictions array" in caplog.text


def test_a_prediction_type_the_boundary_does_not_publish_is_ignored(
    provider: StubbedProvider,
) -> None:
    """
    GIVEN a fixture carrying a prediction type this boundary maps onto no market
    WHEN the window is read
    THEN it contributes no probability and the market beside it is still normalized
    """

    serve_predictions(
        provider,
        [
            prediction(LOG_LOSS_TYPE, {"fulltime_result": 1.05}),
            prediction(BOTH_TEAMS_TO_SCORE_TYPE),
        ],
    )

    assert list(selections_by_market(read_probabilities())) == [
        PredictionMarket.BOTH_TEAMS_TO_SCORE
    ]


def test_a_selection_key_the_market_does_not_name_is_dropped_and_reported(
    provider: StubbedProvider, caplog: pytest.LogCaptureFixture
) -> None:
    """
    GIVEN a market whose payload carries a selection key this boundary maps onto nothing
    WHEN the window is read
    THEN the key is dropped, the drop is reported, and the keys beside it are still normalized
    """

    caplog.set_level(logging.WARNING, logger=PREDICTIONS_LOGGER)

    serve_predictions(
        provider,
        [prediction(BOTH_TEAMS_TO_SCORE_TYPE, {"yes": 55.5, "no": 44.5, "maybe": 0.0})],
    )

    assert read_selections(PredictionMarket.BOTH_TEAMS_TO_SCORE) == {
        PredictionSelection.YES: Decimal("55.50"),
        PredictionSelection.NO: Decimal("44.50"),
    }
    assert "names no such selection" in caplog.text


@pytest.mark.parametrize("unstorable", UNSTORABLE_PERCENTAGES)
def test_a_percentage_the_column_could_not_hold_costs_only_its_own_selection(
    provider: StubbedProvider, caplog: pytest.LogCaptureFixture, unstorable: object
) -> None:
    """
    GIVEN a market one of whose percentages is outside the range the column holds, or is no number
    WHEN the window is read
    THEN that selection alone is dropped and reported, so the rest of the run stays writable
    """

    caplog.set_level(logging.WARNING, logger=PREDICTIONS_LOGGER)

    serve_predictions(
        provider,
        [prediction(FULLTIME_RESULT_TYPE, {"home": unstorable, "draw": 24.82, "away": 48.18})],
    )

    assert read_selections(PredictionMarket.FULLTIME_RESULT) == {
        PredictionSelection.DRAW: Decimal("24.82"),
        PredictionSelection.AWAY: Decimal("48.18"),
    }
    assert "is not a percentage" in caplog.text


def test_the_window_states_the_league_and_type_filter_the_provider_honours(
    provider: StubbedProvider,
) -> None:
    """
    GIVEN a prediction window over two competitions
    WHEN it is read
    THEN one paginated read states both filters, the predictions include, and UTC
    """

    serve_predictions(provider, [prediction(FULLTIME_RESULT_TYPE)])

    fetch_prediction_window(WINDOW_START, WINDOW_END, [PREMIER_LEAGUE_ID, BUNDESLIGA_ID])

    assert provider.calls == [
        (
            WINDOW_PATH,
            {
                "filters": (
                    f"fixtureLeagues:{PREMIER_LEAGUE_ID},{BUNDESLIGA_ID};"
                    f"predictionTypes:{REQUESTED_TYPES}"
                ),
                "include": "predictions",
                "per_page": PAGE_SIZE,
                "timezone": PROVIDER_TIMEZONE,
            },
        )
    ]


def test_requesting_no_competition_is_refused_before_any_window_request(
    provider: StubbedProvider,
) -> None:
    """
    GIVEN a configuration that leaves the requested competitions empty
    WHEN a prediction window is read
    THEN the boundary error is raised and no provider request is made
    """

    with pytest.raises(SportmonksError, match="No Sportmonks league"):
        fetch_prediction_window(WINDOW_START, WINDOW_END, [])

    assert provider.calls == []


def test_reliability_joins_the_graded_word_with_the_hit_ratio_behind_it(
    provider: StubbedProvider,
) -> None:
    """
    GIVEN the five predictability entries a competition is graded by
    WHEN the reliability of the competition is read
    THEN each mapped market carries the word of one type joined to the ratio of the other
    """

    serve_grades(
        provider,
        [
            grade_entry(LOG_LOSS_TYPE, {"fulltime_result": 1.0518}),
            grade_entry(HIT_RATIO_TYPE, RECORDED_HIT_RATIOS),
            grade_entry(QUALITY_TYPE, RECORDED_QUALITIES),
            grade_entry(PREDICTIVE_POWER_TYPE, {"fulltime_result": 61.51}),
            grade_entry(MODELS_LOG_LOSS_TYPE, {"fulltime_result": 1.0322}),
        ],
    )

    assert fetch_market_reliability([PREMIER_LEAGUE_ID]) == [
        grade(PredictionMarket.FULLTIME_RESULT, PredictionReliability.MEDIUM, "0.500"),
        grade(PredictionMarket.FIRST_HALF_RESULT, PredictionReliability.POOR, "0.474"),
        grade(PredictionMarket.HALF_TIME_FULL_TIME, PredictionReliability.POOR, "0.211"),
        grade(PredictionMarket.CORRECT_SCORE, PredictionReliability.POOR, "0.105"),
        grade(PredictionMarket.TEAM_TO_SCORE_FIRST, PredictionReliability.GOOD, "0.632"),
        grade(PredictionMarket.BOTH_TEAMS_TO_SCORE, PredictionReliability.HIGH, "0.737"),
        grade(PredictionMarket.OVER_UNDER_1_5, PredictionReliability.GOOD, "0.789"),
        grade(PredictionMarket.OVER_UNDER_2_5, PredictionReliability.MEDIUM, "0.526"),
        grade(PredictionMarket.OVER_UNDER_3_5, PredictionReliability.GOOD, "0.684"),
    ]


def test_a_market_only_one_of_the_two_types_grades_is_not_reported(
    provider: StubbedProvider,
) -> None:
    """
    GIVEN a competition whose word and whose hit ratio each name a market the other omits
    WHEN the reliability of the competition is read
    THEN only the market both types grade is reported, since neither half stands on its own
    """

    serve_grades(
        provider,
        [
            grade_entry(QUALITY_TYPE, {"fulltime_result": "medium", "ht_ft": "poor"}),
            grade_entry(HIT_RATIO_TYPE, {"fulltime_result": 0.5, "correct_score": 0.1052}),
        ],
    )

    assert fetch_market_reliability([PREMIER_LEAGUE_ID]) == [
        grade(PredictionMarket.FULLTIME_RESULT, PredictionReliability.MEDIUM, "0.500")
    ]


def test_a_predictability_key_naming_no_published_market_is_ignored(
    provider: StubbedProvider,
) -> None:
    """
    GIVEN a competition graded only on the per-side markets the platform does not publish
    WHEN the reliability of the competition is read
    THEN no grade is reported, because those keys belong to no market of the vocabulary
    """

    serve_grades(
        provider,
        [
            grade_entry(
                QUALITY_TYPE, {"home_over_under_0_5": "high", "away_over_under_1_5": "good"}
            ),
            grade_entry(
                HIT_RATIO_TYPE, {"home_over_under_0_5": 0.8421, "away_over_under_1_5": 0.7368}
            ),
        ],
    )

    assert fetch_market_reliability([PREMIER_LEAGUE_ID]) == []


def test_a_word_the_boundary_does_not_map_leaves_its_market_ungraded(
    provider: StubbedProvider, caplog: pytest.LogCaptureFixture
) -> None:
    """
    GIVEN a competition graded with a word this boundary maps onto no reliability
    WHEN the reliability of the competition is read
    THEN that market carries no grade, the drop is reported, and the market beside it survives
    """

    caplog.set_level(logging.WARNING, logger=PREDICTIONS_LOGGER)

    serve_grades(
        provider,
        [
            grade_entry(QUALITY_TYPE, {"fulltime_result": "excellent", "ht_ft": "poor"}),
            grade_entry(HIT_RATIO_TYPE, {"fulltime_result": 0.5, "ht_ft": 0.2106}),
        ],
    )

    assert fetch_market_reliability([PREMIER_LEAGUE_ID]) == [
        grade(PredictionMarket.HALF_TIME_FULL_TIME, PredictionReliability.POOR, "0.211")
    ]
    assert "is not a word this boundary maps" in caplog.text


@pytest.mark.parametrize("unstorable", UNSTORABLE_HIT_RATIOS)
def test_a_hit_ratio_the_column_could_not_hold_leaves_its_market_ungraded(
    provider: StubbedProvider, caplog: pytest.LogCaptureFixture, unstorable: object
) -> None:
    """
    GIVEN a competition whose hit ratio is outside the share the column holds, or is no number
    WHEN the reliability of the competition is read
    THEN that market carries no grade and the drop is reported
    """

    caplog.set_level(logging.WARNING, logger=PREDICTIONS_LOGGER)

    serve_grades(
        provider,
        [
            grade_entry(QUALITY_TYPE, {"fulltime_result": "medium"}),
            grade_entry(HIT_RATIO_TYPE, {"fulltime_result": unstorable}),
        ],
    )

    assert fetch_market_reliability([PREMIER_LEAGUE_ID]) == []
    assert "is not a share" in caplog.text


def test_a_competition_returned_without_one_of_the_two_types_stays_ungraded(
    provider: StubbedProvider, caplog: pytest.LogCaptureFixture
) -> None:
    """
    GIVEN a competition the provider grades with a hit ratio but with no predictability word
    WHEN the reliability of the competition is read
    THEN no market is reported and the absent type is named in the report
    """

    caplog.set_level(logging.WARNING, logger=PREDICTIONS_LOGGER)

    serve_grades(provider, [grade_entry(HIT_RATIO_TYPE, RECORDED_HIT_RATIOS)])

    assert fetch_market_reliability([PREMIER_LEAGUE_ID]) == []
    assert f"without prediction type {QUALITY_TYPE}" in caplog.text


def test_the_reliability_of_each_requested_competition_is_read_once(
    provider: StubbedProvider,
) -> None:
    """
    GIVEN two requested competitions and a resource that grades one competition a request
    WHEN their reliability is read
    THEN each competition is read exactly once and both grades are returned together
    """

    entries = [
        grade_entry(QUALITY_TYPE, {"fulltime_result": "medium"}),
        grade_entry(HIT_RATIO_TYPE, {"fulltime_result": 0.5}),
    ]

    serve_grades(provider, entries)

    serve_grades(
        provider,
        [
            grade_entry(QUALITY_TYPE, {"fulltime_result": "good"}, BUNDESLIGA_ID),
            grade_entry(HIT_RATIO_TYPE, {"fulltime_result": 0.6315}, BUNDESLIGA_ID),
        ],
        BUNDESLIGA_ID,
    )

    grades = fetch_market_reliability([PREMIER_LEAGUE_ID, BUNDESLIGA_ID])

    assert [(reliability.league_provider_id, reliability.quality) for reliability in grades] == [
        (PREMIER_LEAGUE_ID, PredictionReliability.MEDIUM),
        (BUNDESLIGA_ID, PredictionReliability.GOOD),
    ]
    assert [path for path, _ in provider.calls] == [
        predictability_path(PREMIER_LEAGUE_ID),
        predictability_path(BUNDESLIGA_ID),
    ]


def test_reliability_states_the_page_size_and_timezone_of_every_provider_read(
    provider: StubbedProvider,
) -> None:
    """
    GIVEN one requested competition
    WHEN its reliability is read
    THEN the request states the page size and UTC rather than leaving either to a default
    """

    serve_grades(provider, [grade_entry(QUALITY_TYPE, {})])

    fetch_market_reliability([PREMIER_LEAGUE_ID])

    assert provider.calls == [
        (
            predictability_path(PREMIER_LEAGUE_ID),
            {"per_page": PAGE_SIZE, "timezone": PROVIDER_TIMEZONE},
        )
    ]


def test_requesting_no_competition_is_refused_before_any_reliability_request(
    provider: StubbedProvider,
) -> None:
    """
    GIVEN a configuration that leaves the requested competitions empty
    WHEN market reliability is read
    THEN the boundary error is raised and no provider request is made
    """

    with pytest.raises(SportmonksError, match="No Sportmonks league"):
        fetch_market_reliability([])

    assert provider.calls == []


def test_the_provider_selection_table_covers_exactly_the_published_vocabulary() -> None:
    """
    GIVEN the provider selection table and the market vocabulary the public contract promises
    WHEN their markets and the selections of each market are compared
    THEN they name the same markets and the same selections, so neither can drift from the other
    """

    mapped = {
        market: sorted(selections.values()) for market, selections in PROVIDER_SELECTIONS.items()
    }

    assert mapped == {
        market: sorted(selections) for market, selections in MARKET_SELECTIONS.items()
    }
