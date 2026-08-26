import { beforeEach, describe, expect, it, vi } from "vitest";

import { loadFixtureFormAction } from "@/features/fixtures/server/actions";
import type { FixtureFormResult } from "@/features/fixtures/types/form";

const { getFixtureForm } = vi.hoisted(() => ({
  getFixtureForm: vi.fn(),
}));

vi.mock("@/features/fixtures/server/get-fixture-form", () => ({
  getFixtureForm,
}));

const { getFixturePredictions } = vi.hoisted(() => ({
  getFixturePredictions: vi.fn(),
}));

vi.mock("@/features/fixtures/server/get-fixture-predictions", () => ({
  getFixturePredictions,
}));

const FIXTURE_ID = 41;

const READ_FORM: FixtureFormResult = {
  loaded: true,
  form: {
    fixtureId: FIXTURE_ID,
    synchronizedAt: null,
    home: { teamId: 3, samples: [] },
    away: { teamId: 4, samples: [] },
    families: [],
  },
};

const MALFORMED_PAYLOADS: readonly (readonly [string, unknown])[] = [
  ["no payload at all", undefined],
  ["an identifier of zero", 0],
  ["a negative identifier", -1],
  ["a fractional identifier", 1.5],
  ["the identifier as a string", "41"],
  ["the identifier inside an object", { fixtureId: FIXTURE_ID }],
];

describe("loadFixtureFormAction", () => {
  beforeEach(() => {
    getFixtureForm.mockReset();
    getFixturePredictions.mockReset();
    getFixtureForm.mockResolvedValue(READ_FORM);
  });

  /**
   * GIVEN a caller posting the identifier of a fixture it wants form for
   * WHEN the action runs
   * THEN the identifier reaches the reader once, as the number it validated
   */
  it("forwards a valid fixture identifier to the reader", async () => {
    await expect(loadFixtureFormAction(FIXTURE_ID)).resolves.toBe(READ_FORM);

    expect(getFixtureForm).toHaveBeenCalledExactlyOnceWith(FIXTURE_ID);
  });

  /**
   * GIVEN the bodies a public endpoint can be posted instead of an identifier
   * WHEN the action runs on each of them
   * THEN every one is refused before the reader is asked to fetch anything
   */
  it("refuses a payload that is not a fixture identifier", async () => {
    for (const [label, payload] of MALFORMED_PAYLOADS) {
      const result = await loadFixtureFormAction(payload);

      expect(result, label).toEqual({
        loaded: false,
        reason: expect.stringContaining("could not be read"),
      });
    }

    expect(getFixtureForm).not.toHaveBeenCalled();
  });

  /**
   * GIVEN two tabs whose reads are meant to be independent of each other
   * WHEN the form is asked for
   * THEN the predictions reader is never called on its behalf
   */
  it("reads the form without reading the probabilities", async () => {
    await loadFixtureFormAction(FIXTURE_ID);

    expect(getFixturePredictions).not.toHaveBeenCalled();
  });
});
