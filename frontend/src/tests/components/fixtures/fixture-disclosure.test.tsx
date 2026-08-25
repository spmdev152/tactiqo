import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { FixtureDisclosure } from "@/features/fixtures/components/fixture-disclosure";
import type { Fixture } from "@/features/fixtures/types/fixture";
import type { League } from "@/features/fixtures/types/league";
import type { FixturePredictionsResult } from "@/features/fixtures/types/prediction";

const { loadFixturePredictionsAction } = vi.hoisted(() => ({
  loadFixturePredictionsAction: vi.fn(),
}));

vi.mock("@/features/fixtures/server/actions", () => ({
  loadFixturePredictionsAction,
}));

const PREMIER_LEAGUE: League = {
  id: 1,
  name: "Premier League",
  shortCode: "UK PL",
  logoUrl: "",
  countryName: "England",
  countryFlagUrl: "",
};

const FIXTURE: Fixture = {
  id: 41,
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
  hasPredictions: true,
};

const NO_MARKETS: FixturePredictionsResult = {
  loaded: true,
  predictions: { fixtureId: 41, synchronizedAt: null, markets: [] },
};

const ONE_MARKET: FixturePredictionsResult = {
  loaded: true,
  predictions: {
    fixtureId: 41,
    synchronizedAt: null,
    markets: [
      {
        market: "fulltime_result",
        reliability: null,
        hitRatio: null,
        selections: [
          { selection: "home", probability: 54 },
          { selection: "draw", probability: 25 },
          { selection: "away", probability: 21 },
        ],
      },
    ],
  },
};

const UNPUBLISHED_MESSAGE = "Predictions are not published yet.";

const UNAVAILABLE_MESSAGE =
  "Prediction probabilities are unavailable right now.";

const LOADING_MESSAGE = "Reading prediction probabilities.";

const UNREACHABLE_REASON =
  "The request did not complete. Check your connection and try again.";

const MARKET_HEADING = "Full-time result";

const RETRY_LABEL = "Try again";

/**
 * Renders the disclosure around a stand-in for the row's own cells.
 *
 * @returns The control the tests press.
 */
function renderDisclosure(): HTMLElement {
  render(
    <FixtureDisclosure fixture={FIXTURE}>
      <span>Liverpool versus Nottingham Forest</span>
    </FixtureDisclosure>,
  );

  return screen.getByRole("button", { name: /Prediction probabilities/ });
}

/**
 * Reads the region a control claims to expand.
 *
 * @remarks
 * Resolved through `aria-controls` rather than by class or position, so a
 * control pointing at a region that is not there fails the test instead of
 * quietly passing it, which is the defect the attribute exists to prevent.
 *
 * @param toggle - The disclosure's control.
 * @returns The element the control names.
 */
function controlledRegion(toggle: HTMLElement): HTMLElement {
  const id = toggle.getAttribute("aria-controls") ?? "";

  const region = document.getElementById(id);

  if (region === null) {
    throw new Error(`The control names no region with id "${id}".`);
  }

  return region;
}

describe("FixtureDisclosure", () => {
  beforeEach(() => {
    loadFixturePredictionsAction.mockReset();
    loadFixturePredictionsAction.mockResolvedValue(NO_MARKETS);
  });

  /**
   * GIVEN a fixture whose panel nobody has opened
   * WHEN the disclosure is rendered
   * THEN it reports itself collapsed and its panel is unreachable
   */
  it("starts collapsed with the panel unreachable", () => {
    const toggle = renderDisclosure();

    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(controlledRegion(toggle)).toHaveAttribute("inert");
    expect(loadFixturePredictionsAction).not.toHaveBeenCalled();
  });

  /**
   * GIVEN a panel nobody has opened, clipped to nothing rather than removed
   * WHEN the collapsed region is read
   * THEN it holds no text at all, not even the panel's hidden loading line
   */
  it("keeps the unopened panel out of the document entirely", () => {
    const toggle = renderDisclosure();

    expect(controlledRegion(toggle).textContent).toBe("");
    expect(screen.queryByText(LOADING_MESSAGE)).not.toBeInTheDocument();
  });

  /**
   * GIVEN a collapsed panel
   * WHEN the control is pressed
   * THEN the panel opens, becomes reachable, and the fixture is read once
   */
  it("expands and reads the fixture's probabilities once", async () => {
    const toggle = renderDisclosure();

    fireEvent.click(toggle);

    await waitFor(() =>
      expect(toggle).toHaveAttribute("aria-expanded", "true"),
    );

    expect(controlledRegion(toggle)).not.toHaveAttribute("inert");

    expect(loadFixturePredictionsAction).toHaveBeenCalledExactlyOnceWith(41);
  });

  /**
   * GIVEN a panel that has already been opened and answered
   * WHEN it is collapsed and opened again
   * THEN no second request is made, because the answer is already held
   */
  it("never reads the same fixture twice", async () => {
    const toggle = renderDisclosure();

    fireEvent.click(toggle);

    expect(await screen.findByText(UNPUBLISHED_MESSAGE)).toBeVisible();

    fireEvent.click(toggle);
    fireEvent.click(toggle);

    await waitFor(() =>
      expect(toggle).toHaveAttribute("aria-expanded", "true"),
    );

    expect(loadFixturePredictionsAction).toHaveBeenCalledOnce();
  });

  /**
   * GIVEN a first request that has not answered yet
   * WHEN the row is collapsed and expanded again before it does
   * THEN the second expansion adds no request, because one is already running
   */
  it("never reads a fixture it is already reading", async () => {
    const { promise, resolve } =
      Promise.withResolvers<FixturePredictionsResult>();

    loadFixturePredictionsAction.mockReturnValue(promise);

    const toggle = renderDisclosure();

    fireEvent.click(toggle);
    fireEvent.click(toggle);
    fireEvent.click(toggle);

    resolve(NO_MARKETS);

    expect(await screen.findByText(UNPUBLISHED_MESSAGE)).toBeVisible();

    expect(loadFixturePredictionsAction).toHaveBeenCalledExactlyOnceWith(41);
  });

  /**
   * GIVEN a read the platform has not answered yet
   * WHEN the panel is opened
   * THEN the control reports itself busy and the read is announced as running
   */
  it("reports a read still in flight", async () => {
    const { promise, resolve } =
      Promise.withResolvers<FixturePredictionsResult>();

    loadFixturePredictionsAction.mockReturnValue(promise);

    const toggle = renderDisclosure();

    fireEvent.click(toggle);

    await waitFor(() => expect(toggle).toHaveAttribute("aria-busy", "true"));

    expect(screen.getByRole("status")).toHaveTextContent(LOADING_MESSAGE);

    resolve(NO_MARKETS);

    await waitFor(() => expect(toggle).toHaveAttribute("aria-busy", "false"));

    expect(screen.getByRole("status")).toHaveTextContent(UNPUBLISHED_MESSAGE);
  });

  /**
   * GIVEN a read the platform could not answer
   * WHEN the panel is opened
   * THEN it states the failure and repeats the reason it was given
   */
  it("states why the probabilities are unavailable", async () => {
    loadFixturePredictionsAction.mockResolvedValue({
      loaded: false,
      reason: "The predictions service did not answer in time.",
    });

    fireEvent.click(renderDisclosure());

    expect(await screen.findByText(UNAVAILABLE_MESSAGE)).toBeVisible();

    expect(
      screen.getByText("The predictions service did not answer in time."),
    ).toBeVisible();
  });

  /**
   * GIVEN an action that rejects, as an offline browser makes it
   * WHEN the panel is opened
   * THEN the row survives and the panel states a failure of its own
   */
  it("survives a rejected request instead of taking the page down", async () => {
    loadFixturePredictionsAction.mockRejectedValue(
      new Error("Failed to fetch"),
    );

    const toggle = renderDisclosure();

    fireEvent.click(toggle);

    expect(await screen.findByText(UNAVAILABLE_MESSAGE)).toBeVisible();

    expect(screen.getByText(UNREACHABLE_REASON)).toBeVisible();
    expect(toggle).toBeInTheDocument();
    expect(
      screen.getByText("Liverpool versus Nottingham Forest"),
    ).toBeVisible();
  });

  /**
   * GIVEN a panel whose read rejected and left a failure notice behind
   * WHEN the row is collapsed and expanded again
   * THEN the fixture is read a second time and the markets replace the notice
   */
  it("reads again when a failed row is expanded again", async () => {
    loadFixturePredictionsAction.mockRejectedValueOnce(
      new Error("Failed to fetch"),
    );
    loadFixturePredictionsAction.mockResolvedValue(ONE_MARKET);

    const toggle = renderDisclosure();

    fireEvent.click(toggle);

    expect(await screen.findByText(UNREACHABLE_REASON)).toBeVisible();

    fireEvent.click(toggle);
    fireEvent.click(toggle);

    expect(
      await screen.findByRole("heading", { level: 3, name: MARKET_HEADING }),
    ).toBeVisible();

    expect(screen.queryByText(UNREACHABLE_REASON)).not.toBeInTheDocument();
    expect(loadFixturePredictionsAction).toHaveBeenCalledTimes(2);
  });

  /**
   * GIVEN an open panel reporting that its read failed
   * WHEN the visitor presses the notice's retry control
   * THEN the fixture is read again without the panel being collapsed first
   */
  it("reads again from the notice's own retry control", async () => {
    loadFixturePredictionsAction.mockRejectedValueOnce(
      new Error("Failed to fetch"),
    );
    loadFixturePredictionsAction.mockResolvedValue(ONE_MARKET);

    const toggle = renderDisclosure();

    fireEvent.click(toggle);

    expect(await screen.findByText(UNREACHABLE_REASON)).toBeVisible();

    fireEvent.click(screen.getByRole("button", { name: RETRY_LABEL }));

    expect(
      await screen.findByRole("heading", { level: 3, name: MARKET_HEADING }),
    ).toBeVisible();

    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(loadFixturePredictionsAction).toHaveBeenCalledTimes(2);
  });

  /**
   * GIVEN a fixture too far out for the provider's model to have run on
   * WHEN the panel is opened
   * THEN it reports an absence rather than a failure
   */
  it("states an unpublished fixture as unpublished", async () => {
    fireEvent.click(renderDisclosure());

    expect(await screen.findByText(UNPUBLISHED_MESSAGE)).toBeVisible();

    expect(screen.queryByText(UNAVAILABLE_MESSAGE)).not.toBeInTheDocument();
  });

  /**
   * GIVEN an absence the provider will report the same way every time
   * WHEN the panel reports it
   * THEN no retry is offered, so a settled absence cannot be re-read
   */
  it("offers no retry for an unpublished fixture", async () => {
    fireEvent.click(renderDisclosure());

    expect(await screen.findByText(UNPUBLISHED_MESSAGE)).toBeVisible();

    expect(
      screen.queryByRole("button", { name: RETRY_LABEL }),
    ).not.toBeInTheDocument();
  });
});
