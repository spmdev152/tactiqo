import { z } from "zod";

import {
  FORM_FAMILIES,
  FORM_METRICS,
  FORM_RANGES,
  FORM_SCOPES,
  metricCeiling,
} from "@/features/fixtures/domain/form-metrics";

const KNOWN_METRICS: readonly string[] = FORM_METRICS;

const KNOWN_FAMILIES: readonly string[] = FORM_FAMILIES;

const KNOWN_RANGES: readonly string[] = FORM_RANGES;

const metricNameSchema = z.enum(FORM_METRICS);

const unrecognizedMetricNameSchema = z
  .string()
  .refine((name) => !KNOWN_METRICS.includes(name))
  .transform(() => null);

/**
 * Wire contract of one metric's figure inside a form sample.
 *
 * @remarks
 * Both figures are floored at nought rather than merely typed as numbers,
 * because every metric in the vocabulary is a count, an average of counts, or a
 * share, and none of the three can be negative. The backend's columns are
 * unsigned and its scores are too, so a negative figure here means the contract
 * has moved rather than that a match went badly.
 *
 * The ceiling comes from the vocabulary per metric rather than from the unit,
 * and that indirection is the whole point. Four of the seven percentages are
 * bounded by the platform's own arithmetic and are refused above a hundred;
 * three are ratios of two provider counts nothing cross-checks, so a corrupt
 * upstream row can exceed a hundred without anything on the platform being
 * broken, and refusing those would take fifty correct figures down with one bad
 * one. `metricCeiling` documents the split and owns it, so this schema cannot
 * disagree with the panel about which metric is which.
 *
 * `opposed_value` is null for twenty of the twenty-five metrics and that is the
 * ordinary state, not an absence to be filled: only five of them have a sibling
 * figure the opposition recorded, and possession is deliberately not among them
 * because its two sides sum to a hundred. On those five it arrives as `0` rather
 * than null when the sample counted no matches, which the floor accepts.
 */
export const formMetricValuePayloadSchema = z
  .object({
    metric: metricNameSchema,
    value: z.number().min(0),
    opposed_value: z.number().min(0).nullable(),
  })
  .refine((entry) => {
    const ceiling = metricCeiling(entry.metric);

    return (
      ceiling === null ||
      (entry.value <= ceiling && (entry.opposed_value ?? 0) <= ceiling)
    );
  });

const unrecognizedMetricValuePayloadSchema = z
  .object({
    metric: unrecognizedMetricNameSchema,
  })
  .transform(() => null);

/**
 * Wire contract of a sample's figures, tolerant of an unknown metric.
 *
 * @remarks
 * A metric the platform has no name for is dropped rather than fatal, for the
 * reason the predictions schema gives at the same place: `api` and `web` are
 * separate images released by separate jobs, so a backend that starts
 * publishing a twenty-sixth figure is a state this contract has to survive.
 * Refusing the array would lose the whole panel over one row nothing could have
 * labelled.
 *
 * Tolerance stops at the vocabulary. The second branch matches only an object
 * whose `metric` is a string outside the published list, so a figure that is
 * recognized but malformed — a share of `120`, a negative average, a missing
 * `opposed_value` — fails both branches and takes the payload down with it,
 * which is what a structural change to the contract has to do.
 */
const formMetricValuesPayloadSchema = z
  .array(
    z.union([
      formMetricValuePayloadSchema,
      unrecognizedMetricValuePayloadSchema,
    ]),
  )
  .transform((entries) => entries.filter((entry) => entry !== null));

/**
 * Wire contract of one team's form over one window and one scope.
 *
 * @remarks
 * `matches_counted` is validated as a non-negative integer and nought is a real
 * answer rather than an error: a promoted side has no season behind it in
 * August, and the season window is genuinely empty for it. The panel states the
 * count instead of implying it, so a figure drawn from two matches is not read
 * as one drawn from six.
 */
export const formSamplePayloadSchema = z.object({
  range: z.enum(FORM_RANGES),
  scope: z.enum(FORM_SCOPES),
  matches_counted: z.number().int().min(0),
  metrics: formMetricValuesPayloadSchema,
});

const unrecognizedSamplePayloadSchema = z
  .object({
    range: z.string().refine((name) => !KNOWN_RANGES.includes(name)),
  })
  .transform(() => null);

/**
 * Wire contract of one team's samples, tolerant of an unknown window.
 *
 * @remarks
 * Tolerant for the same reason and to the same depth as the metrics above: a
 * window the frontend cannot name is dropped, and a sample whose shape has
 * moved is fatal. Dropping is safe here because the panel resolves the sample
 * it renders by looking up the window and scope the visitor selected, so a
 * missing one is a combination that reports itself as unavailable rather than a
 * silently wrong figure.
 */
const formSamplesPayloadSchema = z
  .array(z.union([formSamplePayloadSchema, unrecognizedSamplePayloadSchema]))
  .transform((entries) => entries.filter((entry) => entry !== null));

/**
 * Wire contract of one side of the fixture.
 */
export const teamFormPayloadSchema = z.object({
  team_id: z.number().int().positive(),
  samples: formSamplesPayloadSchema,
});

/**
 * Wire contract of one family and the metrics published under it.
 *
 * @remarks
 * The grouping is carried on the wire rather than held here, because it is an
 * editorial decision about the vocabulary and the backend owns the vocabulary.
 * A second copy in the panel would be free to disagree with the one the API
 * publishes, and the disagreement would surface as a metric rendered under the
 * wrong heading or under none.
 */
export const formFamilyPayloadSchema = z.object({
  family: z.enum(FORM_FAMILIES),
  metrics: z
    .array(z.union([metricNameSchema, unrecognizedMetricNameSchema]))
    .transform((entries) => entries.filter((entry) => entry !== null)),
});

const unrecognizedFamilyPayloadSchema = z
  .object({
    family: z.string().refine((name) => !KNOWN_FAMILIES.includes(name)),
  })
  .transform(() => null);

const formFamiliesPayloadSchema = z
  .array(z.union([formFamilyPayloadSchema, unrecognizedFamilyPayloadSchema]))
  .transform((entries) => entries.filter((entry) => entry !== null));

/**
 * Wire contract of the `GET /api/v1/fixtures/{id}/form` response body.
 *
 * @remarks
 * `synchronized_at` is validated as an ISO-8601 instant with an offset rather
 * than as a plain string, for the reason the fixtures and predictions schemas
 * validate their own instants that way: the field names an absolute moment, and
 * a value with no offset would be read differently by the server and the
 * browser. Here the mismatch would surface as form claiming to be hours staler
 * or fresher than it is.
 *
 * It is nullable, and null is a real answer rather than a failure. It is the
 * newest stamp across every stored row that fed any sample, so a fixture
 * between two sides with no completed match behind them carries none — the
 * opening weekend of a season, or a promoted side's first fixture.
 *
 * The two sides are separate objects rather than an array keyed by side,
 * because the panel renders them in fixed positions and an array would let a
 * payload carry one side, three sides, or the same side twice.
 */
export const fixtureFormPayloadSchema = z.object({
  fixture_id: z.number().int().positive(),
  synchronized_at: z.iso.datetime({ offset: true }).nullable(),
  home: teamFormPayloadSchema,
  away: teamFormPayloadSchema,
  families: formFamiliesPayloadSchema,
});

/**
 * Decoded shape of one metric's figure as the transport carries it.
 */
export type FormMetricValuePayload = z.infer<
  typeof formMetricValuePayloadSchema
>;

/**
 * Decoded shape of one sample as the transport carries it.
 */
export type FormSamplePayload = z.infer<typeof formSamplePayloadSchema>;

/**
 * Decoded shape of one side's form as the transport carries it.
 */
export type TeamFormPayload = z.infer<typeof teamFormPayloadSchema>;

/**
 * Decoded shape of one family as the transport carries it.
 */
export type FormFamilyPayload = z.infer<typeof formFamilyPayloadSchema>;

/**
 * Decoded shape of one fixture's form as the transport carries it.
 */
export type FixtureFormPayload = z.infer<typeof fixtureFormPayloadSchema>;
