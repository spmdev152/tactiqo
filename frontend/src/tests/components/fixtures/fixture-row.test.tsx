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
    status: "scheduled",
    score: null,
    league: PREMIER_LEAGUE,
    homeTeam: LIVERPOOL,
    awayTeam: NOTTINGHAM_FOREST,
    ...overrides,
  };
}

/** Restricts a text query to the nodes a screen reader can reach. */
const ANNOUNCED = { ignore: '[aria-hidden="true"]' };

/** Restricts a text query to the painted nodes, which are hidden from it. */
const PAINTED = { selector: '[aria-hidden="true"]' };

describe("FixtureRow", () => {
  /**
   * GIVEN a fixture between two clubs that both publish a crest
   * WHEN the row is rendered
   * THEN both full names and both crests are present
   */
  it("renders both sides with their crests", () => {
    const { container } = render(<FixtureRow fixture={buildFixture()} />);

    expect(screen.getByText("Liverpool", PAINTED)).toBeInTheDocument();
    expect(screen.getByText("Nottingham Forest", PAINTED)).toBeInTheDocument();
    expect(container.querySelectorAll("img")).toHaveLength(2);
  });

  /**
   * GIVEN a fixture between two clubs
   * WHEN the row is rendered
   * THEN the sides sit on one line, separated by a marker rather than stacked
   */
  it("separates the two sides with a visible marker", () => {
    render(<FixtureRow fixture={buildFixture()} />);

    const separator = screen.getByText("vs");
    const home = screen.getByText("Liverpool", PAINTED);
    const away = screen.getByText("Nottingham Forest", PAINTED);

    expect(separator).toBeInTheDocument();
    expect(
      separator.compareDocumentPosition(home) &
        Node.DOCUMENT_POSITION_PRECEDING,
    ).toBeTruthy();
    expect(
      separator.compareDocumentPosition(away) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
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
   * GIVEN a row narrow enough to paint abbreviations instead of full names
   * WHEN the names a screen reader can reach are queried
   * THEN each side is announced in full and neither abbreviation is announced
   */
  it("announces the full club name at every width", () => {
    render(<FixtureRow fixture={buildFixture()} />);

    expect(screen.getByText("Liverpool", ANNOUNCED)).toBeInTheDocument();
    expect(
      screen.getByText("Nottingham Forest", ANNOUNCED),
    ).toBeInTheDocument();
    expect(screen.queryByText("LIV", ANNOUNCED)).not.toBeInTheDocument();
    expect(screen.queryByText("NFO", ANNOUNCED)).not.toBeInTheDocument();
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
    expect(
      container.querySelectorAll('[data-slot="crest-placeholder"]'),
    ).toHaveLength(1);
  });

  /**
   * GIVEN a fixture whose competition is named by the heading above its group
   * WHEN the row is rendered
   * THEN the row does not repeat it, leaving the width to the two sides
   */
  it("leaves the competition to the group heading", () => {
    render(<FixtureRow fixture={buildFixture()} />);

    expect(screen.queryByText("Premier League")).not.toBeInTheDocument();
    expect(screen.queryByText("UK PL")).not.toBeInTheDocument();
  });

  /**
   * GIVEN a finished fixture carrying a score
   * WHEN the row is rendered
   * THEN the result replaces the marker between the two sides
   */
  it("states the result of a finished fixture", () => {
    render(
      <FixtureRow
        fixture={buildFixture({
          status: "finished",
          score: { home: 2, away: 0 },
        })}
      />,
    );

    expect(screen.getByText("2 - 0")).toBeInTheDocument();
    expect(screen.queryByText("vs")).not.toBeInTheDocument();
  });

  /**
   * GIVEN a fixture under way, whose score the platform reads hours behind
   * WHEN the row is rendered
   * THEN no score is shown, rather than one already out of date
   */
  it("withholds the score of a fixture still being played", () => {
    render(
      <FixtureRow
        fixture={buildFixture({ status: "live", score: { home: 1, away: 0 } })}
      />,
    );

    expect(screen.queryByText("1 - 0")).not.toBeInTheDocument();
    expect(screen.getByText("vs")).toBeInTheDocument();
  });

  /**
   * GIVEN a finished fixture the platform has no score for
   * WHEN the row is rendered
   * THEN the marker stands, so the row never invents a nil-nil
   */
  it("keeps the marker when a finished fixture has no score", () => {
    render(<FixtureRow fixture={buildFixture({ status: "finished" })} />);

    expect(screen.getByText("vs")).toBeInTheDocument();
  });

  /**
   * GIVEN a marker painted as `vs` by a text transform
   * WHEN the row is announced
   * THEN the word is announced instead of the abbreviation
   */
  it("announces an unplayed match as a word", () => {
    render(<FixtureRow fixture={buildFixture()} />);

    expect(screen.getByText("versus", ANNOUNCED)).toBeInTheDocument();
    expect(screen.queryByText("vs", ANNOUNCED)).not.toBeInTheDocument();
  });

  /**
   * GIVEN a result painted with a hyphen, which assistive technology may drop
   * WHEN the row is announced
   * THEN the score is announced as two numbers joined by a word
   */
  it("announces a result without its separator", () => {
    render(
      <FixtureRow
        fixture={buildFixture({
          status: "finished",
          score: { home: 2, away: 0 },
        })}
      />,
    );

    expect(screen.getByText("2 to 0", ANNOUNCED)).toBeInTheDocument();
    expect(screen.queryByText("2 - 0", ANNOUNCED)).not.toBeInTheDocument();
  });

  /**
   * GIVEN a day holding both a played fixture and one still to come
   * WHEN their rows are rendered
   * THEN the marker column has the same floor on both, so the centre lines up
   */
  it("gives the marker the same width played or not", () => {
    render(
      <>
        <FixtureRow fixture={buildFixture()} />
        <FixtureRow
          fixture={buildFixture({
            status: "finished",
            score: { home: 2, away: 0 },
          })}
        />
      </>,
    );

    expect(screen.getByText("vs")).toHaveClass("min-w-11");
    expect(screen.getByText("2 - 0")).toHaveClass("min-w-11");
  });
});
