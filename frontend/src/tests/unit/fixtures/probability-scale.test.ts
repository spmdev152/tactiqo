import { describe, expect, it } from "vitest";

import { resolveProbabilityFill } from "@/features/fixtures/domain/probability-scale";

const LOW_TOKEN = "--probability-low";

const MID_TOKEN = "--probability-mid";

const HIGH_TOKEN = "--probability-high";

describe("resolveProbabilityFill", () => {
  /**
   * GIVEN a probability of zero
   * WHEN its fill is resolved
   * THEN it sits at the very start of the low half of the ramp
   */
  it("puts an impossible outcome at the start of the low half", () => {
    expect(resolveProbabilityFill(0)).toEqual({
      from: LOW_TOKEN,
      to: MID_TOKEN,
      blend: "0%",
      width: "0%",
    });
  });

  /**
   * GIVEN a coin-flip probability
   * WHEN its fill is resolved
   * THEN it lands exactly on the midpoint colour rather than between two
   */
  it("puts a coin flip exactly on the midpoint", () => {
    expect(resolveProbabilityFill(50)).toEqual({
      from: MID_TOKEN,
      to: HIGH_TOKEN,
      blend: "0%",
      width: "50%",
    });
  });

  /**
   * GIVEN a certain outcome
   * WHEN its fill is resolved
   * THEN it sits at the very end of the high half of the ramp
   */
  it("puts a certainty at the end of the high half", () => {
    expect(resolveProbabilityFill(100)).toEqual({
      from: MID_TOKEN,
      to: HIGH_TOKEN,
      blend: "100%",
      width: "100%",
    });
  });

  /**
   * GIVEN two probabilities either side of the midpoint
   * WHEN their fills are resolved
   * THEN each reads from its own half of the ramp rather than from one gradient
   */
  it("chooses the half of the ramp the probability belongs to", () => {
    expect(resolveProbabilityFill(49.9)).toEqual({
      from: LOW_TOKEN,
      to: MID_TOKEN,
      blend: "99.8%",
      width: "49.9%",
    });

    expect(resolveProbabilityFill(50.1)).toEqual({
      from: MID_TOKEN,
      to: HIGH_TOKEN,
      blend: "0.2%",
      width: "50.1%",
    });
  });

  /**
   * GIVEN probabilities outside the range the API contract promises
   * WHEN their fills are resolved
   * THEN the width is clamped with the blend, not left for the caller to trust
   */
  it("clamps a probability outside the contract to the ends of the ramp", () => {
    expect(resolveProbabilityFill(150)).toEqual({
      from: MID_TOKEN,
      to: HIGH_TOKEN,
      blend: "100%",
      width: "100%",
    });

    expect(resolveProbabilityFill(-20)).toEqual({
      from: LOW_TOKEN,
      to: MID_TOKEN,
      blend: "0%",
      width: "0%",
    });
  });

  /**
   * GIVEN a value with no position on the ramp at all
   * WHEN its fill is resolved
   * THEN it reads as an empty bar rather than as a width the style engine drops
   */
  it("reads a value that is not a number as an empty bar", () => {
    expect(resolveProbabilityFill(Number.NaN)).toEqual({
      from: LOW_TOKEN,
      to: MID_TOKEN,
      blend: "0%",
      width: "0%",
    });

    expect(resolveProbabilityFill(Number.POSITIVE_INFINITY).width).toBe("0%");
  });

  /**
   * GIVEN a probability whose doubled value carries more than two decimals
   * WHEN its fill is resolved
   * THEN the blend is rounded rather than emitted as binary floating-point noise
   */
  it("rounds the blend to at most two decimals", () => {
    expect(resolveProbabilityFill(12.3456).blend).toBe("24.69%");
    expect(resolveProbabilityFill(63.457).blend).toBe("26.91%");
    expect(resolveProbabilityFill(26.96).blend).toBe("53.92%");
  });
});
