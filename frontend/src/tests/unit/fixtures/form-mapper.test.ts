import { describe, expect, it } from "vitest";

import { toFixtureForm } from "@/features/fixtures/mappers/form";

/**
 * One metric's entry as the wire carries it.
 */
interface MetricPayload {
  /** Metric the figure belongs to, possibly one the frontend has no name for. */
  readonly metric: string;

  /** The team's own figure. */
  readonly value: number;

  /** What the opposition recorded, `null` for a metric with no opposite. */
  readonly opposed_value: number | null;
}

/**
 * One sample's entry as the wire carries it.
 */
interface SamplePayload {
  /** Window the sample was drawn from. */
  readonly range: string;

  /** Scope the sample was drawn under. */
  readonly scope: string;

  /** Matches the sample counted. */
  readonly matches_counted: number;

  /** The sample's figures, typed loosely so a malformed one needs no cast. */
  readonly metrics: readonly unknown[];
}

/**
 * Builds one metric's wire entry, defaulting the opposing figure to absent.
 *
 * @param metric - Metric the figure belongs to.
 * @param value - The team's own figure.
 * @param opposed - What the opposition recorded, absent by default.
 * @returns One metric entry in the wire shape.
 */
function metricPayload(
  metric: string,
  value: number,
  opposed: number | null = null,
): MetricPayload {
  return { metric, value, opposed_value: opposed };
}

/**
 * Builds one sample's wire entry.
 *
 * @param range - Window the sample was drawn from.
 * @param scope - Scope the sample was drawn under.
 * @param matches - Matches the sample counted.
 * @param metrics - The sample's figures.
 * @returns One sample in the wire shape.
 */
function samplePayload(
  range: string,
  scope: string,
  matches: number,
  metrics: readonly unknown[],
): SamplePayload {
  return {
    range,
    scope,
    matches_counted: matches,
    metrics: [...metrics],
  };
}

const LAST_3_OVERALL = samplePayload("last_3", "overall", 3, [
  metricPayload("win_share", 66.67),
  metricPayload("goals", 2.33, 0.67),
  metricPayload("possession", 54.2),
]);

const SEASON_VENUE = samplePayload("season", "venue", 19, [
  metricPayload("red_cards", 0.05),
]);

const FORM_PAYLOAD = {
  fixture_id: 41,
  synchronized_at: "2026-08-25T20:00:00Z",
  home: { team_id: 3, samples: [LAST_3_OVERALL, SEASON_VENUE] },
  away: { team_id: 4, samples: [SEASON_VENUE] },
  families: [
    { family: "result", metrics: ["win_share", "goals"] },
    { family: "discipline", metrics: ["red_cards"] },
  ],
};

describe("toFixtureForm", () => {
  /**
   * GIVEN a form payload in the published wire shape
   * WHEN it is normalized for the product
   * THEN the stamp, both sides, every sample and the families reach the product
   */
  it("normalizes a form payload", () => {
    expect(toFixtureForm(FORM_PAYLOAD)).toEqual({
      loaded: true,
      form: {
        fixtureId: 41,
        synchronizedAt: new Date("2026-08-25T20:00:00Z"),
        home: {
          teamId: 3,
          samples: [
            {
              range: "last_3",
              scope: "overall",
              matchesCounted: 3,
              metrics: [
                { metric: "win_share", value: 66.67, opposedValue: null },
                { metric: "goals", value: 2.33, opposedValue: 0.67 },
                { metric: "possession", value: 54.2, opposedValue: null },
              ],
            },
            {
              range: "season",
              scope: "venue",
              matchesCounted: 19,
              metrics: [
                { metric: "red_cards", value: 0.05, opposedValue: null },
              ],
            },
          ],
        },
        away: {
          teamId: 4,
          samples: [
            {
              range: "season",
              scope: "venue",
              matchesCounted: 19,
              metrics: [
                { metric: "red_cards", value: 0.05, opposedValue: null },
              ],
            },
          ],
        },
        families: [
          { family: "result", metrics: ["win_share", "goals"] },
          { family: "discipline", metrics: ["red_cards"] },
        ],
      },
    });
  });

  /**
   * GIVEN a payload whose samples and metrics are not in vocabulary order
   * WHEN it is normalized for the product
   * THEN the API's order survives instead of being re-derived from the tuples
   */
  it("preserves the order the backend sent", () => {
    const result = toFixtureForm({
      ...FORM_PAYLOAD,
      home: { team_id: 3, samples: [SEASON_VENUE, LAST_3_OVERALL] },
    });

    expect(result.loaded).toBe(true);

    expect(
      result.loaded ? result.form.home.samples.map((one) => one.range) : [],
    ).toEqual(["season", "last_3"]);

    expect(
      result.loaded
        ? result.form.home.samples[1].metrics.map((one) => one.metric)
        : [],
    ).toEqual(["win_share", "goals", "possession"]);
  });

  /**
   * GIVEN a backend publishing one figure ahead of the frontend's vocabulary
   * WHEN the payload is normalized for the product
   * THEN that figure alone is dropped and the rest of the sample still loads
   */
  it("drops a metric outside the published vocabulary", () => {
    const result = toFixtureForm({
      ...FORM_PAYLOAD,
      home: {
        team_id: 3,
        samples: [
          samplePayload("last_3", "overall", 3, [
            metricPayload("win_share", 66.67),
            metricPayload("expected_goals", 1.42),
            metricPayload("goals", 2.33, 0.67),
          ]),
        ],
      },
    });

    expect(result.loaded).toBe(true);

    expect(
      result.loaded
        ? result.form.home.samples[0].metrics.map((one) => one.metric)
        : [],
    ).toEqual(["win_share", "goals"]);
  });

  /**
   * GIVEN a family, and a family's metric, the frontend has no name for
   * WHEN the payload is normalized for the product
   * THEN both are dropped and every group the frontend understands survives
   */
  it("drops a family and a family metric outside the vocabulary", () => {
    const result = toFixtureForm({
      ...FORM_PAYLOAD,
      families: [
        { family: "result", metrics: ["win_share", "expected_goals", "goals"] },
        { family: "set_pieces", metrics: ["corners"] },
      ],
    });

    expect(result.loaded).toBe(true);

    expect(result.loaded ? result.form.families : []).toEqual([
      { family: "result", metrics: ["win_share", "goals"] },
    ]);
  });

  /**
   * GIVEN a backend publishing a window the frontend's vocabulary has not got
   * WHEN the payload is normalized for the product
   * THEN that sample is dropped rather than taking the other windows with it
   */
  it("drops a window outside the published vocabulary", () => {
    const result = toFixtureForm({
      ...FORM_PAYLOAD,
      home: {
        team_id: 3,
        samples: [
          LAST_3_OVERALL,
          samplePayload("last_10", "overall", 10, [
            metricPayload("win_share", 50),
          ]),
        ],
      },
    });

    expect(result.loaded).toBe(true);

    expect(
      result.loaded ? result.form.home.samples.map((one) => one.range) : [],
    ).toEqual(["last_3"]);
  });

  /**
   * GIVEN a sample whose shape has moved rather than whose vocabulary has grown
   * WHEN the payload is normalized for the product
   * THEN it is refused, because an emptied panel would read as an unplayed side
   */
  it("refuses a sample whose contract has structurally changed", () => {
    expect(
      toFixtureForm({
        ...FORM_PAYLOAD,
        home: {
          team_id: 3,
          samples: [
            {
              range: "last_3",
              scope: "overall",
              matches: 3,
              metrics: LAST_3_OVERALL.metrics,
            },
          ],
        },
      }),
    ).toEqual({
      loaded: false,
      reason: expect.stringContaining("form contract"),
    });
  });

  /**
   * GIVEN a figure whose own name is published but whose fields have moved
   * WHEN the payload is normalized for the product
   * THEN it is refused rather than dropped, because only a name may be unknown
   */
  it("refuses a known metric that is malformed", () => {
    expect(
      toFixtureForm({
        ...FORM_PAYLOAD,
        home: {
          team_id: 3,
          samples: [
            samplePayload("last_3", "overall", 3, [
              { metric: "goals", value: 2.33 },
            ]),
          ],
        },
      }).loaded,
    ).toBe(false);
  });

  /**
   * GIVEN a platform-computed share above a hundred and an average below nought
   * WHEN each payload is normalized for the product
   * THEN both are refused, because each means the contract itself has moved
   */
  it("refuses figures outside the bounds the contract states", () => {
    expect(
      toFixtureForm({
        ...FORM_PAYLOAD,
        home: {
          team_id: 3,
          samples: [
            samplePayload("last_3", "overall", 3, [
              metricPayload("possession", 120),
            ]),
          ],
        },
      }).loaded,
    ).toBe(false);

    expect(
      toFixtureForm({
        ...FORM_PAYLOAD,
        home: {
          team_id: 3,
          samples: [
            samplePayload("last_3", "overall", 3, [metricPayload("goals", -1)]),
          ],
        },
      }).loaded,
    ).toBe(false);
  });

  /**
   * GIVEN an average above a hundred, which is ordinary for attempted passes
   * WHEN the payload is normalized for the product
   * THEN it is accepted, because an average has no ceiling to exceed
   */
  it("accepts an average above the share ceiling", () => {
    const result = toFixtureForm({
      ...FORM_PAYLOAD,
      home: {
        team_id: 3,
        samples: [
          samplePayload("last_3", "overall", 3, [
            metricPayload("passes", 512.33),
          ]),
        ],
      },
    });

    expect(result.loaded).toBe(true);

    expect(
      result.loaded ? result.form.home.samples[0].metrics[0].value : 0,
    ).toBe(512.33);
  });

  /**
   * GIVEN a corrupt provider row whose completions exceed the attempts
   * WHEN the payload is normalized for the product
   * THEN the odd ratio survives, rather than blanking every other figure with it
   */
  it("keeps a provider ratio above a hundred instead of refusing the payload", () => {
    const result = toFixtureForm({
      ...FORM_PAYLOAD,
      home: {
        team_id: 3,
        samples: [
          samplePayload("last_3", "overall", 3, [
            metricPayload("pass_accuracy", 103.4),
            metricPayload("goals", 2.33, 0.67),
          ]),
        ],
      },
    });

    expect(result.loaded).toBe(true);

    expect(
      result.loaded
        ? result.form.home.samples[0].metrics.map((one) => one.value)
        : [],
    ).toEqual([103.4, 2.33]);
  });

  /**
   * GIVEN a synchronization stamp naming no offset from UTC
   * WHEN the payload is normalized for the product
   * THEN it is refused, rather than read in whichever zone the runtime sits in
   */
  it("refuses a synchronization stamp with no offset", () => {
    expect(
      toFixtureForm({
        ...FORM_PAYLOAD,
        synchronized_at: "2026-08-25T20:00:00",
      }).loaded,
    ).toBe(false);
  });

  /**
   * GIVEN two sides with no completed match behind either of them
   * WHEN the payload is normalized for the product
   * THEN it loads with no stamp and empty samples rather than as a failure
   */
  it("separates a fixture with no matches played from a failure", () => {
    expect(
      toFixtureForm({
        fixture_id: 41,
        synchronized_at: null,
        home: { team_id: 3, samples: [] },
        away: { team_id: 4, samples: [] },
        families: [],
      }),
    ).toEqual({
      loaded: true,
      form: {
        fixtureId: 41,
        synchronizedAt: null,
        home: { teamId: 3, samples: [] },
        away: { teamId: 4, samples: [] },
        families: [],
      },
    });
  });

  /**
   * GIVEN payloads that are not one fixture's form
   * WHEN they are normalized for the product
   * THEN each becomes the unavailable branch instead of an empty panel
   */
  it("reports a payload that does not match the contract", () => {
    expect(toFixtureForm(undefined).loaded).toBe(false);
    expect(toFixtureForm([FORM_PAYLOAD]).loaded).toBe(false);
    expect(toFixtureForm({ ...FORM_PAYLOAD, home: undefined }).loaded).toBe(
      false,
    );
  });
});
