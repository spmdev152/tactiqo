import { describe, expect, it } from "vitest";

import { toLeagues } from "@/features/fixtures/mappers/league";

const LEAGUE_PAYLOAD = {
  id: 1,
  name: "Premier League",
  short_code: "UK PL",
  logo_url: "https://cdn.sportmonks.com/images/soccer/leagues/8.png",
  country_name: "England",
  country_flag_url:
    "https://cdn.sportmonks.com/images/countries/png/short/en.png",
};

describe("toLeagues", () => {
  /**
   * GIVEN a leagues payload in the published wire shape
   * WHEN it is normalized for the product
   * THEN every field is renamed to the product contract and none is dropped
   */
  it("normalizes a leagues payload", () => {
    expect(toLeagues([LEAGUE_PAYLOAD])).toEqual({
      loaded: true,
      leagues: [
        {
          id: 1,
          name: "Premier League",
          shortCode: "UK PL",
          logoUrl: "https://cdn.sportmonks.com/images/soccer/leagues/8.png",
          countryName: "England",
          countryFlagUrl:
            "https://cdn.sportmonks.com/images/countries/png/short/en.png",
        },
      ],
    });
  });

  /**
   * GIVEN a league whose logo and flag are absent
   * WHEN it is normalized for the product
   * THEN the empty strings survive, so a component can choose a placeholder
   */
  it("keeps an absent image as an empty string", () => {
    const result = toLeagues([
      { ...LEAGUE_PAYLOAD, logo_url: "", country_flag_url: "" },
    ]);

    expect(result).toEqual({
      loaded: true,
      leagues: [expect.objectContaining({ logoUrl: "", countryFlagUrl: "" })],
    });
  });

  /**
   * GIVEN an answered request carrying no competitions
   * WHEN it is normalized for the product
   * THEN it loads as an empty list rather than as a failure
   */
  it("separates an empty list from a failure", () => {
    expect(toLeagues([])).toEqual({ loaded: true, leagues: [] });
  });

  /**
   * GIVEN payloads that are not a list of leagues
   * WHEN they are normalized for the product
   * THEN each becomes the unavailable branch instead of an empty list
   */
  it("reports a payload that does not match the contract", () => {
    const identifierMissing = toLeagues([
      { name: "Premier League", short_code: "UK PL" },
    ]);

    expect(toLeagues(undefined).loaded).toBe(false);
    expect(toLeagues({ leagues: [LEAGUE_PAYLOAD] }).loaded).toBe(false);
    expect(identifierMissing).toEqual({
      loaded: false,
      reason: expect.stringContaining("leagues contract"),
    });
  });
});
