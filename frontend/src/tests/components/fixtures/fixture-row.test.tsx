import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { FixtureRow } from "@/features/fixtures/components/fixture-row";
import type { Fixture, FixtureTeam } from "@/features/fixtures/types/fixture";
import type { League } from "@/features/fixtures/types/league";

const PREMIER_LEAGUE: League = {
  id: 1,
  name: "Premier League",
  shortCode: "UK PL",
  logoUrl: "https://cdn.sportmonks.com/images/soccer/leagues/8.png",
  countryName: "England",
  countryFlagUrl:
    "https://cdn.sportmonks.com/images/countries/png/short/en.png",
};

const LIVERPOOL: FixtureTeam = {
  id: 3,
  name: "Liverpool",
  shortCode: "LIV",
  crestUrl: "https://cdn.sportmonks.com/images/soccer/teams/3.png",
};

const NOTTINGHAM_FOREST: FixtureTeam = {
  id: 4,
  name: "Nottingham Forest",
  shortCode: "NFO",
  crestUrl: "https://cdn.sportmonks.com/images/soccer/teams/4.png",
};

/**
 * Builds a fixture, overriding only what a test cares about.
 *
 * @param overrides - Fields to replace on the default fixture.
 * @returns A fixture ready to render.
 */
function buildFixture(overrides: Partial<Fixture> = {}): Fixture {
  return {
    id: 12,
    kickoffAt: new Date("2026-08-29T11:30:00Z"),
    league: PREMIER_LEAGUE,
    homeTeam: LIVERPOOL,
    awayTeam: NOTTINGHAM_FOREST,
    ...overrides,
  };
}

describe("FixtureRow", () => {
  /**
   * GIVEN a fixture between two clubs that both publish a crest
   * WHEN the row is rendered
   * THEN both full names and both crests are present
   */
  it("renders both sides with their crests", () => {
    const { container } = render(<FixtureRow fixture={buildFixture()} />);

    expect(screen.getByText("Liverpool")).toBeInTheDocument();
    expect(screen.getByText("Nottingham Forest")).toBeInTheDocument();
    expect(container.querySelectorAll("img")).toHaveLength(2);
  });

  /**
   * GIVEN a fixture and a narrow viewport that cannot fit a full club name
   * WHEN the row is rendered
   * THEN each side also carries its abbreviation, so the server owes no guess
   */
  it("renders an abbreviation beside each full name", () => {
    render(<FixtureRow fixture={buildFixture()} />);

    expect(screen.getByText("LIV")).toBeInTheDocument();
    expect(screen.getByText("NFO")).toBeInTheDocument();
  });

  /**
   * GIVEN a kick-off at 11:30 UTC
   * WHEN the row is rendered
   * THEN the UTC time is shown and the machine-readable instant matches it
   */
  it("renders the kick-off time in UTC", () => {
    render(<FixtureRow fixture={buildFixture()} />);

    const kickoff = screen.getByText("11:30");

    expect(kickoff.tagName).toBe("TIME");
    expect(kickoff).toHaveAttribute("datetime", "2026-08-29T11:30:00.000Z");
  });

  /**
   * GIVEN a kick-off whose UTC hour differs from the hour in any local timezone
   * WHEN the row is rendered
   * THEN the UTC hour is the one shown, not the renderer's own
   */
  it("never shifts the kick-off into the renderer's timezone", () => {
    render(
      <FixtureRow
        fixture={buildFixture({
          kickoffAt: new Date("2026-08-29T23:45:00Z"),
        })}
      />,
    );

    expect(screen.getByText("23:45")).toBeInTheDocument();
  });

  /**
   * GIVEN a club that publishes no crest
   * WHEN the row is rendered
   * THEN a neutral placeholder stands in and no image is requested for it
   */
  it("replaces a missing crest with a neutral placeholder", () => {
    const { container } = render(
      <FixtureRow
        fixture={buildFixture({
          awayTeam: { ...NOTTINGHAM_FOREST, crestUrl: "" },
        })}
      />,
    );

    expect(container.querySelectorAll("img")).toHaveLength(1);
    expect(container.querySelectorAll('[aria-hidden="true"]')).toHaveLength(1);
  });

  /**
   * GIVEN a fixture in a named competition
   * WHEN the row is rendered
   * THEN the competition is stated beside the match
   */
  it("states the competition", () => {
    render(<FixtureRow fixture={buildFixture()} />);

    expect(screen.getByText("Premier League")).toBeInTheDocument();
  });
});
