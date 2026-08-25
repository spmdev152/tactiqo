import { Badge } from "@/components/ui/badge";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { ProbabilityBar } from "@/features/fixtures/components/probability-bar";
import {
  marketLabel,
  type PredictionReliability,
  type PredictionSides,
  selectionLabel,
} from "@/features/fixtures/domain/prediction-markets";
import type { PredictionMarketProbabilities } from "@/features/fixtures/types/prediction";

const UNGRADED_LABEL = "Reliability not graded";

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

  /** The measured hit rate behind that grade, `null` when there is none. */
  readonly hitRatio: number | null;
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
 * The hit rate the grade stands on moves into a tooltip. Printed beside eleven
 * headings it was a second number competing with the fifty the panel is
 * actually about, and it answers a question a reader only asks once they doubt
 * a grade. The chip therefore takes `tabIndex`, which is what makes the
 * tooltip reachable without a pointer: a chip is a `span` and would otherwise
 * be unfocusable, and the number would be available to a mouse alone. Radix
 * points the trigger's `aria-describedby` at the content, so the grade stays
 * the chip's name and the hit rate becomes its description rather than being
 * folded into one announcement.
 *
 * It opens to the right, into the space the printed hit rate used to occupy,
 * because the first market's heading sits directly under the fixture row: a
 * tooltip above it would cover the two clubs the whole panel is about, and one
 * below it would cover the selections being read. Radix flips it leftwards on
 * its own where the column has no room.
 *
 * It says the number and nothing else. The sentence it replaces named the scope
 * the rate is measured over, which the chip's own position already gives: it
 * sits in one market of one fixture of one competition. On a phone that
 * sentence cost the tooltip the full 20rem the primitive allows, which is wider
 * than the viewport, so a bubble anchored beside a chip had no side left to
 * open on. `collisionPadding` keeps the short one clear of both edges rather
 * than trusting that it always fits.
 *
 * The ungraded chip is built on `outline` rather than on `ghost`, which is the
 * only variant whose hover is not gated behind `[a]:` and so the only one that
 * responds to a pointer on a `span`. None of the graded chips do, and a chip
 * that lights up under the cursor without being a control is a promise of
 * something to click. `outline` already supplies the border colour the dashed
 * override needs, so the two render identically.
 *
 * A grade with no hit rate renders as a plain chip. The provider publishes the
 * two together, so this is unreachable through the synchronization as it
 * stands, but the contract types them independently and a chip that opens an
 * empty tooltip is worse than one that opens none.
 *
 * @returns The grade chip, and the hit rate behind it when there is one.
 */
function ReliabilityChip({ reliability, hitRatio }: ReliabilityChipProps) {
  if (reliability === null) {
    return (
      <Badge
        className="border-dashed font-normal text-muted-foreground"
        variant="outline"
      >
        {UNGRADED_LABEL}
      </Badge>
    );
  }

  const chip = (
    <Badge variant={RELIABILITY_VARIANT[reliability]}>
      {RELIABILITY_LABEL[reliability]}
    </Badge>
  );

  if (hitRatio === null) {
    return chip;
  }

  return (
    <Tooltip>
      <TooltipTrigger asChild tabIndex={0}>
        {chip}
      </TooltipTrigger>

      <TooltipContent align="center" collisionPadding={8} side="right">
        Hit rate of {HIT_RATE_FORMAT.format(hitRatio)}
      </TooltipContent>
    </Tooltip>
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
 * Nothing here says that double chance sums to about 200. Its three selections
 * are named as the pairs they are — the home side or a draw, either side — so a
 * reader who can add already knows why they overlap, and a notice under one
 * heading in eleven was a paragraph spent restating its own labels.
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
  return (
    <section className="flex min-w-0 flex-col gap-2">
      <header className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <h3 className="text-sm font-medium">{marketLabel(market.market)}</h3>

        <ReliabilityChip
          hitRatio={market.hitRatio}
          reliability={market.reliability}
        />
      </header>

      <ul className="flex flex-col gap-1.5">
        {market.selections.map((selection) => (
          <li className="flex items-center gap-2.5" key={selection.selection}>
            <span className="w-24 shrink-0 truncate text-xs">
              {selectionLabel(market.market, selection.selection, sides)}
            </span>

            <ProbabilityBar probability={selection.probability} />

            <span className="w-12 shrink-0 text-right font-mono text-xs tabular-nums">
              {PROBABILITY_FORMAT.format(selection.probability / 100)}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
