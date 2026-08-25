import { describe, expect, it } from "vitest";

import {
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

describe("PREDICTION_MARKETS", () => {
  /**
   * GIVEN the vocabulary the wire schema validates against and the panel reads
   * WHEN the published markets are listed
   * THEN they are these eleven, in this order, until the API says otherwise
   */
  it("publishes the eleven markets the API promises, in its order", () => {
    expect(PREDICTION_MARKETS).toEqual([
      "fulltime_result",
      "double_chance",
      "both_teams_to_score",
      "over_under_1_5",
      "over_under_2_5",
      "over_under_3_5",
      "over_under_4_5",
      "team_to_score_first",
      "first_half_result",
      "half_time_full_time",
      "correct_score",
    ]);
  });
});

describe("PREDICTION_SELECTIONS", () => {
  /**
   * GIVEN the vocabulary every market's outcomes are decoded against
   * WHEN the published selections are listed
   * THEN they are these, so dropping one cannot pass as a contract change
   */
  it("publishes every outcome the API can send", () => {
    expect(PREDICTION_SELECTIONS).toEqual([
      "home",
      "draw",
      "away",
      "home_or_draw",
      "draw_or_away",
      "home_or_away",
      "no_goal",
      "yes",
      "no",
      "home_then_home",
      "home_then_draw",
      "home_then_away",
      "draw_then_home",
      "draw_then_draw",
      "draw_then_away",
      "away_then_home",
      "away_then_draw",
      "away_then_away",
      "score_0_0",
      "score_0_1",
      "score_0_2",
      "score_0_3",
      "score_1_0",
      "score_1_1",
      "score_1_2",
      "score_1_3",
      "score_2_0",
      "score_2_1",
      "score_2_2",
      "score_2_3",
      "score_3_0",
      "score_3_1",
      "score_3_2",
      "score_3_3",
      "any_other_home_win",
      "any_other_draw",
      "any_other_away_win",
    ]);
  });
});

describe("marketLabel", () => {
  /**
   * GIVEN the three markets a visitor recognizes first
   * WHEN each is named for the interface
   * THEN the copy is the market's own name rather than its wire value
   */
  it("names a market as the interface prints it", () => {
    expect(marketLabel("fulltime_result")).toBe("Full-time result");
    expect(marketLabel("over_under_2_5")).toBe("Over/under 2.5 goals");
    expect(marketLabel("half_time_full_time")).toBe("Half-time / full-time");
  });
});

describe("selectionLabel", () => {
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

  /**
   * GIVEN a club whose published short code and name are both padded
   * WHEN a selection naming that club is named for the interface
   * THEN both are trimmed, so neither can render as a label made of spaces
   */
  it("trims the name it falls back to as well as the short code", () => {
    const sides: PredictionSides = {
      home: { ...LIVERPOOL, name: "  Liverpool  ", shortCode: " " },
      away: ARSENAL,
    };

    expect(selectionLabel("fulltime_result", "home", sides)).toBe("Liverpool");

    expect(selectionLabel("half_time_full_time", "home_then_home", sides)).toBe(
      "Liverpool / Liverpool",
    );
  });
});
