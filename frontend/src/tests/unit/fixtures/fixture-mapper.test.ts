import { describe, expect, it } from "vitest";

import { toFixtures } from "@/features/fixtures/mappers/fixture";

const LEAGUE_PAYLOAD = {
  id: 1,
  name: "Premier League",
  short_code: "UK PL",
  logo_url: "https://cdn.sportmonks.com/images/soccer/leagues/8.png",
  country_name: "England",
  country_flag_url:
    "https://cdn.sportmonks.com/images/countries/png/short/en.png",
};

const FIXTURE_PAYLOAD = {
  id: 12,
  kickoff_at: "2026-08-29T11:30:00Z",
  status: "scheduled",
  home_goals: null,
  away_goals: null,
  league: LEAGUE_PAYLOAD,
  home_team: {
    id: 3,
    name: "Liverpool",
    short_code: "LIV",
    crest_url: "https://cdn.sportmonks.com/images/soccer/teams/3.png",
  },
  away_team: {
    id: 4,
    name: "Nottingham Forest",
    short_code: "NFO",
    crest_url: "",
  },
  has_predictions: false,
};

describe("toFixtures", () => {
  /**
   * GIVEN a fixtures payload in the published wire shape
   * WHEN it is normalized for the product
   * THEN both sides, the competition, the kick-off and the state are mapped
   */
  it("normalizes a fixtures payload", () => {
    expect(toFixtures([FIXTURE_PAYLOAD])).toEqual({
      loaded: true,
      fixtures: [
        {
          id: 12,
          kickoffAt: new Date("2026-08-29T11:30:00Z"),
          status: "scheduled",
          score: null,
          league: expect.objectContaining({ id: 1, name: "Premier League" }),
          homeTeam: {
            id: 3,
            name: "Liverpool",
            shortCode: "LIV",
            crestUrl: "https://cdn.sportmonks.com/images/soccer/teams/3.png",
          },
          awayTeam: {
            id: 4,
            name: "Nottingham Forest",
            shortCode: "NFO",
            crestUrl: "",
          },
          hasPredictions: false,
        },
      ],
    });
  });

  /**
   * GIVEN a fixture the platform holds prediction probabilities for
   * WHEN it is normalized for the product
   * THEN the flag reaches the product contract as its own field
   */
  it("carries the prediction availability flag", () => {
    const result = toFixtures([{ ...FIXTURE_PAYLOAD, has_predictions: true }]);

    expect(result).toEqual({
      loaded: true,
      fixtures: [expect.objectContaining({ hasPredictions: true })],
    });
  });

  /**
   * GIVEN a kick-off expressed with a numeric offset rather than with Z
   * WHEN it is normalized for the product
   * THEN the same absolute instant is produced
   */
  it("reads a kick-off carrying an explicit offset", () => {
    const result = toFixtures([
      { ...FIXTURE_PAYLOAD, kickoff_at: "2026-08-29T13:30:00+02:00" },
    ]);

    expect(result).toEqual({
      loaded: true,
      fixtures: [
        expect.objectContaining({
          kickoffAt: new Date("2026-08-29T11:30:00Z"),
        }),
      ],
    });
  });

  /**
   * GIVEN a payload the backend already ordered by kick-off
   * WHEN it is normalized for the product
   * THEN the order survives instead of being re-derived
   */
  it("preserves the order the backend sent", () => {
    const result = toFixtures([
      { ...FIXTURE_PAYLOAD, id: 12, kickoff_at: "2026-08-29T11:30:00Z" },
      { ...FIXTURE_PAYLOAD, id: 7, kickoff_at: "2026-08-29T14:00:00Z" },
    ]);

    expect(result.loaded).toBe(true);
    expect(result.loaded ? result.fixtures.map((one) => one.id) : []).toEqual([
      12, 7,
    ]);
  });

  /**
   * GIVEN a kick-off with no timezone at all, which names no absolute instant
   * WHEN it is normalized for the product
   * THEN it is refused rather than read in whichever timezone the renderer sits
   */
  it("refuses a kick-off without a timezone", () => {
    const result = toFixtures([
      { ...FIXTURE_PAYLOAD, kickoff_at: "2026-08-29 11:30:00" },
    ]);

    expect(result).toEqual({
      loaded: false,
      reason: expect.stringContaining("fixtures contract"),
    });
  });

  /**
   * GIVEN payloads that are not a list of fixtures
   * WHEN they are normalized for the product
   * THEN each becomes the unavailable branch instead of an empty list
   */
  it("reports a payload that does not match the contract", () => {
    expect(toFixtures(undefined).loaded).toBe(false);
    expect(toFixtures({ fixtures: [FIXTURE_PAYLOAD] }).loaded).toBe(false);
  });

  /**
   * GIVEN a day the backend answered with no fixtures
   * WHEN it is normalized for the product
   * THEN it loads as an empty list rather than as a failure
   */
  it("separates an empty day from a failure", () => {
    expect(toFixtures([])).toEqual({ loaded: true, fixtures: [] });
  });

  /**
   * GIVEN a played fixture carrying both goal counts
   * WHEN it is normalized for the product
   * THEN the two counts become one score
   */
  it("pairs the goal counts of a played fixture", () => {
    const result = toFixtures([
      {
        ...FIXTURE_PAYLOAD,
        status: "finished",
        home_goals: 2,
        away_goals: 0,
      },
    ]);

    expect(result).toEqual({
      loaded: true,
      fixtures: [
        expect.objectContaining({
          status: "finished",
          score: { home: 2, away: 0 },
        }),
      ],
    });
  });

  /**
   * GIVEN a fixture carrying one goal count without the other
   * WHEN it is normalized for the product
   * THEN it carries no score, rather than a zero read as a real result
   */
  it("refuses a half-written score", () => {
    const result = toFixtures([
      { ...FIXTURE_PAYLOAD, status: "finished", home_goals: 2 },
    ]);

    expect(result).toEqual({
      loaded: true,
      fixtures: [expect.objectContaining({ score: null })],
    });
  });

  /**
   * GIVEN a state the platform does not publish
   * WHEN it is normalized for the product
   * THEN the payload is refused rather than carried as an unknown state
   */
  it("refuses a state outside the published vocabulary", () => {
    expect(
      toFixtures([{ ...FIXTURE_PAYLOAD, status: "nearly-kicked-off" }]).loaded,
    ).toBe(false);
  });
});
