import { resolveProbabilityFill } from "@/features/fixtures/domain/probability-scale";

/**
 * Props of {@link ProbabilityBar}.
 */
export interface ProbabilityBarProps {
  /** Probability of this selection, as a percentage between 0 and 100. */
  readonly probability: number;
}

/**
 * Renders one selection's probability as a bar on the shared colour scale.
 *
 * @remarks
 * The width is the probability itself and nothing else. A bar normalized to its
 * market's maximum reads better within one market and lies about every
 * comparison across markets: a 34% favourite and a 71% favourite would both
 * reach the end of their track, so the panel would say that eleven markets are
 * equally confident. Absolute width keeps one meaning for one length down the
 * whole panel, and the leading selection of a market is simply the longest bar
 * in its list, read against the others rather than against a reference drawn
 * for it.
 *
 * Both the length and the colour are read from the same resolved fill, so a
 * probability outside the contract cannot paint one of them and break the
 * other. Writing the raw prop into the width did exactly that: `-10%` is a
 * declaration CSS drops, so the bar fell back to `width: auto` and the least
 * likely outcome of a market painted the longest bar in it.
 *
 * The fill colour is a `color-mix` of the two anchors the value falls between,
 * resolved by `domain/probability-scale.ts`. It is assigned to a custom
 * property and read back with `bg-(--probability-fill)` rather than written
 * straight to `background-color`, so the utility stays the one thing that
 * paints a background here and the value the component computes stays a value.
 *
 * The whole bar is hidden from the accessibility tree, because the row around
 * it already carries the selection and its percentage as text. That is what
 * makes the scale a second reading of a value rather than the only one, which
 * is in turn what lets the three anchors be chosen for separation from each
 * other rather than for contrast against the surface — `globals.css` argues
 * that trade where the tokens are declared.
 *
 * @returns The bar for one selection.
 */
export function ProbabilityBar({ probability }: ProbabilityBarProps) {
  const fill = resolveProbabilityFill(probability);

  return (
    <span
      aria-hidden="true"
      className="block h-1.5 w-full overflow-hidden rounded-full bg-muted"
      data-slot="probability-track"
    >
      <span
        className="block h-full rounded-full bg-(--probability-fill)"
        data-slot="probability-fill"
        style={
          {
            "--probability-fill": `color-mix(in oklch, var(${fill.to}) ${fill.blend}, var(${fill.from}))`,
            width: fill.width,
          } as React.CSSProperties
        }
      />
    </span>
  );
}
