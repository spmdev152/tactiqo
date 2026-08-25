"use client";

import { useCallback, useId, useRef, useState, useTransition } from "react";

import { FixturePredictionsPanel } from "@/features/fixtures/components/fixture-predictions-panel";
import { loadFixturePredictionsAction } from "@/features/fixtures/server/actions";
import type { Fixture } from "@/features/fixtures/types/fixture";
import type { FixturePredictionsResult } from "@/features/fixtures/types/prediction";

const TOGGLE_LABEL = "Prediction probabilities";

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
 * The read happens on the first expansion and never again. Reading every row's
 * probabilities to render a collapsed toggle would be dozens of authenticated
 * round trips for data nobody looked at, and re-reading on every expansion would
 * charge the visitor a request for changing their mind about a panel they have
 * already seen. The guard is a ref rather than the cached result, because while
 * the first request is still in flight the result is still `null` and a second
 * click would fire a second request; a ref is set in the same tick as the click,
 * which is the only thing that closes that window.
 *
 * The panel subtree is mounted from the first expansion rather than always. The
 * collapsed region is real markup with a real placeholder in it, so mounting it
 * for every row of a thirty-match day would put thirty pulsing placeholders in
 * the document to be clipped to nothing. Once opened it stays mounted, so
 * collapsing and reopening is free and animates against content that is already
 * there. The condition names the read in flight as well as the answer, because a
 * panel closed again before its request landed would otherwise unmount its own
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
  const [result, setResult] = useState<FixturePredictionsResult | null>(null);

  const requested = useRef(false);

  const toggle = useCallback(() => {
    setOpen((expanded) => !expanded);

    if (requested.current) {
      return;
    }

    requested.current = true;

    startTransition(async () => {
      setResult(await loadFixturePredictionsAction(fixture.id));
    });
  }, [fixture.id]);

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
          {(open || isPending || result !== null) && (
            <FixturePredictionsPanel
              pending={isPending}
              result={result}
              sides={{ home: fixture.homeTeam, away: fixture.awayTeam }}
            />
          )}
        </div>
      </div>
    </>
  );
}
