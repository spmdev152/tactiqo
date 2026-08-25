from decimal import Decimal
from typing import ClassVar

from django.db import models

from apps.predictions.domain.enums import (
    PredictionMarket,
    PredictionReliability,
    PredictionSelection,
)

MARKET_LENGTH = 24

SELECTION_LENGTH = 24

RELIABILITY_LENGTH = 8

PROBABILITY_CEILING = Decimal("100")

HIT_RATIO_CEILING = Decimal("1")


class FixturePrediction(models.Model):
    """
    Probability the provider's model gives one selection of one market.

    A fixture carries one row per selection, fifty of them across the eleven
    markets the platform publishes, so the table is the fixture table an order
    of magnitude over. It is deliberately not a JSON column on the fixture: the
    interface reads a fixture's markets one at a time and the reconciliation
    below deletes at the granularity of a selection, both of which a document
    would make into a read-modify-write of the whole set.

    Availability is a property of the fixture and of when it is asked about, not
    a defect. The provider publishes nothing for a fixture more than roughly a
    fortnight out, so the absence of every row for a fixture is the ordinary
    state and the API reports it as such.

    Attributes
    ----------
    fixture : Fixture
        Match the probability belongs to. Cascading on delete because a
        probability is meaningless without the match it is about, and the
        fixture synchronization genuinely deletes a match the provider stops
        listing.
    market : str
        Market the selection belongs to, one of ``PredictionMarket``. The
        provider's numeric type id is mapped onto this vocabulary inside the
        Sportmonks boundary and never stored.
    selection : str
        Outcome within the market, one of ``PredictionSelection``.
    probability : Decimal
        Chance of the selection as a percentage between nought and a hundred,
        to two decimal places, which is the precision the provider publishes.
        Stored exactly rather than as a float because it is displayed as a
        number a reader compares, and a binary float would print a value the
        provider never sent.
    synchronized_at : datetime
        Instant the last synchronization wrote this row. It is also the
        reconciliation marker: a run stamps every row it writes and then deletes
        the rows of the fixtures it read that still carry an earlier stamp, so a
        selection the provider withdraws leaves the table without the run having
        to enumerate what is missing.

    Methods
    -------
    __str__() -> str
        Return the market, the selection, and the probability.
    """

    fixture = models.ForeignKey(
        "fixtures.Fixture", on_delete=models.CASCADE, related_name="predictions"
    )

    market = models.CharField(max_length=MARKET_LENGTH, choices=PredictionMarket.choices)
    selection = models.CharField(max_length=SELECTION_LENGTH, choices=PredictionSelection.choices)

    probability = models.DecimalField(max_digits=5, decimal_places=2)

    synchronized_at = models.DateTimeField()

    class Meta:
        """
        Admin labels, ordering, read indexes, and invariants of the predictions.

        Attributes
        ----------
        verbose_name : str
            Singular label shown in the Django admin.
        verbose_name_plural : str
            Plural label shown in the Django admin.
        ordering : list of str
            Default ordering, grouped by fixture then by market, broken by
            primary key. It is a deterministic order rather than the published
            one: display order is a property of the vocabulary, which the
            application layer applies, because neither the market order nor the
            selection order within a market is alphabetical.
        constraints : list of BaseConstraint
            Uniqueness of a selection within a market within a fixture, which is
            what makes the upsert idempotent, and the invariant that a
            probability is a percentage. The bound is enforced here because a
            probability outside it is unrenderable on a bar whose width is that
            percentage, and every future writer inherits the rule.

            No separate index is declared: the unique constraint is backed by an
            index on ``(fixture, market, selection)``, whose leftmost prefixes
            already serve both reads this table has, every selection of one
            fixture and the reconciliation delete over the fixtures a run read.
        """

        verbose_name = "fixture prediction"
        verbose_name_plural = "fixture predictions"
        ordering: ClassVar[list[str]] = ["fixture", "market", "id"]

        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=["fixture", "market", "selection"],
                name="fixture_prediction_selection_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(probability__gte=0, probability__lte=PROBABILITY_CEILING),
                name="fixture_prediction_probability_range_check",
            ),
        ]

    def __str__(self) -> str:
        """
        Return the market, the selection, and the probability.

        Returns
        -------
        str
            Market, selection, and the probability as a percentage.
        """

        return f"{self.market}/{self.selection} at {self.probability}%"


class LeagueMarketReliability(models.Model):
    """
    How the provider's model has performed on one market in one competition.

    This is the counterweight the probabilities are shown with. It is graded per
    competition rather than per fixture, so it is a small table of at most
    fifty-five rows for five leagues and eleven markets, refreshed on its own
    schedule from its own provider resource.

    Two of the eleven markets are absent by construction: the provider's
    payload has no entry for double chance or for over/under 4.5, so those
    markets carry no row and the API reports the reliability as unknown rather
    than defaulting it to a grade nobody measured.

    Attributes
    ----------
    league : League
        Competition the grade applies to. Cascading on delete for the same
        reason a prediction cascades: a grade without its competition means
        nothing.
    market : str
        Market the grade applies to, one of ``PredictionMarket``.
    quality : str
        Grade the provider publishes, one of ``PredictionReliability``.
    hit_ratio : Decimal
        Share of the provider's predictions on this market that proved correct,
        between nought and one to three decimal places. It is the number behind
        the grade, so a reader who wants more than a word has it.
    synchronized_at : datetime
        Instant the last synchronization wrote this row, and the reconciliation
        marker, exactly as on ``FixturePrediction``.

    Methods
    -------
    __str__() -> str
        Return the market and the grade.
    """

    league = models.ForeignKey(
        "fixtures.League", on_delete=models.CASCADE, related_name="market_reliabilities"
    )

    market = models.CharField(max_length=MARKET_LENGTH, choices=PredictionMarket.choices)

    quality = models.CharField(max_length=RELIABILITY_LENGTH, choices=PredictionReliability.choices)

    hit_ratio = models.DecimalField(max_digits=4, decimal_places=3)

    synchronized_at = models.DateTimeField()

    class Meta:
        """
        Admin labels, ordering, and invariants of the reliability grades.

        Attributes
        ----------
        verbose_name : str
            Singular label shown in the Django admin.
        verbose_name_plural : str
            Plural label shown in the Django admin.
        ordering : list of str
            Default ordering, grouped by competition then by market.
        constraints : list of BaseConstraint
            Uniqueness of a market within a competition, which is what makes the
            upsert idempotent, and the invariant that a hit ratio is a share.
        """

        verbose_name = "league market reliability"
        verbose_name_plural = "league market reliabilities"
        ordering: ClassVar[list[str]] = ["league", "market"]

        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=["league", "market"],
                name="league_market_reliability_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(hit_ratio__gte=0, hit_ratio__lte=HIT_RATIO_CEILING),
                name="league_market_reliability_hit_ratio_range_check",
            ),
        ]

    def __str__(self) -> str:
        """
        Return the market and the grade.

        Returns
        -------
        str
            Market and the grade the provider published for it.
        """

        return f"{self.market} is {self.quality}"
