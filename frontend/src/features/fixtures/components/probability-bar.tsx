import { resolveProbabilityFill } from "@/features/fixtures/domain/probability-scale";

const CERTAIN_PROBABILITY = 100;

/**
 * Props of {@link ProbabilityBar}.
 */
export interface ProbabilityBarProps {
  /** Probability of this selection, as a percentage between 0 and 100. */
  readonly probability: number;

  /**
   * Highest probability in the same market, as a percentage between 0 and 100.
   * The marker is placed there, so every bar of a market agrees on where it is.
   */
  readonly marketMaximum: number;
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
 * whole panel.
 *
 * Intra-market comparison is what that costs, so it is bought back on a second
 * channel instead of by distorting the first. A hairline marker sits at the
 * market's own maximum, so the leading selection is the one whose fill reaches
 * it and the rest are read as the distance they fall short. It is painted only
 * below 100, where it has somewhere to be: a marker at the very end of the
 * track lands under the fill that reached it and is clipped by the track's own
 * rounding, so it would cost a paint and say nothing.
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
export function ProbabilityBar({
  probability,
  marketMaximum,
}: ProbabilityBarProps) {
  const fill = resolveProbabilityFill(probability);

  return (
    <span
      aria-hidden="true"
      className="relative block h-1.5 w-full overflow-hidden rounded-full bg-muted"
      data-slot="probability-track"
    >
      <span
        className="block h-full rounded-full bg-(--probability-fill)"
        data-slot="probability-fill"
        style={
          {
            "--probability-fill": `color-mix(in oklch, var(${fill.to}) ${fill.blend}, var(${fill.from}))`,
            width: `${probability}%`,
          } as React.CSSProperties
        }
      />

      {marketMaximum < CERTAIN_PROBABILITY && (
        <span
          className="absolute inset-y-0 w-px bg-foreground/45"
          data-slot="probability-marker"
          style={{ left: `${marketMaximum}%` }}
        />
      )}
    </span>
  );
}
