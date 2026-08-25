from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from apps.fixtures.models import Fixture
from apps.predictions.domain.enums import (
    PredictionMarket,
    PredictionReliability,
    PredictionSelection,
)
from apps.predictions.domain.markets import MARKET_ORDER, MARKET_SELECTIONS
from apps.predictions.models import FixturePrediction, LeagueMarketReliability

StoredProbabilities = dict[str, dict[str, Decimal]]

MarketGrades = dict[str, tuple[str, Decimal]]


@dataclass(frozen=True, slots=True)
class SelectionProbability:
    """
    Chance the provider's model gives one outcome of one market.

    Attributes
    ----------
    selection : PredictionSelection
        Outcome the chance belongs to, named in the platform's own vocabulary.
    probability : Decimal
        Percentage between ``0`` and ``100`` with two decimals, kept exact
        because it is read straight from storage and only the HTTP boundary
        decides how to render it.
    """

    selection: PredictionSelection
    probability: Decimal


@dataclass(frozen=True, slots=True)
class MarketProbabilities:
    """
    One market of a fixture, with how much the competition's model is worth.

    Attributes
    ----------
    market : PredictionMarket
        Market the outcomes belong to.
    reliability : PredictionReliability or None
        Graded quality of the provider's model for this market in the
        competition the fixture belongs to, ``None`` when there is no grade.
        Two markets never carry one, because the provider publishes no
        predictability entry for them at all, and any market lacks one until
        the competition has been graded once.
    hit_ratio : Decimal or None
        Share between ``0`` and ``1`` of past predictions this market's model
        got right in the competition, ``None`` under the same condition as
        ``reliability``. The two are stored on one row, so a reader never has
        to render half a grade.
    selections : list of SelectionProbability
        Outcomes in the order ``MARKET_SELECTIONS`` promises, restricted to the
        ones actually stored.
    """

    market: PredictionMarket
    reliability: PredictionReliability | None
    hit_ratio: Decimal | None
    selections: list[SelectionProbability]


@dataclass(frozen=True, slots=True)
class FixtureProbabilities:
    """
    Every prediction stored for one fixture, ready to be serialized.

    Attributes
    ----------
    fixture_id : int
        Primary key of the fixture the markets belong to.
    synchronized_at : datetime or None
        Newest instant among the stored rows, which is when the payload last
        agreed with the provider, and ``None`` when nothing is stored. It is
        taken from the rows rather than from a run, because a synchronization
        that read the fixture and wrote nothing tells a reader nothing about
        the numbers in front of them.
    markets : list of MarketProbabilities
        Markets in the order ``MARKET_ORDER`` promises, empty when the fixture
        carries no prediction.
    """

    fixture_id: int
    synchronized_at: datetime | None
    markets: list[MarketProbabilities]


def get_fixture_predictions(fixture_id: int) -> FixtureProbabilities | None:
    """
    Return every prediction stored for a fixture, in the contracted order.

    Three statements answer the whole payload however many markets are stored:
    one resolving the fixture and the competition it belongs to, one reading
    the stored selections, and one reading that competition's grades. Grouping
    and ordering then happen in memory against ``MARKET_ORDER`` and
    ``MARKET_SELECTIONS``, so eleven markets cost exactly what one does, and a
    fixture that does not exist costs the first statement alone. Both reads
    clear the model's default ordering, because an ``ORDER BY`` whose result is
    poured straight into a dictionary is work the database does for nobody.

    Each read takes only the columns the payload needs. A fixture carrying
    every market stores roughly fifty rows, and instantiating fifty model
    objects in order to read three fields out of each of them is work no reader
    ever sees.

    A market with nothing stored is left out rather than sent empty, and so is
    a selection with nothing stored, because an absent number and a number the
    interface cannot draw are the same thing to the reader. Iterating the
    contracted order rather than the stored rows also means a selection the
    provider invents can never reach the response.

    The graded quality is turned into ``PredictionReliability`` without the
    defensive treatment the market gets, and the asymmetry is deliberate rather
    than an oversight. The market is iterated out of ``MARKET_ORDER`` because
    the contracted order has to be applied anyway, so passing over a value that
    order does not name costs nothing there. The quality has no such loop to
    hide behind and needs none: the column declares the enumeration as its
    ``choices``, and its one writer fills it from a closed mapping of the four
    words the provider publishes, logging and dropping anything else. A word
    outside the enumeration is therefore not a state this system can reach, a
    branch for it would be unreachable, and swallowing it would hide a
    corrupted column rather than report it.

    Parameters
    ----------
    fixture_id : int
        Primary key of the fixture whose predictions are wanted.

    Returns
    -------
    FixtureProbabilities or None
        Stored predictions, or ``None`` when no fixture carries that key. A
        fixture that exists but has never been predicted answers with an empty
        payload instead, because "there is nothing to show" and "there is
        nothing to ask about" are different answers.
    """

    league_id = Fixture.objects.filter(pk=fixture_id).values_list("league_id", flat=True).first()

    if league_id is None:
        return None

    probabilities: StoredProbabilities = {}
    synchronized_at: datetime | None = None

    stored = (
        FixturePrediction.objects.filter(fixture_id=fixture_id)
        .order_by()
        .values_list("market", "selection", "probability", "synchronized_at")
    )

    for market, selection, probability, stamp in stored:
        probabilities.setdefault(market, {})[selection] = probability

        if synchronized_at is None or stamp > synchronized_at:
            synchronized_at = stamp

    stored_grades = (
        LeagueMarketReliability.objects.filter(league_id=league_id)
        .order_by()
        .values_list("market", "quality", "hit_ratio")
    )

    grades: MarketGrades = {
        market: (quality, hit_ratio) for market, quality, hit_ratio in stored_grades
    }

    markets: list[MarketProbabilities] = []

    for market in MARKET_ORDER:
        stored_selections = probabilities.get(market)

        if not stored_selections:
            continue

        quality, hit_ratio = grades.get(market, (None, None))

        markets.append(
            MarketProbabilities(
                market=market,
                reliability=PredictionReliability(quality) if quality is not None else None,
                hit_ratio=hit_ratio,
                selections=[
                    SelectionProbability(
                        selection=selection, probability=stored_selections[selection]
                    )
                    for selection in MARKET_SELECTIONS[market]
                    if selection in stored_selections
                ],
            )
        )

    return FixtureProbabilities(
        fixture_id=fixture_id, synchronized_at=synchronized_at, markets=markets
    )
