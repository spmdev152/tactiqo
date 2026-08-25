import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from apps.predictions.domain.enums import (
    PredictionMarket,
    PredictionReliability,
    PredictionSelection,
)
from integrations.sportmonks.client import ProviderPayload, SportmonksClient
from integrations.sportmonks.exceptions import SportmonksError
from integrations.sportmonks.fixtures import PAGE_SIZE, PROVIDER_TIMEZONE

logger = logging.getLogger(__name__)

# Type 240 is the one market whose selections sit one level deeper, under this key, while every
# other market maps its selection keys straight onto percentages. The nesting is the provider's
# shape rather than one worth reproducing, so it is unwrapped here and nowhere above this module.
NESTED_SCORES_KEY = "scores"

QUALITY_TYPE = 243

HIT_RATIO_TYPE = 242

# The bounds below mirror the columns of ``apps.predictions.models``, and the identifier range
# that of ``apps.fixtures.models``, rather than importing them, because the provider adapter must
# not depend on the persistence it feeds.
PROBABILITY_CEILING = Decimal("100")

PROBABILITY_PLACES = Decimal("0.01")

HIT_RATIO_CEILING = Decimal("1")

HIT_RATIO_PLACES = Decimal("0.001")

IDENTIFIER_MINIMUM = -(2**63)

IDENTIFIER_MAXIMUM = 2**63 - 1

PROVIDER_MARKETS: dict[int, PredictionMarket] = {
    237: PredictionMarket.FULLTIME_RESULT,
    239: PredictionMarket.DOUBLE_CHANCE,
    231: PredictionMarket.BOTH_TEAMS_TO_SCORE,
    234: PredictionMarket.OVER_UNDER_1_5,
    235: PredictionMarket.OVER_UNDER_2_5,
    236: PredictionMarket.OVER_UNDER_3_5,
    1679: PredictionMarket.OVER_UNDER_4_5,
    238: PredictionMarket.TEAM_TO_SCORE_FIRST,
    233: PredictionMarket.FIRST_HALF_RESULT,
    232: PredictionMarket.HALF_TIME_FULL_TIME,
    240: PredictionMarket.CORRECT_SCORE,
}

_RESULT_SELECTIONS: dict[str, PredictionSelection] = {
    "home": PredictionSelection.HOME,
    "draw": PredictionSelection.DRAW,
    "away": PredictionSelection.AWAY,
}

_TWO_WAY_SELECTIONS: dict[str, PredictionSelection] = {
    "yes": PredictionSelection.YES,
    "no": PredictionSelection.NO,
}

# The table is keyed by market rather than by provider key because one provider key means two
# different things: ``home_away`` is the double chance that excludes the draw and the half-time
# home lead turned into an away win, and ``draw_home`` is the reverse pair of the same two.
PROVIDER_SELECTIONS: dict[PredictionMarket, dict[str, PredictionSelection]] = {
    PredictionMarket.FULLTIME_RESULT: _RESULT_SELECTIONS,
    PredictionMarket.DOUBLE_CHANCE: {
        "draw_home": PredictionSelection.HOME_OR_DRAW,
        "home_away": PredictionSelection.HOME_OR_AWAY,
        "draw_away": PredictionSelection.DRAW_OR_AWAY,
    },
    PredictionMarket.BOTH_TEAMS_TO_SCORE: _TWO_WAY_SELECTIONS,
    PredictionMarket.OVER_UNDER_1_5: _TWO_WAY_SELECTIONS,
    PredictionMarket.OVER_UNDER_2_5: _TWO_WAY_SELECTIONS,
    PredictionMarket.OVER_UNDER_3_5: _TWO_WAY_SELECTIONS,
    PredictionMarket.OVER_UNDER_4_5: _TWO_WAY_SELECTIONS,
    PredictionMarket.TEAM_TO_SCORE_FIRST: {
        "home": PredictionSelection.HOME,
        "away": PredictionSelection.AWAY,
        "draw": PredictionSelection.NO_GOAL,
    },
    PredictionMarket.FIRST_HALF_RESULT: _RESULT_SELECTIONS,
    PredictionMarket.HALF_TIME_FULL_TIME: {
        "home_home": PredictionSelection.HOME_THEN_HOME,
        "home_draw": PredictionSelection.HOME_THEN_DRAW,
        "home_away": PredictionSelection.HOME_THEN_AWAY,
        "draw_home": PredictionSelection.DRAW_THEN_HOME,
        "draw_draw": PredictionSelection.DRAW_THEN_DRAW,
        "draw_away": PredictionSelection.DRAW_THEN_AWAY,
        "away_home": PredictionSelection.AWAY_THEN_HOME,
        "away_draw": PredictionSelection.AWAY_THEN_DRAW,
        "away_away": PredictionSelection.AWAY_THEN_AWAY,
    },
    PredictionMarket.CORRECT_SCORE: {
        "0-0": PredictionSelection.SCORE_0_0,
        "0-1": PredictionSelection.SCORE_0_1,
        "0-2": PredictionSelection.SCORE_0_2,
        "0-3": PredictionSelection.SCORE_0_3,
        "1-0": PredictionSelection.SCORE_1_0,
        "1-1": PredictionSelection.SCORE_1_1,
        "1-2": PredictionSelection.SCORE_1_2,
        "1-3": PredictionSelection.SCORE_1_3,
        "2-0": PredictionSelection.SCORE_2_0,
        "2-1": PredictionSelection.SCORE_2_1,
        "2-2": PredictionSelection.SCORE_2_2,
        "2-3": PredictionSelection.SCORE_2_3,
        "3-0": PredictionSelection.SCORE_3_0,
        "3-1": PredictionSelection.SCORE_3_1,
        "3-2": PredictionSelection.SCORE_3_2,
        "3-3": PredictionSelection.SCORE_3_3,
        "Other_1": PredictionSelection.ANY_OTHER_HOME_WIN,
        "Other_X": PredictionSelection.ANY_OTHER_DRAW,
        "Other_2": PredictionSelection.ANY_OTHER_AWAY_WIN,
    },
}

PREDICTABILITY_MARKETS: dict[str, PredictionMarket] = {
    "fulltime_result": PredictionMarket.FULLTIME_RESULT,
    "fulltime_result_1st_half": PredictionMarket.FIRST_HALF_RESULT,
    "ht_ft": PredictionMarket.HALF_TIME_FULL_TIME,
    "correct_score": PredictionMarket.CORRECT_SCORE,
    "team_to_score_first": PredictionMarket.TEAM_TO_SCORE_FIRST,
    "both_teams_to_score": PredictionMarket.BOTH_TEAMS_TO_SCORE,
    "over_under_1_5": PredictionMarket.OVER_UNDER_1_5,
    "over_under_2_5": PredictionMarket.OVER_UNDER_2_5,
    "over_under_3_5": PredictionMarket.OVER_UNDER_3_5,
}

PROVIDER_QUALITIES: dict[str, PredictionReliability] = {
    "poor": PredictionReliability.POOR,
    "medium": PredictionReliability.MEDIUM,
    "good": PredictionReliability.GOOD,
    "high": PredictionReliability.HIGH,
}


@dataclass(frozen=True, slots=True)
class ProviderProbability:
    """
    Chance the provider's model gives one selection of one market.

    Attributes
    ----------
    market : PredictionMarket
        Market the selection belongs to, mapped from the numeric type id the
        provider publishes it under, which never leaves this module.
    selection : PredictionSelection
        Outcome within the market, mapped from the provider's selection key,
        which never leaves this module either.
    probability : Decimal
        Chance of the selection as a percentage between nought and a hundred,
        to the two decimal places the provider publishes.
    """

    market: PredictionMarket
    selection: PredictionSelection
    probability: Decimal


@dataclass(frozen=True, slots=True)
class ProviderFixtureProbabilities:
    """
    Every probability one fixture of the window was read with.

    Attributes
    ----------
    fixture_provider_id : int
        Sportmonks fixture identifier the probabilities belong to.
    probabilities : list of ProviderProbability
        Probabilities the fixture carries, in provider order, and empty for a
        fixture the provider publishes no prediction for. That is the ordinary
        state rather than a defect: nothing is published for a fixture more
        than roughly a fortnight out.
    """

    fixture_provider_id: int
    probabilities: list[ProviderProbability]


@dataclass(frozen=True, slots=True)
class ProviderPredictionWindow:
    """
    Everything one complete read of a prediction window resolved.

    Every fixture the read returned is carried, including one whose
    ``predictions`` array was empty. Reconciliation is by stamp: a run writes
    the probabilities it read and then deletes the rows of the fixtures it read
    that still carry an earlier stamp. Dropping the fixtures that came back
    without a probability would therefore leave a withdrawn selection in the
    table for as long as the provider keeps publishing nothing, which is
    precisely the case the emptiness signals.

    Attributes
    ----------
    fixtures : list of ProviderFixtureProbabilities
        Fixtures of the window, in provider order, each with the probabilities
        it was authoritatively read with.
    """

    fixtures: list[ProviderFixtureProbabilities]


@dataclass(frozen=True, slots=True)
class ProviderReliability:
    """
    How well the provider's model has performed on one market of one competition.

    Attributes
    ----------
    league_provider_id : int
        Sportmonks league identifier the grade belongs to.
    market : PredictionMarket
        Market the grade describes.
    quality : PredictionReliability
        Word the provider grades the market with.
    hit_ratio : Decimal
        Share of predictions the model got right, between nought and one, to
        three decimal places.
    """

    league_provider_id: int
    market: PredictionMarket
    quality: PredictionReliability
    hit_ratio: Decimal


def fetch_prediction_window(
    start: date, end: date, league_ids: Sequence[int]
) -> ProviderPredictionWindow:
    """
    Return the probabilities every fixture of a window was read with, normalized.

    One paginated resource is read, not one request a fixture. The fixtures
    resource accepts ``include=predictions``, and the alternatives do not
    survive contact with the subscription: the global probabilities collection
    ignores a league filter, and the between-dates variant of it does not
    exist. A window of a hundred and fifty fixtures therefore costs three pages
    rather than a hundred and fifty calls against a budget of two thousand an
    hour.

    The type filter is built from ``PROVIDER_MARKETS`` rather than written out,
    so the request cannot come to ask for a type this boundary would then
    ignore, nor omit one it knows how to map. It is honoured server-side, which
    is why the payload of a fixture is already narrowed to the eleven markets
    the platform publishes.

    A row the provider returns malformed is dropped with a warning instead of
    failing the window, so one broken fixture cannot cost a refresh every other
    fixture in the same range. A window the provider cannot serve completely is
    the opposite case and fails: the client raises rather than returning the
    pages it managed to read, because a caller cannot tell a prefix of a window
    from the whole of it and would reconcile the prefix as if it were complete.

    A percentage the column that stores it could not hold makes its own
    selection unusable rather than aborting anything larger, because the window
    is written in one transaction and a single refused value would otherwise
    discard every other probability of the run.

    The request states ``timezone=UTC`` even though nothing here parses an
    instant. The resource shifts every stamp it returns by that parameter, so
    leaving it to a provider default would make this read and the fixture
    window read the same range under two different definitions of a day. That
    timezone and the page size are imported from the fixtures boundary rather
    than restated, because this is the same fixtures resource and both
    constants describe the provider rather than either of its callers.

    One read cannot exceed ``PAGE_SIZE`` rows over ``MAX_PAGE_COUNT`` pages, or
    two thousand fixtures, which is the same ceiling the fixture window is read
    under and an order of magnitude clear of what five leagues schedule in the
    widest window this project synchronizes.

    Parameters
    ----------
    start : date
        First day of the window, inclusive.
    end : date
        Last day of the window, inclusive.
    league_ids : sequence of int
        Sportmonks league identifiers to restrict the window to.

    Returns
    -------
    ProviderPredictionWindow
        Every fixture the read returned, with its normalized probabilities.

    Raises
    ------
    SportmonksError
        When no league is requested, or when the provider cannot be read
        completely.
    """

    if not league_ids:
        raise SportmonksError(
            "No Sportmonks league was requested, so no prediction window can be read."
        )

    client = SportmonksClient()

    params = {
        "filters": (
            f"fixtureLeagues:{_joined(league_ids)};"
            f"predictionTypes:{_joined(sorted(PROVIDER_MARKETS))}"
        ),
        "include": "predictions",
        "per_page": PAGE_SIZE,
        "timezone": PROVIDER_TIMEZONE,
    }

    path = f"/fixtures/between/{start.isoformat()}/{end.isoformat()}"

    fixtures: list[ProviderFixtureProbabilities] = []

    for page in client.get_pages(path, params):
        for entry in page:
            fixture = _fixture_probabilities_of(entry)

            if fixture is not None:
                fixtures.append(fixture)

    return ProviderPredictionWindow(fixtures=fixtures)


def fetch_market_reliability(league_ids: Sequence[int]) -> list[ProviderReliability]:
    """
    Return the grade each competition's markets carry, normalized.

    The resource is per competition, so this is one request a league: five
    against a budget of two thousand an hour, which is why the caller may
    afford to read them all daily rather than track which one changed.

    Each competition is graded by five types, of which two are in scope and are
    joined here: the word the provider calls its predictability and the hit
    ratio its model achieved. A market is reported only when both are present
    and usable, because a word without the number behind it invites exactly the
    reading the pair exists to prevent, and a number without the word is a
    figure with no interpretation attached.

    Two markets are never graded. The provider publishes no predictability key
    for double chance or for over/under 4.5, so those two markets carry no row
    at all and the interface shows their probabilities ungraded.

    Parameters
    ----------
    league_ids : sequence of int
        Sportmonks league identifiers to read the grades of.

    Returns
    -------
    list of ProviderReliability
        One grade for every graded market of every competition read, in the
        order the competitions were requested.

    Raises
    ------
    SportmonksError
        When no league is requested, or when the provider cannot be read
        completely.
    """

    if not league_ids:
        raise SportmonksError(
            "No Sportmonks league was requested, so no market reliability can be read."
        )

    client = SportmonksClient()

    grades: list[ProviderReliability] = []

    for league_id in league_ids:
        grades.extend(_league_grades(client, league_id))

    return grades


def _league_grades(client: SportmonksClient, league_id: int) -> list[ProviderReliability]:
    """
    Return the graded markets of one competition, joining the two types in scope.

    Parameters
    ----------
    client : SportmonksClient
        Client the request is issued through.
    league_id : int
        Sportmonks league identifier being read.

    Returns
    -------
    list of ProviderReliability
        Markets the competition carries both a usable word and a usable hit
        ratio for, in the order the provider listed them.

    Raises
    ------
    SportmonksError
        When the provider cannot be read completely.
    """

    params = {
        "per_page": PAGE_SIZE,
        "timezone": PROVIDER_TIMEZONE,
    }

    path = f"/predictions/predictability/leagues/{league_id}"

    by_type: dict[int, ProviderPayload] = {}

    for page in client.get_pages(path, params):
        for entry in page:
            type_id = _identifier(entry.get("type_id"))

            if type_id is not None:
                by_type[type_id] = entry

    qualities = _qualities_of(by_type.get(QUALITY_TYPE), league_id)
    hit_ratios = _hit_ratios_of(by_type.get(HIT_RATIO_TYPE), league_id)

    return [
        ProviderReliability(
            league_provider_id=league_id,
            market=market,
            quality=quality,
            hit_ratio=hit_ratios[market],
        )
        for market, quality in qualities.items()
        if market in hit_ratios
    ]


def _qualities_of(
    payload: object, league_provider_id: int
) -> dict[PredictionMarket, PredictionReliability]:
    """
    Read the predictability word each graded market of a competition carries.

    Parameters
    ----------
    payload : object
        Entry the predictability type carried, or ``None`` when the competition
        was returned without that type at all.
    league_provider_id : int
        Identifier of the competition, named when a grade is discarded.

    Returns
    -------
    dict of PredictionMarket to PredictionReliability
        Word every market this boundary maps was graded with. A key naming a
        market the platform does not publish is passed over silently: the
        resource grades thirteen markets and this boundary publishes nine of
        them, so those keys are the documented shape rather than a surprise.
    """

    data = _graded_data_of(payload, league_provider_id, QUALITY_TYPE)

    if data is None:
        return {}

    qualities: dict[PredictionMarket, PredictionReliability] = {}

    for key, value in data.items():
        market = PREDICTABILITY_MARKETS.get(key)

        if market is None:
            continue

        quality = PROVIDER_QUALITIES.get(value) if isinstance(value, str) else None

        if quality is None:
            logger.warning(
                "Ignoring the %s grade of Sportmonks league %d: %r is not a word this boundary "
                "maps.",
                market.value,
                league_provider_id,
                value,
            )

            continue

        qualities[market] = quality

    return qualities


def _hit_ratios_of(payload: object, league_provider_id: int) -> dict[PredictionMarket, Decimal]:
    """
    Read the hit ratio each graded market of a competition carries.

    Parameters
    ----------
    payload : object
        Entry the hit ratio type carried, or ``None`` when the competition was
        returned without that type at all.
    league_provider_id : int
        Identifier of the competition, named when a ratio is discarded.

    Returns
    -------
    dict of PredictionMarket to Decimal
        Ratio every market this boundary maps achieved, quantized to the three
        decimal places of the column that stores it. A key naming a market the
        platform does not publish is passed over silently, as above.
    """

    data = _graded_data_of(payload, league_provider_id, HIT_RATIO_TYPE)

    if data is None:
        return {}

    hit_ratios: dict[PredictionMarket, Decimal] = {}

    for key, value in data.items():
        market = PREDICTABILITY_MARKETS.get(key)

        if market is None:
            continue

        hit_ratio = _hit_ratio(value)

        if hit_ratio is None:
            logger.warning(
                "Ignoring the %s hit ratio of Sportmonks league %d: %r is not a share the column "
                "that stores it could hold.",
                market.value,
                league_provider_id,
                value,
            )

            continue

        hit_ratios[market] = hit_ratio

    return hit_ratios


def _graded_data_of(
    payload: object, league_provider_id: int, type_id: int
) -> ProviderPayload | None:
    """
    Unwrap the market-keyed object one predictability entry grades a competition with.

    Parameters
    ----------
    payload : object
        Entry the type carried, or ``None`` when the read returned no entry of
        that type.
    league_provider_id : int
        Identifier of the competition, named when nothing can be read.
    type_id : int
        Provider type the entry was looked up under, named in the same report
        so an absent grade can be told from an unreadable one.

    Returns
    -------
    ProviderPayload or None
        Object mapping a provider market key to its grade, or ``None`` when the
        entry is absent or carries no such object. Both cases leave the
        competition ungraded rather than half-graded, which the join above then
        reports as no market at all.
    """

    if payload is None:
        logger.warning(
            "Sportmonks league %d was returned without prediction type %d, so its markets stay "
            "ungraded.",
            league_provider_id,
            type_id,
        )

        return None

    data = payload.get("data") if isinstance(payload, dict) else None

    if not isinstance(data, dict):
        logger.warning(
            "Leaving Sportmonks league %d ungraded by prediction type %d: %r grades no market.",
            league_provider_id,
            type_id,
            data,
        )

        return None

    return data


def _fixture_probabilities_of(entry: ProviderPayload) -> ProviderFixtureProbabilities | None:
    """
    Normalize the predictions of one fixture entry, or report it as unusable.

    Parameters
    ----------
    entry : ProviderPayload
        One entry of a fixtures page, with its predictions included.

    Returns
    -------
    ProviderFixtureProbabilities or None
        Fixture and its probabilities, empty when the provider published none,
        or ``None`` when the entry carries no usable identifier or no
        predictions array. An unreadable array is not read as an empty one: the
        caller reconciles against what it was authoritatively told, and an
        entry whose include is malformed said nothing it may act on.
    """

    provider_id = _identifier(entry.get("id"))

    if provider_id is None:
        logger.warning("Skipping a Sportmonks prediction entry that names no usable fixture.")

        return None

    payload = entry.get("predictions")

    if not isinstance(payload, list):
        logger.warning(
            "Skipping Sportmonks fixture %d: %r is not a predictions array.",
            provider_id,
            payload,
        )

        return None

    probabilities: list[ProviderProbability] = []

    for prediction in payload:
        if isinstance(prediction, dict):
            probabilities.extend(_probabilities_of(prediction, provider_id))

    return ProviderFixtureProbabilities(
        fixture_provider_id=provider_id, probabilities=probabilities
    )


def _probabilities_of(
    entry: ProviderPayload, fixture_provider_id: int
) -> list[ProviderProbability]:
    """
    Normalize one prediction entry into the probabilities of its market.

    Parameters
    ----------
    entry : ProviderPayload
        One entry of the predictions include, describing a single market.
    fixture_provider_id : int
        Identifier of the fixture, named whenever a probability is discarded.

    Returns
    -------
    list of ProviderProbability
        Probabilities the entry states, empty when it names a type this
        boundary does not publish, states no selection object, or states no
        selection this boundary could use.
    """

    type_id = _identifier(entry.get("type_id"))

    market = PROVIDER_MARKETS.get(type_id) if type_id is not None else None

    if market is None:
        logger.debug(
            "Ignoring prediction type %r of Sportmonks fixture %d: it is not a market this "
            "boundary publishes.",
            type_id,
            fixture_provider_id,
        )

        return []

    selections = _selections_of(entry.get("predictions"), market, fixture_provider_id)

    if selections is None:
        return []

    known = PROVIDER_SELECTIONS[market]

    probabilities: list[ProviderProbability] = []

    for key, value in selections.items():
        selection = known.get(key)

        if selection is None:
            logger.warning(
                "Ignoring %r of Sportmonks fixture %d: the %s market names no such selection.",
                key,
                fixture_provider_id,
                market.value,
            )

            continue

        probability = _probability(value)

        if probability is None:
            logger.warning(
                "Ignoring the %s %s of Sportmonks fixture %d: %r is not a percentage the column "
                "that stores it could hold.",
                market.value,
                selection.value,
                fixture_provider_id,
                value,
            )

            continue

        probabilities.append(
            ProviderProbability(market=market, selection=selection, probability=probability)
        )

    return probabilities


def _selections_of(
    payload: object, market: PredictionMarket, fixture_provider_id: int
) -> ProviderPayload | None:
    """
    Unwrap the selection-keyed object one prediction entry states its market with.

    Parameters
    ----------
    payload : object
        Value the ``predictions`` field of the entry carried.
    market : PredictionMarket
        Market the entry describes, which decides whether the object is nested.
    fixture_provider_id : int
        Identifier of the fixture, named when nothing can be read.

    Returns
    -------
    ProviderPayload or None
        Object mapping a provider selection key to its percentage, or ``None``
        when the entry states no such object.
    """

    if market is PredictionMarket.CORRECT_SCORE:
        payload = payload.get(NESTED_SCORES_KEY) if isinstance(payload, dict) else None

    if not isinstance(payload, dict):
        logger.warning(
            "Skipping the %s prediction of Sportmonks fixture %d: %r states no selection.",
            market.value,
            fixture_provider_id,
            payload,
        )

        return None

    return payload


def _probability(value: object) -> Decimal | None:
    """
    Return a percentage the column that stores it can hold.

    Parameters
    ----------
    value : object
        Value a selection key carried, which the provider sends as an integer
        for a round figure and as a fractional number otherwise.

    Returns
    -------
    Decimal or None
        Percentage to two decimal places, or ``None`` when the value is not a
        number between nought and a hundred.
    """

    return _bounded_decimal(value, PROBABILITY_CEILING, PROBABILITY_PLACES)


def _hit_ratio(value: object) -> Decimal | None:
    """
    Return a hit ratio the column that stores it can hold.

    Parameters
    ----------
    value : object
        Value a predictability market key carried, published as a share rather
        than a percentage.

    Returns
    -------
    Decimal or None
        Share to three decimal places, or ``None`` when the value is not a
        number between nought and one.
    """

    return _bounded_decimal(value, HIT_RATIO_CEILING, HIT_RATIO_PLACES)


def _bounded_decimal(value: object, ceiling: Decimal, places: Decimal) -> Decimal | None:
    """
    Parse a provider number into an exact decimal inside a closed range.

    The decimal is built from the string form of the value, never from the
    float itself: ``Decimal(0.55)`` is the binary approximation of a figure the
    provider published as two decimal places, and storing it would print a
    number nobody sent. A boolean is refused although Python counts it as an
    integer, and a value that is not finite is refused before it can be
    quantized.

    Parameters
    ----------
    value : object
        Value the provider carried, documented as a number.
    ceiling : Decimal
        Largest value the column that stores it accepts, its floor being nought
        in both cases this boundary parses.
    places : Decimal
        Exponent the column rounds to, as the quantize operand.

    Returns
    -------
    Decimal or None
        Value rounded to the column's precision, or ``None`` when it is not a
        finite number inside the range. Refusing it here matters because the
        rows of a run are written in one transaction, so a single value the
        column would reject must cost its own row rather than every other row
        of the run.
    """

    if isinstance(value, bool) or not isinstance(value, int | float):
        return None

    parsed = Decimal(str(value))

    if not parsed.is_finite() or parsed < 0 or parsed > ceiling:
        return None

    return parsed.quantize(places)


def _identifier(value: object) -> int | None:
    """
    Return a provider identifier the column that stores it can hold.

    Parameters
    ----------
    value : object
        Value an identifier field carried, which the provider sends as a number
        but has been observed to send as a string of digits.

    Returns
    -------
    int or None
        Identifier, or ``None`` when the value does not denote one or falls
        outside the signed 64-bit range of the column that stores it.
    """

    if isinstance(value, bool):
        return None

    if isinstance(value, int):
        return value if IDENTIFIER_MINIMUM <= value <= IDENTIFIER_MAXIMUM else None

    if isinstance(value, str) and value.isdigit():
        parsed = int(value)

        return parsed if parsed <= IDENTIFIER_MAXIMUM else None

    return None


def _joined(values: Sequence[int]) -> str:
    """
    Render numeric identifiers as the comma-separated list a filter expects.

    Parameters
    ----------
    values : sequence of int
        League identifiers or prediction type identifiers.

    Returns
    -------
    str
        Identifiers joined by commas.
    """

    return ",".join(str(value) for value in values)
