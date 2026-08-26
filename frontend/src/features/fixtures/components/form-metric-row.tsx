import {
  formatMetricValue,
  type FormMetric,
  metricLabel,
} from "@/features/fixtures/domain/form-metrics";
import type { FormMetricValue } from "@/features/fixtures/types/form";

const MISSING_FIGURE = "—";

const MISSING_ANNOUNCEMENT = "not published";

const OPPOSED_SEPARATOR = " / ";

const OPPOSED_ANNOUNCEMENT = " against ";

const EVEN_SPLIT = 50;

const FULL_TRACK = 100;

/**
 * Props of {@link MetricFigure}.
 */
interface MetricFigureProps {
  /** Metric the figure belongs to, which decides how it is formatted. */
  readonly metric: FormMetric;

  /** The team's figure, `null` when the sample published none. */
  readonly value: FormMetricValue | null;

  /** Club the figure belongs to, which a column position alone cannot say. */
  readonly teamName: string;

  /** Utility classes aligning the figure within its side of the row. */
  readonly className: string;
}

/**
 * Renders one team's figure for one metric, and the opposing figure where the
 * metric has one.
 *
 * @remarks
 * The club is named from visually hidden text before the number. A sighted
 * reader knows whose figure this is from the column it sits in, and a column is
 * exactly the thing a screen reader does not convey, so without this the panel
 * would announce sixty bare numbers in pairs.
 *
 * The opposing figure is separated by a slash for the eye and by the word
 * "against" for the ear, which is why the slash is hidden and the word is not.
 * A slash is verbalized inconsistently and often dropped, and "one point six
 * seven nought point eight three" is two figures read as one.
 *
 * A metric the sample published nothing for renders as a dash with the reason
 * announced beside it. This is reachable rather than defensive: the wire schema
 * drops a figure whose name the frontend does not know, so a backend one release
 * ahead leaves exactly this gap, and a dash under a heading is more honest than
 * a nought that would be read as a measurement.
 *
 * @returns The figure, or a dash where there is none.
 */
function MetricFigure({
  metric,
  value,
  teamName,
  className,
}: MetricFigureProps) {
  if (value === null) {
    return (
      <span className={className}>
        <span className="sr-only">{`${teamName}, `}</span>

        <span aria-hidden="true">{MISSING_FIGURE}</span>

        <span className="sr-only">{MISSING_ANNOUNCEMENT}</span>
      </span>
    );
  }

  return (
    <span className={className}>
      <span className="sr-only">{`${teamName}, `}</span>

      {formatMetricValue(metric, value.value)}

      {value.opposedValue !== null && (
        <span className="text-muted-foreground">
          <span aria-hidden="true">{OPPOSED_SEPARATOR}</span>

          <span className="sr-only">{OPPOSED_ANNOUNCEMENT}</span>

          {formatMetricValue(metric, value.opposedValue)}
        </span>
      )}
    </span>
  );
}

/**
 * Props of {@link FormMetricRow}.
 */
export interface FormMetricRowProps {
  /** Metric this row compares the two sides on. */
  readonly metric: FormMetric;

  /** The home side's figure, `null` when the sample published none. */
  readonly home: FormMetricValue | null;

  /** The away side's figure, `null` when the sample published none. */
  readonly away: FormMetricValue | null;

  /** Full name of the home club. */
  readonly homeName: string;

  /** Full name of the away club. */
  readonly awayName: string;
}

/**
 * Renders one metric as both sides' figures either side of a comparison bar.
 *
 * @remarks
 * The bar is proportional between the two teams rather than absolute, and this
 * is the opposite of the choice the probability bar documents — deliberately,
 * because the two answer different questions. A probability has a fixed scale
 * every market shares, so an absolute width keeps one meaning down the whole
 * panel. A form figure has no such scale: five hundred passes and one and a half
 * goals are both ordinary, and there is no denominator to draw them against.
 * What a reader wants here is which side does more of this and by how much,
 * which is exactly what a split track shows.
 *
 * Two sides with nothing between them split the track evenly, which is also what
 * two sides that both recorded nought get. That is the honest reading of a pair
 * of equal figures, and the alternative — an empty track — would look like
 * missing data rather than like a tie.
 *
 * The bar is hidden from the accessibility tree, and it is allowed to be
 * because both figures are in the row as text with their clubs named. The length
 * is a second reading of a value stated in words, never the only channel
 * carrying it, which is the same contract the probability bar keeps one panel
 * over. A figure the sample did not publish contributes nothing to the split, so
 * a row with one side missing paints the whole track for the side that has one.
 *
 * The two halves are painted from the chart tokens rather than from the
 * probability ramp. The ramp encodes magnitude on a fixed scale, which is not
 * what this bar means; these two colours encode identity, and they need to
 * differ from each other rather than to sit anywhere in particular.
 *
 * @returns The metric row.
 */
export function FormMetricRow({
  metric,
  home,
  away,
  homeName,
  awayName,
}: FormMetricRowProps) {
  const homeValue = home?.value ?? 0;
  const awayValue = away?.value ?? 0;
  const total = homeValue + awayValue;

  const homeShare = total === 0 ? EVEN_SPLIT : (homeValue * FULL_TRACK) / total;

  return (
    <li className="flex items-center gap-2.5">
      <MetricFigure
        className="w-20 shrink-0 text-right font-mono text-xs tabular-nums"
        metric={metric}
        teamName={homeName}
        value={home}
      />

      <span className="flex min-w-0 flex-1 flex-col items-center gap-1">
        <span className="max-w-full truncate text-[0.7rem] text-muted-foreground">
          {metricLabel(metric)}
        </span>

        <span
          aria-hidden="true"
          className="flex h-1.5 w-full overflow-hidden rounded-full bg-muted"
          data-slot="form-comparison-track"
        >
          <span
            className="block h-full bg-chart-1"
            data-slot="form-comparison-home"
            style={{ width: `${homeShare}%` }}
          />

          <span
            className="block h-full flex-1 bg-chart-2"
            data-slot="form-comparison-away"
          />
        </span>
      </span>

      <MetricFigure
        className="w-20 shrink-0 font-mono text-xs tabular-nums"
        metric={metric}
        teamName={awayName}
        value={away}
      />
    </li>
  );
}
