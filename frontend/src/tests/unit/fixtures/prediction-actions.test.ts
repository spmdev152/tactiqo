import { beforeEach, describe, expect, it, vi } from "vitest";

import { loadFixturePredictionsAction } from "@/features/fixtures/server/actions";
import type { FixturePredictionsResult } from "@/features/fixtures/types/prediction";

const { getFixturePredictions } = vi.hoisted(() => ({
  getFixturePredictions: vi.fn(),
}));

vi.mock("@/features/fixtures/server/get-fixture-predictions", () => ({
  getFixturePredictions,
}));

const FIXTURE_ID = 41;

const READ_PREDICTIONS: FixturePredictionsResult = {
  loaded: true,
  predictions: { fixtureId: FIXTURE_ID, synchronizedAt: null, markets: [] },
};

const MALFORMED_PAYLOADS: readonly (readonly [string, unknown])[] = [
  ["no payload at all", undefined],
  ["an identifier of zero", 0],
  ["a negative identifier", -1],
  ["a fractional identifier", 1.5],
  ["the identifier as a string", "41"],
  ["the identifier inside an object", { fixtureId: FIXTURE_ID }],
];

describe("loadFixturePredictionsAction", () => {
  beforeEach(() => {
    getFixturePredictions.mockReset();
    getFixturePredictions.mockResolvedValue(READ_PREDICTIONS);
  });

  /**
   * GIVEN a caller posting the identifier of a fixture it wants predictions for
   * WHEN the action runs
   * THEN the identifier reaches the reader once, as the number it validated
   */
  it("forwards a valid fixture identifier to the reader", async () => {
    await expect(loadFixturePredictionsAction(FIXTURE_ID)).resolves.toBe(
      READ_PREDICTIONS,
    );

    expect(getFixturePredictions).toHaveBeenCalledExactlyOnceWith(FIXTURE_ID);
  });

  /**
   * GIVEN the bodies a public endpoint can be posted instead of an identifier
   * WHEN the action runs on each of them
   * THEN every one is refused before the reader is asked to fetch anything
   */
  it("refuses a payload that is not a fixture identifier", async () => {
    for (const [label, payload] of MALFORMED_PAYLOADS) {
      const result = await loadFixturePredictionsAction(payload);

      expect(result, label).toEqual({
        loaded: false,
        reason: expect.stringContaining("could not be read"),
      });
    }

    expect(getFixturePredictions).not.toHaveBeenCalled();
  });
});
