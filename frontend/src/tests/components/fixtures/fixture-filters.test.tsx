import { fireEvent, render, screen } from "@testing-library/react";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import { FixtureFilters } from "@/features/fixtures/components/fixture-filters";
import type { League } from "@/features/fixtures/types/league";

const { push, useSearchParams } = vi.hoisted(() => ({
  push: vi.fn(),
  useSearchParams: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
  useSearchParams,
}));

const LEAGUES: readonly League[] = [
  {
    id: 1,
    name: "Premier League",
    shortCode: "UK PL",
    logoUrl: "https://cdn.sportmonks.com/images/soccer/leagues/8.png",
    countryName: "England",
    countryFlagUrl:
      "https://cdn.sportmonks.com/images/countries/png/short/en.png",
  },
  {
    id: 2,
    name: "Serie A",
    shortCode: "ITA SA",
    logoUrl: "https://cdn.sportmonks.com/images/soccer/leagues/384.png",
    countryName: "Italy",
    countryFlagUrl: "",
  },
];

/**
 * Teaches jsdom the layout and pointer APIs the two popups measure themselves
 * with. None of them exist there, and both throw on mount without them.
 */
function installPopupEnvironment(): void {
  globalThis.ResizeObserver = class {
    observe(): void {}
    unobserve(): void {}
    disconnect(): void {}
  };

  Element.prototype.scrollIntoView = () => {};
  Element.prototype.hasPointerCapture = () => false;
  Element.prototype.releasePointerCapture = () => {};
  Element.prototype.setPointerCapture = () => {};
}

/**
 * Renders the filter bar on a given applied scope.
 *
 * @param appliedDay - UTC calendar day the list currently shows.
 * @param appliedLeagueId - Competition the list is filtered to, or `null`.
 * @returns The render result, so a test can move the applied scope underneath.
 */
function renderFilters(
  appliedDay = "2026-08-29",
  appliedLeagueId: number | null = null,
) {
  return render(
    <FixtureFilters
      appliedDay={appliedDay}
      appliedLeagueId={appliedLeagueId}
      leagues={LEAGUES}
    />,
  );
}

/**
 * Stages a competition through the select.
 *
 * @param name - Option label to choose.
 */
function chooseCompetition(name: string): void {
  fireEvent.keyDown(screen.getByRole("combobox"), { key: "ArrowDown" });
  fireEvent.click(screen.getByRole("option", { name }));
}

describe("FixtureFilters", () => {
  beforeAll(installPopupEnvironment);

  beforeEach(() => {
    push.mockReset();
    useSearchParams.mockReturnValue(
      new URLSearchParams({ date: "2026-08-29" }),
    );
  });

  /**
   * GIVEN a scope already applied to the list
   * WHEN the bar is rendered untouched
   * THEN the control that applies it is disabled, since there is nothing to apply
   */
  it("offers nothing to apply until something is staged", () => {
    renderFilters();

    expect(screen.getByRole("button", { name: "Filter" })).toBeDisabled();
  });

  /**
   * GIVEN a competition chosen in the picker
   * WHEN nothing else happens
   * THEN the choice is staged and no navigation is requested
   */
  it("stages a choice without requesting the list", () => {
    renderFilters();

    chooseCompetition("Serie A");

    expect(push).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Filter" })).toBeEnabled();
  });

  /**
   * GIVEN a staged competition
   * WHEN the filter is applied
   * THEN both the day and the competition are written to the query at once
   */
  it("applies the staged scope in one navigation", () => {
    renderFilters();

    chooseCompetition("Serie A");

    fireEvent.click(screen.getByRole("button", { name: "Filter" }));

    expect(push).toHaveBeenCalledExactlyOnceWith("?date=2026-08-29&league=2", {
      scroll: false,
    });
  });

  /**
   * GIVEN a list already narrowed to one competition
   * WHEN the filter is widened back to all of them and applied
   * THEN the competition parameter is removed rather than set to a sentinel
   */
  it("removes the competition parameter when the filter is cleared", () => {
    useSearchParams.mockReturnValue(
      new URLSearchParams({ date: "2026-08-29", league: "2" }),
    );

    renderFilters("2026-08-29", 2);

    chooseCompetition("All competitions");

    fireEvent.click(screen.getByRole("button", { name: "Filter" }));

    expect(push).toHaveBeenCalledExactlyOnceWith("?date=2026-08-29", {
      scroll: false,
    });
  });

  /**
   * GIVEN a staged choice that is then reverted to the applied one
   * WHEN the bar is inspected
   * THEN applying is refused again, so the list on screen cannot be re-requested
   */
  it("refuses to apply a scope equal to the one on screen", () => {
    renderFilters("2026-08-29", 2);

    chooseCompetition("Premier League");

    expect(screen.getByRole("button", { name: "Filter" })).toBeEnabled();

    chooseCompetition("Serie A");

    expect(screen.getByRole("button", { name: "Filter" })).toBeDisabled();
  });

  /**
   * GIVEN a competition staged against one applied scope
   * WHEN the applied scope moves underneath it, as a back navigation does
   * THEN the staging is abandoned and the bar describes the list on screen
   */
  it("abandons a staging the applied scope has moved past", () => {
    const { rerender } = renderFilters("2026-08-29", null);

    chooseCompetition("Serie A");

    expect(screen.getByRole("combobox")).toHaveTextContent("Serie A");

    rerender(
      <FixtureFilters
        appliedDay="2026-08-30"
        appliedLeagueId={null}
        leagues={LEAGUES}
      />,
    );

    expect(screen.getByRole("combobox")).toHaveTextContent("All competitions");
    expect(screen.getByRole("button", { name: "Match day" })).toHaveTextContent(
      "Sun, 30 Aug 2026",
    );
    expect(screen.getByRole("button", { name: "Filter" })).toBeDisabled();
  });
});
