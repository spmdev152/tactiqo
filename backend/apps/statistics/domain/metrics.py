from apps.statistics.domain.enums import FormFamily, FormMetric, FormRange, FormScope

# Every structure below is the order or the property the public contract
# promises, so the interface renders what it is handed instead of holding a
# second copy of this vocabulary and having to be kept in step with it. None of
# them is derivable: the enumerations declare their members for readability, and
# a family's metrics are neither alphabetical nor a partition of the enumeration.
FAMILY_ORDER: tuple[FormFamily, ...] = (
    FormFamily.RESULT,
    FormFamily.ATTACKING,
    FormFamily.POSSESSION,
    FormFamily.DEFENDING,
    FormFamily.DISCIPLINE,
)

FAMILY_METRICS: dict[FormFamily, tuple[FormMetric, ...]] = {
    FormFamily.RESULT: (
        FormMetric.WIN_SHARE,
        FormMetric.DRAW_SHARE,
        FormMetric.LOSS_SHARE,
        FormMetric.GOALS,
    ),
    FormFamily.ATTACKING: (
        FormMetric.SHOTS,
        FormMetric.SHOTS_ON_TARGET,
        FormMetric.SHOTS_INSIDE_BOX,
        FormMetric.BIG_CHANCES_CREATED,
        FormMetric.KEY_PASSES,
        FormMetric.CORNERS,
    ),
    FormFamily.POSSESSION: (
        FormMetric.POSSESSION,
        FormMetric.PASSES,
        FormMetric.PASS_ACCURACY,
        FormMetric.CROSSES,
        FormMetric.CROSS_ACCURACY,
        FormMetric.DRIBBLE_SUCCESS,
    ),
    FormFamily.DEFENDING: (
        FormMetric.SAVES,
        FormMetric.TACKLES,
        FormMetric.INTERCEPTIONS,
        FormMetric.DUELS_WON,
        FormMetric.SHOTS_BLOCKED,
    ),
    FormFamily.DISCIPLINE: (
        FormMetric.FOULS,
        FormMetric.YELLOW_CARDS,
        FormMetric.RED_CARDS,
        FormMetric.OFFSIDES,
    ),
}

METRIC_ORDER: tuple[FormMetric, ...] = tuple(
    metric for family in FAMILY_ORDER for metric in FAMILY_METRICS[family]
)

# The metrics that also state what the opposition recorded, which is the sibling
# row of the same match rather than a second stored column. Possession is
# deliberately absent: its two sides sum to a hundred, so the opposing figure
# would carry no information the published one does not.
OPPOSED_METRICS: frozenset[FormMetric] = frozenset(
    {
        FormMetric.GOALS,
        FormMetric.SHOTS,
        FormMetric.SHOTS_ON_TARGET,
        FormMetric.BIG_CHANCES_CREATED,
        FormMetric.CORNERS,
    }
)

# The metrics whose value is a percentage rather than a per-match average. The
# distinction is published so the panel formats a share and an average
# differently without inferring it from the member name.
SHARE_METRICS: frozenset[FormMetric] = frozenset(
    {
        FormMetric.WIN_SHARE,
        FormMetric.DRAW_SHARE,
        FormMetric.LOSS_SHARE,
        FormMetric.POSSESSION,
        FormMetric.PASS_ACCURACY,
        FormMetric.CROSS_ACCURACY,
        FormMetric.DRIBBLE_SUCCESS,
    }
)

RANGE_ORDER: tuple[FormRange, ...] = (FormRange.LAST_3, FormRange.LAST_6, FormRange.SEASON)

SCOPE_ORDER: tuple[FormScope, ...] = (FormScope.OVERALL, FormScope.VENUE)

# How many matches each range keeps. ``SEASON`` is unbounded by a count and
# bounded by the season instead, which is why it maps to nothing rather than to a
# large number.
RANGE_SIZES: dict[FormRange, int | None] = {
    FormRange.LAST_3: 3,
    FormRange.LAST_6: 6,
    FormRange.SEASON: None,
}

# Deepest count any range asks for, which is what bounds the number of matches a
# read has to load per team and per scope.
DEEPEST_COUNTED_RANGE = max(size for size in RANGE_SIZES.values() if size is not None)
