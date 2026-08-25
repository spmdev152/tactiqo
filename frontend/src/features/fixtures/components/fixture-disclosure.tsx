"use client";

import { useCallback, useId, useRef, useState, useTransition } from "react";

import { FixturePredictionsPanel } from "@/features/fixtures/components/fixture-predictions-panel";
import { loadFixturePredictionsAction } from "@/features/fixtures/server/actions";
import type { Fixture } from "@/features/fixtures/types/fixture";
import type { FixturePredictionsResult } from "@/features/fixtures/types/prediction";

const TOGGLE_LABEL = "Prediction probabilities";

const UNREACHABLE_RESULT: FixturePredictionsResult = {
  loaded: false,
  reason: "The request did not complete. Check your connection and try again.",
};

/**
 * Props of {@link FixtureDisclosure}.
 */
export interface FixtureDisclosureProps {
  /** Match whose probabilities the panel reads. */
  readonly fixture: Fixture;

  /** Row content, which becomes the label of the control that expands it. */
  readonly children: React.ReactNode;
}

/**
 * Turns a fixture row into the control that opens its prediction panel.
 *
 * @remarks
 * The one client component in the list, and it is a client component for two
 * reasons and no others: it holds whether the panel is open, and it decides when
 * to ask for the probabilities. Everything it renders — the row above and the
 * panel below — stays server-renderable and is handed to it.
 *
 * The read happens on the first expansion and, when it worked, never again.
 * Reading every row's probabilities to render a collapsed toggle would be dozens
 * of authenticated round trips for data nobody looked at, and re-reading on
 * every expansion would charge the visitor a request for changing their mind
 * about a panel they have already seen. The guard is a ref rather than the
 * cached result, because while the first request is still in flight the result
 * is still `null` and a second click would fire a second request; a ref is set
 * in the same tick as the click, which is the only thing that closes that
 * window. Only an expansion reads; collapsing a row that failed would otherwise
 * spend a request on a panel the visitor is in the act of dismissing.
 *
 * A failed read reopens that guard, and this is the whole difference between a
 * panel that recovers and one that does not. An unavailable answer is worth
 * asking again — the connection blipped, the API was restarting — so the guard
 * is closed again only on the answer that is worth keeping. A visitor whose read
 * failed can therefore collapse and reopen the row, or press the panel's own
 * retry, instead of reloading the page.
 *
 * The rejection is caught rather than left to propagate. A Server Action can
 * reject for reasons that have nothing to do with the fixture — an offline
 * browser, an action identifier a redeploy invalidated — and React unwraps a
 * rejected transition thenable during render and rethrows it. With no
 * `error.tsx` above this route that replaces the entire page with a client
 * exception, so one unreachable row would take the whole day's list with it. The
 * substituted reason is a constant here and names nothing server-side, because
 * the throw carries no reason a visitor could use.
 *
 * Whether the panel has anything to render is the panel's own decision, and it
 * is handed the one fact it cannot infer: whether a read was ever asked for. A
 * `null` result on its own conflates "nobody asked" with "the answer has not
 * landed", and the second of those is a placeholder while the first is nothing at
 * all. Passing it down also means there is no mount condition here to get wrong:
 * a collapsed row renders a panel that returns nothing, so a thirty-match day
 * puts no pulsing placeholder in the document, and once asked the subtree stays
 * mounted for as long as the row does — including while a request is in flight
 * that the visitor closed the panel on, which would otherwise unmount its own
 * placeholder mid-transition and vanish instead of sliding shut.
 *
 * The region grows from `grid-template-rows: 0fr` to `1fr` rather than from a
 * `max-height`. A height animation needs a number chosen in advance, and this
 * panel has no such number: eleven markets against an unavailable notice differ
 * by an order of magnitude, so any ceiling is either a clip or a pause at the
 * end of every open. A grid track sized in `fr` resolves against the content
 * itself, which is why the child carries `overflow-hidden` — that is what has a
 * measurable height to be clipped while the track is still smaller than it.
 *
 * The state is spelled `data-state="open"` and animated through the
 * `data-open:` variant `globals.css` registers, rather than through a variant of
 * its own. That variant exists because the registry primitives write Radix's
 * state that way, and reusing it means this transition is expressed the same way
 * as every other one in the application.
 *
 * No `prefers-reduced-motion` query is needed here. The base layer at the foot
 * of `globals.css` already clamps `transition-duration` to `0.01ms` on `*`,
 * `*::before` and `*::after` with `!important`, and grants an exemption to the
 * spinner alone, so both transitions this component declares are already
 * suppressed for a visitor who asked for that. Durations are left to the theme's
 * `--default-transition-duration` for the same reason a second timing constant
 * is not wanted.
 *
 * The collapsed region is `inert`. Clipping content to zero height leaves it
 * focusable and readable, so without this a keyboard visitor would tab into a
 * panel they never opened and a screen reader would find eleven markets under
 * every row. `inert` is also what makes the collapsed subtree consistent with
 * `aria-expanded`, which is a claim about the panel and would otherwise be
 * false.
 *
 * The control names itself from inside. A visually hidden label after the row
 * content composes into the accessible name rather than replacing it, which is
 * what an `aria-label` would have done: the button would then announce
 * "prediction probabilities" and withhold which match it belongs to. The
 * codebase's competition picker documents the same choice for the same reason.
 *
 * @returns The row as a disclosure, and its panel.
 */
export function FixtureDisclosure({
  fixture,
  children,
}: FixtureDisclosureProps) {
  const panelId = useId();

  const [isPending, startTransition] = useTransition();
  const [open, setOpen] = useState(false);
  const [asked, setAsked] = useState(false);
  const [result, setResult] = useState<FixturePredictionsResult | null>(null);

  const requested = useRef(false);

  const read = useCallback(() => {
    if (requested.current) {
      return;
    }

    requested.current = true;
    setAsked(true);

    startTransition(async () => {
      try {
        const answer = await loadFixturePredictionsAction(fixture.id);

        requested.current = answer.loaded;
        setResult(answer);
      } catch {
        requested.current = false;
        setResult(UNREACHABLE_RESULT);
      }
    });
  }, [fixture.id]);

  const toggle = useCallback(() => {
    const expanding = !open;

    setOpen(expanding);

    if (expanding) {
      read();
    }
  }, [open, read]);

  const retry = useCallback(() => {
    setResult(null);
    read();
  }, [read]);

  return (
    <>
      <button
        aria-busy={isPending}
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
          <FixturePredictionsPanel
            onRetry={retry}
            pending={isPending}
            requested={asked}
            result={result}
            sides={{ home: fixture.homeTeam, away: fixture.awayTeam }}
          />
        </div>
      </div>
    </>
  );
}
