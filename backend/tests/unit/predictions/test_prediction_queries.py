from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal

import pytest
from pytest_django.fixtures import DjangoAssertNumQueries

from apps.fixtures.models import Fixture
from apps.predictions.application.queries import get_fixture_predictions
from apps.predictions.domain.enums import (
    PredictionMarket,
    PredictionReliability,
    PredictionSelection,
)
from apps.predictions.domain.markets import MARKET_ORDER, MARKET_SELECTIONS
from apps.predictions.models import FixturePrediction
from integrations.sportmonks.predictions import ProviderProbability
from tests.unit.fixtures.conftest import LA_LIGA, PREMIER_LEAGUE
from tests.unit.predictions.conftest import (
    FIXTURE_PROVIDER_ID,
    LATER_SYNCHRONIZED_AT,
    SYNCHRONIZED_AT,
    fixture_probabilities,
    probability,
    reliability,
    seed_fixtures,
    seed_leagues,
    store_predictions,
    store_reliability,
)

EXPECTED_QUERY_COUNT = 3

SECOND_FIXTURE_PROVIDER_ID = FIXTURE_PROVIDER_ID + 1

HOME_CHANCE = probability(PredictionMarket.FULLTIME_RESULT, PredictionSelection.HOME, "26.96")


def store_outcomes(
    fixture: Fixture,
    outcomes: Sequence[ProviderProbability],
    synchronized_at: datetime = SYNCHRONIZED_AT,
) -> None:
    """
    Persist outcomes for one fixture through a single reconciled run.

    Everything a test stores for one fixture goes through one call, because the
    reconciliation stamps every row a run writes and then deletes the earlier
    rows of the fixtures that run read. A second call for the same fixture
    would therefore replace what the first one wrote instead of adding to it.

    Parameters
    ----------
    fixture : Fixture
        Stored fixture the outcomes belong to, addressed by the provider
        identifier the boundary reads it under.
    outcomes : sequence of ProviderProbability
        Outcomes to store, in the order the run reads them, which is the order
        the rows are then stored in.
    synchronized_at : datetime
        Stamp the run writes onto every row.
    """

    store_predictions([fixture_probabilities(fixture.sportmonks_id, outcomes)], synchronized_at)


def store_grade(
    league_provider_id: int,
    market: PredictionMarket,
    quality: PredictionReliability,
    hit_ratio: str,
) -> None:
    """
    Persist how much the provider's model for one market is worth in a league.

    Parameters
    ----------
    league_provider_id : int
        Provider identifier of the competition the grade applies to.
    market : PredictionMarket
        Market the grade applies to.
    quality : PredictionReliability
        Graded quality of the model.
    hit_ratio : str
        Share of past predictions the model got right, as a decimal string, so
        the stored scale is written rather than inherited from a float literal.
    """

    store_reliability([reliability(league_provider_id, market, quality, hit_ratio)])


def restamp_read_position(fixture: Fixture, position: int) -> None:
    """
    Re-stamp one of a fixture's rows, chosen by where the query reads it.

    A synchronization run stamps every row it writes with its own instant, so a
    fixture whose rows carry different stamps is not a state the writer can
    produce and has to be written directly. The row is chosen by its position
    in the order the query reads the rows in rather than by its selection,
    because the point is that no position is privileged and the writer is free
    to insert its rows in any order it likes.

    Parameters
    ----------
    fixture : Fixture
        Stored fixture whose rows are read.
    position : int
        Index into the read order, negative counting from the end.
    """

    keys = list(FixturePrediction.objects.filter(fixture=fixture).values_list("pk", flat=True))

    FixturePrediction.objects.filter(pk=keys[position]).update(
        synchronized_at=LATER_SYNCHRONIZED_AT
    )


def stored_markets(fixture_id: int) -> list[PredictionMarket]:
    """
    Read a fixture's payload and return the markets it carries, in order.

    Parameters
    ----------
    fixture_id : int
        Primary key of the fixture to read.

    Returns
    -------
    list of PredictionMarket
        Markets of the payload, in the order the query emitted them.
    """

    predictions = get_fixture_predictions(fixture_id)

    assert predictions is not None

    return [market.market for market in predictions.markets]


@pytest.mark.django_db
def test_get_fixture_predictions_returns_none_for_an_unknown_fixture() -> None:
    """
    GIVEN a stored fixture and the identifier that follows its primary key
    WHEN the predictions of that identifier are read
    THEN nothing comes back, which is how the caller learns there is no fixture
    """

    fixture = seed_fixtures()[FIXTURE_PROVIDER_ID]

    assert get_fixture_predictions(fixture.pk + 1) is None


@pytest.mark.django_db
def test_get_fixture_predictions_returns_an_empty_payload_for_an_unpredicted_fixture() -> None:
    """
    GIVEN a stored fixture nothing has ever predicted
    WHEN its predictions are read
    THEN a payload with no markets and no stamp comes back rather than nothing
    """

    fixture = seed_fixtures()[FIXTURE_PROVIDER_ID]

    predictions = get_fixture_predictions(fixture.pk)

    assert predictions is not None
    assert (predictions.fixture_id, predictions.synchronized_at, predictions.markets) == (
        fixture.pk,
        None,
        [],
    )


@pytest.mark.django_db
def test_get_fixture_predictions_reads_every_market_in_three_queries(
    django_assert_num_queries: DjangoAssertNumQueries,
) -> None:
    """
    GIVEN a fixture carrying all eleven markets in a graded competition
    WHEN its predictions are read
    THEN three statements answer the whole payload
    """

    fixture = seed_fixtures()[FIXTURE_PROVIDER_ID]

    store_outcomes(
        fixture,
        [probability(market, MARKET_SELECTIONS[market][0], "50.00") for market in MARKET_ORDER],
    )

    store_grade(
        PREMIER_LEAGUE.provider_id,
        PredictionMarket.FULLTIME_RESULT,
        PredictionReliability.MEDIUM,
        "0.500",
    )

    with django_assert_num_queries(EXPECTED_QUERY_COUNT):
        predictions = get_fixture_predictions(fixture.pk)

    assert predictions is not None
    assert len(predictions.markets) == len(MARKET_ORDER)


@pytest.mark.django_db
def test_get_fixture_predictions_reads_one_market_in_the_same_three_queries(
    django_assert_num_queries: DjangoAssertNumQueries,
) -> None:
    """
    GIVEN a fixture carrying a single market
    WHEN its predictions are read
    THEN the same three statements answer it, so the cost is not per market
    """

    fixture = seed_fixtures()[FIXTURE_PROVIDER_ID]

    store_outcomes(fixture, [HOME_CHANCE])

    with django_assert_num_queries(EXPECTED_QUERY_COUNT):
        predictions = get_fixture_predictions(fixture.pk)

    assert predictions is not None
    assert len(predictions.markets) == 1


@pytest.mark.django_db
def test_get_fixture_predictions_orders_the_markets_as_the_contract_promises() -> None:
    """
    GIVEN a fixture whose markets were stored in the reverse contracted order
    WHEN its predictions are read
    THEN they come back in the contracted order rather than the stored one
    """

    fixture = seed_fixtures()[FIXTURE_PROVIDER_ID]

    store_outcomes(
        fixture,
        [
            probability(market, MARKET_SELECTIONS[market][0], "50.00")
            for market in reversed(MARKET_ORDER)
        ],
    )

    assert stored_markets(fixture.pk) == list(MARKET_ORDER)


@pytest.mark.django_db
def test_get_fixture_predictions_orders_the_selections_within_a_market() -> None:
    """
    GIVEN a full-time result whose outcomes were stored away, home, then draw
    WHEN its predictions are read
    THEN the outcomes come back home, draw, then away as the contract promises
    """

    fixture = seed_fixtures()[FIXTURE_PROVIDER_ID]

    store_outcomes(
        fixture,
        [
            probability(PredictionMarket.FULLTIME_RESULT, PredictionSelection.AWAY, "48.18"),
            HOME_CHANCE,
            probability(PredictionMarket.FULLTIME_RESULT, PredictionSelection.DRAW, "24.82"),
        ],
    )

    predictions = get_fixture_predictions(fixture.pk)

    assert predictions is not None
    assert [
        (selection.selection, selection.probability)
        for selection in predictions.markets[0].selections
    ] == [
        (PredictionSelection.HOME, Decimal("26.96")),
        (PredictionSelection.DRAW, Decimal("24.82")),
        (PredictionSelection.AWAY, Decimal("48.18")),
    ]


@pytest.mark.django_db
def test_get_fixture_predictions_omits_a_market_with_nothing_stored() -> None:
    """
    GIVEN a fixture carrying two of the eleven markets
    WHEN its predictions are read
    THEN only those two come back, rather than nine markets with no outcomes
    """

    fixture = seed_fixtures()[FIXTURE_PROVIDER_ID]

    store_outcomes(
        fixture,
        [
            probability(PredictionMarket.BOTH_TEAMS_TO_SCORE, PredictionSelection.YES, "54.00"),
            HOME_CHANCE,
        ],
    )

    assert stored_markets(fixture.pk) == [
        PredictionMarket.FULLTIME_RESULT,
        PredictionMarket.BOTH_TEAMS_TO_SCORE,
    ]


@pytest.mark.django_db
def test_get_fixture_predictions_omits_a_selection_with_nothing_stored() -> None:
    """
    GIVEN a full-time result carrying a home and an away chance but no draw
    WHEN its predictions are read
    THEN the market comes back with two outcomes rather than an empty draw
    """

    fixture = seed_fixtures()[FIXTURE_PROVIDER_ID]

    store_outcomes(
        fixture,
        [
            HOME_CHANCE,
            probability(PredictionMarket.FULLTIME_RESULT, PredictionSelection.AWAY, "48.18"),
        ],
    )

    predictions = get_fixture_predictions(fixture.pk)

    assert predictions is not None
    assert [selection.selection for selection in predictions.markets[0].selections] == [
        PredictionSelection.HOME,
        PredictionSelection.AWAY,
    ]


@pytest.mark.django_db
def test_get_fixture_predictions_grades_only_the_markets_the_competition_covers() -> None:
    """
    GIVEN a fixture whose competition grades its full-time result alone
    WHEN its predictions are read
    THEN the graded market carries the grade and the other carries neither half
    """

    fixture = seed_fixtures()[FIXTURE_PROVIDER_ID]

    store_outcomes(
        fixture,
        [
            HOME_CHANCE,
            probability(PredictionMarket.DOUBLE_CHANCE, PredictionSelection.HOME_OR_DRAW, "51.78"),
        ],
    )

    store_grade(
        PREMIER_LEAGUE.provider_id,
        PredictionMarket.FULLTIME_RESULT,
        PredictionReliability.MEDIUM,
        "0.500",
    )

    predictions = get_fixture_predictions(fixture.pk)

    assert predictions is not None
    assert [(market.reliability, market.hit_ratio) for market in predictions.markets] == [
        (PredictionReliability.MEDIUM, Decimal("0.500")),
        (None, None),
    ]


@pytest.mark.django_db
def test_get_fixture_predictions_ignores_the_grades_of_another_competition() -> None:
    """
    GIVEN two competitions grading the same market at different qualities
    WHEN a fixture of the first competition is read
    THEN it carries its own competition's grade rather than the other one's
    """

    seed_leagues([PREMIER_LEAGUE, LA_LIGA])

    fixture = seed_fixtures()[FIXTURE_PROVIDER_ID]

    store_outcomes(fixture, [HOME_CHANCE])

    store_grade(
        PREMIER_LEAGUE.provider_id,
        PredictionMarket.FULLTIME_RESULT,
        PredictionReliability.MEDIUM,
        "0.500",
    )

    store_grade(
        LA_LIGA.provider_id,
        PredictionMarket.FULLTIME_RESULT,
        PredictionReliability.HIGH,
        "0.750",
    )

    predictions = get_fixture_predictions(fixture.pk)

    assert predictions is not None
    assert (predictions.markets[0].reliability, predictions.markets[0].hit_ratio) == (
        PredictionReliability.MEDIUM,
        Decimal("0.500"),
    )


@pytest.mark.django_db
def test_get_fixture_predictions_reports_the_newest_stamp_wherever_it_sits() -> None:
    """
    GIVEN two predicted fixtures, one re-stamped on its first read row and one on its last
    WHEN each fixture's predictions are read
    THEN both report the newer stamp, so neither end of the read order is assumed
    """

    fixtures = seed_fixtures([FIXTURE_PROVIDER_ID, SECOND_FIXTURE_PROVIDER_ID])

    outcomes = [
        HOME_CHANCE,
        probability(PredictionMarket.FULLTIME_RESULT, PredictionSelection.DRAW, "24.82"),
        probability(PredictionMarket.FULLTIME_RESULT, PredictionSelection.AWAY, "48.18"),
    ]

    bumped_first = fixtures[FIXTURE_PROVIDER_ID]
    bumped_last = fixtures[SECOND_FIXTURE_PROVIDER_ID]

    store_outcomes(bumped_first, outcomes)
    store_outcomes(bumped_last, outcomes)

    restamp_read_position(bumped_first, 0)
    restamp_read_position(bumped_last, -1)

    payloads = [get_fixture_predictions(bumped_first.pk), get_fixture_predictions(bumped_last.pk)]

    assert [payload.synchronized_at for payload in payloads if payload is not None] == [
        LATER_SYNCHRONIZED_AT,
        LATER_SYNCHRONIZED_AT,
    ]


@pytest.mark.django_db
def test_get_fixture_predictions_reports_the_stamp_of_its_own_fixture() -> None:
    """
    GIVEN two fixtures predicted by runs whose stamps differ
    WHEN each fixture's predictions are read
    THEN each payload reports its own run's stamp rather than the newer one
    """

    fixtures = seed_fixtures([FIXTURE_PROVIDER_ID, SECOND_FIXTURE_PROVIDER_ID])

    earlier = fixtures[FIXTURE_PROVIDER_ID]
    later = fixtures[SECOND_FIXTURE_PROVIDER_ID]

    store_outcomes(earlier, [HOME_CHANCE], SYNCHRONIZED_AT)
    store_outcomes(later, [HOME_CHANCE], LATER_SYNCHRONIZED_AT)

    payloads = [get_fixture_predictions(earlier.pk), get_fixture_predictions(later.pk)]

    assert [payload.synchronized_at for payload in payloads if payload is not None] == [
        SYNCHRONIZED_AT,
        LATER_SYNCHRONIZED_AT,
    ]
