from decimal import Decimal

import pytest
from django.db import IntegrityError

from apps.fixtures.models import Fixture, League
from apps.predictions.domain.enums import (
    PredictionMarket,
    PredictionReliability,
    PredictionSelection,
)
from apps.predictions.models import (
    HIT_RATIO_CEILING,
    PROBABILITY_CEILING,
    FixturePrediction,
    LeagueMarketReliability,
)
from tests.unit.fixtures.conftest import PREMIER_LEAGUE
from tests.unit.predictions.conftest import (
    FIXTURE_PROVIDER_ID,
    SYNCHRONIZED_AT,
    seed_fixtures,
    seed_leagues,
)

SMALLEST_PERCENTAGE_STEP = Decimal("0.01")

SMALLEST_RATIO_STEP = Decimal("0.001")

HALF = Decimal("50.00")


def store_prediction(
    fixture: Fixture,
    percentage: Decimal,
    *,
    market: PredictionMarket = PredictionMarket.FULLTIME_RESULT,
    selection: PredictionSelection = PredictionSelection.HOME,
) -> FixturePrediction:
    """
    Write one probability row directly, bypassing the repository upsert.

    The constraints are what the upsert relies on, so they are exercised against
    a plain write: the repository collapses a duplicate natural key and clamps
    nothing, which is exactly why the database has to be the one refusing.

    Parameters
    ----------
    fixture : Fixture
        Match the row belongs to.
    percentage : Decimal
        Probability to write, valid or otherwise.
    market : PredictionMarket
        Market the selection belongs to.
    selection : PredictionSelection
        Outcome within that market.

    Returns
    -------
    FixturePrediction
        Stored row.
    """

    return FixturePrediction.objects.create(
        fixture=fixture,
        market=market,
        selection=selection,
        probability=percentage,
        synchronized_at=SYNCHRONIZED_AT,
    )


def store_grade(
    league: League,
    hit_ratio: Decimal,
    *,
    market: PredictionMarket = PredictionMarket.FULLTIME_RESULT,
    quality: PredictionReliability = PredictionReliability.MEDIUM,
) -> LeagueMarketReliability:
    """
    Write one reliability row directly, bypassing the repository upsert.

    Parameters
    ----------
    league : League
        Competition the row belongs to.
    hit_ratio : Decimal
        Share to write, valid or otherwise.
    market : PredictionMarket
        Market the grade applies to.
    quality : PredictionReliability
        Grade to write.

    Returns
    -------
    LeagueMarketReliability
        Stored row.
    """

    return LeagueMarketReliability.objects.create(
        league=league,
        market=market,
        quality=quality,
        hit_ratio=hit_ratio,
        synchronized_at=SYNCHRONIZED_AT,
    )


@pytest.mark.django_db
def test_the_database_refuses_a_second_probability_for_one_selection() -> None:
    """
    GIVEN a stored probability for one selection of a fixture
    WHEN a second row is written for the same fixture, market, and selection
    THEN the database refuses it, which is what makes the upsert idempotent
    """

    fixture = seed_fixtures()[FIXTURE_PROVIDER_ID]

    store_prediction(fixture, HALF)

    with pytest.raises(IntegrityError, match="selection"):
        store_prediction(fixture, Decimal("40.00"))


@pytest.mark.django_db
def test_the_database_accepts_a_probability_of_exactly_a_hundred() -> None:
    """
    GIVEN a market whose only selection the model gives every chance to
    WHEN a probability of exactly a hundred is written
    THEN the row is stored, because the bound is inclusive
    """

    fixture = seed_fixtures()[FIXTURE_PROVIDER_ID]

    store_prediction(fixture, PROBABILITY_CEILING)

    assert FixturePrediction.objects.get().probability == PROBABILITY_CEILING


@pytest.mark.django_db
def test_the_database_refuses_a_probability_above_a_hundred() -> None:
    """
    GIVEN a fixture whose probabilities are stored as percentages
    WHEN a probability one step above a hundred is written
    THEN the database refuses it rather than storing an unrenderable bar
    """

    fixture = seed_fixtures()[FIXTURE_PROVIDER_ID]

    with pytest.raises(IntegrityError, match="fixture_prediction_probability_range_check"):
        store_prediction(fixture, PROBABILITY_CEILING + SMALLEST_PERCENTAGE_STEP)


@pytest.mark.django_db
def test_the_database_refuses_a_negative_probability() -> None:
    """
    GIVEN a fixture whose probabilities are stored as percentages
    WHEN a probability one step below nought is written
    THEN the database refuses it rather than storing a negative chance
    """

    fixture = seed_fixtures()[FIXTURE_PROVIDER_ID]

    with pytest.raises(IntegrityError, match="fixture_prediction_probability_range_check"):
        store_prediction(fixture, -SMALLEST_PERCENTAGE_STEP)


@pytest.mark.django_db
def test_the_database_refuses_a_second_grade_for_one_market() -> None:
    """
    GIVEN a stored grade for one market of a competition
    WHEN a second row is written for the same competition and market
    THEN the database refuses it, which is what makes the upsert idempotent
    """

    league = seed_leagues()[PREMIER_LEAGUE.provider_id]

    store_grade(league, Decimal("0.500"))

    with pytest.raises(IntegrityError, match="market"):
        store_grade(league, Decimal("0.612"), quality=PredictionReliability.GOOD)


@pytest.mark.django_db
def test_the_database_refuses_a_hit_ratio_above_one() -> None:
    """
    GIVEN a competition whose hit ratio is stored as a share
    WHEN a ratio one step above one is written
    THEN the database refuses it rather than storing a share nobody can hit
    """

    league = seed_leagues()[PREMIER_LEAGUE.provider_id]

    with pytest.raises(IntegrityError, match="league_market_reliability_hit_ratio_range_check"):
        store_grade(league, HIT_RATIO_CEILING + SMALLEST_RATIO_STEP)


@pytest.mark.django_db
def test_the_database_refuses_a_negative_hit_ratio() -> None:
    """
    GIVEN a competition whose hit ratio is stored as a share
    WHEN a ratio one step below nought is written
    THEN the database refuses it rather than storing a negative share
    """

    league = seed_leagues()[PREMIER_LEAGUE.provider_id]

    with pytest.raises(IntegrityError, match="league_market_reliability_hit_ratio_range_check"):
        store_grade(league, -SMALLEST_RATIO_STEP)
