from collections.abc import Sequence
from datetime import UTC, date, datetime
from decimal import Decimal

from apps.fixtures.infrastructure.repositories import upsert_fixtures
from apps.fixtures.models import Fixture, League
from apps.predictions.domain.enums import (
    PredictionMarket,
    PredictionReliability,
    PredictionSelection,
)
from apps.predictions.infrastructure.repositories import (
    upsert_fixture_predictions,
    upsert_market_reliability,
)
from integrations.sportmonks.fixtures import ProviderLeague
from integrations.sportmonks.predictions import (
    ProviderFixtureProbabilities,
    ProviderPredictionWindow,
    ProviderProbability,
    ProviderReliability,
)
from tests.unit.fixtures.conftest import (
    PREMIER_LEAGUE,
    WINDOW_END,
    WINDOW_START,
    kickoff,
    provider_fixture,
    provider_window,
)

SYNCHRONIZED_AT = datetime(2026, 8, 25, 6, 0, tzinfo=UTC)

LATER_SYNCHRONIZED_AT = SYNCHRONIZED_AT.replace(hour=18)

FIXTURE_PROVIDER_ID = 1

# A day no seeded fixture is played on, so storing competitions on its own
# cannot reconcile away fixtures a test has already seeded.
FIXTURELESS_DAY = date(2026, 8, 20)


def seed_leagues(leagues: Sequence[ProviderLeague] = (PREMIER_LEAGUE,)) -> dict[int, League]:
    """
    Store competitions through the fixtures slice, without touching a fixture.

    The reliability grades hang off competitions rather than fixtures, so a
    reliability test needs the ``League`` rows and nothing else. They are still
    written by the repository that owns them instead of by ``objects.create``,
    so the rows a test points at are shaped exactly as a synchronization leaves
    them.

    Parameters
    ----------
    leagues : Sequence of ProviderLeague
        Competitions to store.

    Returns
    -------
    dict of int to League
        Every stored competition, keyed by provider identifier.
    """

    upsert_fixtures(
        provider_window([], leagues),
        FIXTURELESS_DAY,
        FIXTURELESS_DAY,
        SYNCHRONIZED_AT,
    )

    return {league.sportmonks_id: league for league in League.objects.all()}


def seed_fixtures(
    provider_ids: Sequence[int] = (FIXTURE_PROVIDER_ID,),
    *,
    league: ProviderLeague = PREMIER_LEAGUE,
) -> dict[int, Fixture]:
    """
    Store the fixtures a prediction points at, through the fixtures repository.

    One call is one authoritative window, so ``upsert_fixtures`` reconciles the
    range and a second call replaces the fixtures the first stored. Seed every
    fixture a test needs in a single call.

    Parameters
    ----------
    provider_ids : Sequence of int
        Provider identifiers of the fixtures to store.
    league : ProviderLeague
        Competition the fixtures belong to.

    Returns
    -------
    dict of int to Fixture
        Every stored fixture, keyed by provider identifier, carrying the primary
        keys the prediction rows point at.
    """

    upsert_fixtures(
        provider_window(
            [
                provider_fixture(provider_id, kickoff(12), league=league)
                for provider_id in provider_ids
            ],
            [league],
        ),
        WINDOW_START,
        WINDOW_END,
        SYNCHRONIZED_AT,
    )

    return {fixture.sportmonks_id: fixture for fixture in Fixture.objects.all()}


def probability(
    market: PredictionMarket, selection: PredictionSelection, value: str
) -> ProviderProbability:
    """
    Build one provider probability without contacting the provider.

    Parameters
    ----------
    market : PredictionMarket
        Market the selection belongs to.
    selection : PredictionSelection
        Outcome within that market.
    value : str
        Percentage as a decimal string, so the stored value is exactly the one
        the test wrote rather than the nearest binary float to it.

    Returns
    -------
    ProviderProbability
        Probability shaped exactly as the Sportmonks boundary yields one.
    """

    return ProviderProbability(market=market, selection=selection, probability=Decimal(value))


def fixture_probabilities(
    fixture_provider_id: int, probabilities: Sequence[ProviderProbability]
) -> ProviderFixtureProbabilities:
    """
    Build the probabilities the provider published for one fixture.

    Parameters
    ----------
    fixture_provider_id : int
        Provider identifier of the fixture the probabilities belong to.
    probabilities : Sequence of ProviderProbability
        Probabilities the provider published, empty for a fixture it read and
        published nothing for.

    Returns
    -------
    ProviderFixtureProbabilities
        Entry shaped exactly as the Sportmonks boundary yields one.
    """

    return ProviderFixtureProbabilities(
        fixture_provider_id=fixture_provider_id, probabilities=list(probabilities)
    )


def prediction_window(entries: Sequence[ProviderFixtureProbabilities]) -> ProviderPredictionWindow:
    """
    Build a provider prediction read without contacting the provider.

    Parameters
    ----------
    entries : Sequence of ProviderFixtureProbabilities
        Fixtures the read covered, in the order the provider listed them.

    Returns
    -------
    ProviderPredictionWindow
        Read shaped exactly as the Sportmonks boundary yields one.
    """

    return ProviderPredictionWindow(fixtures=list(entries))


def reliability(
    league_provider_id: int,
    market: PredictionMarket,
    quality: PredictionReliability,
    hit_ratio: str,
) -> ProviderReliability:
    """
    Build one provider reliability grade without contacting the provider.

    Parameters
    ----------
    league_provider_id : int
        Provider identifier of the competition the grade applies to.
    market : PredictionMarket
        Market the grade applies to.
    quality : PredictionReliability
        Grade the provider published.
    hit_ratio : str
        Share as a decimal string, for the reason the probability is one.

    Returns
    -------
    ProviderReliability
        Grade shaped exactly as the Sportmonks boundary yields one.
    """

    return ProviderReliability(
        league_provider_id=league_provider_id,
        market=market,
        quality=quality,
        hit_ratio=Decimal(hit_ratio),
    )


def store_predictions(
    entries: Sequence[ProviderFixtureProbabilities],
    synchronized_at: datetime = SYNCHRONIZED_AT,
) -> int:
    """
    Store a prediction read through the repository under test.

    Parameters
    ----------
    entries : Sequence of ProviderFixtureProbabilities
        Fixtures the read covered, with the probabilities of each.
    synchronized_at : datetime
        Instant stamped on every row the call writes.

    Returns
    -------
    int
        Number of probability rows written.
    """

    return upsert_fixture_predictions(prediction_window(entries), synchronized_at)


def store_reliability(
    grades: Sequence[ProviderReliability],
    synchronized_at: datetime = SYNCHRONIZED_AT,
) -> int:
    """
    Store a reliability read through the repository under test.

    Parameters
    ----------
    grades : Sequence of ProviderReliability
        Grades the read carried, in the order the provider listed them.
    synchronized_at : datetime
        Instant stamped on every row the call writes.

    Returns
    -------
    int
        Number of reliability rows written.
    """

    return upsert_market_reliability(grades, synchronized_at)
