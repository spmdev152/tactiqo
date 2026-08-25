import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ProbabilityBar } from "@/features/fixtures/components/probability-bar";

const FILL_SELECTOR = '[data-slot="probability-fill"]';

/**
 * Reads the inline style the bar computed for its own fill.
 *
 * @param container - Element the bar was rendered into.
 * @returns The style declaration of the fill.
 * @throws When the rendered bar carries no fill at all.
 */
function fillStyleOf(container: HTMLElement): CSSStyleDeclaration {
  const fill = container.querySelector<HTMLElement>(FILL_SELECTOR);

  if (fill === null) {
    throw new Error("The rendered bar carries no fill.");
  }

  return fill.style;
}

/**
 * Renders one bar and reads the inline style of its fill.
 *
 * @param probability - Probability to render.
 * @returns The style declaration of the fill.
 */
function renderFillStyle(probability: number): CSSStyleDeclaration {
  const { container } = render(<ProbabilityBar probability={probability} />);

  return fillStyleOf(container);
}

describe("ProbabilityBar", () => {
  /**
   * GIVEN a selection the platform puts at 26.96%
   * WHEN its bar is rendered
   * THEN the fill is 26.96% wide, so one length means one probability everywhere
   */
  it("gives the fill the width of its own probability", () => {
    expect(renderFillStyle(26.96).width).toBe("26.96%");
  });

  /**
   * GIVEN a probability above the midpoint and one below it
   * WHEN both bars are rendered
   * THEN each is mixed from its own half of the ramp rather than from one pair
   */
  it("flips the token pair either side of the midpoint", () => {
    expect(renderFillStyle(72).getPropertyValue("--probability-fill")).toBe(
      "color-mix(in oklch, var(--probability-high) 44%, var(--probability-mid))",
    );

    expect(renderFillStyle(28).getPropertyValue("--probability-fill")).toBe(
      "color-mix(in oklch, var(--probability-mid) 56%, var(--probability-low))",
    );
  });

  /**
   * GIVEN a probability below the floor of the range the props contract promises
   * WHEN its bar is rendered
   * THEN the length is clamped with the colour, rather than dropped for `auto`
   */
  it("empties the bar of a probability under the floor", () => {
    const style = renderFillStyle(-10);

    expect(style.width).toBe("0%");

    expect(style.getPropertyValue("--probability-fill")).toBe(
      "color-mix(in oklch, var(--probability-mid) 0%, var(--probability-low))",
    );
  });

  /**
   * GIVEN a probability above the ceiling of the range the contract promises
   * WHEN its bar is rendered
   * THEN it fills its track exactly once rather than overflowing its own row
   */
  it("fills the bar of a probability over the ceiling", () => {
    const style = renderFillStyle(140);

    expect(style.width).toBe("100%");

    expect(style.getPropertyValue("--probability-fill")).toBe(
      "color-mix(in oklch, var(--probability-high) 100%, var(--probability-mid))",
    );
  });

  /**
   * GIVEN a probability that is not a number at all
   * WHEN its bar is rendered
   * THEN it claims nothing, instead of painting the widest bar on the screen
   */
  it("empties the bar of a probability that is not a number", () => {
    const style = renderFillStyle(Number.NaN);

    expect(style.width).toBe("0%");

    expect(style.getPropertyValue("--probability-fill")).toBe(
      "color-mix(in oklch, var(--probability-mid) 0%, var(--probability-low))",
    );
  });

  /**
   * GIVEN a bar whose value the row beside it already states in words
   * WHEN the bar is rendered
   * THEN it is hidden from the accessibility tree rather than announced twice
   */
  it("keeps the bar out of the accessibility tree", () => {
    const { container } = render(<ProbabilityBar probability={26.96} />);

    expect(
      container.querySelector('[data-slot="probability-track"]'),
    ).toHaveAttribute("aria-hidden", "true");
  });
});
