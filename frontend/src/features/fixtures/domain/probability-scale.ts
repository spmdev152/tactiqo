const PROBABILITY_FLOOR = 0;

const PROBABILITY_MIDPOINT = 50;

const PROBABILITY_CEILING = 100;

const HIGH_TOKEN = "--probability-high";

const MID_TOKEN = "--probability-mid";

const LOW_TOKEN = "--probability-low";

const BLEND_PRECISION = 100;

/**
 * The two ends of the probability ramp a bar is filled from, and how far along
 * it a given probability sits.
 *
 * @remarks
 * Both ends are the *names* of CSS custom properties, not colours. The caller
 * writes `color-mix(in oklch, var(${fill.to}) ${fill.blend}, var(${fill.from}))`.
 */
export interface ProbabilityFill {
  /** Name of the custom property holding the colour at the segment's start. */
  readonly from: string;

  /** Name of the custom property holding the colour at the segment's end. */
  readonly to: string;

  /** How far along the segment the probability sits, as a CSS percentage. */
  readonly blend: string;
}

/**
 * Resolves where a probability sits on the platform's probability ramp.
 *
 * @remarks
 * The ramp is piecewise: a low half running `--probability-low` to
 * `--probability-mid`, and a high half running `--probability-mid` to
 * `--probability-high`. A coin-flip probability therefore lands exactly on the
 * midpoint colour and is visibly neither end, which a single two-stop gradient
 * could not express.
 *
 * The pair is teal to amber to earth red rather than green to yellow to red.
 * Red against green is precisely the pair that collapses under deuteranopia and
 * protanopia, so the most common probability scale in the industry is the one
 * that carries the least information to roughly one man in twelve. A yellow
 * midpoint is the second problem: yellow cannot hold a 3:1 contrast ratio
 * against this theme's light background, so the middle of the scale would be
 * the part hardest to see. And red carries a third, non-visual cost, because it
 * reads as an error and a 12% probability is not one — it is an ordinary,
 * useful reading about a match unlikely to end that way.
 *
 * The function deliberately returns two token names and a weight rather than a
 * colour. CSS interpolates `color-mix(in oklch, ...)` in oklch itself, so the
 * ramp is perceptually uniform without this module implementing an
 * interpolation, and because the browser resolves `var()` at paint time the one
 * weight produces the light theme's ramp or the dark theme's, whichever is
 * active. Returning a colour would mean this module knowing both themes'
 * values, recomputing on every theme change, and re-implementing an oklch blend
 * in JavaScript to reach an answer the style engine already has.
 *
 * The input is clamped rather than trusted. A probability outside `0`–`100`
 * breaks the API contract, but the honest reading of one is a full or an empty
 * bar rather than a blend weight past the end of its own segment, which paints
 * as a colour belonging to neither.
 *
 * @param probability - Probability as a percentage between `0` and `100`.
 * @returns The segment of the ramp to fill from, and how far along it to blend.
 */
export function resolveProbabilityFill(probability: number): ProbabilityFill {
  const clamped = Math.min(
    PROBABILITY_CEILING,
    Math.max(PROBABILITY_FLOOR, probability),
  );

  const isHighHalf = clamped >= PROBABILITY_MIDPOINT;
  const offset = isHighHalf ? clamped - PROBABILITY_MIDPOINT : clamped;
  const spanned = (offset * PROBABILITY_CEILING) / PROBABILITY_MIDPOINT;
  const blend = Math.round(spanned * BLEND_PRECISION) / BLEND_PRECISION;

  return {
    from: isHighHalf ? MID_TOKEN : LOW_TOKEN,
    to: isHighHalf ? HIGH_TOKEN : MID_TOKEN,
    blend: `${blend}%`,
  };
}
