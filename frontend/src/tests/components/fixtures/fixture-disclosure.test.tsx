import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { TooltipProvider } from "@/components/ui/tooltip";
import { FixtureDisclosure } from "@/features/fixtures/components/fixture-disclosure";
import type { Fixture } from "@/features/fixtures/types/fixture";
import type { FixtureFormResult } from "@/features/fixtures/types/form";
import type { League } from "@/features/fixtures/types/league";
import type { FixturePredictionsResult } from "@/features/fixtures/types/prediction";

const { loadFixtureFormAction, loadFixturePredictionsAction } = vi.hoisted(
  () => ({
    loadFixtureFormAction: vi.fn(),
    loadFixturePredictionsAction: vi.fn(),
  }),
);

vi.mock("@/features/fixtures/server/actions", () => ({
  loadFixtureFormAction,
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

const NO_FORM: FixtureFormResult = {
  loaded: true,
  form: {
    fixtureId: 41,
    synchronizedAt: null,
    home: { teamId: 3, samples: [] },
    away: { teamId: 4, samples: [] },
    families: [],
  },
};

const SOME_FORM: FixtureFormResult = {
  loaded: true,
  form: {
    fixtureId: 41,
    synchronizedAt: null,
    home: {
      teamId: 3,
      samples: [
        {
          range: "last_6",
          scope: "overall",
          matchesCounted: 6,
          metrics: [{ metric: "goals", value: 2, opposedValue: 1 }],
        },
      ],
    },
    away: {
      teamId: 4,
      samples: [
        {
          range: "last_6",
          scope: "overall",
          matchesCounted: 6,
          metrics: [{ metric: "goals", value: 1, opposedValue: 2 }],
        },
      ],
    },
    families: [{ family: "result", metrics: ["goals"] }],
  },
};

const UNPUBLISHED_MESSAGE = "Predictions are not published yet.";

const UNAVAILABLE_MESSAGE =
  "Prediction probabilities are unavailable right now.";

const FORM_UNAVAILABLE_MESSAGE = "Pre-match form is unavailable right now.";

const FORM_EMPTY_MESSAGE = "Neither side has a completed match on record.";

const LOADING_MESSAGE = "Reading prediction probabilities.";

const UNREACHABLE_REASON =
  "The request did not complete. Check your connection and try again.";

const MARKET_HEADING = "Full-time result";

const FAMILY_HEADING = "Result";

const RETRY_LABEL = "Try again";

const PLAYED_NOTE =
  "This match has already been played, so the figures stop at its kick-off";

const TOGGLE_NAME = /Match insights/;

/**
 * Renders the disclosure around a stand-in for the row's own cells.
 *
 * @param fixture - Match to render, defaulting to one holding probabilities.
 * @returns The control the tests press.
 */
function renderDisclosure(fixture: Fixture = FIXTURE): HTMLElement {
  render(
    <TooltipProvider>
      <FixtureDisclosure fixture={fixture}>
        <span>Liverpool versus Nottingham Forest</span>
      </FixtureDisclosure>
    </TooltipProvider>,
  );

  return screen.getByRole("button", { name: TOGGLE_NAME });
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

/**
 * Activates one of the panel's tabs the way a pointer does.
 *
 * @remarks
 * The primitive selects on `mousedown` rather than on `click`, so that a drag
 * beginning on a tab still switches to it. `fireEvent.click` dispatches only the
 * click, which the primitive does not listen for, so a test written that way
 * passes its assertion against the tab it was already on.
 *
 * @param name - Label of the tab to activate.
 */
function selectTab(name: string): void {
  fireEvent.mouseDown(screen.getByRole("tab", { name }));
}

/**
 * Reads the sliding indicator the tab list paints under its selected tab.
 *
 * @returns The indicator element, which is decorative and has no role to query.
 */
function tabIndicator(): HTMLElement {
  const indicator = document.querySelector<HTMLElement>(
    '[data-slot="fixture-tab-indicator"]',
  );

  if (indicator === null) {
    throw new Error("The tab list painted no indicator.");
  }

  return indicator;
}

describe("FixtureDisclosure", () => {
  beforeEach(() => {
    loadFixturePredictionsAction.mockReset();
    loadFixtureFormAction.mockReset();
    loadFixturePredictionsAction.mockResolvedValue(NO_MARKETS);
    loadFixtureFormAction.mockResolvedValue(NO_FORM);
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
    expect(loadFixtureFormAction).not.toHaveBeenCalled();
  });

  /**
   * GIVEN a panel nobody has opened, clipped to nothing rather than removed
   * WHEN the collapsed region is read
   * THEN it holds no text at all, not even the two tab labels
   */
  it("keeps the unopened panel out of the document entirely", () => {
    const toggle = renderDisclosure();

    expect(controlledRegion(toggle).textContent).toBe("");
    expect(screen.queryByRole("tab")).not.toBeInTheDocument();
    expect(screen.queryByText(LOADING_MESSAGE)).not.toBeInTheDocument();
  });

  /**
   * GIVEN a fixture the platform holds no probabilities for
   * WHEN the row is rendered
   * THEN the toggle is offered anyway, because form does not depend on a model
   */
  it("offers the toggle on a fixture with no probabilities", () => {
    const toggle = renderDisclosure({ ...FIXTURE, hasPredictions: false });

    expect(toggle).toHaveAttribute("aria-expanded", "false");
  });

  /**
   * GIVEN a collapsed panel on a fixture holding probabilities
   * WHEN the control is pressed
   * THEN it opens on the probabilities tab and reads that tab alone, once
   */
  it("opens on the probabilities of a fixture that has them", async () => {
    const toggle = renderDisclosure();

    fireEvent.click(toggle);

    await waitFor(() =>
      expect(toggle).toHaveAttribute("aria-expanded", "true"),
    );

    expect(controlledRegion(toggle)).not.toHaveAttribute("inert");

    expect(screen.getByRole("tab", { name: "Probabilities" })).toHaveAttribute(
      "aria-selected",
      "true",
    );

    expect(loadFixturePredictionsAction).toHaveBeenCalledExactlyOnceWith(41);
    expect(loadFixtureFormAction).not.toHaveBeenCalled();
  });

  /**
   * GIVEN a fixture too far out for the provider's model to have run on
   * WHEN its panel is opened
   * THEN it opens on the form tab and never asks for probabilities it has none of
   */
  it("opens on the form of a fixture with no probabilities", async () => {
    const toggle = renderDisclosure({ ...FIXTURE, hasPredictions: false });

    fireEvent.click(toggle);

    await waitFor(() =>
      expect(toggle).toHaveAttribute("aria-expanded", "true"),
    );

    expect(await screen.findByText(FORM_EMPTY_MESSAGE)).toBeVisible();

    expect(screen.getByRole("tab", { name: "Form" })).toHaveAttribute(
      "aria-selected",
      "true",
    );

    expect(loadFixtureFormAction).toHaveBeenCalledExactlyOnceWith(41);
    expect(loadFixturePredictionsAction).not.toHaveBeenCalled();
  });

  /**
   * GIVEN a fixture the platform reports as finished
   * WHEN its form panel is opened
   * THEN the panel's note explains that the figures stop at its own kick-off
   */
  it("hands the form panel the state the match is in", async () => {
    loadFixtureFormAction.mockResolvedValue(SOME_FORM);

    fireEvent.click(renderDisclosure({ ...FIXTURE, status: "finished" }));

    selectTab("Form");

    expect(
      await screen.findByRole("heading", { level: 3, name: FAMILY_HEADING }),
    ).toBeVisible();

    expect(screen.getByText(PLAYED_NOTE, { exact: false })).toBeInTheDocument();
  });

  /**
   * GIVEN an open panel showing the probabilities it has already read
   * WHEN the form tab is activated and the two tabs are switched between
   * THEN each tab is read exactly once, on its own first activation
   */
  it("reads each tab once, on its first activation", async () => {
    loadFixtureFormAction.mockResolvedValue(SOME_FORM);

    const toggle = renderDisclosure();

    fireEvent.click(toggle);

    expect(await screen.findByText(UNPUBLISHED_MESSAGE)).toBeVisible();
    expect(loadFixtureFormAction).not.toHaveBeenCalled();

    selectTab("Form");

    expect(
      await screen.findByRole("heading", { level: 3, name: FAMILY_HEADING }),
    ).toBeVisible();

    selectTab("Probabilities");

    expect(await screen.findByText(UNPUBLISHED_MESSAGE)).toBeVisible();

    selectTab("Form");

    expect(
      await screen.findByRole("heading", { level: 3, name: FAMILY_HEADING }),
    ).toBeVisible();

    expect(loadFixturePredictionsAction).toHaveBeenCalledOnce();
    expect(loadFixtureFormAction).toHaveBeenCalledOnce();
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
   * GIVEN a form read the platform could not answer
   * WHEN the form tab is activated and its retry pressed
   * THEN the reason is repeated, the retry re-reads, and the other tab is untouched
   */
  it("retries the form without disturbing the probabilities", async () => {
    loadFixtureFormAction.mockResolvedValueOnce({
      loaded: false,
      reason: "The form service did not answer in time.",
    });
    loadFixtureFormAction.mockResolvedValue(SOME_FORM);

    const toggle = renderDisclosure();

    fireEvent.click(toggle);

    expect(await screen.findByText(UNPUBLISHED_MESSAGE)).toBeVisible();

    selectTab("Form");

    expect(await screen.findByText(FORM_UNAVAILABLE_MESSAGE)).toBeVisible();

    expect(
      screen.getByText("The form service did not answer in time."),
    ).toBeVisible();

    fireEvent.click(screen.getByRole("button", { name: RETRY_LABEL }));

    expect(
      await screen.findByRole("heading", { level: 3, name: FAMILY_HEADING }),
    ).toBeVisible();

    expect(loadFixtureFormAction).toHaveBeenCalledTimes(2);
    expect(loadFixturePredictionsAction).toHaveBeenCalledOnce();
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

  /**
   * GIVEN an open panel offering two tabs, one of them selected
   * WHEN the tab list is read and the arrow key pressed on the selected tab
   * THEN it exposes both tabs with their state and moves between them
   */
  it("exposes a keyboard-operable tab list", async () => {
    loadFixtureFormAction.mockResolvedValue(SOME_FORM);

    const toggle = renderDisclosure();

    fireEvent.click(toggle);

    expect(await screen.findByText(UNPUBLISHED_MESSAGE)).toBeVisible();

    expect(
      screen.getByRole("tablist", { name: "Match insights" }),
    ).toBeInTheDocument();

    expect(screen.getAllByRole("tab").map((one) => one.textContent)).toEqual([
      "Probabilities",
      "Form",
    ]);

    const probabilities = screen.getByRole("tab", { name: "Probabilities" });

    probabilities.focus();
    fireEvent.keyDown(probabilities, { key: "ArrowRight" });

    await waitFor(() =>
      expect(screen.getByRole("tab", { name: "Form" })).toHaveAttribute(
        "aria-selected",
        "true",
      ),
    );

    expect(loadFixtureFormAction).toHaveBeenCalledOnce();
  });

  /**
   * GIVEN a tab list whose selection is painted by a bar that slides between halves
   * WHEN the panel is opened and the other tab is then selected
   * THEN both the announced selection and the indicator's own state follow it
   */
  it("paints which tab is selected and slides the indicator to it", async () => {
    loadFixtureFormAction.mockResolvedValue(SOME_FORM);

    const toggle = renderDisclosure();

    fireEvent.click(toggle);

    expect(await screen.findByText(UNPUBLISHED_MESSAGE)).toBeVisible();

    expect(screen.getByRole("tab", { name: "Probabilities" })).toHaveAttribute(
      "aria-selected",
      "true",
    );

    expect(tabIndicator()).toHaveAttribute("data-shifted", "false");
    expect(tabIndicator()).toHaveAttribute("aria-hidden", "true");

    selectTab("Form");

    await waitFor(() =>
      expect(screen.getByRole("tab", { name: "Form" })).toHaveAttribute(
        "aria-selected",
        "true",
      ),
    );

    expect(tabIndicator()).toHaveAttribute("data-shifted", "true");

    expect(screen.getByRole("tab", { name: "Probabilities" })).toHaveAttribute(
      "aria-selected",
      "false",
    );
  });
});
