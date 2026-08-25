import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeAll, describe, expect, it } from "vitest";

import { TooltipProvider } from "@/components/ui/tooltip";
import { PredictionMarketSection } from "@/features/fixtures/components/prediction-market-section";
import type { PredictionSides } from "@/features/fixtures/domain/prediction-markets";
import type { PredictionMarketProbabilities } from "@/features/fixtures/types/prediction";

const SIDES: PredictionSides = {
  home: { id: 3, name: "Liverpool", shortCode: "LIV", crestUrl: "" },
  away: { id: 4, name: "Nottingham Forest", shortCode: "NFO", crestUrl: "" },
};

const FULL_TIME_RESULT: PredictionMarketProbabilities = {
  market: "fulltime_result",
  reliability: "good",
  hitRatio: 0.55,
  selections: [
    { selection: "home", probability: 26.96 },
    { selection: "draw", probability: 24.82 },
    { selection: "away", probability: 48.18 },
  ],
};

const UNMEASURED_FIRST_HALF: PredictionMarketProbabilities = {
  market: "first_half_result",
  reliability: "medium",
  hitRatio: null,
  selections: [
    { selection: "home", probability: 21.4 },
    { selection: "draw", probability: 45.9 },
    { selection: "away", probability: 32.7 },
  ],
};

const DOUBLE_CHANCE: PredictionMarketProbabilities = {
  market: "double_chance",
  reliability: null,
  hitRatio: null,
  selections: [
    { selection: "home_or_draw", probability: 51.78 },
    { selection: "home_or_away", probability: 75.14 },
    { selection: "draw_or_away", probability: 73 },
  ],
};

const HIT_RATE_LABEL = "Hit rate of 55%";

const CHIP_SELECTOR = '[data-slot="badge"], [data-slot="tooltip-trigger"]';

/**
 * Teaches jsdom the layout and pointer APIs the tooltip measures itself with.
 * None of them exist there, and the tooltip throws on mount without them.
 */
function installPopupEnvironment(): void {
  globalThis.ResizeObserver = class {
    observe(): void {}
    unobserve(): void {}
    disconnect(): void {}
  };

  Element.prototype.scrollIntoView = () => {};
  Element.prototype.hasPointerCapture = () => false;
  Element.prototype.releasePointerCapture = () => {};
  Element.prototype.setPointerCapture = () => {};
}

/**
 * Renders one market section inside the provider its tooltip needs.
 *
 * @param market - Market to render.
 * @returns The element the section was rendered into.
 */
function renderSection(market: PredictionMarketProbabilities): HTMLElement {
  const { container } = render(
    <TooltipProvider>
      <PredictionMarketSection market={market} sides={SIDES} />
    </TooltipProvider>,
  );

  return container;
}

/**
 * Reads the grade chip out of a rendered market section. It cannot be found by
 * its text, because the hit rate the chip carries for a screen reader is part
 * of that text, and its slot is renamed by Radix when the chip is a tooltip
 * trigger, so either name identifies it.
 *
 * @param container - Element the section was rendered into.
 * @returns The chip element.
 * @throws When the section rendered no chip at all.
 */
function chipOf(container: HTMLElement): HTMLElement {
  const chip = container.querySelector<HTMLElement>(CHIP_SELECTOR);

  if (chip === null) {
    throw new Error("The rendered section carries no reliability chip.");
  }

  return chip;
}

describe("PredictionMarketSection", () => {
  beforeAll(installPopupEnvironment);

  /**
   * GIVEN a market the provider grades and every selection it published
   * WHEN the section is rendered
   * THEN each selection carries its own label and percentage as readable text
   */
  it("states every selection and its probability in words", () => {
    renderSection(FULL_TIME_RESULT);

    expect(
      screen.getByRole("heading", { level: 3, name: "Full-time result" }),
    ).toBeVisible();

    expect(screen.getByText("LIV")).toBeVisible();
    expect(screen.getByText("Draw")).toBeVisible();
    expect(screen.getByText("NFO")).toBeVisible();

    expect(screen.getByText("27.0%")).toBeVisible();
    expect(screen.getByText("24.8%")).toBeVisible();
    expect(screen.getByText("48.2%")).toBeVisible();
  });

  /**
   * GIVEN a market the provider has graded and measured
   * WHEN the section is rendered and nothing is hovered, tapped or focused
   * THEN the hit rate is already inside the chip, unprinted but readable aloud
   */
  it("states the hit rate without waiting for an interaction", () => {
    const container = renderSection(FULL_TIME_RESULT);

    const hitRate = screen.getByText(HIT_RATE_LABEL);

    expect(chipOf(container)).toContainElement(hitRate);
    expect(hitRate).toHaveClass("sr-only");
  });

  /**
   * GIVEN a grade whose hit rate is not printed in the layout
   * WHEN the chip takes focus, which is the pointerless way to reach it
   * THEN the tooltip shows the number and the chip is described by it
   */
  it("shows the hit rate to a sighted reader from the grade chip", async () => {
    const container = renderSection(FULL_TIME_RESULT);
    const chip = chipOf(container);

    expect(chip).toHaveAttribute("tabindex", "0");
    expect(chip).toHaveAttribute("data-state", "closed");

    fireEvent.focus(chip);

    await waitFor(() => {
      expect(screen.getByRole("tooltip")).toHaveTextContent(HIT_RATE_LABEL);
    });

    expect(chip).toHaveAttribute("aria-describedby");
  });

  /**
   * GIVEN a graded market carrying no measured hit rate behind the grade
   * WHEN the section is rendered
   * THEN the grade stands alone, with no tooltip, tab stop or hidden number
   */
  it("states a graded market the provider has not measured", () => {
    const container = renderSection(UNMEASURED_FIRST_HALF);
    const chip = chipOf(container);

    expect(chip).toHaveTextContent("Medium reliability");
    expect(chip).not.toHaveAttribute("tabindex");
    expect(chip).not.toHaveAttribute("data-state");
    expect(screen.queryByText(/hit rate/i)).not.toBeInTheDocument();
  });

  /**
   * GIVEN a market the provider publishes no predictability row for
   * WHEN the section is rendered
   * THEN it says so, rather than borrowing a grade it was never given
   */
  it("states an ungraded market as ungraded", () => {
    renderSection(DOUBLE_CHANCE);

    expect(screen.getByText("Reliability not graded")).toBeVisible();

    expect(
      screen.queryByText(/^(Poor|Medium|Good|High) reliability$/),
    ).not.toBeInTheDocument();
  });

  /**
   * GIVEN an ungraded market, whose chip has no hit rate to reveal
   * WHEN the section is rendered
   * THEN its chip is not a tooltip trigger and takes no place in the tab order
   */
  it("leaves an ungraded chip out of the tab order", () => {
    const chip = chipOf(renderSection(DOUBLE_CHANCE));

    expect(chip).not.toHaveAttribute("tabindex");
    expect(chip).not.toHaveAttribute("data-state");
  });

  /**
   * GIVEN double chance, whose selections are named as the pairs they cover
   * WHEN the section is rendered
   * THEN the pairs name themselves and no notice explains the overlap
   */
  it("names an overlapping market's selections as pairs", () => {
    renderSection(DOUBLE_CHANCE);

    expect(screen.getByText("LIV or draw")).toBeVisible();
    expect(screen.getByText("LIV or NFO")).toBeVisible();
    expect(screen.queryByText(/overlap/i)).not.toBeInTheDocument();
  });
});
