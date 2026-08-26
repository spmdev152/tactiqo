"use client";

import { useCallback, useId, useRef, useState, useTransition } from "react";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { FixtureFormPanel } from "@/features/fixtures/components/fixture-form-panel";
import { FixturePredictionsPanel } from "@/features/fixtures/components/fixture-predictions-panel";
import {
  loadFixtureFormAction,
  loadFixturePredictionsAction,
} from "@/features/fixtures/server/actions";
import type { Fixture } from "@/features/fixtures/types/fixture";
import type { FixtureFormResult } from "@/features/fixtures/types/form";
import type { FixturePredictionsResult } from "@/features/fixtures/types/prediction";

const TOGGLE_LABEL = "Match insights";

const TAB_LIST_LABEL = "Match insights";

const PROBABILITIES_TAB = "probabilities";

const FORM_TAB = "form";

const PROBABILITIES_LABEL = "Probabilities";

const FORM_LABEL = "Form";

const TAB_TRIGGER =
  "h-full rounded-none after:hidden data-[state=active]:font-semibold data-[state=active]:text-foreground dark:data-[state=active]:text-foreground";

const UNREACHABLE_REASON =
  "The request did not complete. Check your connection and try again.";

const UNREACHABLE_PREDICTIONS: FixturePredictionsResult = {
  loaded: false,
  reason: UNREACHABLE_REASON,
};

const UNREACHABLE_FORM: FixtureFormResult = {
  loaded: false,
  reason: UNREACHABLE_REASON,
};

/**
 * The one fact a lazily read answer has to expose for the guard to close.
 */
interface LazyOutcome {
  /** Whether the read produced an answer worth keeping. */
  readonly loaded: boolean;
}

/**
 * One tab's read: whether it has been asked for, is running, and what it said.
 */
interface LazyRead<TOutcome extends LazyOutcome> {
  /** Whether a read is in flight. */
  readonly pending: boolean;

  /** Whether a read has been asked for at all. */
  readonly asked: boolean;

  /** The answer, or `null` while none has landed. */
  readonly result: TOutcome | null;

  /** Asks for the read, at most once while it keeps succeeding. */
  readonly read: () => void;

  /** Asks again after a failure, clearing the answer that failed. */
  readonly retry: () => void;
}

/**
 * Holds one tab's read: its guard, its pending flag and its answer.
 *
 * @remarks
 * Two tabs need this and they must not share any part of it, which is what makes
 * a hook the right shape rather than an abstraction for its own sake. Sharing a
 * pending flag would put a skeleton in the tab that had already answered;
 * sharing the guard would let one tab's success suppress the other's request.
 *
 * The read happens on the first activation of its own tab and, when it worked,
 * never again. Reading both tabs of every row to render a collapsed toggle would
 * be dozens of authenticated round trips for data nobody looked at, and
 * re-reading on every activation would charge the visitor a request for
 * switching back to a tab they have already seen.
 *
 * The guard is a ref rather than the cached result, because while the first
 * request is still in flight the result is still `null` and a second activation
 * would fire a second request; a ref is set in the same tick as the click, which
 * is the only thing that closes that window.
 *
 * A failed read reopens the guard, and this is the whole difference between a
 * tab that recovers and one that does not. An unavailable answer is worth asking
 * again — the connection blipped, the API was restarting — so the guard closes
 * only on the answer that is worth keeping. A visitor whose read failed can
 * therefore collapse and reopen the row, switch away and back, or press the
 * panel's own retry, instead of reloading the page.
 *
 * The rejection is caught rather than left to propagate. A Server Action can
 * reject for reasons that have nothing to do with the fixture — an offline
 * browser, an action identifier a redeploy invalidated — and React unwraps a
 * rejected transition thenable during render and rethrows it. With no
 * `error.tsx` above this route that replaces the entire page with a client
 * exception, so one unreachable row would take the whole day's list with it. The
 * substituted answer names nothing server-side, because the throw carries no
 * reason a visitor could use.
 *
 * @param load - Server Action that answers for one fixture.
 * @param fixtureId - Fixture to read.
 * @param unreachable - Answer to substitute when the action rejects outright.
 * @returns The state of that tab's read, and the two ways to start it.
 */
function useLazyRead<TOutcome extends LazyOutcome>(
  load: (fixtureId: number) => Promise<TOutcome>,
  fixtureId: number,
  unreachable: TOutcome,
): LazyRead<TOutcome> {
  const [pending, startTransition] = useTransition();
  const [asked, setAsked] = useState(false);
  const [result, setResult] = useState<TOutcome | null>(null);

  const requested = useRef(false);

  const read = useCallback(() => {
    if (requested.current) {
      return;
    }

    requested.current = true;
    setAsked(true);

    startTransition(async () => {
      try {
        const answer = await load(fixtureId);

        requested.current = answer.loaded;
        setResult(answer);
      } catch {
        requested.current = false;
        setResult(unreachable);
      }
    });
  }, [fixtureId, load, unreachable]);

  const retry = useCallback(() => {
    setResult(null);
    read();
  }, [read]);

  return { pending, asked, result, read, retry };
}

/**
 * Props of {@link FixtureDisclosure}.
 */
export interface FixtureDisclosureProps {
  /** Match whose insights the panel reads. */
  readonly fixture: Fixture;

  /** Row content, which becomes the label of the control that expands it. */
  readonly children: React.ReactNode;
}

/**
 * Turns a fixture row into the control that opens its insights panel.
 *
 * @remarks
 * The one client component in the list, and it is a client component for three
 * reasons and no others: it holds whether the panel is open, which of its two
 * tabs is showing, and when to ask for each tab's data. Everything it renders —
 * the row above and both panels below — stays server-renderable and is handed to
 * it.
 *
 * Every row offers the toggle. It used to be offered only where the platform
 * held probabilities, which was correct while probabilities were the only thing
 * behind it: a chevron pointing at an empty drawer is worse than no chevron. Form
 * changes that, because form is drawn from matches already played and is
 * therefore available for almost every fixture the list can show, including every
 * fixture too far out for a model to have run on. `hasPredictions` still decides
 * something, but it decides which tab opens first rather than whether anything
 * opens at all, so a fixture with no probabilities opens on its form instead of
 * on an apology.
 *
 * Each tab reads independently and only on its own first activation, which is
 * what keeps opening a row to one request. The probabilities are a small
 * prepared payload and the form is two sides of six windows of twenty-five
 * figures, so a single read answering both would make the cheaper tab pay for
 * the larger one and would let either failure take the other down.
 *
 * Neither panel is told which tab is showing, because Radix mounts only the
 * active one. That is also why the answers are held here rather than inside the
 * panels: switching away unmounts a panel, and state kept in it would restart
 * the request on the way back.
 *
 * The tabs themselves are mounted on the first expansion and stay mounted
 * afterwards. Mounting them with the row would put two more controls in the
 * document for every match of a thirty-match day, for a panel nobody has opened;
 * unmounting them on collapse would remove the content mid-transition, so the
 * panel would vanish instead of sliding shut.
 *
 * The region grows from `grid-template-rows: 0fr` to `1fr` rather than from a
 * `max-height`. A height animation needs a number chosen in advance, and this
 * panel has no such number: five families of figures against an unavailable
 * notice differ by an order of magnitude, so any ceiling is either a clip or a
 * pause at the end of every open. A grid track sized in `fr` resolves against
 * the content itself, which is why the child carries `overflow-hidden` — that is
 * what has a measurable height to be clipped while the track is still smaller
 * than it.
 *
 * The state is spelled `data-state="open"` and animated through the `data-open:`
 * variant `globals.css` registers, rather than through a variant of its own.
 * That variant exists because the registry primitives write Radix's state that
 * way, and reusing it means this transition is expressed the same way as every
 * other one in the application.
 *
 * The tab list is the full width of the panel, flush against the row above it,
 * with each tab exactly half. It is a two-column grid rather than a flex row
 * with `flex-1` on each trigger, because a grid states the halves and flex only
 * approximates them: a trigger's padding and its label's width both feed into a
 * flex basis, so "Probabilities" and "Form" would settle on unequal halves and
 * the indicator under them would line up with neither.
 *
 * `variant="line"` rather than `variant="default"`, chosen for the size of the
 * override it leaves behind. Under `default` the list carries an opaque
 * `bg-muted` and the trigger a `data-active:bg-background` pill with its own
 * shadow and three dark-mode siblings, all of which fight a full-bleed bar and
 * all of which would have to be suppressed from here. Under `line` the list is
 * already `bg-transparent` and `rounded-none`, the primitive itself forces the
 * trigger's background transparent both idle and active, and the only affordance
 * left is the `after:` underline — one `after:hidden` on the trigger. That
 * underline sits at `bottom-[-5px]`, outside a list that now carries a border of
 * its own, so suppressing it is what a flush bar requires rather than a taste.
 *
 * `flex-col` on the root and a plain `h-10` on the list are overrides of two
 * dead declarations in the primitive, and neither is redundant however much it
 * reads that way. `data-horizontal:flex-col` and
 * `group-data-horizontal/tabs:h-8` compile to `&[data-horizontal]`, but Radix
 * writes the attribute as `data-orientation="horizontal"`, so both candidates
 * match nothing: measured here, the root laid out as a flex *row* and put the
 * tab list beside its panel at 778px against 196px, with the list stretched to
 * the panel's full 1870px height. Declaring the direction and the height
 * outright is what makes a bar above its content. The primitive's
 * `data-active:` rules miss for the same reason — Radix writes
 * `data-state="active"` — which is why the selected tab had no visible state at
 * all before this and why the reinforcement below is keyed on
 * `data-[state=active]:`. The file is registry-generated and Prettier-excluded,
 * so the correction belongs here rather than in it.
 *
 * The indicator is a `w-1/2` bar translated by nothing or by its own width, and
 * that is exact rather than measured: with two tabs at half the grid each, the
 * distance to travel is the width of the bar. Nothing is observed, no layout is
 * read back, and `transition-transform` animates the one property that moves.
 * The measured alternative — a ref on the active trigger and its offset held in
 * state — buys nothing at two tabs and would have to relayout on every resize.
 *
 * It slides on `data-shifted`, written from the same state the list is driven
 * by, so the attribute the CSS keys on is the attribute a test asserts and the
 * two cannot drift apart. It is `aria-hidden` because it is decoration: which
 * tab is selected is stated by `aria-selected` and painted a second time as the
 * label's own weight and colour, for a reader who cannot place a moving bar.
 *
 * No `prefers-reduced-motion` query is needed here. The base layer at the foot
 * of `globals.css` already clamps `transition-duration` to `0.01ms` on `*`,
 * `*::before` and `*::after` with `!important`, and grants an exemption to the
 * spinner alone, so every transition this component declares — the region's own
 * grid track and the indicator's slide — is already suppressed for a visitor who
 * asked for that.
 *
 * The collapsed region is `inert`. Clipping content to zero height leaves it
 * focusable and readable, so without this a keyboard visitor would tab into a
 * tab list they never opened and a screen reader would find five families of
 * figures under every row. `inert` is also what makes the collapsed subtree
 * consistent with `aria-expanded`, which is a claim about the panel and would
 * otherwise be false.
 *
 * The control names itself from inside. A visually hidden label after the row
 * content composes into the accessible name rather than replacing it, which is
 * what an `aria-label` would have done: the button would then announce "match
 * insights" and withhold which match it belongs to.
 *
 * @returns The row as a disclosure, and its two panels.
 */
export function FixtureDisclosure({
  fixture,
  children,
}: FixtureDisclosureProps) {
  const panelId = useId();

  const predictions = useLazyRead(
    loadFixturePredictionsAction,
    fixture.id,
    UNREACHABLE_PREDICTIONS,
  );

  const form = useLazyRead(loadFixtureFormAction, fixture.id, UNREACHABLE_FORM);

  const [open, setOpen] = useState(false);
  const [revealed, setRevealed] = useState(false);

  const [tab, setTab] = useState(
    fixture.hasPredictions ? PROBABILITIES_TAB : FORM_TAB,
  );

  const { read: readPredictions } = predictions;
  const { read: readForm } = form;

  const activate = useCallback(
    (value: string) => {
      if (value === FORM_TAB) {
        readForm();

        return;
      }

      readPredictions();
    },
    [readForm, readPredictions],
  );

  const toggle = useCallback(() => {
    const expanding = !open;

    setOpen(expanding);

    if (expanding) {
      setRevealed(true);
      activate(tab);
    }
  }, [activate, open, tab]);

  const select = useCallback(
    (value: string) => {
      setTab(value);
      activate(value);
    },
    [activate],
  );

  return (
    <>
      <button
        aria-busy={predictions.pending || form.pending}
        aria-controls={panelId}
        aria-expanded={open}
        className="group/fixture-row block w-full text-left outline-none hover:bg-muted/50 focus-visible:inset-ring-3 focus-visible:inset-ring-ring/50"
        onClick={toggle}
        type="button"
      >
        {children}

        <span className="sr-only">{TOGGLE_LABEL}</span>
      </button>

      <div
        className="grid grid-rows-[0fr] transition-[grid-template-rows] ease-out data-open:grid-rows-[1fr]"
        data-state={open ? "open" : "closed"}
        id={panelId}
        inert={!open}
      >
        <div className="overflow-hidden">
          {revealed && (
            <Tabs className="flex-col gap-0" onValueChange={select} value={tab}>
              <TabsList
                aria-label={TAB_LIST_LABEL}
                className="relative grid h-10 w-full grid-cols-2 gap-0 border-b border-border bg-muted/50 p-0"
                variant="line"
              >
                <span
                  aria-hidden="true"
                  className="pointer-events-none absolute bottom-0 left-0 h-[3px] w-1/2 bg-primary transition-transform ease-out data-[shifted=true]:translate-x-full"
                  data-shifted={tab === FORM_TAB}
                  data-slot="fixture-tab-indicator"
                />

                <TabsTrigger className={TAB_TRIGGER} value={PROBABILITIES_TAB}>
                  {PROBABILITIES_LABEL}
                </TabsTrigger>

                <TabsTrigger className={TAB_TRIGGER} value={FORM_TAB}>
                  {FORM_LABEL}
                </TabsTrigger>
              </TabsList>

              <TabsContent value={PROBABILITIES_TAB}>
                <FixturePredictionsPanel
                  onRetry={predictions.retry}
                  pending={predictions.pending}
                  requested={predictions.asked}
                  result={predictions.result}
                  sides={{ home: fixture.homeTeam, away: fixture.awayTeam }}
                />
              </TabsContent>

              <TabsContent value={FORM_TAB}>
                <FixtureFormPanel
                  away={fixture.awayTeam}
                  home={fixture.homeTeam}
                  onRetry={form.retry}
                  pending={form.pending}
                  requested={form.asked}
                  result={form.result}
                />
              </TabsContent>
            </Tabs>
          )}
        </div>
      </div>
    </>
  );
}
