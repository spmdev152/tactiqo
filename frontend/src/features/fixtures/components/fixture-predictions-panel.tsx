import { CalendarClock, TriangleAlert } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { PredictionMarketSection } from "@/features/fixtures/components/prediction-market-section";
import type { PredictionSides } from "@/features/fixtures/domain/prediction-markets";
import type { FixturePredictionsResult } from "@/features/fixtures/types/prediction";
import { cn } from "@/lib/utils";

const LOADING_MESSAGE = "Reading prediction probabilities.";

const LOADED_MESSAGE = "Prediction probabilities are ready.";

const ERROR_MESSAGE = "Prediction probabilities are unavailable right now.";

const EMPTY_MESSAGE = "Predictions are not published yet.";

const EMPTY_HINT =
  "Probabilities are modelled in the fortnight before kick-off, so a match further out has none.";

const RETRY_LABEL = "Try again";

const UPDATED_PREFIX = "Updated";

const MARKET_FLOW = "gap-x-8 *:break-inside-avoid *:not-first:mt-5";

const MARKET_COLUMNS = "columns-[22rem]";

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
 * It declares the loaded branch's column geometry unconditionally, because it
 * always draws two markets: a placeholder of one geometry followed by markets of
 * another would move the panel's whole content sideways on settlement.
 *
 * @returns The placeholder markets.
 */
function PredictionsPlaceholder() {
  return (
    <div aria-hidden="true" className={cn(MARKET_FLOW, MARKET_COLUMNS)}>
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

  /** Asks for the read again, or `null` when there is nothing to retry. */
  readonly onRetry: (() => void) | null;
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
 * Only one of the two offers a retry, and the prop rather than `failed` decides
 * it: a fixture the model has not run on yet will answer the same way however
 * many times it is asked, so offering to ask again would be an invitation to
 * find the same absence. The caller that knows the read can be repeated is the
 * one that supplies the callback.
 *
 * The box itself is the live region. Its text is already the whole of what the
 * visitor needs to be told, so announcing it means giving the element a live
 * role rather than adding a second, hidden copy of the same sentence that could
 * then drift from the visible one. `status` rather than `alert` because the
 * visitor asked for this panel and the answer is not worth interrupting them
 * over; the platform health card states its outcome the same way.
 *
 * @returns The stated notice.
 */
function PredictionsNotice({
  message,
  detail,
  failed,
  onRetry,
}: PredictionsNoticeProps) {
  const Icon = failed ? TriangleAlert : CalendarClock;

  return (
    <div
      className={cn(
        "flex items-start gap-2.5 rounded-lg border px-3.5 py-3",
        failed ? "border-destructive/40 bg-destructive/5" : "border-dashed",
      )}
      role="status"
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

        {onRetry !== null && (
          <Button
            className="mt-2 self-start"
            onClick={onRetry}
            size="sm"
            type="button"
            variant="outline"
          >
            {RETRY_LABEL}
          </Button>
        )}
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

  /** Whether a read has been asked for at all. */
  readonly requested: boolean;

  /** Whether a read is in flight. */
  readonly pending: boolean;

  /** The two clubs, which name half the selections in the panel. */
  readonly sides: PredictionSides;

  /** Asks for the read again after a failure. */
  readonly onRetry: () => void;
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
 * A `null` result means the answer has not arrived, never that there is nothing
 * to wait for: the wrapper has already turned away the case where nothing was
 * asked, and every settlement — including a failed one — puts a result here.
 * That is what makes the first branch safe to read as "loading", and it is the
 * whole of the fix for a failed read that used to sit on the placeholder for as
 * long as the page stayed open.
 *
 * @returns The markets, the placeholder, or why there are none.
 */
function PredictionsBody({
  result,
  pending,
  sides,
  onRetry,
}: FixturePredictionsPanelProps) {
  if (pending || result === null) {
    return (
      <>
        <p className="sr-only" role="status">
          {LOADING_MESSAGE}
        </p>

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
        onRetry={onRetry}
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
        onRetry={null}
      />
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <p className="sr-only" role="status">
        {LOADED_MESSAGE}
      </p>

      <div className={cn(MARKET_FLOW, markets.length > 1 && MARKET_COLUMNS)}>
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
          {UPDATED_PREFIX}{" "}
          <time dateTime={synchronizedAt.toISOString()}>
            {SYNCHRONIZED_FORMAT.format(synchronizedAt)}
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
 * A fifth state precedes all four, and it is the reason `requested` exists: a
 * panel nobody has asked for has nothing to say, and it says nothing rather
 * than drawing an empty tinted box. Owning that decision here is what lets the
 * caller mount the panel unconditionally — a collapsed list of thirty matches
 * renders thirty of these and puts no placeholder in the document — and it is
 * also what keeps the two facts apart that a single nullable result conflates.
 * "Nothing was asked" and "the answer has not landed" look identical from a
 * `null`, and the branch that reads a `null` as "loading" was left painting a
 * pulsing skeleton over a failed read until the visitor reloaded the page.
 *
 * The unavailable branch repeats the reason the read produced rather than
 * inventing one, as the fixture list does, so an outage is diagnosable from the
 * interface. That reason is composed on the server for this surface and names
 * nothing internal. It is also the one branch that offers to ask again, because
 * a request that failed can succeed on the next attempt, which an unpublished
 * fixture cannot.
 *
 * Both the placeholder and the settled outcome carry their own `role="status"`.
 * The list wraps its rows in `aria-live="off"` so that a filter returning thirty
 * matches does not read all thirty aloud, politeness is inherited, and a panel
 * opened inside that region would therefore swap eleven markets in for a
 * skeleton and announce neither. An element's own live role is what beats the
 * inherited value, and it has to be on both nodes: a region that says a read
 * started and never says how it ended is worse than silence.
 *
 * What the settled node announces is that the panel has arrived, not what is in
 * it. Fifty rows of probabilities read aloud is not an announcement, it is the
 * panel, and a screen reader already navigates it by its market headings.
 *
 * The markets are a multi-column flow declared by column *width*. A count would
 * cut the box into that many column boxes however little there is to put in
 * them, and the provider does not publish every market for every fixture, so a
 * fixture with one market rendered it across half the panel with an empty half
 * beside it. A width lets the used count follow the space: at the page's
 * `max-w-5xl` the panel is around 59rem, which fits exactly two 22rem columns
 * and never a third, and on a narrow pane it fits one — which is also why no
 * container variant is needed any more. The single-market case is the one thing
 * a width cannot fix, because the used count is geometric and does not consult
 * the content, so that case drops the property instead.
 *
 * Multi-column rather than a two-track grid. The markets differ in height by an
 * order of magnitude — two rows for an over/under, nineteen for a correct
 * score — and a grid makes every row as tall as its tallest cell, so pairing a
 * three-row market with a nine-row one left a void under the shorter of the two
 * and pushed the market after it down past both. Multi-column has no rows to
 * align: it balances the columns by height, which is the thing that was wanted,
 * and it keeps the markets in the order the contract sends them.
 *
 * The spacing between markets is a leading margin, because a multi-column
 * container has no row gap to set, and because a trailing one would sit under
 * the last market and push the timestamp away from it. A leading margin cannot:
 * fragmentation truncates a margin adjoining a column break, so the second
 * column's first market keeps its top flush with the first column's rather than
 * starting a row lower.
 *
 * The read's own timestamp is stated, because a probability with no date is a
 * claim with no shelf life and the platform synchronizes on a schedule rather
 * than on demand. It is formatted in UTC and left unlabelled, as the kick-off on
 * the row above it is: the visitor's zone is not knowable while rendering on the
 * server, so the machine-readable `dateTime` is the only statement of the zone
 * until there is a stored preference to resolve it against. The word "Updated"
 * sits outside the `<time>`, because that element's text is its value and a verb
 * is not part of an instant.
 *
 * The surface is tinted rather than separated by a rule. The list puts its
 * dividers between matches, and a border here would read as one more of those,
 * splitting a match from its own panel.
 *
 * @returns The panel, or nothing when no read has been asked for.
 */
export function FixturePredictionsPanel({
  result,
  requested,
  pending,
  sides,
  onRetry,
}: FixturePredictionsPanelProps) {
  if (!requested && result === null) {
    return null;
  }

  return (
    <div className="bg-muted/30 p-4">
      <PredictionsBody
        onRetry={onRetry}
        pending={pending}
        requested={requested}
        result={result}
        sides={sides}
      />
    </div>
  );
}
