import { fireEvent, render, screen } from "@testing-library/react";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import { LeagueSelect } from "@/features/fixtures/components/league-select";
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
    shortCode: "IT SA",
    logoUrl: "https://cdn.sportmonks.com/images/soccer/leagues/384.png",
    countryName: "Italy",
    countryFlagUrl: "",
  },
];

/**
 * Teaches jsdom the layout and pointer APIs the select popup measures itself
 * with. None of them exist there, and the popup throws on mount without them.
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
 * Renders the competition filter and opens its list of options.
 *
 * @param selectedLeagueId - Competition the filter starts on.
 */
function renderOpenSelect(selectedLeagueId: number | null = null): void {
  render(
    <LeagueSelect leagues={LEAGUES} selectedLeagueId={selectedLeagueId} />,
  );

  fireEvent.keyDown(screen.getByRole("combobox"), { key: "ArrowDown" });
}

describe("LeagueSelect", () => {
  beforeAll(installPopupEnvironment);

  beforeEach(() => {
    useSearchParams.mockReturnValue(
      new URLSearchParams({ date: "2026-08-29" }),
    );
  });

  /**
   * GIVEN a filter narrowed to one competition and a list never opened
   * WHEN the trigger is read
   * THEN it names that competition, which the unmounted options cannot supply
   */
  it("names the current competition before the list is opened", () => {
    render(<LeagueSelect leagues={LEAGUES} selectedLeagueId={2} />);

    expect(
      screen.getByRole("combobox", { name: "Competition" }),
    ).toHaveTextContent("Serie A");
  });

  /**
   * GIVEN an unfiltered list and a list never opened
   * WHEN the trigger is read
   * THEN it states that every competition is included
   */
  it("states an unfiltered list on the trigger", () => {
    render(<LeagueSelect leagues={LEAGUES} selectedLeagueId={null} />);

    expect(
      screen.getByRole("combobox", { name: "Competition" }),
    ).toHaveTextContent("All competitions");
  });

  /**
   * GIVEN the covered competitions
   * WHEN the filter is opened
   * THEN every competition is offered alongside the option that clears the filter
   */
  it("lists every competition and the clear option", () => {
    renderOpenSelect();

    const options = screen.getAllByRole("option").map((one) => one.textContent);

    expect(options).toEqual(["All competitions", "Premier League", "Serie A"]);
  });

  /**
   * GIVEN a competition that publishes a country flag and one that does not
   * WHEN the filter is opened
   * THEN only the first carries a decorative flag beside its name
   */
  it("renders a decorative flag only where one is published", () => {
    renderOpenSelect();

    const flags = screen
      .getAllByRole("option")
      .flatMap((option) => Array.from(option.querySelectorAll("img")));

    expect(flags).toHaveLength(1);
    expect(flags[0]).toHaveAttribute("alt", "");
  });

  /**
   * GIVEN a filter showing every competition and a day already in the query
   * WHEN a competition is chosen
   * THEN the competition is written to the query and the day is kept
   */
  it("writes the chosen competition and keeps the day", () => {
    renderOpenSelect();

    fireEvent.click(screen.getByRole("option", { name: "Serie A" }));

    expect(push).toHaveBeenCalledWith("?date=2026-08-29&league=2", {
      scroll: false,
    });
  });

  /**
   * GIVEN a filter narrowed to one competition
   * WHEN the clear option is chosen
   * THEN the competition parameter is removed rather than set to a sentinel
   */
  it("removes the competition parameter when the filter is cleared", () => {
    useSearchParams.mockReturnValue(
      new URLSearchParams({ date: "2026-08-29", league: "2" }),
    );

    renderOpenSelect(2);

    fireEvent.click(screen.getByRole("option", { name: "All competitions" }));

    expect(push).toHaveBeenCalledWith("?date=2026-08-29", { scroll: false });
  });

  /**
   * GIVEN competitions that could not be loaded
   * WHEN the filter is rendered
   * THEN the control is disabled instead of offering an empty list
   */
  it("disables itself when no competition is available", () => {
    render(<LeagueSelect leagues={[]} selectedLeagueId={null} />);

    expect(screen.getByRole("combobox")).toBeDisabled();
  });
});
