from collections.abc import Sequence
from datetime import date, timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.fixtures.domain.enums import FixtureStatus
from apps.fixtures.models import Fixture
from apps.statistics.application.queries import (
    FixtureForm,
    FormSample,
    MetricValue,
    TeamForm,
    get_fixture_form,
)
from apps.statistics.domain.enums import FormMetric, FormRange, FormScope, MatchSide
from apps.statistics.domain.metrics import METRIC_ORDER, RANGE_ORDER, SCOPE_ORDER
from integrations.sportmonks.fixtures import ProviderFixture, ProviderTeam
from integrations.sportmonks.statistics import ProviderFixtureStatistics
from tests.unit.fixtures.conftest import (
    LIVERPOOL,
    NOTTINGHAM_FOREST,
    SEASON_ID,
    kickoff,
    provider_fixture,
)
from tests.unit.statistics.conftest import (
    LATER_SYNCHRONIZED_AT,
    fixture_statistics,
    seed_fixtures,
    store_statistics,
    team_statistics,
)

TARGET_PROVIDER_ID = 100

KICKOFF_AT = kickoff(12)

PREVIOUS_SEASON_ID = SEASON_ID - 1

OLDER_SEASON_ID = PREVIOUS_SEASON_ID - 1

# Wide enough for every match a test seeds, because one call is one
# authoritative window and the range is what the reconciliation clears.
SEEDED_START = date(2025, 1, 1)

SEEDED_END = date(2027, 1, 1)

# One statement resolving the fixture, one loading the already-played matches of
# its season for both clubs, and one loading the statistic rows of those
# matches. Every range is a prefix of what the second returned, so no sample
# costs a read of its own.
EXPECTED_QUERY_COUNT = 3

ARSENAL = ProviderTeam(
    provider_id=19,
    name="Arsenal",
    short_code="ARS",
    crest_url="https://cdn.example.test/teams/19.png",
)

CHELSEA = ProviderTeam(
    provider_id=18,
    name="Chelsea",
    short_code="CHE",
    crest_url="https://cdn.example.test/teams/18.png",
)

EVERTON = ProviderTeam(
    provider_id=13,
    name="Everton",
    short_code="EVE",
    crest_url="https://cdn.example.test/teams/13.png",
)


def target(
    *,
    season_provider_id: int | None = SEASON_ID,
    status: FixtureStatus = FixtureStatus.SCHEDULED,
    home_goals: int | None = None,
    away_goals: int | None = None,
) -> ProviderFixture:
    """
    Build the fixture whose form every test below reads.

    Parameters
    ----------
    season_provider_id : int or None
        Season the match belongs to, ``None`` for one the provider states no
        season for.
    status : FixtureStatus
        Lifecycle stage of the match, which is scheduled for a form read taken
        before it and finished for one taken after.
    home_goals : int or None
        Goals the home club has scored.
    away_goals : int or None
        Goals the away club has scored.

    Returns
    -------
    ProviderFixture
        Liverpool at home to Nottingham Forest, shaped as the boundary yields
        one.
    """

    return provider_fixture(
        TARGET_PROVIDER_ID,
        KICKOFF_AT,
        season_provider_id=season_provider_id,
        status=status,
        home_goals=home_goals,
        away_goals=away_goals,
    )


UPCOMING = target()


def played(
    provider_id: int,
    days_before: int,
    *,
    home_team: ProviderTeam = LIVERPOOL,
    away_team: ProviderTeam = NOTTINGHAM_FOREST,
    home_goals: int | None = 1,
    away_goals: int | None = 0,
    season_provider_id: int | None = SEASON_ID,
) -> ProviderFixture:
    """
    Build one already-played match, positioned relative to the target kick-off.

    Parameters
    ----------
    provider_id : int
        Provider identifier of the match, which is its natural key.
    days_before : int
        Days between this kick-off and the target one, negative for a match
        played after it.
    home_team : ProviderTeam
        Club playing at home.
    away_team : ProviderTeam
        Club playing away.
    home_goals : int or None
        Goals the home club scored, ``None`` for a finished match the provider
        published no score for.
    away_goals : int or None
        Goals the away club scored.
    season_provider_id : int or None
        Season the match belongs to.

    Returns
    -------
    ProviderFixture
        Finished match shaped as the boundary yields one.
    """

    return provider_fixture(
        provider_id,
        KICKOFF_AT - timedelta(days=days_before),
        season_provider_id=season_provider_id,
        home_team=home_team,
        away_team=away_team,
        status=FixtureStatus.FINISHED,
        home_goals=home_goals,
        away_goals=away_goals,
    )


def seed(
    matches: Sequence[ProviderFixture] = (), upcoming: ProviderFixture = UPCOMING
) -> dict[int, Fixture]:
    """
    Store the target fixture together with the history behind it.

    Parameters
    ----------
    matches : Sequence of ProviderFixture
        Already-played matches to store alongside the target.
    upcoming : ProviderFixture
        The target fixture itself, stated where a test is about its season or
        its own lifecycle stage.

    Returns
    -------
    dict of int to Fixture
        Every stored match, keyed by provider identifier.
    """

    return seed_fixtures([upcoming, *matches], start=SEEDED_START, end=SEEDED_END)


def performances(
    provider_id: int,
    *,
    home: dict[str, int] | None = None,
    away: dict[str, int] | None = None,
    home_team: ProviderTeam = LIVERPOOL,
    away_team: ProviderTeam = NOTTINGHAM_FOREST,
) -> ProviderFixtureStatistics:
    """
    Build both sides' figures for one match.

    Both sides are always built, because the provider publishes a match with
    both or with neither and the opposing figures a sample reads are the sibling
    row of the same match.

    Parameters
    ----------
    provider_id : int
        Provider identifier of the match the figures belong to.
    home : dict of str to int or None
        Figures to override for the home club, keyed by stored column.
    away : dict of str to int or None
        Figures to override for the away club.
    home_team : ProviderTeam
        Club that played at home.
    away_team : ProviderTeam
        Club that played away.

    Returns
    -------
    ProviderFixtureStatistics
        Entry shaped exactly as the Sportmonks boundary yields one.
    """

    return fixture_statistics(
        provider_id,
        [
            team_statistics(home_team.provider_id, MatchSide.HOME, **(home or {})),
            team_statistics(away_team.provider_id, MatchSide.AWAY, **(away or {})),
        ],
    )


def read_form(stored: dict[int, Fixture]) -> FixtureForm:
    """
    Read the form of the target fixture, asserting the query found it.

    Parameters
    ----------
    stored : dict of int to Fixture
        Every stored match, as ``seed`` returned it.

    Returns
    -------
    FixtureForm
        Form of both clubs of the target fixture.
    """

    form = get_fixture_form(stored[TARGET_PROVIDER_ID].pk)

    assert form is not None

    return form


def sample_of(team: TeamForm, counted_range: FormRange, scope: FormScope) -> FormSample:
    """
    Return one sample of one club, addressed by its range and scope.

    Parameters
    ----------
    team : TeamForm
        Form of the club.
    counted_range : FormRange
        Range the sample covers.
    scope : FormScope
        Scope the sample counts under.

    Returns
    -------
    FormSample
        The single sample carrying that range and that scope.
    """

    return next(
        sample for sample in team.samples if sample.range == counted_range and sample.scope == scope
    )


def figure_of(sample: FormSample, metric: FormMetric) -> MetricValue:
    """
    Return one published figure of one sample.

    Parameters
    ----------
    sample : FormSample
        Sample the figure belongs to.
    metric : FormMetric
        Metric wanted.

    Returns
    -------
    MetricValue
        The single figure of that metric.
    """

    return next(figure for figure in sample.metrics if figure.metric == metric)


def recent_share(team: TeamForm, scope: FormScope, metric: FormMetric) -> float:
    """
    Return one figure of a club's last three matches under one scope.

    Parameters
    ----------
    team : TeamForm
        Form of the club.
    scope : FormScope
        Scope the sample counts under.
    metric : FormMetric
        Metric wanted.

    Returns
    -------
    float
        Published figure of that metric.
    """

    return figure_of(sample_of(team, FormRange.LAST_3, scope), metric).value


@pytest.mark.django_db
def test_get_fixture_form_returns_none_for_an_unknown_fixture() -> None:
    """
    GIVEN a stored fixture and the identifier that follows its primary key
    WHEN the form of that identifier is read
    THEN nothing comes back, which is how the caller learns there is no fixture
    """

    stored = seed()

    assert get_fixture_form(stored[TARGET_PROVIDER_ID].pk + 1) is None


@pytest.mark.django_db
def test_get_fixture_form_counts_the_venue_scope_from_each_club_s_own_side() -> None:
    """
    GIVEN two clubs that won on the side each takes here and lost on the other
    WHEN the form before the fixture is read
    THEN each venue scope counts that club's own side rather than the home one
    """

    form = read_form(
        seed(
            [
                played(1, 1, away_team=ARSENAL, home_goals=2, away_goals=0),
                played(2, 2, home_team=CHELSEA, away_team=LIVERPOOL, home_goals=3, away_goals=0),
                played(3, 3, away_team=EVERTON, home_goals=1, away_goals=0),
                played(4, 1, home_team=ARSENAL, home_goals=0, away_goals=1),
                played(
                    5, 2, home_team=NOTTINGHAM_FOREST, away_team=CHELSEA, home_goals=0, away_goals=2
                ),
                played(6, 3, home_team=EVERTON, home_goals=1, away_goals=2),
            ]
        )
    )

    assert (
        recent_share(form.home, FormScope.OVERALL, FormMetric.WIN_SHARE),
        recent_share(form.home, FormScope.VENUE, FormMetric.WIN_SHARE),
        recent_share(form.away, FormScope.OVERALL, FormMetric.WIN_SHARE),
        recent_share(form.away, FormScope.VENUE, FormMetric.WIN_SHARE),
    ) == (66.67, 100.0, 66.67, 100.0)


@pytest.mark.django_db
def test_get_fixture_form_confines_every_range_to_the_fixture_s_own_season() -> None:
    """
    GIVEN a club with two matches this season and two in the one before it
    WHEN the form before the fixture is read
    THEN the boundary stops every range, so all three count the same two
    """

    form = read_form(
        seed(
            [
                played(1, 1, away_team=ARSENAL),
                played(2, 2, home_team=CHELSEA, away_team=LIVERPOOL),
                played(3, 300, away_team=EVERTON, season_provider_id=PREVIOUS_SEASON_ID),
                played(
                    4,
                    301,
                    home_team=ARSENAL,
                    away_team=LIVERPOOL,
                    season_provider_id=PREVIOUS_SEASON_ID,
                ),
            ]
        )
    )

    assert [
        sample_of(form.home, counted_range, FormScope.OVERALL).matches_counted
        for counted_range in RANGE_ORDER
    ] == [2, 2, 2]


@pytest.mark.django_db
def test_get_fixture_form_publishes_one_match_identically_across_the_three_ranges() -> None:
    """
    GIVEN a club whose season holds a single match before the fixture
    WHEN the form before the fixture is read
    THEN the three ranges count that match and publish figures that agree
    """

    stored = seed([played(1, 1, away_team=ARSENAL, home_goals=2, away_goals=1)])

    store_statistics([performances(1, home={"shots_total": 14}, away_team=ARSENAL)])

    form = read_form(stored)

    samples = [
        sample_of(form.home, counted_range, FormScope.OVERALL) for counted_range in RANGE_ORDER
    ]

    assert (
        {sample.matches_counted for sample in samples},
        len({sample.metrics for sample in samples}),
        figure_of(samples[0], FormMetric.GOALS).value,
        figure_of(samples[0], FormMetric.SHOTS).value,
    ) == ({1}, 1, 2.0, 14.0)


@pytest.mark.django_db
def test_get_fixture_form_takes_the_three_newest_of_four_matches_in_a_season() -> None:
    """
    GIVEN a club whose season holds four matches before the fixture, scoring 4 to 1
    WHEN the form before the fixture is read
    THEN the last three counts the three newest and the wider two count all four
    """

    form = read_form(
        seed(
            [
                played(1, 1, away_team=ARSENAL, home_goals=4, away_goals=0),
                played(2, 2, away_team=EVERTON, home_goals=3, away_goals=0),
                played(3, 3, away_team=CHELSEA, home_goals=2, away_goals=0),
                played(4, 4, away_team=ARSENAL, home_goals=1, away_goals=0),
            ]
        )
    )

    samples = [
        sample_of(form.home, counted_range, FormScope.OVERALL) for counted_range in RANGE_ORDER
    ]

    assert [
        (sample.matches_counted, figure_of(sample, FormMetric.GOALS).value) for sample in samples
    ] == [(3, 3.0), (4, 2.5), (4, 2.5)]


@pytest.mark.django_db
def test_get_fixture_form_reads_a_past_fixture_from_the_season_it_belongs_to() -> None:
    """
    GIVEN a played fixture of an earlier season, with a match on each side of it
    WHEN the form before it is read
    THEN only that season's earlier match counts, in every one of the ranges
    """

    form = read_form(
        seed(
            [
                played(
                    1,
                    1,
                    away_team=ARSENAL,
                    home_goals=3,
                    away_goals=0,
                    season_provider_id=PREVIOUS_SEASON_ID,
                ),
                played(2, 300, away_team=EVERTON, season_provider_id=OLDER_SEASON_ID),
                played(3, -1, away_team=CHELSEA, home_goals=5, away_goals=0),
            ],
            target(
                season_provider_id=PREVIOUS_SEASON_ID,
                status=FixtureStatus.FINISHED,
                home_goals=1,
                away_goals=0,
            ),
        )
    )

    samples = [
        sample_of(form.home, counted_range, FormScope.OVERALL) for counted_range in RANGE_ORDER
    ]

    assert [
        (sample.matches_counted, figure_of(sample, FormMetric.GOALS).value) for sample in samples
    ] == [(1, 3.0), (1, 3.0), (1, 3.0)]


@pytest.mark.django_db
def test_get_fixture_form_counts_nothing_at_all_for_a_fixture_without_a_season() -> None:
    """
    GIVEN a fixture the provider stated no season for, behind it two matches
    WHEN the form before it is read
    THEN no range reaches them, and every sample still publishes every metric
    """

    form = read_form(
        seed(
            [
                played(1, 1, away_team=ARSENAL),
                played(2, 2, home_team=CHELSEA, away_team=LIVERPOOL),
            ],
            target(season_provider_id=None),
        )
    )

    sample = sample_of(form.home, FormRange.LAST_3, FormScope.OVERALL)

    assert (
        [counted.matches_counted for counted in form.home.samples],
        tuple(figure.metric for figure in sample.metrics),
        {figure.value for figure in sample.metrics},
    ) == ([0, 0, 0, 0, 0, 0], METRIC_ORDER, {0.0})


@pytest.mark.django_db
def test_get_fixture_form_counts_a_goalless_match_as_a_draw() -> None:
    """
    GIVEN a club whose single previous match finished without a goal in it
    WHEN the form before the fixture is read
    THEN it is a draw with no goals either way rather than an uncounted match
    """

    form = read_form(seed([played(1, 1, away_team=ARSENAL, home_goals=0, away_goals=0)]))

    sample = sample_of(form.home, FormRange.LAST_3, FormScope.OVERALL)

    goals = figure_of(sample, FormMetric.GOALS)

    assert (
        sample.matches_counted,
        figure_of(sample, FormMetric.DRAW_SHARE).value,
        figure_of(sample, FormMetric.WIN_SHARE).value,
        goals.value,
        goals.opposed_value,
    ) == (1, 100.0, 0.0, 0.0, 0.0)


@pytest.mark.django_db
def test_get_fixture_form_excludes_a_finished_match_without_a_score() -> None:
    """
    GIVEN two finished matches, the more recent of which carries no score
    WHEN the form before the fixture is read
    THEN only the scored one is counted, and it does not lose its place to it
    """

    form = read_form(
        seed(
            [
                played(1, 1, away_team=ARSENAL, home_goals=None, away_goals=None),
                played(2, 2, away_team=EVERTON, home_goals=2, away_goals=0),
            ]
        )
    )

    sample = sample_of(form.home, FormRange.LAST_3, FormScope.OVERALL)

    assert (
        sample.matches_counted,
        figure_of(sample, FormMetric.WIN_SHARE).value,
        figure_of(sample, FormMetric.GOALS).value,
    ) == (1, 100.0, 2.0)


@pytest.mark.django_db
def test_get_fixture_form_takes_an_accuracy_as_the_ratio_of_the_sums() -> None:
    """
    GIVEN two matches completing a quarter of a few attempts and most of many
    WHEN the form before the fixture is read
    THEN every rate is the summed completions over the summed attempts, 65 here
    """

    stored = seed(
        [
            played(1, 1, away_team=ARSENAL),
            played(2, 2, away_team=EVERTON),
        ]
    )

    store_statistics(
        [
            performances(
                1,
                home={
                    "passes": 100,
                    "successful_passes": 25,
                    "crosses": 20,
                    "accurate_crosses": 5,
                    "dribble_attempts": 20,
                    "successful_dribbles": 5,
                },
                away_team=ARSENAL,
            ),
            performances(
                2,
                home={
                    "passes": 400,
                    "successful_passes": 300,
                    "crosses": 80,
                    "accurate_crosses": 60,
                    "dribble_attempts": 80,
                    "successful_dribbles": 60,
                },
                away_team=EVERTON,
            ),
        ]
    )

    sample = sample_of(read_form(stored).home, FormRange.LAST_3, FormScope.OVERALL)

    assert [
        figure_of(sample, metric).value
        for metric in (
            FormMetric.PASS_ACCURACY,
            FormMetric.CROSS_ACCURACY,
            FormMetric.DRIBBLE_SUCCESS,
        )
    ] == [65.0, 65.0, 65.0]


@pytest.mark.django_db
def test_get_fixture_form_publishes_a_zero_rate_for_a_club_that_attempted_none() -> None:
    """
    GIVEN a club whose single previous match produced no cross at all
    WHEN the form before the fixture is read
    THEN its cross accuracy is zero rather than a division by nothing
    """

    stored = seed([played(1, 1, away_team=ARSENAL)])

    store_statistics(
        [performances(1, home={"crosses": 0, "accurate_crosses": 0}, away_team=ARSENAL)]
    )

    sample = sample_of(read_form(stored).home, FormRange.LAST_3, FormScope.OVERALL)

    assert figure_of(sample, FormMetric.CROSS_ACCURACY).value == 0.0


@pytest.mark.django_db
def test_get_fixture_form_takes_the_opposed_figure_from_the_sibling_row() -> None:
    """
    GIVEN one previous match whose two clubs recorded different figures
    WHEN the form before the fixture is read
    THEN an opposed metric carries the other club's figure and the rest carry none
    """

    stored = seed([played(1, 1, away_team=ARSENAL, home_goals=2, away_goals=1)])

    store_statistics(
        [
            performances(
                1,
                home={"shots_total": 14, "corners": 7, "fouls": 11},
                away={"shots_total": 7, "corners": 3, "fouls": 16},
                away_team=ARSENAL,
            )
        ]
    )

    sample = sample_of(read_form(stored).home, FormRange.LAST_3, FormScope.OVERALL)

    shots = figure_of(sample, FormMetric.SHOTS)

    goals = figure_of(sample, FormMetric.GOALS)

    fouls = figure_of(sample, FormMetric.FOULS)

    assert (
        (shots.value, shots.opposed_value),
        (goals.value, goals.opposed_value),
        (fouls.value, fouls.opposed_value),
    ) == ((14.0, 7.0), (2.0, 1.0), (11.0, None))


@pytest.mark.django_db
def test_get_fixture_form_publishes_every_metric_for_a_club_without_history() -> None:
    """
    GIVEN a fixture between two clubs that have never played a counted match
    WHEN the form before it is read
    THEN every sample counts nothing and still publishes every metric at zero
    """

    form = read_form(seed())

    sample = sample_of(form.home, FormRange.LAST_3, FormScope.OVERALL)

    assert (
        [counted.matches_counted for counted in form.home.samples],
        tuple(figure.metric for figure in sample.metrics),
        {figure.value for figure in sample.metrics},
        form.synchronized_at,
    ) == ([0, 0, 0, 0, 0, 0], METRIC_ORDER, {0.0}, None)


@pytest.mark.django_db
def test_get_fixture_form_emits_the_samples_in_the_contracted_order() -> None:
    """
    GIVEN a fixture whose form is read
    WHEN its samples are listed
    THEN they come back by range then by scope, as the domain tables promise
    """

    form = read_form(seed())

    assert [(sample.range, sample.scope) for sample in form.home.samples] == [
        (counted_range, scope) for counted_range in RANGE_ORDER for scope in SCOPE_ORDER
    ]


@pytest.mark.django_db
def test_get_fixture_form_counts_neither_the_fixture_itself_nor_a_later_match() -> None:
    """
    GIVEN a played fixture with one match before it and one after it
    WHEN the form before it is read
    THEN only the earlier match is counted, neither the later one nor itself
    """

    form = read_form(
        seed(
            [
                played(1, 1, away_team=ARSENAL, home_goals=1, away_goals=0),
                played(2, -1, away_team=EVERTON, home_goals=5, away_goals=0),
            ],
            target(status=FixtureStatus.FINISHED, home_goals=3, away_goals=0),
        )
    )

    sample = sample_of(form.home, FormRange.LAST_3, FormScope.OVERALL)

    assert (sample.matches_counted, figure_of(sample, FormMetric.GOALS).value) == (1, 1.0)


@pytest.mark.django_db
def test_get_fixture_form_stamps_the_payload_with_the_newest_row_that_fed_it() -> None:
    """
    GIVEN two counted matches whose statistics were synchronized at two instants
    WHEN the form before the fixture is read
    THEN the payload carries the newer of the two rather than the newer fixture
    """

    stored = seed(
        [
            played(1, 1, away_team=ARSENAL),
            played(2, 2, away_team=EVERTON),
        ]
    )

    store_statistics([performances(1, away_team=ARSENAL)])
    store_statistics([performances(2, away_team=EVERTON)], LATER_SYNCHRONIZED_AT)

    assert read_form(stored).synchronized_at == LATER_SYNCHRONIZED_AT


@pytest.mark.django_db
def test_get_fixture_form_reads_a_long_history_in_three_statements() -> None:
    """
    GIVEN a club with a full season of counted matches behind the fixture
    WHEN the form before it is read
    THEN three statements answer all twelve samples
    """

    stored = seed(
        [
            played(index, index, away_team=ARSENAL if index % 2 else EVERTON)
            for index in range(1, 13)
        ]
    )

    store_statistics([performances(1, away_team=ARSENAL)])

    with CaptureQueriesContext(connection) as statements:
        read_form(stored)

    assert len(statements) == EXPECTED_QUERY_COUNT


@pytest.mark.django_db
def test_get_fixture_form_reads_a_short_history_in_the_same_three_statements() -> None:
    """
    GIVEN a club with a single counted match behind the fixture
    WHEN the form before it is read
    THEN the same three statements answer it, so the cost is not per match
    """

    stored = seed([played(1, 1, away_team=ARSENAL)])

    store_statistics([performances(1, away_team=ARSENAL)])

    with CaptureQueriesContext(connection) as statements:
        read_form(stored)

    assert len(statements) == EXPECTED_QUERY_COUNT
