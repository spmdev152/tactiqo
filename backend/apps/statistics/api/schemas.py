from datetime import datetime

from ninja import Schema

from apps.statistics.domain.enums import FormFamily, FormMetric, FormRange, FormScope
from apps.statistics.domain.metrics import FAMILY_METRICS, FAMILY_ORDER


class MetricValueResponse(Schema):
    """
    Public projection of one figure of one form sample.

    Attributes
    ----------
    metric : FormMetric
        Metric the figure belongs to, serialized as the value of the member. The
        closed vocabulary is the platform's own: the provider type identifiers
        the columns were read from never reach this contract.
    value : float
        Figure the club recorded, rounded to two decimals. Whether it is a
        per-match average or a percentage is not stated here: the interface owns
        the unit, so a client renders ``possession`` as a share and ``shots`` as
        an average from its own vocabulary rather than from a flag it would have
        to be handed on every metric of every sample.
    opposed_value : float or None
        Same figure for the opposition of the counted matches, ``null`` for
        every metric that carries no opposing figure. Possession never carries
        one, because its two sides sum to a hundred and the opposing share would
        say nothing the published one does not.
    """

    metric: FormMetric
    value: float
    opposed_value: float | None


class FormSampleResponse(Schema):
    """
    Public projection of one club's form over one range and one scope.

    Attributes
    ----------
    range : FormRange
        Range of matches the sample covers, serialized as the value of the
        member. The field shadows a Python builtin and is named for the wire
        anyway, because the contract is what both sides of it read.
    scope : FormScope
        Whether the sample counts every match or only the ones played on the
        side the club takes in this fixture, serialized as the value of the
        member.
    matches_counted : int
        Matches the figures are an average over, so a reader can tell a club
        three matches into a season from one thirty matches in. It is ``0`` for a
        club with no qualifying history, and every figure is then ``0.0``.
    metrics : tuple of MetricValueResponse
        Every metric the platform publishes, in the promised order and always
        complete, so the interface never has to decide what a missing metric
        means. Declared as a tuple because the query yields one, which spares
        Pydantic a list it would only have to copy.
    """

    range: FormRange
    scope: FormScope
    matches_counted: int
    metrics: tuple[MetricValueResponse, ...]


class TeamFormResponse(Schema):
    """
    Public projection of every sample of one club of the fixture.

    Attributes
    ----------
    team_id : int
        Primary key of the club, echoed so a client holding the payload alone
        can match each half of it against the fixture it already has.
    samples : tuple of FormSampleResponse
        Samples in the promised order, always the same grid for both clubs of a
        fixture so the interface can draw them against each other without
        aligning two different shapes first.
    """

    team_id: int
    samples: tuple[FormSampleResponse, ...]


class MetricFamilyResponse(Schema):
    """
    Public projection of one heading of the published metric vocabulary.

    Attributes
    ----------
    family : FormFamily
        Heading the metrics are grouped under, serialized as the value of the
        member.
    metrics : tuple of FormMetric
        Metrics of the heading, in the promised order. Naming them here is what
        lets the interface group and order twenty-five figures without holding a
        second copy of an editorial decision that would then have to be kept in
        step with this one.
    """

    family: FormFamily
    metrics: tuple[FormMetric, ...]


PUBLISHED_FAMILIES: tuple[MetricFamilyResponse, ...] = tuple(
    MetricFamilyResponse(family=family, metrics=FAMILY_METRICS[family]) for family in FAMILY_ORDER
)


class FixtureFormResponse(Schema):
    """
    Public projection of both clubs' form before one fixture.

    Attributes
    ----------
    fixture_id : int
        Primary key of the fixture, echoed so a client holding the payload alone
        still knows what it describes.
    synchronized_at : datetime or None
        Instant the figures last agreed with the provider, serialized as an
        ISO 8601 UTC timestamp, and ``null`` when no stored statistic fed any
        sample. That happens for a club whose matches have not been
        synchronized yet and for one with no history at all, so an empty answer
        is an ordinary one rather than a failure.
    home : TeamFormResponse
        Form of the club playing at home, whose venue scope is its home
        matches.
    away : TeamFormResponse
        Form of the club playing away, whose venue scope is its away matches.
    families : tuple of MetricFamilyResponse
        The published vocabulary, grouped and ordered as the platform promises.
        It is a constant of the contract rather than a property of the fixture,
        which is why it is resolved rather than read: the query computes form,
        and the editorial decision about how twenty-five metrics are grouped
        lives in one place and is served from it. It is resolved rather than
        defaulted so the field stays required, because a default would tell
        every generated client that a body may arrive without it when no body
        ever does.

    Methods
    -------
    resolve_families(_form) -> tuple[MetricFamilyResponse, ...]
        Return the published vocabulary, whatever fixture is being serialized.
    """

    fixture_id: int
    synchronized_at: datetime | None
    home: TeamFormResponse
    away: TeamFormResponse
    families: tuple[MetricFamilyResponse, ...]

    @staticmethod
    def resolve_families(_form: object) -> tuple[MetricFamilyResponse, ...]:
        """
        Return the published vocabulary, whatever fixture is being serialized.

        Parameters
        ----------
        _form : object
            Form being serialized, which the vocabulary does not depend on. The
            parameter is positional in Django Ninja's resolver protocol, so the
            name is free and says that nothing is read from it.

        Returns
        -------
        tuple of MetricFamilyResponse
            Every family in the promised order, with the metrics of each.
        """

        return PUBLISHED_FAMILIES
