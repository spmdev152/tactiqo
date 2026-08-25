import { fireEvent, render, screen } from "@testing-library/react";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import { LeagueSelect } from "@/features/fixtures/components/league-select";
import type { League } from "@/features/fixtures/types/league";

const onChange = vi.fn();

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
 * Teaches jsdom the layout and pointer APIs the menu measures itself with.
 * None of them exist there, and the menu throws on mount without them.
 */
function installMenuEnvironment(): void {
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
 * Renders the competition picker and opens its menu.
 *
 * @param value - Competitions the filter starts staged on.
 */
function renderOpenMenu(value: readonly number[] = []): void {
  render(<LeagueSelect leagues={LEAGUES} onChange={onChange} value={value} />);

  fireEvent.keyDown(screen.getByRole("button", { name: "Competitions" }), {
    key: "Enter",
  });
}

describe("LeagueSelect", () => {
  beforeAll(installMenuEnvironment);

  beforeEach(() => {
    onChange.mockReset();
  });

  /**
   * GIVEN an unfiltered day and a menu never opened
   * WHEN the trigger is read
   * THEN it states that every competition is included
   */
  it("states an unfiltered day on the trigger", () => {
    render(<LeagueSelect leagues={LEAGUES} onChange={onChange} value={[]} />);

    expect(
      screen.getByRole("button", { name: "Competitions" }),
    ).toHaveTextContent("All competitions");
  });

  /**
   * GIVEN exactly one competition staged
   * WHEN the trigger is read
   * THEN it names that competition rather than counting it
   */
  it("names a single staged competition", () => {
    render(<LeagueSelect leagues={LEAGUES} onChange={onChange} value={[2]} />);

    expect(
      screen.getByRole("button", { name: "Competitions" }),
    ).toHaveTextContent("Serie A");
  });

  /**
   * GIVEN several competitions staged
   * WHEN the trigger is read
   * THEN it summarises them as a count, which a narrow control can hold
   */
  it("summarises several staged competitions", () => {
    render(
      <LeagueSelect leagues={LEAGUES} onChange={onChange} value={[1, 2]} />,
    );

    expect(
      screen.getByRole("button", { name: "Competitions" }),
    ).toHaveTextContent("2 competitions");
  });

  /**
   * GIVEN the covered competitions
   * WHEN the menu is opened
   * THEN each is offered as a checkbox alongside the one that clears the filter
   */
  it("offers every competition and the clear entry as checkboxes", () => {
    renderOpenMenu();

    const options = screen
      .getAllByRole("menuitemcheckbox")
      .map((one) => one.textContent);

    expect(options).toEqual(["All competitions", "Premier League", "Serie A"]);
  });

  /**
   * GIVEN a competition already staged
   * WHEN another is ticked
   * THEN both are staged, so the filter accumulates rather than replaces
   */
  it("adds a competition to the staged ones", () => {
    renderOpenMenu([1]);

    fireEvent.click(screen.getByRole("menuitemcheckbox", { name: "Serie A" }));

    expect(onChange).toHaveBeenCalledExactlyOnceWith([1, 2]);
  });

  /**
   * GIVEN two competitions staged
   * WHEN one of them is unticked
   * THEN only the other remains staged
   */
  it("removes a competition from the staged ones", () => {
    renderOpenMenu([1, 2]);

    fireEvent.click(
      screen.getByRole("menuitemcheckbox", { name: "Premier League" }),
    );

    expect(onChange).toHaveBeenCalledExactlyOnceWith([2]);
  });

  /**
   * GIVEN a filter narrowed to some competitions
   * WHEN the clear entry is chosen
   * THEN the staged competitions are emptied rather than set to a sentinel
   */
  it("clears every staged competition", () => {
    renderOpenMenu([1, 2]);

    fireEvent.click(
      screen.getByRole("menuitemcheckbox", { name: "All competitions" }),
    );

    expect(onChange).toHaveBeenCalledExactlyOnceWith([]);
  });

  /**
   * GIVEN competitions that could not be loaded
   * WHEN the picker is rendered
   * THEN the control is disabled instead of offering an empty menu
   */
  it("disables itself when no competition is available", () => {
    render(<LeagueSelect leagues={[]} onChange={onChange} value={[]} />);

    expect(screen.getByRole("button", { name: "Competitions" })).toBeDisabled();
  });
});
