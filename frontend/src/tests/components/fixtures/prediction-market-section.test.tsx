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

const HIT_RATE_SENTENCE =
  "Right on 55% of this market's predictions in this competition.";

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
 */
function renderSection(market: PredictionMarketProbabilities): void {
  render(
    <TooltipProvider>
      <PredictionMarketSection market={market} sides={SIDES} />
    </TooltipProvider>,
  );
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
   * WHEN the section is rendered
   * THEN the grade is stated and the hit rate behind it stays out of the layout
   */
  it("states the grade without printing the hit rate beside it", () => {
    renderSection(FULL_TIME_RESULT);

    expect(screen.getByText("Good reliability")).toBeVisible();
    expect(screen.queryByText(/hit rate/)).not.toBeInTheDocument();
    expect(screen.queryByText(HIT_RATE_SENTENCE)).not.toBeInTheDocument();
  });

  /**
   * GIVEN a grade whose hit rate is only reachable through its chip
   * WHEN the chip takes focus, which is the pointerless way to reach it
   * THEN the hit rate is revealed and the chip is described by it
   */
  it("reveals the hit rate from the grade chip", async () => {
    renderSection(FULL_TIME_RESULT);

    const chip = screen.getByText("Good reliability");

    expect(chip).toHaveAttribute("tabindex", "0");

    fireEvent.focus(chip);

    await waitFor(() => {
      expect(screen.getAllByText(HIT_RATE_SENTENCE)[0]).toBeInTheDocument();
    });

    expect(chip).toHaveAttribute("aria-describedby");
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
    renderSection(DOUBLE_CHANCE);

    const chip = screen.getByText("Reliability not graded");

    expect(chip).not.toHaveAttribute("tabindex");
    expect(chip).not.toHaveAttribute("data-slot", "tooltip-trigger");
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
