import { CalendarClock, TriangleAlert } from "lucide-react";

import { Skeleton } from "@/components/ui/skeleton";
import { PredictionMarketSection } from "@/features/fixtures/components/prediction-market-section";
import type { PredictionSides } from "@/features/fixtures/domain/prediction-markets";
import type { FixturePredictionsResult } from "@/features/fixtures/types/prediction";
import { cn } from "@/lib/utils";

const LOADING_MESSAGE = "Reading prediction probabilities.";

const ERROR_MESSAGE = "Prediction probabilities are unavailable right now.";

const EMPTY_MESSAGE = "Predictions are not published yet.";

const EMPTY_HINT =
  "Probabilities are modelled in the fortnight before kick-off, so a match further out has none.";

const PLACEHOLDER_MARKETS = [
  { key: "prediction-placeholder-market-0", rows: 3 },
  { key: "prediction-placeholder-market-1", rows: 2 },
];

const SYNCHRONIZED_FORMAT = new Intl.DateTimeFormat("en-GB", {
  day: "numeric",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
  timeZone: "UTC",
});

/**
 * Renders the panel's own shape while the probabilities are being read.
 *
 * @remarks
 * Two markets of differing length rather than a spinner, for the reason the
 * fixture list's own placeholder gives: the panel opens and grows to whatever it
 * is about to hold, so a placeholder of the wrong shape makes the row settle
 * twice.
 *
 * Nothing here is announced. It is a picture of a layout, and the branch that
 * renders it states in words that a read is in flight.
 *
 * @returns The placeholder markets.
 */
function PredictionsPlaceholder() {
  return (
    <div
      aria-hidden="true"
      className="grid grid-cols-1 gap-x-8 gap-y-5 @lg:grid-cols-2"
    >
      {PLACEHOLDER_MARKETS.map((market) => (
        <div className="flex min-w-0 flex-col gap-2" key={market.key}>
          <div className="flex items-center gap-2">
            <Skeleton className="h-4 w-28" />

            <Skeleton className="h-5 w-24 rounded-4xl" />
          </div>

          <div className="flex flex-col gap-1.5">
            {Array.from({ length: market.rows }, (_unused, index) => (
              <div
                className="flex items-center gap-2.5"
                key={`${market.key}-row-${index}`}
              >
                <Skeleton className="h-3 w-24 shrink-0" />

                <Skeleton className="h-1.5 flex-1 rounded-full" />

                <Skeleton className="h-3 w-12 shrink-0" />
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

/**
 * Props of {@link PredictionsNotice}.
 */
interface PredictionsNoticeProps {
  /** What the panel has to report, in the visitor's terms. */
  readonly message: string;

  /** Why, either as the read reported it or as product copy. */
  readonly detail: string;

  /** Whether this is a failure rather than an ordinary absence. */
  readonly failed: boolean;
}

/**
 * Renders, in the markets' place, why there are none.
 *
 * @remarks
 * One component for two branches, because they must not differ in shape: a
 * panel that reports an outage in a dense box and an absence in a sparse one
 * reads as two features rather than as two answers. What the visitor needs is
 * which of the two it is, and that is carried by the border — dashed and
 * neutral for an absence, solid and red-tinted for a failure — exactly as the
 * fixture list paints the same pair one level up.
 *
 * @returns The stated notice.
 */
function PredictionsNotice({
  message,
  detail,
  failed,
}: PredictionsNoticeProps) {
  const Icon = failed ? TriangleAlert : CalendarClock;

  return (
    <div
      className={cn(
        "flex items-start gap-2.5 rounded-lg border px-3.5 py-3",
        failed ? "border-destructive/40 bg-destructive/5" : "border-dashed",
      )}
    >
      <Icon
        aria-hidden="true"
        className={cn(
          "mt-px size-4 shrink-0",
          failed ? "text-destructive" : "text-muted-foreground",
        )}
      />

      <div className="flex min-w-0 flex-col gap-0.5">
        <p className="text-sm font-medium">{message}</p>

        <p className="text-xs text-muted-foreground">{detail}</p>
      </div>
    </div>
  );
}

/**
 * Props of {@link FixturePredictionsPanel} and of the body it wraps.
 */
export interface FixturePredictionsPanelProps {
  /** Outcome of the read, or `null` while it has not answered yet. */
  readonly result: FixturePredictionsResult | null;

  /** Whether a read is in flight. */
  readonly pending: boolean;

  /** The two clubs, which name half the selections in the panel. */
  readonly sides: PredictionSides;
}

/**
 * Renders whichever of the four outcomes the read has produced.
 *
 * @remarks
 * Split from the surface around it so the padding and the background are
 * declared once. Four branches sharing one wrapper was four copies of the same
 * three utilities, and the first time one of them drifted the panel would have
 * changed shape depending on which answer it got. The two take one interface
 * for the same reason: the split is where the wrapper goes, not a narrowing of
 * what either is told.
 *
 * @returns The markets, the placeholder, or why there are none.
 */
function PredictionsBody({
  result,
  pending,
  sides,
}: FixturePredictionsPanelProps) {
  if (pending || result === null) {
    return (
      <>
        <p className="sr-only">{LOADING_MESSAGE}</p>

        <PredictionsPlaceholder />
      </>
    );
  }

  if (!result.loaded) {
    return (
      <PredictionsNotice
        detail={result.reason}
        failed
        message={ERROR_MESSAGE}
      />
    );
  }

  const { markets, synchronizedAt } = result.predictions;

  if (markets.length === 0) {
    return (
      <PredictionsNotice
        detail={EMPTY_HINT}
        failed={false}
        message={EMPTY_MESSAGE}
      />
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-1 gap-x-8 gap-y-5 @lg:grid-cols-2">
        {markets.map((market) => (
          <PredictionMarketSection
            key={market.market}
            market={market}
            sides={sides}
          />
        ))}
      </div>

      {synchronizedAt !== null && (
        <p className="font-mono text-[0.68rem] text-muted-foreground">
          <time dateTime={synchronizedAt.toISOString()}>
            Updated {SYNCHRONIZED_FORMAT.format(synchronizedAt)}
          </time>
        </p>
      )}
    </div>
  );
}

/**
 * Renders the prediction probabilities of one fixture.
 *
 * @remarks
 * Four outcomes, and the one that matters most is the third. A fixture the
 * platform has no probabilities for is neither a failure nor rare: the model
 * runs in roughly the fortnight before kick-off, so every match further out
 * answers with nothing at all. Reporting that as an outage would make the
 * ordinary case look broken, and the advice it implies — come back later — is
 * the correct advice, so the panel gives it as an absence with a reason instead
 * of as an error with a diagnosis.
 *
 * The unavailable branch repeats the reason the read produced rather than
 * inventing one, as the fixture list does, so an outage is diagnosable from the
 * interface. That reason is composed on the server for this surface and names
 * nothing internal.
 *
 * The markets are one column and become two at `@lg`. Eleven markets are around
 * fifty rows, which is a page and a half of scrolling in one column for no
 * reason. The variant is a container variant because the page is the container:
 * the sidebar owns 16rem of the window when it is expanded, so a viewport
 * breakpoint would split the panel in two while the pane was still too narrow
 * for either column.
 *
 * The read's own timestamp is stated, because a probability with no date is a
 * claim with no shelf life and the platform synchronizes on a schedule rather
 * than on demand. It is formatted in UTC and left unlabelled, as the kick-off on
 * the row above it is: the visitor's zone is not knowable while rendering on the
 * server, so the machine-readable `dateTime` is the only statement of the zone
 * until there is a stored preference to resolve it against.
 *
 * The surface is tinted rather than separated by a rule. The list puts its
 * dividers between matches, and a border here would read as one more of those,
 * splitting a match from its own panel.
 *
 * @returns The panel.
 */
export function FixturePredictionsPanel({
  result,
  pending,
  sides,
}: FixturePredictionsPanelProps) {
  return (
    <div className="bg-muted/30 px-4 pt-1 pb-4">
      <PredictionsBody pending={pending} result={result} sides={sides} />
    </div>
  );
}
