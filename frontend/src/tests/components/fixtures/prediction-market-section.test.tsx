import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

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

const OVERLAP_NOTICE =
  "These selections overlap, so they sum to about 200% rather than 100%.";

describe("PredictionMarketSection", () => {
  /**
   * GIVEN a market the provider grades and every selection it published
   * WHEN the section is rendered
   * THEN each selection carries its own label and percentage as readable text
   */
  it("states every selection and its probability in words", () => {
    render(<PredictionMarketSection market={FULL_TIME_RESULT} sides={SIDES} />);

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
   * THEN the grade and the historical hit rate are both stated
   */
  it("states a graded market's grade and hit rate", () => {
    render(<PredictionMarketSection market={FULL_TIME_RESULT} sides={SIDES} />);

    expect(screen.getByText("Good reliability")).toBeVisible();
    expect(screen.getByText("55% hit rate")).toBeVisible();
  });

  /**
   * GIVEN a market the provider publishes no predictability row for
   * WHEN the section is rendered
   * THEN it says so, rather than borrowing a grade it was never given
   */
  it("states an ungraded market as ungraded", () => {
    render(<PredictionMarketSection market={DOUBLE_CHANCE} sides={SIDES} />);

    expect(screen.getByText("Reliability not graded")).toBeVisible();

    expect(
      screen.queryByText(/^(Poor|Medium|Good|High) reliability$/),
    ).not.toBeInTheDocument();

    expect(screen.queryByText(/hit rate/)).not.toBeInTheDocument();
  });

  /**
   * GIVEN double chance, whose three selections each cover two results
   * WHEN the section is rendered
   * THEN it states that they overlap, so summing past 100 is not a defect
   */
  it("states that an overlapping market's selections overlap", () => {
    render(<PredictionMarketSection market={DOUBLE_CHANCE} sides={SIDES} />);

    expect(screen.getByText(OVERLAP_NOTICE)).toBeVisible();
    expect(screen.getByText("LIV or draw")).toBeVisible();
  });

  /**
   * GIVEN a market whose selections are mutually exclusive
   * WHEN the section is rendered
   * THEN no overlap notice is shown, because the numbers already sum to 100
   */
  it("says nothing about overlap for an exclusive market", () => {
    render(<PredictionMarketSection market={FULL_TIME_RESULT} sides={SIDES} />);

    expect(screen.queryByText(OVERLAP_NOTICE)).not.toBeInTheDocument();
  });

  /**
   * GIVEN a market whose likeliest selection is the away win at 48.18%
   * WHEN the section is rendered
   * THEN every bar's marker stands at that maximum, not at its own value
   */
  it("marks every bar with the market's own maximum", () => {
    const { container } = render(
      <PredictionMarketSection market={FULL_TIME_RESULT} sides={SIDES} />,
    );

    const markers = Array.from(
      container.querySelectorAll<HTMLElement>(
        '[data-slot="probability-marker"]',
      ),
    );

    expect(markers.map((marker) => marker.style.left)).toEqual([
      "48.18%",
      "48.18%",
      "48.18%",
    ]);
  });
});
