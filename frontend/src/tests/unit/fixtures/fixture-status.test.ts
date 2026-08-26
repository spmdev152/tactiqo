import { describe, expect, it } from "vitest";

import {
  FIXTURE_STATUSES,
  hasKickedOff,
} from "@/features/fixtures/domain/fixture-status";

describe("fixture status vocabulary", () => {
  /**
   * GIVEN the five states the platform reports for a match
   * WHEN each is asked whether the match has kicked off
   * THEN exactly the two that were played answer yes, in vocabulary order
   */
  it("counts only a live or finished match as kicked off", () => {
    expect(FIXTURE_STATUSES.filter(hasKickedOff)).toEqual(["live", "finished"]);
  });

  /**
   * GIVEN a match whose published kick-off has passed without being played
   * WHEN it is asked whether the match has kicked off
   * THEN it answers no, because no football happened at that instant
   */
  it("refuses a postponed or cancelled match its passed kick-off", () => {
    expect(hasKickedOff("postponed")).toBe(false);
    expect(hasKickedOff("cancelled")).toBe(false);
  });
});
