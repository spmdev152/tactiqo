import { describe, expect, it } from "vitest";

import { groupFixturesByLeague } from "@/features/fixtures/domain/fixture-groups";
import type { Fixture } from "@/features/fixtures/types/fixture";
import type { League } from "@/features/fixtures/types/league";

/**
 * Builds a competition with only the fields grouping reads.
 *
 * @param id - Internal competition identifier.
 * @param name - Competition name, which breaks a tie between equal kick-offs.
 * @returns A competition.
 */
function league(id: number, name: string): League {
  return {
    id,
    name,
    shortCode: "",
    logoUrl: "",
    countryName: "",
    countryFlagUrl: "",
  };
}

/**
 * Builds a fixture with only the fields grouping reads.
 *
 * @param id - Internal fixture identifier.
 * @param kickoff - Kick-off instant, as an ISO 8601 UTC timestamp.
 * @param competition - Competition the fixture belongs to.
 * @returns A fixture.
 */
function fixture(id: number, kickoff: string, competition: League): Fixture {
  return {
    id,
    kickoffAt: new Date(kickoff),
    league: competition,
    homeTeam: { id: id * 10, name: "Home", shortCode: "HOM", crestUrl: "" },
    awayTeam: { id: id * 10 + 1, name: "Away", shortCode: "AWA", crestUrl: "" },
  };
}

const PREMIER_LEAGUE = league(1, "Premier League");

const SERIE_A = league(2, "Serie A");

const BUNDESLIGA = league(3, "Bundesliga");

describe("groupFixturesByLeague", () => {
  /**
   * GIVEN a day with no fixtures
   * WHEN it is grouped
   * THEN there are no groups rather than one empty group
   */
  it("produces no group for an empty day", () => {
    expect(groupFixturesByLeague([])).toEqual([]);
  });

  /**
   * GIVEN a competition whose matches are interleaved with another's by kick-off
   * WHEN the day is grouped
   * THEN each competition appears once, carrying all of its own matches
   */
  it("collects every match of a competition under one group", () => {
    const groups = groupFixturesByLeague([
      fixture(1, "2026-08-29T11:30:00Z", PREMIER_LEAGUE),
      fixture(2, "2026-08-29T13:30:00Z", SERIE_A),
      fixture(3, "2026-08-29T14:00:00Z", PREMIER_LEAGUE),
    ]);

    expect(groups.map((group) => group.league.id)).toEqual([1, 2]);
    expect(groups[0]?.fixtures.map((one) => one.id)).toEqual([1, 3]);
    expect(groups[1]?.fixtures.map((one) => one.id)).toEqual([2]);
  });

  /**
   * GIVEN competitions whose first matches kick off at different times
   * WHEN the day is grouped
   * THEN the competition playing next comes first, whatever its name
   */
  it("orders groups by their earliest kick-off", () => {
    const groups = groupFixturesByLeague([
      fixture(1, "2026-08-29T11:30:00Z", SERIE_A),
      fixture(2, "2026-08-29T13:30:00Z", BUNDESLIGA),
    ]);

    expect(groups.map((group) => group.league.name)).toEqual([
      "Serie A",
      "Bundesliga",
    ]);
  });

  /**
   * GIVEN two competitions whose first matches kick off at the same instant
   * WHEN the day is grouped
   * THEN the tie breaks on the competition name, so the order cannot drift
   */
  it("breaks a tie on the competition name", () => {
    const groups = groupFixturesByLeague([
      fixture(1, "2026-08-29T13:30:00Z", SERIE_A),
      fixture(2, "2026-08-29T13:30:00Z", BUNDESLIGA),
    ]);

    expect(groups.map((group) => group.league.name)).toEqual([
      "Bundesliga",
      "Serie A",
    ]);
  });
});
