import {
  formatMetricValue,
  type FormMetric,
  metricLabel,
  opposedMetricLabels,
} from "@/features/fixtures/domain/form-metrics";
import type { FormMetricValue } from "@/features/fixtures/types/form";

const MISSING_FIGURE = "—";

const MISSING_ANNOUNCEMENT = "not published";

const EVEN_SPLIT = 50;

const FULL_TRACK = 100;

/**
 * Props of {@link MetricFigure}.
 */
interface MetricFigureProps {
  /** Metric the figure belongs to, which decides how it is formatted. */
  readonly metric: FormMetric;

  /** The team's figure, `null` when the sample published none. */
  readonly value: number | null;

  /** Club the figure belongs to, which a column position alone cannot say. */
  readonly teamName: string;

  /** Utility classes aligning the figure within its side of the row. */
  readonly className: string;
}

/**
 * Renders one team's figure for one comparison.
 *
 * @remarks
 * The club is named from visually hidden text before the number. A sighted
 * reader knows whose figure this is from the column it sits in, and a column is
 * exactly the thing a screen reader does not convey, so without this the panel
 * would announce sixty bare numbers in pairs.
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

      {formatMetricValue(metric, value)}
    </span>
  );
}

/**
 * Props of {@link ComparisonLine}.
 */
interface ComparisonLineProps {
  /** Metric the two figures belong to, which decides how they are formatted. */
  readonly metric: FormMetric;

  /** What this line compares, which is not always the metric's own name. */
  readonly label: string;

  /** The home side's figure, `null` when the sample published none. */
  readonly home: number | null;

  /** The away side's figure, `null` when the sample published none. */
  readonly away: number | null;

  /** Full name of the home club. */
  readonly homeName: string;

  /** Full name of the away club. */
  readonly awayName: string;
}

/**
 * Renders one comparison as both sides' figures either side of a split track.
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
 * @returns The comparison as one row.
 */
function ComparisonLine({
  metric,
  label,
  home,
  away,
  homeName,
  awayName,
}: ComparisonLineProps) {
  const homeValue = home ?? 0;
  const awayValue = away ?? 0;
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
          {label}
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
 * Renders one metric as the one or two comparisons it is worth reading as.
 *
 * @remarks
 * Five of the twenty-five figures carry what the opposition recorded against the
 * side, and each of those is two comparisons rather than one. They were drawn as
 * a single line reading `1.83 / 0.83`, which asked a reader to hold four numbers
 * and a slash in their head to answer either question, and answered neither with
 * a bar: the track compared what the two sides score and said nothing at all
 * about what they concede.
 *
 * Split, the second line is the one that earns its place. It compares the two
 * sides on what is done to them, so a track that leans right means the away side
 * concedes more of this — a reading the panel could not previously give at any
 * width. Both lines are named, because two adjacent tracks under one heading
 * would be indistinguishable.
 *
 * Whether a metric splits is asked of the vocabulary rather than of the sample,
 * for the reason {@link opposedMetricLabels} documents: a nought conceded is a
 * measurement, and a row that split only where the figure was non-null would
 * change shape as the visitor widened the window. A figure the sample did not
 * publish therefore reaches both lines as a dash, which is what it is.
 *
 * @returns One row for a plain metric, two for an opposed one.
 */
export function FormMetricRow({
  metric,
  home,
  away,
  homeName,
  awayName,
}: FormMetricRowProps) {
  const opposed = opposedMetricLabels(metric);

  if (opposed === null) {
    return (
      <ComparisonLine
        away={away?.value ?? null}
        awayName={awayName}
        home={home?.value ?? null}
        homeName={homeName}
        label={metricLabel(metric)}
        metric={metric}
      />
    );
  }

  return (
    <>
      <ComparisonLine
        away={away?.value ?? null}
        awayName={awayName}
        home={home?.value ?? null}
        homeName={homeName}
        label={opposed.forLabel}
        metric={metric}
      />

      <ComparisonLine
        away={away?.opposedValue ?? null}
        awayName={awayName}
        home={home?.opposedValue ?? null}
        homeName={homeName}
        label={opposed.againstLabel}
        metric={metric}
      />
    </>
  );
}
