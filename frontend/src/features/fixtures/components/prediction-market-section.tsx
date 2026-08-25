import { Badge } from "@/components/ui/badge";
import { ProbabilityBar } from "@/features/fixtures/components/probability-bar";
import {
  isExclusiveMarket,
  marketLabel,
  type PredictionReliability,
  type PredictionSides,
  selectionLabel,
} from "@/features/fixtures/domain/prediction-markets";
import type { PredictionMarketProbabilities } from "@/features/fixtures/types/prediction";

const UNGRADED_LABEL = "Reliability not graded";

const OVERLAP_NOTICE =
  "These selections overlap, so they sum to about 200% rather than 100%.";

const RELIABILITY_LABEL: Record<PredictionReliability, string> = {
  poor: "Poor reliability",
  medium: "Medium reliability",
  good: "Good reliability",
  high: "High reliability",
};

const RELIABILITY_VARIANT = {
  poor: "destructive",
  medium: "outline",
  good: "secondary",
  high: "default",
} as const satisfies Record<PredictionReliability, string>;

const PROBABILITY_FORMAT = new Intl.NumberFormat("en-GB", {
  style: "percent",
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});

const HIT_RATE_FORMAT = new Intl.NumberFormat("en-GB", {
  style: "percent",
  maximumFractionDigits: 0,
});

/**
 * Props of {@link ReliabilityChip}.
 */
interface ReliabilityChipProps {
  /** How the provider grades its own model here, `null` when it does not. */
  readonly reliability: PredictionReliability | null;
}

/**
 * Renders how much the provider's model is worth on this market.
 *
 * @remarks
 * An ungraded market states that it is ungraded. The alternative a reader would
 * have to guess at is worse in both directions: showing nothing implies the
 * grade is the same as the market above, and defaulting to the middle grade
 * invents a claim the platform never received. Two of the eleven markets are
 * permanently in this branch, because the provider publishes no predictability
 * row for double chance or for over/under 4.5, so it is a normal state rather
 * than a gap waiting to be filled.
 *
 * The variant carries the grade a second time, so a poor model is not
 * distinguished from a good one by a word alone. The ungraded chip is dashed,
 * which is how the fixture list and the competition picker already paint a
 * state that is absent rather than bad.
 *
 * @returns The grade chip.
 */
function ReliabilityChip({ reliability }: ReliabilityChipProps) {
  if (reliability === null) {
    return (
      <Badge
        className="border-dashed border-border font-normal text-muted-foreground"
        variant="ghost"
      >
        {UNGRADED_LABEL}
      </Badge>
    );
  }

  return (
    <Badge variant={RELIABILITY_VARIANT[reliability]}>
      {RELIABILITY_LABEL[reliability]}
    </Badge>
  );
}

/**
 * Props of {@link PredictionMarketSection}.
 */
export interface PredictionMarketSectionProps {
  /** One market, its grade and every selection the platform stored for it. */
  readonly market: PredictionMarketProbabilities;

  /** The two clubs, which name half the selections in the panel. */
  readonly sides: PredictionSides;
}

/**
 * Renders one prediction market: its heading, its grade and its selections.
 *
 * @remarks
 * Every selection appears three times over: as a label, as a bar, and as a
 * percentage. That is deliberate rather than redundant, because it is what lets
 * the bar be hidden from the accessibility tree and lets the colour scale be a
 * second reading of the value instead of the only one.
 *
 * A market whose selections overlap says so. Double chance covers two outcomes
 * per selection, so its three add up to roughly 200, and a panel showing eleven
 * markets that sum to 100 and one that sums to 200 looks broken rather than
 * different. Which markets those are is not decided here: the domain owns
 * {@link isExclusiveMarket}, because the same fact governs how the numbers may
 * be read anywhere else in the product.
 *
 * The marker on every bar is placed at this market's own maximum, computed once
 * here rather than per bar, so the leading selection is the one whose fill
 * reaches its marker.
 *
 * The percentages are shown to one decimal. The platform stores two, which is
 * what the provider publishes, but fifty rows of two decimals is a wall of
 * digits and the second one changes no reading of a probability. One decimal
 * keeps the column a fixed width and still separates the long tail of a correct
 * score, where several selections sit under one percent.
 *
 * @returns The market section.
 */
export function PredictionMarketSection({
  market,
  sides,
}: PredictionMarketSectionProps) {
  const marketMaximum = market.selections.reduce(
    (highest, selection) => Math.max(highest, selection.probability),
    0,
  );

  return (
    <section className="flex min-w-0 flex-col gap-2">
      <header className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <h3 className="text-sm font-medium">{marketLabel(market.market)}</h3>

        <ReliabilityChip reliability={market.reliability} />

        {market.hitRatio !== null && (
          <span className="font-mono text-[0.68rem] text-muted-foreground tabular-nums">
            {HIT_RATE_FORMAT.format(market.hitRatio)} hit rate
          </span>
        )}
      </header>

      {!isExclusiveMarket(market.market) && (
        <p className="text-xs text-muted-foreground">{OVERLAP_NOTICE}</p>
      )}

      <ul className="flex flex-col gap-1.5">
        {market.selections.map((selection) => (
          <li className="flex items-center gap-2.5" key={selection.selection}>
            <span className="w-24 shrink-0 truncate text-xs">
              {selectionLabel(market.market, selection.selection, sides)}
            </span>

            <ProbabilityBar
              marketMaximum={marketMaximum}
              probability={selection.probability}
            />

            <span className="w-12 shrink-0 text-right font-mono text-xs tabular-nums">
              {PROBABILITY_FORMAT.format(selection.probability / 100)}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
