import { fireEvent, render, screen } from "@testing-library/react";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import { LeagueSelect } from "@/features/fixtures/components/league-select";
import type { League, LeaguesResult } from "@/features/fixtures/types/league";

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

const COVERED: LeaguesResult = { loaded: true, leagues: LEAGUES };

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
 * Reads the picker's trigger, whatever it currently says.
 *
 * @returns The trigger button.
 */
function trigger(): HTMLElement {
  return screen.getByRole("button", { name: /^Competitions/ });
}

/**
 * Renders the competition picker and opens its menu.
 *
 * @param value - Competitions the filter starts staged on.
 */
function renderOpenMenu(value: readonly number[] = []): void {
  render(<LeagueSelect leagues={COVERED} onChange={onChange} value={value} />);

  fireEvent.keyDown(trigger(), { key: "Enter" });
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
    render(<LeagueSelect leagues={COVERED} onChange={onChange} value={[]} />);

    expect(trigger()).toHaveTextContent("All competitions");
  });

  /**
   * GIVEN exactly one competition staged
   * WHEN the trigger is read
   * THEN it names that competition rather than counting it
   */
  it("names a single staged competition", () => {
    render(<LeagueSelect leagues={COVERED} onChange={onChange} value={[2]} />);

    expect(trigger()).toHaveTextContent("Serie A");
  });

  /**
   * GIVEN several competitions staged
   * WHEN the trigger is read
   * THEN it summarises them as a count, which a narrow control can hold
   */
  it("summarises several staged competitions", () => {
    render(
      <LeagueSelect leagues={COVERED} onChange={onChange} value={[1, 2]} />,
    );

    expect(trigger()).toHaveTextContent("2 competitions");
  });

  /**
   * GIVEN a trigger whose visible content is the staged scope
   * WHEN its accessible name is computed
   * THEN the name carries the label and the scope, not the label alone
   */
  it("announces the staged scope beside its own label", () => {
    render(
      <LeagueSelect leagues={COVERED} onChange={onChange} value={[1, 2]} />,
    );

    expect(trigger()).toHaveAccessibleName(/^Competitions/);
    expect(trigger()).toHaveAccessibleName(/2 competitions$/);
  });

  /**
   * GIVEN a URL staging an identifier the platform never named
   * WHEN the trigger is read
   * THEN it counts what is staged instead of claiming every competition
   */
  it("counts a staged competition it cannot name", () => {
    render(
      <LeagueSelect leagues={COVERED} onChange={onChange} value={[999]} />,
    );

    expect(trigger()).toHaveTextContent("1 competition");
    expect(trigger()).not.toHaveTextContent("All competitions");
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
   * GIVEN competitions the platform could not read
   * WHEN the picker is rendered
   * THEN the failure is stated with its reason instead of an inert control
   */
  it("states why there is nothing to pick from", () => {
    render(
      <LeagueSelect
        leagues={{ loaded: false, reason: "The API could not be reached." }}
        onChange={onChange}
        value={[]}
      />,
    );

    expect(screen.getByText("Competitions unavailable")).toBeVisible();
    expect(screen.getByText("The API could not be reached.")).toBeVisible();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  /**
   * GIVEN a platform that answered with no covered competition at all
   * WHEN the picker is rendered
   * THEN that is stated too, rather than offering a menu holding nothing
   */
  it("states an empty answer apart from a failed one", () => {
    render(
      <LeagueSelect
        leagues={{ loaded: true, leagues: [] }}
        onChange={onChange}
        value={[]}
      />,
    );

    expect(screen.getByText("No competitions covered")).toBeVisible();
    expect(screen.queryByText("Competitions unavailable")).toBeNull();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  /**
   * GIVEN competitions still being read
   * WHEN the picker is rendered
   * THEN its slot holds a placeholder of the control's shape and nothing to press
   */
  it("holds the control's shape while the competitions are read", () => {
    const { container } = render(
      <LeagueSelect leagues={null} onChange={onChange} value={[]} />,
    );

    const placeholder = container.firstElementChild;

    expect(placeholder).toHaveClass("h-8", "@xl:w-56");
    expect(placeholder).toHaveAttribute("aria-hidden", "true");
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});
