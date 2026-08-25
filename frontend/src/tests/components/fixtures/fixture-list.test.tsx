import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { FixtureList } from "@/features/fixtures/components/fixture-list";
import type { Fixture } from "@/features/fixtures/types/fixture";
import type { League } from "@/features/fixtures/types/league";

const PREMIER_LEAGUE: League = {
  id: 1,
  name: "Premier League",
  shortCode: "UK PL",
  logoUrl: "",
  countryName: "England",
  countryFlagUrl: "",
};

const FIXTURE: Fixture = {
  id: 12,
  kickoffAt: new Date("2026-08-29T11:30:00Z"),
  status: "scheduled",
  score: null,
  league: PREMIER_LEAGUE,
  homeTeam: { id: 3, name: "Liverpool", shortCode: "LIV", crestUrl: "" },
  awayTeam: {
    id: 4,
    name: "Nottingham Forest",
    shortCode: "NFO",
    crestUrl: "",
  },
};

const SERIE_A: League = {
  id: 2,
  name: "Serie A",
  shortCode: "ITA SA",
  logoUrl: "",
  countryName: "Italy",
  countryFlagUrl: "",
};

describe("FixtureList", () => {
  /**
   * GIVEN a day the backend answered with no fixtures
   * WHEN the list is rendered
   * THEN the empty state states it and offers the two ways out
   */
  it("renders the empty state for an answered day with no fixtures", () => {
    render(<FixtureList result={{ loaded: true, fixtures: [] }} />);

    expect(screen.getByText("No fixtures on this day.")).toBeVisible();

    expect(
      screen.getByText("Pick another day, or widen the competition filter."),
    ).toBeVisible();

    expect(screen.queryByRole("list")).not.toBeInTheDocument();
  });

  /**
   * GIVEN any of the three outcomes of a fixtures request
   * WHEN each is rendered
   * THEN none declares a live region of its own, since the route owns the one
   */
  it("declares no live region of its own", () => {
    const { container, rerender } = render(
      <FixtureList result={{ loaded: true, fixtures: [] }} />,
    );

    expect(screen.queryByRole("status")).not.toBeInTheDocument();

    rerender(<FixtureList result={{ loaded: false, reason: "Nope." }} />);

    expect(screen.queryByRole("status")).not.toBeInTheDocument();

    rerender(<FixtureList result={{ loaded: true, fixtures: [FIXTURE] }} />);

    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    expect(container.querySelector("[aria-live='polite']")).toBeNull();
  });

  /**
   * GIVEN a day that produced rows, the one outcome that used to announce nothing
   * WHEN the list is rendered
   * THEN it states its own counts and keeps the rows out of the announcement
   */
  it("summarises a loaded day for the region above it", () => {
    const { container } = render(
      <FixtureList
        result={{
          loaded: true,
          fixtures: [
            FIXTURE,
            {
              ...FIXTURE,
              id: 13,
              kickoffAt: new Date("2026-08-29T13:30:00Z"),
              league: SERIE_A,
            },
          ],
        }}
      />,
    );

    expect(
      screen.getByText("2 matches in 2 competitions."),
    ).toBeInTheDocument();

    expect(container.querySelector("[aria-live='off']")).toContainElement(
      screen.getAllByRole("listitem")[0] ?? null,
    );
  });

  /**
   * GIVEN a fixtures request the platform could not answer
   * WHEN the list is rendered
   * THEN the error state is shown with the reason, not the empty state
   */
  it("renders the error state with its reason", () => {
    render(
      <FixtureList
        result={{ loaded: false, reason: "The API could not be reached." }}
      />,
    );

    expect(
      screen.getByText("Fixtures are unavailable right now."),
    ).toBeVisible();
    expect(screen.getByText("The API could not be reached.")).toBeVisible();

    expect(
      screen.queryByText("No fixtures on this day."),
    ).not.toBeInTheDocument();
  });

  /**
   * GIVEN two fixtures in the order the backend sent them
   * WHEN the list is rendered
   * THEN one row is rendered per fixture, in that order
   */
  it("renders one row per fixture", () => {
    render(
      <FixtureList
        result={{
          loaded: true,
          fixtures: [
            FIXTURE,
            {
              ...FIXTURE,
              id: 13,
              kickoffAt: new Date("2026-08-29T14:00:00Z"),
            },
          ],
        }}
      />,
    );

    const times = screen
      .getAllByRole("listitem")
      .map((row) => row.querySelector("time")?.textContent);

    expect(times).toEqual(["11:30", "14:00"]);
  });

  /**
   * GIVEN fixtures of two competitions interleaved by kick-off
   * WHEN the list is rendered
   * THEN each competition gets one heading and its own matches, not a heading per match
   */
  it("groups the day under one heading per competition", () => {
    render(
      <FixtureList
        result={{
          loaded: true,
          fixtures: [
            FIXTURE,
            {
              ...FIXTURE,
              id: 13,
              kickoffAt: new Date("2026-08-29T13:30:00Z"),
              league: SERIE_A,
            },
            {
              ...FIXTURE,
              id: 14,
              kickoffAt: new Date("2026-08-29T14:00:00Z"),
            },
          ],
        }}
      />,
    );

    const headings = screen.getAllByRole("heading", { level: 2 });

    expect(headings.map((one) => one.textContent)).toEqual([
      "Premier League",
      "Serie A",
    ]);

    expect(screen.getAllByRole("list")).toHaveLength(2);
  });

  /**
   * GIVEN a competition with several matches and one with a single match
   * WHEN the list is rendered
   * THEN each heading counts its own matches, in the singular where there is one
   */
  it("counts the matches under each heading", () => {
    render(
      <FixtureList
        result={{
          loaded: true,
          fixtures: [
            FIXTURE,
            {
              ...FIXTURE,
              id: 13,
              kickoffAt: new Date("2026-08-29T13:30:00Z"),
              league: SERIE_A,
            },
            {
              ...FIXTURE,
              id: 14,
              kickoffAt: new Date("2026-08-29T14:00:00Z"),
            },
          ],
        }}
      />,
    );

    expect(screen.getByText("2 matches")).toBeVisible();
    expect(screen.getByText("1 match")).toBeVisible();
  });
});
