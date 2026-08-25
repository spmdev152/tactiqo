import { describe, expect, it } from "vitest";

import { toFixturePredictions } from "@/features/fixtures/mappers/prediction";

const FULLTIME_RESULT_PAYLOAD = {
  market: "fulltime_result",
  reliability: "medium",
  hit_ratio: 0.5,
  selections: [
    { selection: "away", probability: 48.18 },
    { selection: "home", probability: 26.96 },
    { selection: "draw", probability: 24.82 },
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

const UNKNOWN_MARKET_PAYLOAD = {
  market: "anytime_goalscorer",
  reliability: null,
  hit_ratio: null,
  selections: [{ selection: "player_142", probability: 31.5 }],
};

const PREDICTIONS_PAYLOAD = {
  fixture_id: 41,
  synchronized_at: "2026-08-25T20:00:00Z",
  markets: [DOUBLE_CHANCE_PAYLOAD, FULLTIME_RESULT_PAYLOAD],
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
            market: "double_chance",
            reliability: null,
            hitRatio: null,
            selections: [
              { selection: "home_or_draw", probability: 51.78 },
              { selection: "home_or_away", probability: 75.14 },
              { selection: "draw_or_away", probability: 73 },
            ],
          },
          {
            market: "fulltime_result",
            reliability: "medium",
            hitRatio: 0.5,
            selections: [
              { selection: "away", probability: 48.18 },
              { selection: "home", probability: 26.96 },
              { selection: "draw", probability: 24.82 },
            ],
          },
        ],
      },
    });
  });

  /**
   * GIVEN a payload whose markets and selections are not in vocabulary order
   * WHEN it is normalized for the product
   * THEN the API's order survives instead of being re-derived from the tuples
   */
  it("preserves the order the backend sent", () => {
    const result = toFixturePredictions(PREDICTIONS_PAYLOAD);

    expect(result.loaded).toBe(true);

    expect(
      result.loaded ? result.predictions.markets.map((one) => one.market) : [],
    ).toEqual(["double_chance", "fulltime_result"]);

    expect(
      result.loaded
        ? result.predictions.markets[1].selections.map((one) => one.selection)
        : [],
    ).toEqual(["away", "home", "draw"]);
  });

  /**
   * GIVEN a backend publishing one market ahead of the frontend's vocabulary
   * WHEN the payload is normalized for the product
   * THEN that market alone is dropped and the rest of the panel still loads
   */
  it("drops a market outside the published vocabulary", () => {
    const result = toFixturePredictions({
      ...PREDICTIONS_PAYLOAD,
      markets: [
        DOUBLE_CHANCE_PAYLOAD,
        UNKNOWN_MARKET_PAYLOAD,
        FULLTIME_RESULT_PAYLOAD,
      ],
    });

    expect(result.loaded).toBe(true);

    expect(
      result.loaded ? result.predictions.markets.map((one) => one.market) : [],
    ).toEqual(["double_chance", "fulltime_result"]);
  });

  /**
   * GIVEN a market carrying one outcome the frontend has no name for
   * WHEN the payload is normalized for the product
   * THEN the outcome is dropped and its market keeps every other row
   */
  it("drops a selection outside the published vocabulary", () => {
    const result = toFixturePredictions({
      ...PREDICTIONS_PAYLOAD,
      markets: [
        {
          ...FULLTIME_RESULT_PAYLOAD,
          selections: [
            ...FULLTIME_RESULT_PAYLOAD.selections,
            { selection: "home_by_two", probability: 12.5 },
          ],
        },
      ],
    });

    expect(
      result.loaded
        ? result.predictions.markets[0].selections.map((one) => one.selection)
        : [],
    ).toEqual(["away", "home", "draw"]);
  });

  /**
   * GIVEN a market whose shape has moved rather than whose vocabulary has grown
   * WHEN the payload is normalized for the product
   * THEN it is refused, because an emptied panel would read as an unrun model
   */
  it("refuses a market whose contract has structurally changed", () => {
    expect(
      toFixturePredictions({
        ...PREDICTIONS_PAYLOAD,
        markets: [
          {
            market: "fulltime_result",
            reliability: "medium",
            hit_rate: 0.5,
            selections: FULLTIME_RESULT_PAYLOAD.selections,
          },
        ],
      }),
    ).toEqual({
      loaded: false,
      reason: expect.stringContaining("predictions contract"),
    });
  });

  /**
   * GIVEN numbers outside the bounds the wire contract states
   * WHEN each payload is normalized for the product
   * THEN both are refused rather than carried into a bar or a grade
   */
  it("refuses a probability and a hit ratio out of bounds", () => {
    expect(
      toFixturePredictions({
        ...PREDICTIONS_PAYLOAD,
        markets: [
          {
            ...FULLTIME_RESULT_PAYLOAD,
            selections: [{ selection: "home", probability: 120 }],
          },
        ],
      }).loaded,
    ).toBe(false);

    expect(
      toFixturePredictions({
        ...PREDICTIONS_PAYLOAD,
        markets: [{ ...FULLTIME_RESULT_PAYLOAD, hit_ratio: 1.4 }],
      }).loaded,
    ).toBe(false);
  });

  /**
   * GIVEN a synchronization stamp naming no offset from UTC
   * WHEN the payload is normalized for the product
   * THEN it is refused, rather than read in whichever zone the runtime sits in
   */
  it("refuses a synchronization stamp with no offset", () => {
    expect(
      toFixturePredictions({
        ...PREDICTIONS_PAYLOAD,
        synchronized_at: "2026-08-25T20:00:00",
      }).loaded,
    ).toBe(false);
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
   * GIVEN payloads that are not one fixture's predictions
   * WHEN they are normalized for the product
   * THEN each becomes the unavailable branch instead of empty predictions
   */
  it("reports a payload that does not match the contract", () => {
    expect(toFixturePredictions(undefined).loaded).toBe(false);
    expect(toFixturePredictions([PREDICTIONS_PAYLOAD]).loaded).toBe(false);
  });
});
