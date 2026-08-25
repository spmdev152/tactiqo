import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ProbabilityBar } from "@/features/fixtures/components/probability-bar";

const FILL = '[data-slot="probability-fill"]';

describe("ProbabilityBar", () => {
  /**
   * GIVEN a selection the platform puts at 26.96%
   * WHEN its bar is rendered
   * THEN the fill is 26.96% wide, so one length means one probability everywhere
   */
  it("gives the fill the width of its own probability", () => {
    const { container } = render(<ProbabilityBar probability={26.96} />);

    expect(container.querySelector<HTMLElement>(FILL)?.style.width).toBe(
      "26.96%",
    );
  });

  /**
   * GIVEN a probability above the midpoint and one below it
   * WHEN both bars are rendered
   * THEN each is mixed from its own half of the ramp rather than from one pair
   */
  it("flips the token pair either side of the midpoint", () => {
    const high = render(<ProbabilityBar probability={72} />);
    const low = render(<ProbabilityBar probability={28} />);

    expect(
      high.container
        .querySelector<HTMLElement>(FILL)
        ?.style.getPropertyValue("--probability-fill"),
    ).toBe(
      "color-mix(in oklch, var(--probability-high) 44%, var(--probability-mid))",
    );

    expect(
      low.container
        .querySelector<HTMLElement>(FILL)
        ?.style.getPropertyValue("--probability-fill"),
    ).toBe(
      "color-mix(in oklch, var(--probability-mid) 56%, var(--probability-low))",
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
