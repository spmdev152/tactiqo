from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime

from django.db.models import Q, QuerySet

from apps.fixtures.domain.enums import FixtureStatus
from apps.fixtures.models import Fixture
from apps.statistics.domain.enums import FormMetric, FormRange, FormScope, MatchSide
from apps.statistics.domain.metrics import (
    DEEPEST_COUNTED_RANGE,
    METRIC_ORDER,
    OPPOSED_METRICS,
    RANGE_ORDER,
    RANGE_SIZES,
    SCOPE_ORDER,
)
from apps.statistics.models import MatchTeamStatistic

# The stored columns a sample reads, in the order every read loads them. They
# are addressed by position through ``COLUMN_POSITIONS`` rather than by
# attribute, because a sample sums a column over several rows and summing
# twenty-two attributes of a model instance means instantiating the instance.
STATISTIC_COLUMNS: tuple[str, ...] = (
    "shots_total",
    "shots_on_target",
    "shots_inside_box",
    "shots_blocked",
    "big_chances_created",
    "key_passes",
    "corners",
    "possession",
    "passes",
    "successful_passes",
    "crosses",
    "accurate_crosses",
    "dribble_attempts",
    "successful_dribbles",
    "saves",
    "tackles",
    "interceptions",
    "duels_won",
    "fouls",
    "yellow_cards",
    "red_cards",
    "offsides",
)

COLUMN_POSITIONS: dict[str, int] = {
    column: position for position, column in enumerate(STATISTIC_COLUMNS)
}

# The metrics whose published figure is the per-match average of one stored
# column. This is where the published vocabulary meets the stored one, so the
# domain tables stay free of column names and this module stays free of
# editorial decisions about which metrics exist or in what order.
AVERAGED_COLUMNS: dict[FormMetric, str] = {
    FormMetric.SHOTS: "shots_total",
    FormMetric.SHOTS_ON_TARGET: "shots_on_target",
    FormMetric.SHOTS_INSIDE_BOX: "shots_inside_box",
    FormMetric.BIG_CHANCES_CREATED: "big_chances_created",
    FormMetric.KEY_PASSES: "key_passes",
    FormMetric.CORNERS: "corners",
    FormMetric.POSSESSION: "possession",
    FormMetric.PASSES: "passes",
    FormMetric.CROSSES: "crosses",
    FormMetric.SAVES: "saves",
    FormMetric.TACKLES: "tackles",
    FormMetric.INTERCEPTIONS: "interceptions",
    FormMetric.DUELS_WON: "duels_won",
    FormMetric.SHOTS_BLOCKED: "shots_blocked",
    FormMetric.FOULS: "fouls",
    FormMetric.YELLOW_CARDS: "yellow_cards",
    FormMetric.RED_CARDS: "red_cards",
    FormMetric.OFFSIDES: "offsides",
}

# The metrics whose published figure is a completion rate, as the numerator
# column over the denominator column. It is the summed numerator over the summed
# denominator across the whole sample, never the mean of the per-match rates:
# the two differ whenever the per-match denominators do, and only the first is
# the rate the sample actually achieved.
RATIO_COLUMNS: dict[FormMetric, tuple[str, str]] = {
    FormMetric.PASS_ACCURACY: ("successful_passes", "passes"),
    FormMetric.CROSS_ACCURACY: ("accurate_crosses", "crosses"),
    FormMetric.DRIBBLE_SUCCESS: ("successful_dribbles", "dribble_attempts"),
}

# The fixture columns a counted match is read through. The two goal columns are
# never null in a loaded row, because the read filters a null score out.
MATCH_COLUMNS: tuple[str, ...] = (
    "id",
    "home_team_id",
    "away_team_id",
    "home_goals",
    "away_goals",
)

# Newest first, broken by primary key so two matches kicking off together are
# taken in a stable order and the deepest range keeps the same matches twice.
RECENT_ORDER: tuple[str, ...] = ("-kickoff_at", "-id")

PERCENTAGE_SCALE = 100

PUBLISHED_DECIMALS = 2

MatchRow = tuple[int, int, int, int, int]


@dataclass(frozen=True, slots=True)
class MetricValue:
    """
    One published figure of one sample, with what the opposition recorded.

    Attributes
    ----------
    metric : FormMetric
        Metric the figure belongs to, named in the platform's own vocabulary.
    value : float
        Figure the club recorded, a per-match average or a percentage depending
        on the metric, rounded to two decimals. It is a ``float`` rather than a
        ``Decimal`` because it is computed here from stored integers rather than
        read from a decimal column, so there is no exact scale to preserve.
    opposed_value : float or None
        Same figure for the opposition of each counted match, ``None`` for every
        metric outside ``OPPOSED_METRICS``. It is what the other clubs recorded
        against this one, which is the only way an average reads as good or bad
        without the reader knowing the competition.
    """

    metric: FormMetric
    value: float
    opposed_value: float | None


@dataclass(frozen=True, slots=True)
class FormSample:
    """
    One club's form over one range of matches, seen through one scope.

    Attributes
    ----------
    range : FormRange
        Range of matches the sample covers. The field shadows the builtin
        deliberately: it is the name the public contract publishes, and renaming
        it here would only move the mismatch to the HTTP boundary.
    scope : FormScope
        Whether the sample counts every match or only the ones played on the
        side the club takes in the fixture being read.
    matches_counted : int
        Matches the sample is an average over, published so a reader can tell a
        thin sample from a full one. It is ``0`` for a club with no qualifying
        history, and the metrics are then all ``0.0``.
    metrics : tuple of MetricValue
        Every metric of ``METRIC_ORDER``, in that order, always complete so the
        interface never has to decide what an absent metric means.
    """

    range: FormRange
    scope: FormScope
    matches_counted: int
    metrics: tuple[MetricValue, ...]


@dataclass(frozen=True, slots=True)
class TeamForm:
    """
    Every sample of one of the two clubs of the fixture being read.

    Attributes
    ----------
    team_id : int
        Primary key of the club the samples belong to.
    samples : tuple of FormSample
        Samples in ``RANGE_ORDER`` by ``SCOPE_ORDER`` order, always complete: a
        range the club has no matches for is published with no matches counted
        rather than left out, so the two clubs of a fixture always answer with
        the same grid and the interface can draw them side by side.
    """

    team_id: int
    samples: tuple[FormSample, ...]


@dataclass(frozen=True, slots=True)
class FixtureForm:
    """
    Both clubs' form before one fixture, ready to be serialized.

    Attributes
    ----------
    fixture_id : int
        Primary key of the fixture the form was computed for.
    synchronized_at : datetime or None
        Newest instant among the statistic rows that fed any sample, which is
        how fresh the figures in front of the reader are, and ``None`` when no
        row fed any sample. It is taken from the rows that were actually read
        rather than from a synchronization run, because a run that wrote
        somebody else's matches says nothing about these.
    home : TeamForm
        Form of the club playing at home in the fixture being read.
    away : TeamForm
        Form of the club playing away in the fixture being read.
    """

    fixture_id: int
    synchronized_at: datetime | None
    home: TeamForm
    away: TeamForm


@dataclass(frozen=True, slots=True)
class CountedMatch:
    """
    One already-played match, reduced to what a sample counts from it.

    Attributes
    ----------
    fixture_id : int
        Primary key of the match, which is what its two statistic rows are
        found by.
    side : MatchSide
        Side the club whose form is being read took in that match, which
        selects its own statistic row and, inverted, the opposing one.
    goals_for : int
        Goals the club scored, taken from the fixture score rather than from a
        statistic column, because the provider omits its own goals statistic at
        nought and a goalless performance would otherwise read as missing.
    goals_against : int
        Goals the club conceded, taken from the same score.
    """

    fixture_id: int
    side: MatchSide
    goals_for: int
    goals_against: int


@dataclass(frozen=True, slots=True)
class SideStatistics:
    """
    One stored performance, reduced to what a sample reads from it.

    Attributes
    ----------
    columns : tuple of int
        Values of ``STATISTIC_COLUMNS``, in that order, addressed through
        ``COLUMN_POSITIONS`` so a metric names its column once, in the table
        that maps metrics onto columns.
    synchronized_at : datetime
        Instant the row last agreed with the provider.
    """

    columns: tuple[int, ...]
    synchronized_at: datetime


StoredStatistics = dict[tuple[int, str], SideStatistics]

ScopedMatches = dict[FormScope, list[CountedMatch]]


def mean(total: int, counted: int) -> float:
    """
    Return the per-match average of a total, rounded as published.

    Parameters
    ----------
    total : int
        Sum over the counted matches.
    counted : int
        Matches the sum was taken over.

    Returns
    -------
    float
        Average rounded to two decimals, or ``0.0`` when nothing was counted. A
        sample with nothing in it publishes zero rather than nothing, because
        every metric of every sample is published and the interface draws a
        figure it is handed instead of deciding what an absent one means.
    """

    return round(total / counted, PUBLISHED_DECIMALS) if counted else 0.0


def percentage(part: int, whole: int) -> float:
    """
    Return a part of a whole as a percentage, rounded as published.

    Parameters
    ----------
    part : int
        Sum of the qualifying quantity, such as the wins of the sample or the
        passes it completed.
    whole : int
        Sum it is a part of, such as the matches counted or the passes
        attempted.

    Returns
    -------
    float
        Share between ``0`` and ``100`` rounded to two decimals, or ``0.0`` when
        the whole is zero, which is a club that attempted none of the thing
        rather than one that failed at it.
    """

    return round(part * PERCENTAGE_SCALE / whole, PUBLISHED_DECIMALS) if whole else 0.0


@dataclass(slots=True)
class SideTotals:
    """
    Running column totals of one side of a sample.

    Attributes
    ----------
    rows_counted : int
        Statistic rows folded in. It is the divisor of every average, and it is
        counted separately from the matches of the sample: a match whose
        statistics have not been synchronized still counts as a match and still
        carries a result, so dividing by the matches would dilute every average
        by the rows that are missing.
    columns : list of int
        Sums of ``STATISTIC_COLUMNS``, in that order.

    Methods
    -------
    add(columns) -> None
        Fold one stored row into the totals.
    total(column) -> int
        Return the sum of one column.
    """

    rows_counted: int = 0
    columns: list[int] = field(default_factory=lambda: [0] * len(STATISTIC_COLUMNS))

    def add(self, columns: tuple[int, ...]) -> None:
        """
        Fold one stored row into the totals.

        Parameters
        ----------
        columns : tuple of int
            Values of ``STATISTIC_COLUMNS``, in that order.
        """

        self.rows_counted += 1

        for position, value in enumerate(columns):
            self.columns[position] += value

    def total(self, column: str) -> int:
        """
        Return the sum of one column.

        Parameters
        ----------
        column : str
            Name of a column of ``STATISTIC_COLUMNS``.

        Returns
        -------
        int
            Sum of that column over the folded rows.
        """

        return self.columns[COLUMN_POSITIONS[column]]


@dataclass(slots=True)
class SampleTotals:
    """
    Everything one sample accumulates while its matches are folded in.

    Attributes
    ----------
    matches_counted : int
        Matches folded in, which is what the sample publishes and the divisor of
        the results and the goals.
    wins : int
        Matches the club won.
    draws : int
        Matches the club drew, a goalless one included: a nil-nil is a draw with
        no goals for either side, not a match with nothing to say about it.
    losses : int
        Matches the club lost.
    goals_for : int
        Goals the club scored.
    goals_against : int
        Goals the club conceded.
    synchronized_at : datetime or None
        Newest instant among the statistic rows folded in, ``None`` when none
        were.
    own : SideTotals
        Column totals of the club itself.
    opposition : SideTotals
        Column totals of the clubs it played, taken from the sibling row of each
        match rather than from a second stored figure.

    Methods
    -------
    count(match, statistics) -> None
        Fold one already-played match into the sample.
    metrics() -> tuple[MetricValue, ...]
        Return every metric of the sample, in the contracted order.
    """

    matches_counted: int = 0
    wins: int = 0
    draws: int = 0
    losses: int = 0
    goals_for: int = 0
    goals_against: int = 0
    synchronized_at: datetime | None = None
    own: SideTotals = field(default_factory=SideTotals)
    opposition: SideTotals = field(default_factory=SideTotals)

    def count(self, match: CountedMatch, statistics: StoredStatistics) -> None:
        """
        Fold one already-played match into the sample.

        Parameters
        ----------
        match : CountedMatch
            Match to count, whose score decides the result and whose identifier
            and side find the two statistic rows.
        statistics : StoredStatistics
            Every statistic row of every candidate match, keyed by match and
            side. A match with no row for a side contributes its result and
            nothing else, which is what a match whose statistics have not been
            synchronized yet looks like.
        """

        self.matches_counted += 1
        self.goals_for += match.goals_for
        self.goals_against += match.goals_against

        if match.goals_for > match.goals_against:
            self.wins += 1
        elif match.goals_for == match.goals_against:
            self.draws += 1
        else:
            self.losses += 1

        for side, totals in (
            (match.side, self.own),
            (opposing_side(match.side), self.opposition),
        ):
            stored = statistics.get((match.fixture_id, side))

            if stored is None:
                continue

            totals.add(stored.columns)

            if self.synchronized_at is None or stored.synchronized_at > self.synchronized_at:
                self.synchronized_at = stored.synchronized_at

    def metrics(self) -> tuple[MetricValue, ...]:
        """
        Return every metric of the sample, in the contracted order.

        Returns
        -------
        tuple of MetricValue
            Every metric of ``METRIC_ORDER``, in that order.
        """

        return tuple(metric_value(metric, self) for metric in METRIC_ORDER)


def opposing_side(side: MatchSide) -> MatchSide:
    """
    Return the side facing the given one in the same match.

    Parameters
    ----------
    side : MatchSide
        Side a club took.

    Returns
    -------
    MatchSide
        Side its opposition took, which is what selects the sibling statistic
        row of that match.
    """

    return MatchSide.AWAY if side == MatchSide.HOME else MatchSide.HOME


def metric_value(metric: FormMetric, totals: SampleTotals) -> MetricValue:
    """
    Compute one published figure of one sample.

    Four metrics come from the fixture score and the rest from the stored
    columns, which is a difference in where the number lives rather than a
    special case: the provider omits its own goals statistic at nought, so a
    goalless performance carries no statistic row and a goals metric sourced
    from the statistics would read every one of them as missing data.

    Parameters
    ----------
    metric : FormMetric
        Metric to compute. A member named by no table raises ``KeyError``, which
        is unreachable while the tables partition ``METRIC_ORDER`` and is worth
        hearing about if they ever stop.
    totals : SampleTotals
        Accumulated sample the figure is taken from.

    Returns
    -------
    MetricValue
        Published figure, carrying what the opposition recorded for every metric
        of ``OPPOSED_METRICS`` and ``None`` for the others.
    """

    match metric:
        case FormMetric.WIN_SHARE:
            share = percentage(totals.wins, totals.matches_counted)

            return MetricValue(metric=metric, value=share, opposed_value=None)

        case FormMetric.DRAW_SHARE:
            share = percentage(totals.draws, totals.matches_counted)

            return MetricValue(metric=metric, value=share, opposed_value=None)

        case FormMetric.LOSS_SHARE:
            share = percentage(totals.losses, totals.matches_counted)

            return MetricValue(metric=metric, value=share, opposed_value=None)

        case FormMetric.GOALS:
            return MetricValue(
                metric=metric,
                value=mean(totals.goals_for, totals.matches_counted),
                opposed_value=mean(totals.goals_against, totals.matches_counted),
            )

        case _ if metric in RATIO_COLUMNS:
            numerator, denominator = RATIO_COLUMNS[metric]

            completed = percentage(totals.own.total(numerator), totals.own.total(denominator))

            return MetricValue(metric=metric, value=completed, opposed_value=None)

        case _:
            column = AVERAGED_COLUMNS[metric]

            opposed = (
                mean(totals.opposition.total(column), totals.opposition.rows_counted)
                if metric in OPPOSED_METRICS
                else None
            )

            return MetricValue(
                metric=metric,
                value=mean(totals.own.total(column), totals.own.rows_counted),
                opposed_value=opposed,
            )


def counted_match(row: MatchRow, team_id: int) -> CountedMatch:
    """
    Read one loaded fixture row from the point of view of one club.

    Parameters
    ----------
    row : MatchRow
        Values of ``MATCH_COLUMNS`` of an already-played match.
    team_id : int
        Primary key of the club whose form is being read, which is one of the
        two clubs of the row.

    Returns
    -------
    CountedMatch
        Match seen from that club, with the side it took and the score the way
        round that club experienced it.
    """

    fixture_key, home_team_id, _away_team_id, home_goals, away_goals = row

    side = MatchSide.HOME if home_team_id == team_id else MatchSide.AWAY

    scored, conceded = (
        (home_goals, away_goals)
        if side == MatchSide.HOME
        else (
            away_goals,
            home_goals,
        )
    )

    return CountedMatch(fixture_id=fixture_key, side=side, goals_for=scored, goals_against=conceded)


def played_before(kickoff_at: datetime) -> QuerySet[Fixture]:
    """
    Return the matches a form sample is allowed to count.

    A match counts once it has kicked off before the fixture being read and has
    been played to a result. The fixture itself can never qualify, because a
    match does not kick off before itself, and neither can a later one, so the
    read is backward-looking by construction rather than by a caller
    remembering to make it so.

    A finished match with no score is excluded here rather than later. It cannot
    be classified as a win, a draw, or a loss, so a sample counting it would
    publish result shares that do not sum to a hundred, and excluding it in the
    statement also stops it from consuming one of the three or six places a
    range has.

    Parameters
    ----------
    kickoff_at : datetime
        Kick-off of the fixture being read, which is the exclusive upper bound
        of the window.

    Returns
    -------
    QuerySet of Fixture
        Unordered, unsliced base query the scoped reads narrow further.
    """

    return Fixture.objects.filter(
        kickoff_at__lt=kickoff_at,
        status=FixtureStatus.FINISHED,
        home_goals__isnull=False,
        away_goals__isnull=False,
    )


def recent_matches(
    team_id: int, kickoff_at: datetime, side: MatchSide | None
) -> list[CountedMatch]:
    """
    Read the deepest counted range of one club's latest matches.

    The statement is sliced to ``DEEPEST_COUNTED_RANGE``, so a club with fifteen
    seasons behind it costs exactly what a promoted one does, and the shallower
    ranges are then prefixes of the same list. It deliberately says nothing
    about the season: a range counted by matches crosses a season boundary,
    because a club's last three matches are its last three whether or not a
    summer fell in the middle of them.

    Parameters
    ----------
    team_id : int
        Primary key of the club whose matches are wanted.
    kickoff_at : datetime
        Kick-off of the fixture being read.
    side : MatchSide or None
        Side the matches have to have been played on, or ``None`` for either,
        which is the difference between the two scopes.

    Returns
    -------
    list of CountedMatch
        Matches newest first, at most ``DEEPEST_COUNTED_RANGE`` of them.
    """

    matches = played_before(kickoff_at)

    if side is None:
        matches = matches.filter(Q(home_team_id=team_id) | Q(away_team_id=team_id))
    elif side == MatchSide.HOME:
        matches = matches.filter(home_team_id=team_id)
    else:
        matches = matches.filter(away_team_id=team_id)

    rows = matches.order_by(*RECENT_ORDER).values_list(*MATCH_COLUMNS)[:DEEPEST_COUNTED_RANGE]

    return [counted_match(row, team_id) for row in rows]


def recent_scopes(team_id: int, side: MatchSide, kickoff_at: datetime) -> ScopedMatches:
    """
    Read both scopes of one club's latest matches.

    Parameters
    ----------
    team_id : int
        Primary key of the club whose matches are wanted.
    side : MatchSide
        Side that club takes in the fixture being read, which is what its
        venue scope means: the home club's venue form is its home matches and
        the away club's is its away matches.
    kickoff_at : datetime
        Kick-off of the fixture being read.

    Returns
    -------
    dict of FormScope to list of CountedMatch
        Matches newest first under each scope, two statements in total.
    """

    return {
        FormScope.OVERALL: recent_matches(team_id, kickoff_at, None),
        FormScope.VENUE: recent_matches(team_id, kickoff_at, side),
    }


def season_matches(
    team_ids: Sequence[int], season_provider_id: int | None, kickoff_at: datetime
) -> list[MatchRow]:
    """
    Read every already-played match of the fixture's season, for both clubs.

    One statement serves both clubs, which is what makes the read cost the same
    whether the two have met before or not: a derby appears once and is counted
    from both points of view in memory.

    Parameters
    ----------
    team_ids : sequence of int
        Primary keys of the two clubs of the fixture being read.
    season_provider_id : int or None
        Provider identifier of the season the fixture belongs to, or ``None``
        for a fixture the provider gave no season. The season is then unknown
        rather than empty, so nothing is read and the season samples come back
        with no matches counted: a read filtering on a null season would gather
        every other seasonless match in the table, which is a different
        question and a wrong answer.
    kickoff_at : datetime
        Kick-off of the fixture being read.

    Returns
    -------
    list of MatchRow
        Values of ``MATCH_COLUMNS`` of every qualifying match, newest first.
    """

    if season_provider_id is None:
        return []

    rows = (
        played_before(kickoff_at)
        .filter(season_sportmonks_id=season_provider_id)
        .filter(Q(home_team_id__in=team_ids) | Q(away_team_id__in=team_ids))
        .order_by(*RECENT_ORDER)
        .values_list(*MATCH_COLUMNS)
    )

    return list(rows)


def season_scopes(rows: Sequence[MatchRow], team_id: int, side: MatchSide) -> ScopedMatches:
    """
    Split the season's matches into the two scopes of one club.

    Parameters
    ----------
    rows : sequence of MatchRow
        Season rows of both clubs, as ``season_matches`` returned them.
    team_id : int
        Primary key of the club the scopes belong to.
    side : MatchSide
        Side that club takes in the fixture being read.

    Returns
    -------
    dict of FormScope to list of CountedMatch
        Every season match of the club under the overall scope, and the ones it
        played on its own side under the venue scope.
    """

    overall = [counted_match(row, team_id) for row in rows if team_id in (row[1], row[2])]

    return {
        FormScope.OVERALL: overall,
        FormScope.VENUE: [match for match in overall if match.side == side],
    }


def counted_fixture_ids(scopes: Iterable[ScopedMatches]) -> set[int]:
    """
    Return the matches every sample of the fixture could read a statistic of.

    Parameters
    ----------
    scopes : iterable of dict of FormScope to list of CountedMatch
        Every scoped set of matches the samples will be folded from.

    Returns
    -------
    set of int
        Primary keys of the matches, deduplicated because the scopes overlap: a
        club's venue matches are also overall matches, and its recent matches
        are usually also season ones.
    """

    return {
        match.fixture_id for scoped in scopes for matches in scoped.values() for match in matches
    }


def load_statistics(fixture_ids: set[int]) -> StoredStatistics:
    """
    Read both statistic rows of every candidate match, in one statement.

    Both sides of a match are loaded rather than only the club being read,
    because what the opposition recorded is the sibling row of the same match
    and loading it here costs no statement at all. The read takes columns rather
    than model instances: a fixture carrying twelve matches per scope would
    otherwise instantiate dozens of objects to sum twenty-two integers out of
    each.

    Parameters
    ----------
    fixture_ids : set of int
        Primary keys of the matches whose statistics are wanted. An empty set
        issues no statement, which is what two clubs with no qualifying history
        cost.

    Returns
    -------
    dict of tuple of (int, str) to SideStatistics
        Stored performances keyed by match and side.
    """

    stored = (
        MatchTeamStatistic.objects.filter(fixture_id__in=fixture_ids)
        .order_by()
        .values_list("fixture_id", "side", *STATISTIC_COLUMNS, "synchronized_at")
    )

    return {
        (row[0], row[1]): SideStatistics(columns=row[2:-1], synchronized_at=row[-1])
        for row in stored
    }


def team_form(
    team_id: int, recent: ScopedMatches, season: ScopedMatches, statistics: StoredStatistics
) -> tuple[TeamForm, datetime | None]:
    """
    Fold one club's loaded matches into the six samples it publishes.

    Nothing here reaches the database. The ranges counted by matches are
    prefixes of the loaded list and the season ranges are the loaded season, so
    the six samples are six folds over rows already in memory, and the ordering
    the contract promises is applied from the domain tables rather than by a
    second query with a different ``ORDER BY``.

    Parameters
    ----------
    team_id : int
        Primary key of the club.
    recent : dict of FormScope to list of CountedMatch
        Its latest matches under each scope, newest first.
    season : dict of FormScope to list of CountedMatch
        Its matches of the fixture's season under each scope.
    statistics : StoredStatistics
        Every statistic row of every candidate match, keyed by match and side.

    Returns
    -------
    TeamForm
        Samples in ``RANGE_ORDER`` by ``SCOPE_ORDER`` order.
    datetime or None
        Newest instant among the statistic rows that fed any of those samples,
        ``None`` when none did.
    """

    samples: list[FormSample] = []
    synchronized_at: datetime | None = None

    for counted_range in RANGE_ORDER:
        depth = RANGE_SIZES[counted_range]

        for scope in SCOPE_ORDER:
            matches = season[scope] if depth is None else recent[scope][:depth]

            totals = SampleTotals()

            for match in matches:
                totals.count(match, statistics)

            samples.append(
                FormSample(
                    range=counted_range,
                    scope=scope,
                    matches_counted=totals.matches_counted,
                    metrics=totals.metrics(),
                )
            )

            if totals.synchronized_at is not None and (
                synchronized_at is None or totals.synchronized_at > synchronized_at
            ):
                synchronized_at = totals.synchronized_at

    return TeamForm(team_id=team_id, samples=tuple(samples)), synchronized_at


def get_fixture_form(fixture_id: int) -> FixtureForm | None:
    """
    Return both clubs' form before a fixture, in the contracted order.

    Seven statements answer the whole payload however much history the two
    clubs have: one resolving the fixture, one per club and scope for the
    matches a counted range can reach, one for the season of both clubs at
    once, and one for the statistic rows of everything loaded. The twelve
    samples are then folded in memory. Nothing in that count depends on how
    many matches a club has played, because every backward-looking read is
    either sliced to ``DEEPEST_COUNTED_RANGE`` or bounded by one season, and
    nothing depends on how many samples are published, because they all read
    the same loaded rows.

    A fixture the provider gave no season costs one statement fewer and
    publishes empty season samples, and two clubs with no qualifying history
    cost one fewer again, because there are no matches to read statistics of.

    Parameters
    ----------
    fixture_id : int
        Primary key of the fixture whose form is wanted.

    Returns
    -------
    FixtureForm or None
        Form of both clubs, or ``None`` when no fixture carries that key. A
        fixture whose clubs have never played answers with samples counting no
        matches instead, because "there is nothing behind this match" and
        "there is no such match" are different answers.
    """

    stored = (
        Fixture.objects.filter(pk=fixture_id)
        .values_list("home_team_id", "away_team_id", "kickoff_at", "season_sportmonks_id")
        .first()
    )

    if stored is None:
        return None

    home_team_id, away_team_id, kickoff_at, season_provider_id = stored

    home_recent = recent_scopes(home_team_id, MatchSide.HOME, kickoff_at)
    away_recent = recent_scopes(away_team_id, MatchSide.AWAY, kickoff_at)

    rows = season_matches((home_team_id, away_team_id), season_provider_id, kickoff_at)

    home_season = season_scopes(rows, home_team_id, MatchSide.HOME)
    away_season = season_scopes(rows, away_team_id, MatchSide.AWAY)

    statistics = load_statistics(
        counted_fixture_ids((home_recent, away_recent, home_season, away_season))
    )

    home, home_synchronized_at = team_form(home_team_id, home_recent, home_season, statistics)
    away, away_synchronized_at = team_form(away_team_id, away_recent, away_season, statistics)

    stamps = [stamp for stamp in (home_synchronized_at, away_synchronized_at) if stamp is not None]

    return FixtureForm(
        fixture_id=fixture_id,
        synchronized_at=max(stamps) if stamps else None,
        home=home,
        away=away,
    )
