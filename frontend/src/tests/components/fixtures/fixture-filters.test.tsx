import {
  act,
  fireEvent,
  render,
  type RenderResult,
  screen,
} from "@testing-library/react";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import { FixtureFilters } from "@/features/fixtures/components/fixture-filters";
import type { League, LeaguesResult } from "@/features/fixtures/types/league";

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

// One promise for the whole file: a new one per render suspends the picker again.
const COVERED: Promise<LeaguesResult> = Promise.resolve({
  loaded: true,
  leagues: LEAGUES,
});

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
 * Reads the competition picker's trigger, whatever it currently says.
 *
 * @returns The trigger button.
 */
function competitionTrigger(): HTMLElement {
  return screen.getByRole("button", { name: /^Competitions/ });
}

/**
 * Renders the filter bar and lets the competition read settle.
 *
 * @remarks
 * The render is awaited because the picker suspends on mount: the competitions
 * arrive as a promise, so a synchronous render would leave React holding an
 * unresolved boundary.
 *
 * @param leagues - Competitions as the route hands them over.
 * @param appliedDay - UTC calendar day the list currently shows.
 * @param appliedLeagueIds - Competitions the list is filtered to.
 * @returns The render result, so a test can move the applied scope underneath.
 */
async function renderBar(
  leagues: Promise<LeaguesResult> = COVERED,
  appliedDay = "2026-08-29",
  appliedLeagueIds: readonly number[] = [],
): Promise<RenderResult> {
  let rendered!: RenderResult;

  await act(async () => {
    rendered = render(
      <FixtureFilters
        appliedDay={appliedDay}
        appliedLeagueIds={appliedLeagueIds}
        leagues={leagues}
      />,
    );
  });

  return rendered;
}

/**
 * Stages a competition through the picker.
 *
 * @param name - Menu entry to choose.
 */
function chooseCompetition(name: string): void {
  fireEvent.keyDown(competitionTrigger(), { key: "Enter" });

  fireEvent.click(screen.getByRole("menuitemcheckbox", { name }));

  fireEvent.keyDown(document.activeElement ?? document.body, {
    key: "Escape",
  });
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
  it("offers nothing to apply until something is staged", async () => {
    await renderBar();

    expect(screen.getByRole("button", { name: "Filter" })).toBeDisabled();
  });

  /**
   * GIVEN competitions that have not arrived yet
   * WHEN the bar is rendered
   * THEN the day and the apply control are already there, resolved from the URL
   */
  it("renders the controls the URL resolves without waiting for the API", async () => {
    await renderBar(new Promise<LeaguesResult>(() => {}));

    expect(
      screen.getByRole("button", { name: /^Match day/ }),
    ).toHaveTextContent("Sat, 29 Aug 2026");

    expect(screen.getByRole("button", { name: "Filter" })).toBeInTheDocument();

    expect(
      screen.queryByRole("button", { name: /^Competitions/ }),
    ).not.toBeInTheDocument();
  });

  /**
   * GIVEN competitions the platform could not read
   * WHEN the bar is rendered
   * THEN the reason reaches the visitor instead of being discarded
   */
  it("states a competition read the platform could not answer", async () => {
    await renderBar(
      Promise.resolve({
        loaded: false,
        reason: "The API could not be reached.",
      }),
    );

    expect(screen.getByText("Competitions unavailable")).toBeVisible();
    expect(screen.getByText("The API could not be reached.")).toBeVisible();
  });

  /**
   * GIVEN a competition chosen in the picker
   * WHEN nothing else happens
   * THEN the choice is staged and no navigation is requested
   */
  it("stages a choice without requesting the list", async () => {
    await renderBar();

    chooseCompetition("Serie A");

    expect(push).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Filter" })).toBeEnabled();
  });

  /**
   * GIVEN a staged competition
   * WHEN the filter is applied
   * THEN both the day and the competition are written to the query at once
   */
  it("applies the staged scope in one navigation", async () => {
    await renderBar();

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
  it("removes the competition parameter when the filter is cleared", async () => {
    useSearchParams.mockReturnValue(
      new URLSearchParams({ date: "2026-08-29", league: "2" }),
    );

    await renderBar(COVERED, "2026-08-29", [2]);

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
  it("refuses to apply a scope equal to the one on screen", async () => {
    await renderBar(COVERED, "2026-08-29", [2]);

    chooseCompetition("Premier League");

    expect(screen.getByRole("button", { name: "Filter" })).toBeEnabled();

    chooseCompetition("Premier League");

    expect(screen.getByRole("button", { name: "Filter" })).toBeDisabled();
  });

  /**
   * GIVEN two competitions applied in the order a lexicographic sort reverses
   * WHEN the untouched bar compares that scope against itself
   * THEN they compare equal, so there is still nothing to apply
   */
  it("compares scopes by identifier rather than by digit", async () => {
    await renderBar(COVERED, "2026-08-29", [2, 1]);

    expect(screen.getByRole("button", { name: "Filter" })).toBeDisabled();
  });

  /**
   * GIVEN a competition staged against one applied scope
   * WHEN the applied scope moves underneath it, as a back navigation does
   * THEN the staging is abandoned and the bar describes the list on screen
   */
  it("abandons a staging the applied scope has moved past", async () => {
    const { rerender } = await renderBar();

    chooseCompetition("Serie A");

    expect(competitionTrigger()).toHaveTextContent("Serie A");

    rerender(
      <FixtureFilters
        appliedDay="2026-08-30"
        appliedLeagueIds={[]}
        leagues={COVERED}
      />,
    );

    expect(competitionTrigger()).toHaveTextContent("All competitions");

    expect(
      screen.getByRole("button", { name: /^Match day/ }),
    ).toHaveTextContent("Sun, 30 Aug 2026");

    expect(screen.getByRole("button", { name: "Filter" })).toBeDisabled();
  });

  /**
   * GIVEN a scope applied and then left through a link back to the plain route
   * WHEN the applied scope returns to the one the staging was made against
   * THEN the staging stays abandoned rather than reappearing over the new list
   */
  it("does not resurrect a staging when the applied scope comes back", async () => {
    const { rerender } = await renderBar();

    chooseCompetition("Serie A");

    rerender(
      <FixtureFilters
        appliedDay="2026-08-29"
        appliedLeagueIds={[2]}
        leagues={COVERED}
      />,
    );

    rerender(
      <FixtureFilters
        appliedDay="2026-08-29"
        appliedLeagueIds={[]}
        leagues={COVERED}
      />,
    );

    expect(competitionTrigger()).toHaveTextContent("All competitions");

    expect(screen.getByRole("button", { name: "Filter" })).toBeDisabled();
  });
});
