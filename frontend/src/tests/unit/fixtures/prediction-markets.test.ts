import { describe, expect, it } from "vitest";

import {
  isExclusiveMarket,
  marketLabel,
  PREDICTION_MARKETS,
  PREDICTION_SELECTIONS,
  type PredictionSides,
  selectionLabel,
} from "@/features/fixtures/domain/prediction-markets";
import type { FixtureTeam } from "@/features/fixtures/types/fixture";

const LIVERPOOL: FixtureTeam = {
  id: 3,
  name: "Liverpool",
  shortCode: "LIV",
  crestUrl: "",
};

const ARSENAL: FixtureTeam = {
  id: 5,
  name: "Arsenal",
  shortCode: "ARS",
  crestUrl: "",
};

const SIDES: PredictionSides = { home: LIVERPOOL, away: ARSENAL };

describe("marketLabel", () => {
  /**
   * GIVEN every market the platform publishes
   * WHEN each is named for the interface
   * THEN none falls back to its wire value or to nothing at all
   */
  it("names every published market", () => {
    for (const market of PREDICTION_MARKETS) {
      expect(marketLabel(market)).not.toBe("");
      expect(marketLabel(market)).not.toBe(market);
    }
  });
});

describe("selectionLabel", () => {
  /**
   * GIVEN every selection the platform publishes
   * WHEN each is named inside the market it is most at home in
   * THEN none falls back to its wire value or to nothing at all
   */
  it("names every published selection", () => {
    for (const selection of PREDICTION_SELECTIONS) {
      expect(selectionLabel("fulltime_result", selection, SIDES)).not.toBe("");

      expect(selectionLabel("fulltime_result", selection, SIDES)).not.toBe(
        selection,
      );
    }
  });

  /**
   * GIVEN the same stored yes/no selections in a goal-line and a yes/no market
   * WHEN each is named for the interface
   * THEN the goal line reaches the label rather than a bare Yes and No
   */
  it("names a yes/no selection differently per market", () => {
    expect(selectionLabel("over_under_2_5", "yes", SIDES)).toBe("Over 2.5");
    expect(selectionLabel("over_under_2_5", "no", SIDES)).toBe("Under 2.5");
    expect(selectionLabel("over_under_1_5", "yes", SIDES)).toBe("Over 1.5");
    expect(selectionLabel("over_under_4_5", "no", SIDES)).toBe("Under 4.5");
    expect(selectionLabel("both_teams_to_score", "yes", SIDES)).toBe("Yes");
    expect(selectionLabel("both_teams_to_score", "no", SIDES)).toBe("No");
  });

  /**
   * GIVEN selections naming one or two of a fixture's three outcomes
   * WHEN each is named for the interface
   * THEN the clubs playing reach the label instead of the words home and away
   */
  it("names the clubs a selection stands for", () => {
    expect(selectionLabel("fulltime_result", "home", SIDES)).toBe("LIV");
    expect(selectionLabel("fulltime_result", "draw", SIDES)).toBe("Draw");
    expect(selectionLabel("fulltime_result", "away", SIDES)).toBe("ARS");

    expect(selectionLabel("double_chance", "home_or_draw", SIDES)).toBe(
      "LIV or draw",
    );

    expect(selectionLabel("double_chance", "home_or_away", SIDES)).toBe(
      "LIV or ARS",
    );

    expect(selectionLabel("double_chance", "draw_or_away", SIDES)).toBe(
      "Draw or ARS",
    );
  });

  /**
   * GIVEN a selection naming a half-time and a full-time outcome at once
   * WHEN it is named for the interface
   * THEN both outcomes are resolved into one scannable pair
   */
  it("names both halves of a half-time/full-time selection", () => {
    expect(selectionLabel("half_time_full_time", "home_then_away", SIDES)).toBe(
      "LIV / ARS",
    );

    expect(selectionLabel("half_time_full_time", "draw_then_draw", SIDES)).toBe(
      "Draw / Draw",
    );
  });

  /**
   * GIVEN selections outside the three ordinary outcomes
   * WHEN each is named for the interface
   * THEN the copy reads as a scoreline or as a stated absence of goals
   */
  it("names a scoreline and a goalless first scorer", () => {
    expect(selectionLabel("correct_score", "score_1_2", SIDES)).toBe("1-2");
    expect(selectionLabel("correct_score", "score_0_0", SIDES)).toBe("0-0");

    expect(selectionLabel("team_to_score_first", "no_goal", SIDES)).toBe(
      "No goal",
    );
  });

  /**
   * GIVEN a club with no published short code
   * WHEN a selection naming that club is named for the interface
   * THEN the full club name is used rather than an empty label
   */
  it("falls back to the full name of a club with no short code", () => {
    const sides: PredictionSides = {
      home: { ...LIVERPOOL, shortCode: "" },
      away: ARSENAL,
    };

    expect(selectionLabel("fulltime_result", "home", sides)).toBe("Liverpool");

    expect(selectionLabel("double_chance", "home_or_draw", sides)).toBe(
      "Liverpool or draw",
    );
  });
});

describe("isExclusiveMarket", () => {
  /**
   * GIVEN every market the platform publishes
   * WHEN each is classified by whether its selections overlap
   * THEN only double chance, whose selections sum to roughly 200, is not exclusive
   */
  it("reports only double chance as non-exclusive", () => {
    const overlapping = PREDICTION_MARKETS.filter(
      (market) => !isExclusiveMarket(market),
    );

    expect(overlapping).toEqual(["double_chance"]);
  });
});
