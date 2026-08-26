import type {
  FormFamily,
  FormMetric,
  FormRange,
  FormScope,
} from "@/features/fixtures/domain/form-metrics";

/**
 * One figure a form sample published, and what the opposition recorded against
 * it where the metric has such a sibling.
 */
export interface FormMetricValue {
  /** Metric the figure belongs to. */
  readonly metric: FormMetric;

  /** The team's own figure, a percentage or a per-match average. */
  readonly value: number;

  /** What the opposition recorded, `null` for a metric with no opposite. */
  readonly opposedValue: number | null;
}

/**
 * One team's form over one window and one scope.
 *
 * @remarks
 * The number of matches is carried beside the figures rather than inferred from
 * the window, because the two differ often enough to matter: the last six
 * matches of a promoted side in August are however many it has played, and the
 * narrow scope halves whatever the wide one found. An average over two matches
 * and an average over six are read very differently, so the count is part of
 * the sample rather than a caveat the panel could omit.
 *
 * A sample with no matches behind it still publishes every metric, at nought.
 * That is the contract rather than an accident, and it is why the panel has to
 * state the count: nought goals per match over nought matches is not a claim
 * about a team.
 */
export interface FormSample {
  /** Window the sample was drawn from. */
  readonly range: FormRange;

  /** Whether the sample was narrowed to the side the team will occupy. */
  readonly scope: FormScope;

  /** How many completed matches fed the sample, possibly none. */
  readonly matchesCounted: number;

  /** The sample's figures, in the order the API sent them. */
  readonly metrics: readonly FormMetricValue[];
}

/**
 * One side of the fixture, with every window and scope the API published.
 */
export interface TeamForm {
  /** Internal team identifier the samples belong to. */
  readonly teamId: number;

  /** Every sample for this team, in the order the API sent them. */
  readonly samples: readonly FormSample[];
}

/**
 * One group of metrics, as the API groups them.
 */
export interface FormFamilyGroup {
  /** Family the metrics are presented under. */
  readonly family: FormFamily;

  /** Metrics in this family, in the order the API sent them. */
  readonly metrics: readonly FormMetric[];
}

/**
 * Every form figure the platform holds for one fixture.
 *
 * @remarks
 * An available-but-empty state is representable on purpose, as `synchronizedAt`
 * of `null` with every sample counting no matches. Two sides meeting on the
 * opening weekend of a season have no statistics behind them at all, and that is
 * a fixture with nothing to show rather than a fixture the platform could not
 * read.
 */
export interface FixtureForm {
  /** Internal fixture identifier the form belongs to. */
  readonly fixtureId: number;

  /** Instant the newest row feeding any sample was read, `null` when none did. */
  readonly synchronizedAt: Date | null;

  /** Form of the side playing at home. */
  readonly home: TeamForm;

  /** Form of the side playing away. */
  readonly away: TeamForm;

  /** How the metrics are grouped, in the order the API sent them. */
  readonly families: readonly FormFamilyGroup[];
}

/**
 * Outcome of asking the backend for one fixture's form.
 *
 * @remarks
 * Three answers rather than two, for the reason the predictions result gives:
 * the platform can have form, can have none yet, and can be unable to tell, and
 * only the last is a failure. The first two are both the `loaded` branch,
 * separated inside {@link FixtureForm}, so an outage can never render as "no
 * matches played yet" and a season's opening fixture can never render as an
 * error the visitor is invited to retry.
 */
export type FixtureFormResult =
  | {
      readonly loaded: true;
      readonly form: FixtureForm;
    }
  | {
      readonly loaded: false;
      readonly reason: string;
    };
