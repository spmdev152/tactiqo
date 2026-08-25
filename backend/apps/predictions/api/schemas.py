from datetime import datetime

from ninja import Schema

from apps.predictions.domain.enums import (
    PredictionMarket,
    PredictionReliability,
    PredictionSelection,
)


class PredictionSelectionResponse(Schema):
    """
    Public projection of the chance one outcome of one market is given.

    Attributes
    ----------
    selection : PredictionSelection
        Outcome the chance belongs to, serialized as the value of the member.
        The closed vocabulary is the platform's own: the provider's per-market
        selection keys, where one key means two different things in two
        markets, never reach this contract.
    probability : float
        Percentage between ``0`` and ``100``, declared ``float`` rather than
        ``Decimal`` so Pydantic renders the stored value as a JSON number. A
        ``Decimal`` serializes as a string, which would make every reader parse
        a number the interface immediately has to draw as a bar.
    """

    selection: PredictionSelection
    probability: float


class PredictionMarketResponse(Schema):
    """
    Public projection of one predicted market of a fixture.

    Attributes
    ----------
    market : PredictionMarket
        Market the outcomes belong to, serialized as the value of the member.
        The provider type identifiers this was read from are deliberately
        absent.
    reliability : PredictionReliability or None
        Graded quality of the provider's model for this market in the fixture's
        competition, ``null`` when there is no grade. Double chance and
        over/under 4.5 never carry one, because the provider publishes no
        predictability entry for them, and any market lacks one until its
        competition has been graded.
    hit_ratio : float or None
        Share between ``0`` and ``1`` of past predictions the model got right
        in that competition, ``null`` under the same condition as
        ``reliability`` and declared ``float`` for the same reason as
        ``probability``.
    selections : list of PredictionSelectionResponse
        Outcomes of the market, in the order the platform promises rather than
        the order they were stored or read.
    """

    market: PredictionMarket
    reliability: PredictionReliability | None
    hit_ratio: float | None
    selections: list[PredictionSelectionResponse]


class FixturePredictionsResponse(Schema):
    """
    Public projection of every prediction stored for one fixture.

    Attributes
    ----------
    fixture_id : int
        Primary key of the fixture, echoed so a client holding the payload
        alone still knows what it describes.
    synchronized_at : datetime or None
        Instant the payload last agreed with the provider, serialized as an
        ISO 8601 UTC timestamp, and ``null`` when the fixture carries no
        prediction. Prediction availability is fixture-dependent, so an empty
        payload is an ordinary answer rather than a failure.
    markets : list of PredictionMarketResponse
        Predicted markets, in the order the platform promises and empty when
        the fixture has none. A market with nothing stored is left out rather
        than sent empty, so the interface never has to decide whether an empty
        list of outcomes deserves a heading.
    """

    fixture_id: int
    synchronized_at: datetime | None
    markets: list[PredictionMarketResponse]
