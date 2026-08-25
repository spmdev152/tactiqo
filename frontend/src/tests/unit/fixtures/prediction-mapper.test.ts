import { describe, expect, it } from "vitest";

import { toFixturePredictions } from "@/features/fixtures/mappers/prediction";

const FULLTIME_RESULT_PAYLOAD = {
  market: "fulltime_result",
  reliability: "medium",
  hit_ratio: 0.5,
  selections: [
    { selection: "home", probability: 26.96 },
    { selection: "draw", probability: 24.82 },
    { selection: "away", probability: 48.18 },
  ],
};

const DOUBLE_CHANCE_PAYLOAD = {
  market: "double_chance",
  reliability: null,
  hit_ratio: null,
  selections: [
    { selection: "home_or_draw", probability: 51.78 },
    { selection: "home_or_away", probability: 75.14 },
    { selection: "draw_or_away", probability: 73 },
  ],
};

const PREDICTIONS_PAYLOAD = {
  fixture_id: 41,
  synchronized_at: "2026-08-25T20:00:00Z",
  markets: [FULLTIME_RESULT_PAYLOAD, DOUBLE_CHANCE_PAYLOAD],
};

describe("toFixturePredictions", () => {
  /**
   * GIVEN a predictions payload in the published wire shape
   * WHEN it is normalized for the product
   * THEN the stamp, the grades and every selection reach the product contract
   */
  it("normalizes a predictions payload", () => {
    expect(toFixturePredictions(PREDICTIONS_PAYLOAD)).toEqual({
      loaded: true,
      predictions: {
        fixtureId: 41,
        synchronizedAt: new Date("2026-08-25T20:00:00Z"),
        markets: [
          {
            market: "fulltime_result",
            reliability: "medium",
            hitRatio: 0.5,
            selections: [
              { selection: "home", probability: 26.96 },
              { selection: "draw", probability: 24.82 },
              { selection: "away", probability: 48.18 },
            ],
          },
          {
            market: "double_chance",
            reliability: null,
            hitRatio: null,
            selections: [
              { selection: "home_or_draw", probability: 51.78 },
              { selection: "home_or_away", probability: 75.14 },
              { selection: "draw_or_away", probability: 73 },
            ],
          },
        ],
      },
    });
  });

  /**
   * GIVEN a market the platform does not publish
   * WHEN the payload is normalized for the product
   * THEN it is refused rather than carried as a market nothing can label
   */
  it("refuses a market outside the published vocabulary", () => {
    const result = toFixturePredictions({
      ...PREDICTIONS_PAYLOAD,
      markets: [{ ...FULLTIME_RESULT_PAYLOAD, market: "anytime_goalscorer" }],
    });

    expect(result).toEqual({
      loaded: false,
      reason: expect.stringContaining("predictions contract"),
    });
  });

  /**
   * GIVEN a fixture the provider's model has not reached yet
   * WHEN the payload is normalized for the product
   * THEN it loads with no stamp and no markets rather than as a failure
   */
  it("separates a fixture with no predictions from a failure", () => {
    expect(
      toFixturePredictions({
        fixture_id: 41,
        synchronized_at: null,
        markets: [],
      }),
    ).toEqual({
      loaded: true,
      predictions: { fixtureId: 41, synchronizedAt: null, markets: [] },
    });
  });

  /**
   * GIVEN a payload the backend already ordered by market and by selection
   * WHEN it is normalized for the product
   * THEN both orders survive instead of being re-derived
   */
  it("preserves the order the backend sent", () => {
    const result = toFixturePredictions(PREDICTIONS_PAYLOAD);

    expect(result.loaded).toBe(true);

    expect(
      result.loaded ? result.predictions.markets.map((one) => one.market) : [],
    ).toEqual(["fulltime_result", "double_chance"]);

    expect(
      result.loaded
        ? result.predictions.markets[0].selections.map((one) => one.selection)
        : [],
    ).toEqual(["home", "draw", "away"]);
  });

  /**
   * GIVEN payloads that are not one fixture's predictions
   * WHEN they are normalized for the product
   * THEN each becomes the unavailable branch instead of empty predictions
   */
  it("reports a payload that does not match the contract", () => {
    expect(toFixturePredictions(undefined).loaded).toBe(false);
    expect(toFixturePredictions([PREDICTIONS_PAYLOAD]).loaded).toBe(false);
  });
});
