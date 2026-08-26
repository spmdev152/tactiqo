"use client";

import { useId, useState } from "react";

import { CalendarClock, Info, TriangleAlert } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { FormFilters } from "@/features/fixtures/components/form-filters";
import { FormMetricRow } from "@/features/fixtures/components/form-metric-row";
import {
  type FixtureStatus,
  hasKickedOff,
} from "@/features/fixtures/domain/fixture-status";
import {
  DEFAULT_FORM_RANGE,
  DEFAULT_FORM_SCOPE,
  familyLabel,
  type FormMetric,
  type FormRange,
  type FormScope,
  rangeSize,
} from "@/features/fixtures/domain/form-metrics";
import type { FixtureTeam } from "@/features/fixtures/types/fixture";
import type {
  FixtureFormResult,
  FormMetricValue,
  FormSample,
  TeamForm,
} from "@/features/fixtures/types/form";
import { cn } from "@/lib/utils";

const LOADING_MESSAGE = "Reading pre-match form.";

const LOADED_MESSAGE = "Pre-match form is ready.";

const ERROR_MESSAGE = "Pre-match form is unavailable right now.";

const EMPTY_MESSAGE = "Neither side has a completed match on record.";

const EMPTY_HINT =
  "Form is drawn from matches the platform has already synchronized, so a fixture early in a season has none to draw from.";

const NO_SAMPLE_MESSAGE = "No matches in this window.";

const NO_SAMPLE_HINT =
  "Neither side has played in the window selected. A wider window may hold matches this one does not.";

const MISSING_SAMPLE_MESSAGE = "This window was not published.";

const MISSING_SAMPLE_HINT =
  "The platform published no sample for the window and scope selected, so there is nothing to compare.";

const RETRY_LABEL = "Try again";

const UPDATED_PREFIX = "Updated";

const NO_MATCHES_LABEL = "No matches counted";

const NO_SAMPLE_COUNT_LABEL = "No sample published";

const MATCH_NOUN = "match";

const MATCHES_NOUN = "matches";

const SHORT_JOINER = "of";

const NOTE_TRIGGER_LABEL = "About these figures";

const SEASON_WINDOW_NOTE =
  "Every window counts only matches from this fixture's own season.";

const PLAYED_WINDOW_NOTE =
  "This match has already been played, so the figures stop at its kick-off: they count only the matches each side had played beforehand, and nothing that has happened since. They are the form both sides took into this match.";

const PLACEHOLDER_FAMILIES = [
  { key: "form-placeholder-family-0", rows: 4 },
  { key: "form-placeholder-family-1", rows: 6 },
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
 * Reads how many matches a sample counted, and whether that is fewer than the
 * window asked for.
 *
 * @remarks
 * The window's size is not on the wire, because it is a property of the window
 * rather than of the fixture, so the shortfall is computed against the
 * vocabulary's own definition of it. The season window has no target to fall
 * short of and therefore never reads as short, however few matches it found.
 *
 * The noun agrees with the number it follows, which in the short form is the
 * window and not the count: one match out of six is "1 of 6 matches", never
 * "1 of 6 match".
 *
 * @param counted - Matches the sample was drawn from.
 * @param range - Window the sample was asked for.
 * @returns The count as copy.
 */
function matchesLabel(counted: number, range: FormRange): string {
  if (counted === 0) {
    return NO_MATCHES_LABEL;
  }

  const wanted = rangeSize(range);

  if (wanted !== null && counted < wanted) {
    return `${counted} ${SHORT_JOINER} ${wanted} ${wanted === 1 ? MATCH_NOUN : MATCHES_NOUN}`;
  }

  return `${counted} ${counted === 1 ? MATCH_NOUN : MATCHES_NOUN}`;
}

/**
 * Renders the panel's own shape while the form is being read.
 *
 * @remarks
 * Two families of differing length rather than a spinner, for the reason the
 * predictions placeholder gives one panel over: the disclosure grows to whatever
 * it is about to hold, so a placeholder of the wrong shape makes the row settle
 * twice. The filter row is drawn as well, because it is the tallest thing above
 * the figures and leaving it out would move every row of the panel upwards on
 * settlement.
 *
 * Nothing here is announced. It is a picture of a layout, and the branch that
 * renders it states in words that a read is in flight.
 *
 * @returns The placeholder families.
 */
function FormPlaceholder() {
  return (
    <div aria-hidden="true" className="flex flex-col gap-4">
      <div className="flex items-center gap-4">
        <Skeleton className="h-8 w-44 rounded-lg" />

        <Skeleton className="h-8 w-36 rounded-lg" />
      </div>

      {PLACEHOLDER_FAMILIES.map((family) => (
        <div className="flex flex-col gap-2" key={family.key}>
          <Skeleton className="h-4 w-24" />

          <div className="flex flex-col gap-2">
            {Array.from({ length: family.rows }, (_unused, index) => (
              <div
                className="flex items-center gap-2.5"
                key={`${family.key}-row-${index}`}
              >
                <Skeleton className="h-3 w-20 shrink-0" />

                <Skeleton className="h-1.5 flex-1 rounded-full" />

                <Skeleton className="h-3 w-20 shrink-0" />
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

/**
 * Props of {@link FormNotice}.
 */
interface FormNoticeProps {
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
 * Renders, in the figures' place, why there are none.
 *
 * @remarks
 * The same component and the same reasoning as the predictions panel's own
 * notice: one shape for every branch, so a panel reporting an outage and one
 * reporting an absence read as two answers rather than as two features, with the
 * border carrying which of the two it is. Only a failure offers to ask again,
 * and the callback rather than `failed` decides it, because a window that holds
 * no matches will hold none however many times it is asked.
 *
 * The box is the live region, so the sentence a visitor needs is announced from
 * the element that already carries it rather than from a hidden second copy free
 * to drift from the visible one.
 *
 * @returns The stated notice.
 */
function FormNotice({ message, detail, failed, onRetry }: FormNoticeProps) {
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
 * Props of {@link TeamFormHeader}.
 */
interface TeamFormHeaderProps {
  /** Club the column belongs to. */
  readonly team: FixtureTeam;

  /** The club's sample for the selected window, `undefined` when unpublished. */
  readonly sample: FormSample | undefined;

  /** Window the sample was asked for, which the count is measured against. */
  readonly range: FormRange;

  /** Utility classes aligning the column within its side of the panel. */
  readonly className: string;
}

/**
 * Renders one club's name above its column, with the matches behind its figures.
 *
 * @remarks
 * The count is stated rather than implied, and it is stated per club rather than
 * once for the panel, because the two sides of a fixture rarely have the same
 * number of matches behind them: the narrow scope keeps a different number for
 * each, and a promoted side has a shorter season than the one it is being
 * compared with. A panel that printed one count would be wrong about at least
 * one column half the time.
 *
 * @returns The column heading.
 */
function TeamFormHeader({
  team,
  sample,
  range,
  className,
}: TeamFormHeaderProps) {
  return (
    <div className={cn("flex min-w-0 flex-col gap-0.5", className)}>
      <span className="truncate text-sm font-medium">{team.name}</span>

      <span className="text-xs text-muted-foreground">
        {sample === undefined
          ? NO_SAMPLE_COUNT_LABEL
          : matchesLabel(sample.matchesCounted, range)}
      </span>
    </div>
  );
}

/**
 * One side's sample for a window and scope, and its figures keyed by metric.
 */
interface ResolvedSample {
  /** The sample itself, `undefined` when the API published none. */
  readonly sample: FormSample | undefined;

  /** The sample's figures, addressable by metric. */
  readonly figures: Partial<Record<FormMetric, FormMetricValue>>;
}

/**
 * Reads one team's sample for a window and scope, and keys its figures.
 *
 * @remarks
 * Keyed rather than scanned per row, because a family renders its metrics in
 * the order the API published them and each of those lookups would otherwise
 * walk the sample's twenty-five figures. It is rebuilt on every render, which is
 * fifty property writes and cheaper than the memoization that would avoid them.
 *
 * The record is partial rather than total, and that is the contract rather than
 * a convenience: the wire schema drops a figure whose name the frontend does not
 * know, so a metric the panel asks for may genuinely be absent, and the row
 * renders a dash for it.
 *
 * @param team - One side of the fixture.
 * @param range - Window to resolve.
 * @param scope - Scope to resolve.
 * @returns The sample, and its figures keyed by metric.
 */
function resolveSample(
  team: TeamForm,
  range: FormRange,
  scope: FormScope,
): ResolvedSample {
  const sample = team.samples.find(
    (one) => one.range === range && one.scope === scope,
  );

  const figures: Partial<Record<FormMetric, FormMetricValue>> = {};

  for (const figure of sample?.metrics ?? []) {
    figures[figure.metric] = figure;
  }

  return { sample, figures };
}

/**
 * Props of {@link FixtureFormPanel} and of the body it wraps.
 */
export interface FixtureFormPanelProps {
  /** Outcome of the read, or `null` while it has not answered yet. */
  readonly result: FixtureFormResult | null;

  /** Whether a read has been asked for at all. */
  readonly requested: boolean;

  /** Whether a read is in flight. */
  readonly pending: boolean;

  /** Side playing at home, which names the left column. */
  readonly home: FixtureTeam;

  /** Side playing away, which names the right column. */
  readonly away: FixtureTeam;

  /** State the match is in, which decides what the panel's note explains. */
  readonly status: FixtureStatus;

  /** Asks for the read again after a failure. */
  readonly onRetry: () => void;
}

/**
 * Renders whichever of the four outcomes the read has produced.
 *
 * @remarks
 * Split from the surface around it so the padding and the background are
 * declared once, exactly as the predictions panel splits its own body: four
 * branches sharing one wrapper was four copies of the same utilities, and the
 * first time one drifted the panel would have changed shape depending on which
 * answer it got.
 *
 * A `null` result means the answer has not arrived, never that there is nothing
 * to wait for, because the wrapper has already turned away the case where
 * nothing was asked and every settlement puts a result here.
 *
 * The window and the scope are held here, beside the samples they select from,
 * rather than in the disclosure above. They are applied to figures the panel
 * already holds, which is the point of the backend publishing every window in
 * one response: changing either control re-renders and requests nothing.
 *
 * The price of that placement is that the primitive unmounts an inactive tab, so
 * switching to the probabilities and back returns the panel to its default
 * window. That is accepted rather than worked around. Hoisting the two values
 * into the disclosure would make a component that owns whether a row is open
 * also own the form vocabulary, and keeping the panel mounted while hidden would
 * leave two hundred and fifty figures in the document for every row a visitor
 * has opened. Nothing is lost by the reset: no read is repeated and no state the
 * visitor cannot restore in one click is discarded.
 *
 * The note under the filters explains two things a reader would otherwise take
 * for a fault, and it is reached through an info icon rather than printed. Every
 * window walks backwards from this fixture's kick-off and stops at the season
 * boundary, so in August `Last 3`, `Last 6` and `Season` legitimately show the
 * same figures. And for a match that has already kicked off, every window
 * stopped counting at that kick-off, so the figures record what the two sides
 * brought into the match rather than anything that came after it — which is
 * worth saying outright, because a reader looking at a played match reasonably
 * expects the figures to include it. The range labels themselves are left alone:
 * `Last 6` still means the last six matches it could find.
 *
 * A caveat nobody hovers is a caveat nobody reads, which is what the printed
 * line was protecting, so nothing here depends on hovering. The trigger is an
 * ordinary button, reached by Tab like the filters beside it, and the primitive
 * opens the bubble on focus as well as under a pointer; the icon inside it is
 * decorative and the button takes its name from hidden text, because an icon
 * has none of its own.
 *
 * The sentences live in a permanently rendered hidden paragraph that the trigger
 * names through `aria-describedby`, not only in the bubble. The bubble is in the
 * document only while it is open, so a reader who never opens it would otherwise
 * never be told at all. That association deliberately replaces the one Radix
 * makes to its own content, which carries the same words: the difference is that
 * this one holds when the tooltip is shut.
 *
 * It opens to the right, into the empty band the filter row leaves beside the
 * icon, because the tab strip and the two clubs sit directly above it and the
 * figures the note is about sit directly below. For a played match the note is
 * two sentences rather than one, so a bubble opening upwards covered the fixture
 * row the whole panel belongs to. Radix flips it where the band has no room.
 *
 * Which sentences those are follows from the status rather than from the clock,
 * for the reasons `hasKickedOff` documents.
 *
 * @returns The figures, the placeholder, or why there are none.
 */
function FormBody({
  result,
  pending,
  home,
  away,
  status,
  onRetry,
}: FixtureFormPanelProps) {
  const [range, setRange] = useState<FormRange>(DEFAULT_FORM_RANGE);
  const [scope, setScope] = useState<FormScope>(DEFAULT_FORM_SCOPE);

  const noteId = useId();

  const note = hasKickedOff(status)
    ? `${SEASON_WINDOW_NOTE} ${PLAYED_WINDOW_NOTE}`
    : SEASON_WINDOW_NOTE;

  if (pending || result === null) {
    return (
      <>
        <p className="sr-only" role="status">
          {LOADING_MESSAGE}
        </p>

        <FormPlaceholder />
      </>
    );
  }

  if (!result.loaded) {
    return (
      <FormNotice
        detail={result.reason}
        failed
        message={ERROR_MESSAGE}
        onRetry={onRetry}
      />
    );
  }

  const { form } = result;

  const played = [...form.home.samples, ...form.away.samples].some(
    (sample) => sample.matchesCounted > 0,
  );

  if (!played) {
    return (
      <FormNotice
        detail={EMPTY_HINT}
        failed={false}
        message={EMPTY_MESSAGE}
        onRetry={null}
      />
    );
  }

  const homeSide = resolveSample(form.home, range, scope);
  const awaySide = resolveSample(form.away, range, scope);

  const unpublished =
    homeSide.sample === undefined || awaySide.sample === undefined;

  const counted =
    (homeSide.sample?.matchesCounted ?? 0) +
    (awaySide.sample?.matchesCounted ?? 0);

  return (
    <div className="flex flex-col gap-4">
      <p className="sr-only" role="status">
        {LOADED_MESSAGE}
      </p>

      <div className="flex flex-wrap items-center gap-x-2 gap-y-1.5">
        <FormFilters
          onRangeChange={setRange}
          onScopeChange={setScope}
          range={range}
          scope={scope}
        />

        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              aria-describedby={noteId}
              className="text-muted-foreground"
              size="icon-sm"
              type="button"
              variant="ghost"
            >
              <Info aria-hidden="true" />

              <span className="sr-only">{NOTE_TRIGGER_LABEL}</span>
            </Button>
          </TooltipTrigger>

          <TooltipContent align="center" collisionPadding={8} side="right">
            {note}
          </TooltipContent>
        </Tooltip>

        <p className="sr-only" id={noteId}>
          {note}
        </p>
      </div>

      <div className="flex items-start justify-between gap-3">
        <TeamFormHeader
          className="items-start text-left"
          range={range}
          sample={homeSide.sample}
          team={home}
        />

        <TeamFormHeader
          className="items-end text-right"
          range={range}
          sample={awaySide.sample}
          team={away}
        />
      </div>

      {unpublished && (
        <FormNotice
          detail={MISSING_SAMPLE_HINT}
          failed={false}
          message={MISSING_SAMPLE_MESSAGE}
          onRetry={null}
        />
      )}

      {!unpublished && counted === 0 && (
        <FormNotice
          detail={NO_SAMPLE_HINT}
          failed={false}
          message={NO_SAMPLE_MESSAGE}
          onRetry={null}
        />
      )}

      {!unpublished &&
        counted > 0 &&
        form.families.map((family) => (
          <section className="flex flex-col gap-2" key={family.family}>
            <h3 className="text-sm font-medium">
              {familyLabel(family.family)}
            </h3>

            <ul className="flex flex-col gap-2">
              {family.metrics.map((metric) => (
                <FormMetricRow
                  away={awaySide.figures[metric] ?? null}
                  awayName={away.name}
                  home={homeSide.figures[metric] ?? null}
                  homeName={home.name}
                  key={metric}
                  metric={metric}
                />
              ))}
            </ul>
          </section>
        ))}

      {form.synchronizedAt !== null && (
        <p className="font-mono text-[0.68rem] text-muted-foreground">
          {UPDATED_PREFIX}{" "}
          <time dateTime={form.synchronizedAt.toISOString()}>
            {SYNCHRONIZED_FORMAT.format(form.synchronizedAt)}
          </time>
        </p>
      )}
    </div>
  );
}

/**
 * Renders the pre-match form of both sides of one fixture.
 *
 * @remarks
 * Four outcomes, and the one worth naming is the third. Two sides with no
 * completed match between them is neither a failure nor rare: it is every
 * fixture of an opening weekend and every promoted side's first away trip.
 * Reporting that as an outage would make the ordinary case look broken, so the
 * panel gives it as an absence with a reason and offers no retry, because
 * asking again cannot produce a match that has not been played.
 *
 * A fifth state precedes all four, and it is why `requested` exists: a panel
 * nobody has asked for has nothing to say, and it says nothing rather than
 * drawing an empty tinted box. Owning that decision here is what lets the caller
 * mount the panel unconditionally.
 *
 * Two further absences live inside the loaded branch rather than replacing it,
 * and that placement is the point. A window with no matches behind it, and a
 * window the backend published no sample for, are both properties of the
 * *selection* rather than of the fixture, so the filters stay on screen and the
 * visitor can widen the window instead of being told the fixture has no form.
 *
 * Both the placeholder and the settled outcome carry their own `role="status"`,
 * for the reason the predictions panel documents: the list wraps its rows in
 * `aria-live="off"`, politeness is inherited, and an element's own live role is
 * what beats the inherited value. It has to be on both, because a region that
 * says a read started and never says how it ended is worse than silence.
 *
 * What the settled node announces is that the panel has arrived, not what is in
 * it. Two hundred and fifty figures read aloud is not an announcement, it is the
 * panel, and a screen reader navigates it by its family headings.
 *
 * The read's own timestamp is stated, because a form figure with no date is a
 * claim with no shelf life and the platform synchronizes on a schedule. It is
 * formatted in UTC and left unlabelled, as every other instant in this list is,
 * and the word "Updated" sits outside the `<time>` because that element's text
 * is its value and a verb is not part of an instant.
 *
 * The surface is tinted rather than separated by a rule, because the list puts
 * its dividers between matches and a border here would read as one more of
 * those.
 *
 * @returns The panel, or nothing when no read has been asked for.
 */
export function FixtureFormPanel({
  result,
  requested,
  pending,
  home,
  away,
  status,
  onRetry,
}: FixtureFormPanelProps) {
  if (!requested && result === null) {
    return null;
  }

  return (
    <div className="bg-muted/30 p-4">
      <FormBody
        away={away}
        home={home}
        onRetry={onRetry}
        pending={pending}
        requested={requested}
        result={result}
        status={status}
      />
    </div>
  );
}
