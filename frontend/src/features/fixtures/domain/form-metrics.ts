/**
 * Every figure a form sample publishes, as the API serializes them.
 *
 * @remarks
 * A closed vocabulary the backend owns, kept here as one tuple so the wire
 * schema and the product type cannot drift apart: the schema validates against
 * it and the type is derived from it.
 *
 * The order is the order the API promises, which is also the order the panel
 * reads in — every family's metrics in turn, families in their own order. It is
 * preserved rather than re-derived, so the product decision lives in one place.
 *
 * The members are the platform's own names, not the provider's numeric type
 * ids. Sportmonks identifies a statistic by an integer, and that integer stops
 * at the provider boundary so nothing above it has to know that `86` and
 * `shots_on_target` are the same thing. Three members are not provider figures
 * at all: the result shares are computed from the stored score, because the
 * provider omits its goals type at nought and a goalless match would otherwise
 * read as missing data.
 */
export const FORM_METRICS = [
  "win_share",
  "draw_share",
  "loss_share",
  "goals",
  "shots",
  "shots_on_target",
  "shots_inside_box",
  "big_chances_created",
  "key_passes",
  "corners",
  "possession",
  "passes",
  "pass_accuracy",
  "crosses",
  "cross_accuracy",
  "dribble_success",
  "saves",
  "tackles",
  "interceptions",
  "duels_won",
  "shots_blocked",
  "fouls",
  "yellow_cards",
  "red_cards",
  "offsides",
] as const;

/**
 * One figure a form sample publishes.
 */
export type FormMetric = (typeof FORM_METRICS)[number];

/**
 * Every figure a sample publishes twice: once for what the team records and
 * once for what the opposition records against it.
 *
 * @remarks
 * A subset of {@link FORM_METRICS} rather than a flag on the wire, because
 * which figures have an opposite is a property of the metric and never varies
 * by fixture. Each of these is read as two comparisons — what a side does and
 * what is done to it — and the second is the one a pre-match reader cannot get
 * anywhere else in the panel, because it says which side concedes more of this.
 *
 * The order is the order these members hold in {@link FORM_METRICS}, so the two
 * tuples read the same way round.
 */
export const OPPOSED_FORM_METRICS = [
  "goals",
  "shots",
  "shots_on_target",
  "big_chances_created",
  "corners",
] as const;

/**
 * One figure a sample publishes for the team and against it.
 */
type OpposedFormMetric = (typeof OPPOSED_FORM_METRICS)[number];

/**
 * The two names one opposed figure's two comparisons are presented under.
 */
export interface OpposedMetricLabels {
  /** Names the comparison of what each side records. */
  readonly forLabel: string;

  /** Names the comparison of what each side has recorded against it. */
  readonly againstLabel: string;
}

/**
 * Every window of completed matches a form sample can be drawn from.
 *
 * @remarks
 * The two short windows count matches rather than days, so they mean what a
 * reader means by recent form however a calendar has been arranged around
 * international breaks. The season window is not the widest of the three: it
 * never reaches into an earlier season, so through August and September it is
 * the narrowest, which is why every sample states how many matches it found.
 */
export const FORM_RANGES = ["last_3", "last_6", "season"] as const;

/**
 * One window of completed matches a form sample is drawn from.
 */
export type FormRange = (typeof FORM_RANGES)[number];

/**
 * Every narrowing of a form sample to the side a team will occupy.
 */
export const FORM_SCOPES = ["overall", "venue"] as const;

/**
 * Whether a form sample is narrowed to the side the team will occupy.
 */
export type FormScope = (typeof FORM_SCOPES)[number];

/**
 * Every group a form metric is presented under.
 */
export const FORM_FAMILIES = [
  "result",
  "attacking",
  "possession",
  "defending",
  "discipline",
] as const;

/**
 * One group a form metric is presented under.
 */
export type FormFamily = (typeof FORM_FAMILIES)[number];

/**
 * Whether a metric's value is a percentage or a per-match average.
 *
 * @remarks
 * The unit is a property of the metric rather than of the number, and it is
 * owned here rather than carried on the wire. The API publishes a bare figure
 * because the unit never varies for a given metric, so sending it would be
 * sending a constant sixty times per fixture and inviting the two copies to
 * disagree.
 */
export type FormMetricUnit = "percentage" | "average";

/**
 * The value a percentage metric is expressed out of.
 *
 * @remarks
 * Exported because the formatter divides by it and the ceilings below are
 * written in terms of it. It is the scale of a share, not a claim that every
 * share is bounded by it: {@link metricCeiling} draws that distinction.
 */
export const SHARE_CEILING = 100;

const METRIC_LABELS: Record<FormMetric, string> = {
  win_share: "Wins",
  draw_share: "Draws",
  loss_share: "Losses",
  goals: "Goals",
  shots: "Shots",
  shots_on_target: "Shots on target",
  shots_inside_box: "Shots inside the box",
  big_chances_created: "Big chances",
  key_passes: "Key passes",
  corners: "Corners",
  possession: "Possession",
  passes: "Passes",
  pass_accuracy: "Pass accuracy",
  crosses: "Crosses",
  cross_accuracy: "Cross accuracy",
  dribble_success: "Dribble success",
  saves: "Saves",
  tackles: "Tackles",
  interceptions: "Interceptions",
  duels_won: "Duels won",
  shots_blocked: "Shots blocked",
  fouls: "Fouls",
  yellow_cards: "Yellow cards",
  red_cards: "Red cards",
  offsides: "Offsides",
};

const OPPOSED_METRIC_LABELS: Record<OpposedFormMetric, OpposedMetricLabels> = {
  goals: { forLabel: "Goals for", againstLabel: "Goals against" },
  shots: { forLabel: "Shots for", againstLabel: "Shots against" },
  shots_on_target: {
    forLabel: "Shots on target for",
    againstLabel: "Shots on target against",
  },
  big_chances_created: {
    forLabel: "Big chances for",
    againstLabel: "Big chances against",
  },
  corners: { forLabel: "Corners for", againstLabel: "Corners against" },
};

const OPPOSED_LABEL_LOOKUP: Partial<Record<FormMetric, OpposedMetricLabels>> =
  OPPOSED_METRIC_LABELS;

const METRIC_UNITS: Record<FormMetric, FormMetricUnit> = {
  win_share: "percentage",
  draw_share: "percentage",
  loss_share: "percentage",
  goals: "average",
  shots: "average",
  shots_on_target: "average",
  shots_inside_box: "average",
  big_chances_created: "average",
  key_passes: "average",
  corners: "average",
  possession: "percentage",
  passes: "average",
  pass_accuracy: "percentage",
  crosses: "average",
  cross_accuracy: "percentage",
  dribble_success: "percentage",
  saves: "average",
  tackles: "average",
  interceptions: "average",
  duels_won: "average",
  shots_blocked: "average",
  fouls: "average",
  yellow_cards: "average",
  red_cards: "average",
  offsides: "average",
};

// The largest value each metric may carry, `null` where the contract can state
// no ceiling. Three of the seven percentages are deliberately unbounded, and the
// distinction is not cosmetic: `metricCeiling` explains it, and moving one of
// them into the bounded column turns a corrupt provider row into a blank panel.
const METRIC_CEILINGS: Record<FormMetric, number | null> = {
  win_share: SHARE_CEILING,
  draw_share: SHARE_CEILING,
  loss_share: SHARE_CEILING,
  goals: null,
  shots: null,
  shots_on_target: null,
  shots_inside_box: null,
  big_chances_created: null,
  key_passes: null,
  corners: null,
  possession: SHARE_CEILING,
  passes: null,
  pass_accuracy: null,
  crosses: null,
  cross_accuracy: null,
  dribble_success: null,
  saves: null,
  tackles: null,
  interceptions: null,
  duels_won: null,
  shots_blocked: null,
  fouls: null,
  yellow_cards: null,
  red_cards: null,
  offsides: null,
};

const RANGE_LABELS: Record<FormRange, string> = {
  last_3: "Last 3",
  last_6: "Last 6",
  season: "Season",
};

const RANGE_SIZES: Record<FormRange, number | null> = {
  last_3: 3,
  last_6: 6,
  season: null,
};

const SCOPE_LABELS: Record<FormScope, string> = {
  overall: "Overall",
  venue: "Home / away",
};

const FAMILY_LABELS: Record<FormFamily, string> = {
  result: "Result",
  attacking: "Attacking",
  possession: "Possession",
  defending: "Defending",
  discipline: "Discipline",
};

const PERCENTAGE_FORMAT = new Intl.NumberFormat("en-GB", {
  style: "percent",
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});

const AVERAGE_FORMAT = new Intl.NumberFormat("en-GB", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

/**
 * The window a form sample opens with, before the visitor narrows it.
 *
 * @remarks
 * Six matches rather than three or a season. Three is a sample small enough for
 * one freak result to dominate every figure in the panel, and the season window
 * is empty in August and shallow into September, which is exactly when a
 * visitor most wants to know what recent form looks like.
 */
export const DEFAULT_FORM_RANGE: FormRange = "last_6";

/**
 * The scope a form sample opens with, before the visitor narrows it.
 *
 * @remarks
 * Every completed match, because the narrowed scope halves an already small
 * sample and a panel that opens on three home matches out of six would state
 * its own caveat before it stated a figure.
 */
export const DEFAULT_FORM_SCOPE: FormScope = "overall";

/**
 * Reads the name of one form metric.
 *
 * @param metric - Metric to name.
 * @returns The metric's name.
 */
export function metricLabel(metric: FormMetric): string {
  return METRIC_LABELS[metric];
}

/**
 * Reads the two names an opposed figure is presented under, `null` for a figure
 * that has no opposite.
 *
 * @remarks
 * The lookup is the same record widened to every metric. That keeps the total
 * record the thing a sixth opposed figure has to satisfy, so one cannot be added
 * without naming both of its lines, while still letting a caller holding an
 * arbitrary metric ask without a cast.
 *
 * A caller asks the metric rather than testing the sample, because whether a
 * figure splits is a property of the metric. A side that conceded nothing
 * publishes a nought against it and not an absence, so a row that split only
 * where the figure happened to be non-null would change shape between windows.
 *
 * @param metric - Figure to name.
 * @returns Both names, or `null` where the figure has no opposite.
 */
export function opposedMetricLabels(
  metric: FormMetric,
): OpposedMetricLabels | null {
  return OPPOSED_LABEL_LOOKUP[metric] ?? null;
}

/**
 * Reads the name of one form window.
 *
 * @param range - Window to name.
 * @returns The window's name.
 */
export function rangeLabel(range: FormRange): string {
  return RANGE_LABELS[range];
}

/**
 * Reads the name of one form scope.
 *
 * @param scope - Scope to name.
 * @returns The scope's name.
 */
export function scopeLabel(scope: FormScope): string {
  return SCOPE_LABELS[scope];
}

/**
 * Reads the name of one metric family.
 *
 * @param family - Family to name.
 * @returns The family's name.
 */
export function familyLabel(family: FormFamily): string {
  return FAMILY_LABELS[family];
}

/**
 * Reads how many matches a window asks for, `null` when it asks for a season.
 *
 * @remarks
 * This is what lets the panel say that a window came up short. A sample states
 * how many matches it found and the wire does not repeat how many were wanted,
 * because the number is a property of the window rather than of the fixture, so
 * the comparison is made here against the vocabulary's own definition.
 *
 * The season window is bounded by a season rather than by a count, so there is
 * no target to fall short of and it maps to nothing rather than to a large
 * number.
 *
 * @param range - Window to read the size of.
 * @returns The number of matches the window asks for, or `null`.
 */
export function rangeSize(range: FormRange): number | null {
  return RANGE_SIZES[range];
}

/**
 * Reports whether a metric's value is a percentage rather than an average.
 *
 * @remarks
 * This governs how a figure is *rendered*, and nothing else. Whether it is also
 * bounded is a separate question with a different answer, which is why
 * {@link metricCeiling} exists rather than this predicate doubling as the
 * boundary check.
 *
 * @param metric - Metric to read the unit of.
 * @returns `true` when the metric carries a percentage.
 */
export function isShareMetric(metric: FormMetric): boolean {
  return METRIC_UNITS[metric] === "percentage";
}

/**
 * Reads the largest value a metric may carry, `null` when it has no ceiling.
 *
 * @remarks
 * Four of the seven percentages are bounded and three are not, and the split is
 * about who guarantees the bound rather than about the unit. The result shares
 * are a count of matches over the matches counted, and possession is an average
 * of a column the database constrains to a hundred, so a value above a hundred
 * there would mean the platform's own arithmetic is wrong — a contract
 * violation, which the schema refuses. Pass, cross and dribble accuracy are a
 * summed numerator over a summed denominator of two provider counts that nothing
 * cross-checks, so a corrupt upstream row where completions exceed attempts
 * publishes a figure above a hundred without anything on the platform being
 * broken.
 *
 * Refusing those three would be the wrong trade, and it is the trade this
 * function exists to avoid: the payload carries fifty figures across two sides,
 * and taking all of them down over one provider-supplied ratio would turn a data
 * blip into a panel that reports an outage. The odd figure renders as it arrived
 * — visibly wrong, and therefore reportable — which is also why it is not
 * clamped, since clamping would hide the corrupt row instead of showing it.
 *
 * The asymmetry with the predictions schema, where a probability of `120` is
 * fatal, is deliberate and rests on what the number drives. A probability is the
 * absolute width of a bar, so an out-of-range one overflows its own track. A
 * form figure drives a bar drawn in proportion to the opposing side's figure, so
 * a hundred and three paints a perfectly ordinary bar.
 *
 * An average is unbounded for a plainer reason: a side attempts five hundred
 * passes in one match and three hundred in another, so any number invented here
 * would eventually refuse a real figure.
 *
 * @param metric - Metric to read the ceiling of.
 * @returns The metric's ceiling, or `null` when it has none.
 */
export function metricCeiling(metric: FormMetric): number | null {
  return METRIC_CEILINGS[metric];
}

/**
 * Renders one metric's value in the unit that metric is measured in.
 *
 * @remarks
 * The two units are formatted to different precisions on purpose. A percentage
 * gets one decimal, as the probability panel's figures do, because the second
 * changes no reading of a share and fifty rows of two decimals is a wall of
 * digits. An average gets two, because several of them live below a tenth — a
 * side collects roughly one red card every twenty matches — and one decimal
 * would round every disciplined team in the league to the same nought.
 *
 * A percentage is divided by a hundred and formatted as a percentage rather
 * than having a sign appended, so the locale decides where the sign goes and
 * whether a space precedes it.
 *
 * @param metric - Metric the value belongs to, which decides the unit.
 * @param value - Figure the sample published.
 * @returns The formatted figure.
 */
export function formatMetricValue(metric: FormMetric, value: number): string {
  if (isShareMetric(metric)) {
    return PERCENTAGE_FORMAT.format(value / SHARE_CEILING);
  }

  return AVERAGE_FORMAT.format(value);
}
