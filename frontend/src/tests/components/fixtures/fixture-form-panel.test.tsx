import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { FixtureFormPanel } from "@/features/fixtures/components/fixture-form-panel";
import type { FixtureTeam } from "@/features/fixtures/types/fixture";
import type {
  FixtureForm,
  FixtureFormResult,
  FormSample,
} from "@/features/fixtures/types/form";

const LIVERPOOL: FixtureTeam = {
  id: 3,
  name: "Liverpool",
  shortCode: "LIV",
  crestUrl: "",
};

const NOTTINGHAM_FOREST: FixtureTeam = {
  id: 4,
  name: "Nottingham Forest",
  shortCode: "NFO",
  crestUrl: "",
};

const FAMILIES = [
  { family: "result", metrics: ["win_share", "goals"] },
  { family: "possession", metrics: ["possession"] },
] as const;

/**
 * Builds one sample, whose figures scale with a single factor.
 *
 * @remarks
 * One factor rather than three explicit figures, so a test can state that the
 * `last_6` window differs from `last_3` without restating the whole sample and
 * without two windows accidentally sharing a number the assertion depends on.
 *
 * @param range - Window the sample belongs to.
 * @param scope - Scope the sample belongs to.
 * @param matches - Matches the sample counted.
 * @param goals - Goals per match, which the other figures are derived from.
 * @returns One sample ready to render.
 */
function buildSample(
  range: FormSample["range"],
  scope: FormSample["scope"],
  matches: number,
  goals: number,
): FormSample {
  return {
    range,
    scope,
    matchesCounted: matches,
    metrics: [
      { metric: "win_share", value: goals * 20, opposedValue: null },
      { metric: "goals", value: goals, opposedValue: 1 },
      { metric: "possession", value: 50, opposedValue: null },
    ],
  };
}

/**
 * Builds a fixture's form, overriding only what a test cares about.
 *
 * @param overrides - Fields to replace on the default form.
 * @returns A fixture's form ready to render.
 */
function buildForm(overrides: Partial<FixtureForm> = {}): FixtureForm {
  return {
    fixtureId: 41,
    synchronizedAt: new Date("2026-08-25T20:00:00Z"),
    home: {
      teamId: 3,
      samples: [
        buildSample("last_3", "overall", 3, 3),
        buildSample("last_6", "overall", 6, 2),
        buildSample("last_6", "venue", 3, 4),
        buildSample("season", "overall", 19, 1),
      ],
    },
    away: {
      teamId: 4,
      samples: [
        buildSample("last_3", "overall", 3, 1),
        buildSample("last_6", "overall", 6, 1),
        buildSample("last_6", "venue", 2, 1),
        buildSample("season", "overall", 19, 1),
      ],
    },
    families: [...FAMILIES],
    ...overrides,
  };
}

/**
 * Renders the panel around one settled read.
 *
 * @param result - Outcome the panel is handed.
 * @param onRetry - Retry callback the failure branch is given.
 */
function renderPanel(
  result: FixtureFormResult | null,
  onRetry: () => void = vi.fn(),
): void {
  render(
    <FixtureFormPanel
      away={NOTTINGHAM_FOREST}
      home={LIVERPOOL}
      onRetry={onRetry}
      pending={false}
      requested
      result={result}
    />,
  );
}

/**
 * Reads an element's text as a screen reader would, without its hidden parts.
 *
 * @remarks
 * `toHaveTextContent` reads the whole subtree, including the nodes marked
 * `aria-hidden`, so it cannot tell a value stated in words from one drawn as a
 * bar. Copying the markup into a detached element and removing the hidden nodes
 * from the copy leaves exactly what is announced, which is what the assertion is
 * about.
 *
 * The remaining text nodes are joined with a space rather than concatenated,
 * because `textContent` runs two adjacent elements together and assistive
 * technology does not: a figure followed by its label would read as one token
 * and the assertion would be about the markup's whitespace instead of about what
 * is said.
 *
 * @param element - Element to read, or `null` when the query found none.
 * @returns The announced text, one space between neighbours.
 */
function announcedText(element: Element | null): string {
  const clone = document.createElement("div");

  clone.innerHTML = element?.innerHTML ?? "";

  for (const hidden of clone.querySelectorAll('[aria-hidden="true"]')) {
    hidden.remove();
  }

  const spoken: string[] = [];
  const walker = document.createTreeWalker(clone, NodeFilter.SHOW_TEXT);

  while (walker.nextNode() !== null) {
    const text = (walker.currentNode.textContent ?? "").trim();

    if (text !== "") {
      spoken.push(text);
    }
  }

  return spoken.join(" ");
}

describe("FixtureFormPanel", () => {
  /**
   * GIVEN a panel nobody has asked a read for
   * WHEN it is rendered
   * THEN it draws nothing at all, not even an empty surface
   */
  it("draws nothing until a read is asked for", () => {
    const { container } = render(
      <FixtureFormPanel
        away={NOTTINGHAM_FOREST}
        home={LIVERPOOL}
        onRetry={vi.fn()}
        pending={false}
        requested={false}
        result={null}
      />,
    );

    expect(container).toBeEmptyDOMElement();
  });

  /**
   * GIVEN a read that has been asked for but has not answered
   * WHEN the panel is rendered
   * THEN it announces the read in words and draws the shape it is about to hold
   */
  it("announces a read still in flight", () => {
    renderPanel(null);

    expect(screen.getByRole("status")).toHaveTextContent(
      "Reading pre-match form.",
    );
  });

  /**
   * GIVEN a read the platform could not answer
   * WHEN the panel is rendered
   * THEN it states the failure, repeats the reason and offers to ask again
   */
  it("states why the form is unavailable and offers a retry", () => {
    const onRetry = vi.fn();

    renderPanel(
      { loaded: false, reason: "The form service did not answer in time." },
      onRetry,
    );

    expect(
      screen.getByText("Pre-match form is unavailable right now."),
    ).toBeVisible();

    expect(
      screen.getByText("The form service did not answer in time."),
    ).toBeVisible();

    fireEvent.click(screen.getByRole("button", { name: "Try again" }));

    expect(onRetry).toHaveBeenCalledOnce();
  });

  /**
   * GIVEN two sides with no completed match behind either of them
   * WHEN the panel is rendered
   * THEN it reports an absence with no retry rather than a failure
   */
  it("states a fixture with nothing played as an absence", () => {
    renderPanel({
      loaded: true,
      form: buildForm({
        synchronizedAt: null,
        home: { teamId: 3, samples: [buildSample("last_6", "overall", 0, 0)] },
        away: { teamId: 4, samples: [buildSample("last_6", "overall", 0, 0)] },
      }),
    });

    expect(
      screen.getByText("Neither side has a completed match on record."),
    ).toBeVisible();

    expect(
      screen.queryByRole("button", { name: "Try again" }),
    ).not.toBeInTheDocument();
  });

  /**
   * GIVEN a fixture whose form the platform holds
   * WHEN the panel is rendered
   * THEN both clubs, every family and the read's own timestamp are shown
   */
  it("renders both sides under their families", () => {
    renderPanel({ loaded: true, form: buildForm() });

    expect(screen.getByText("Liverpool")).toBeVisible();
    expect(screen.getByText("Nottingham Forest")).toBeVisible();

    expect(
      screen
        .getAllByRole("heading", { level: 3 })
        .map((one) => one.textContent),
    ).toEqual(["Result", "Possession"]);

    expect(screen.getByText("Goals")).toBeVisible();
    expect(screen.getByText("25 Aug, 20:00")).toBeVisible();
  });

  /**
   * GIVEN a panel opened on its default window of six matches
   * WHEN the visitor selects the three-match window instead
   * THEN the figures change to that window's and no read is asked for
   */
  it("changes the figures shown without asking for another read", () => {
    renderPanel({ loaded: true, form: buildForm() });

    expect(screen.getByText("2.00")).toBeVisible();
    expect(screen.getAllByText("6 matches")).toHaveLength(2);

    fireEvent.click(screen.getByRole("button", { name: "Last 3" }));

    expect(screen.getByText("3.00")).toBeVisible();
    expect(screen.getAllByText("3 matches")).toHaveLength(2);
    expect(screen.queryByText("2.00")).not.toBeInTheDocument();
  });

  /**
   * GIVEN a panel showing every completed match of the default window
   * WHEN the visitor narrows it to the side each club will occupy
   * THEN that scope's figures replace the wider ones
   */
  it("narrows the figures to the selected scope", () => {
    renderPanel({ loaded: true, form: buildForm() });

    fireEvent.click(screen.getByRole("button", { name: "Home / away" }));

    expect(screen.getByText("4.00")).toBeVisible();
    expect(screen.getByText("3 of 6 matches")).toBeVisible();
    expect(screen.getByText("2 of 6 matches")).toBeVisible();
  });

  /**
   * GIVEN two controls whose selected state a sighted reader sees by its colour
   * WHEN the groups are read
   * THEN each is named and states which of its options is pressed
   */
  it("names each filter group and states which option is pressed", () => {
    renderPanel({ loaded: true, form: buildForm() });

    const ranges = screen.getByRole("group", { name: "Matches counted" });
    const scopes = screen.getByRole("group", { name: "Matches included" });

    expect(screen.getByRole("button", { name: "Last 6" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );

    expect(screen.getByRole("button", { name: "Last 3" })).toHaveAttribute(
      "aria-pressed",
      "false",
    );

    expect(ranges).toContainElement(
      screen.getByRole("button", { name: "Season" }),
    );

    expect(scopes).toContainElement(
      screen.getByRole("button", { name: "Overall" }),
    );
  });

  /**
   * GIVEN a window in which neither side has played, beside windows where they did
   * WHEN that window is selected
   * THEN the panel says so and both counts read as nought rather than as figures
   */
  it("states a window that counted no matches", () => {
    renderPanel({
      loaded: true,
      form: buildForm({
        home: {
          teamId: 3,
          samples: [
            buildSample("last_6", "overall", 6, 2),
            buildSample("season", "overall", 0, 0),
          ],
        },
        away: {
          teamId: 4,
          samples: [
            buildSample("last_6", "overall", 6, 1),
            buildSample("season", "overall", 0, 0),
          ],
        },
      }),
    });

    fireEvent.click(screen.getByRole("button", { name: "Season" }));

    expect(screen.getByText("No matches in this window.")).toBeVisible();
    expect(screen.getAllByText("No matches counted")).toHaveLength(2);
    expect(screen.queryByText("Goals")).not.toBeInTheDocument();
  });

  /**
   * GIVEN a window the backend published no sample for on one side
   * WHEN that window is selected
   * THEN the panel says the window was not published rather than showing zeros
   */
  it("states a window the backend published no sample for", () => {
    renderPanel({
      loaded: true,
      form: buildForm({
        away: { teamId: 4, samples: [buildSample("last_3", "overall", 3, 1)] },
      }),
    });

    expect(screen.getByText("This window was not published.")).toBeVisible();
    expect(screen.getByText("No sample published")).toBeVisible();
    expect(screen.queryByText("Goals")).not.toBeInTheDocument();
  });

  /**
   * GIVEN a figure whose name the frontend's vocabulary does not carry
   * WHEN the family that lists it is rendered
   * THEN the row shows a dash and says the figure was not published
   */
  it("renders a dash for a metric the sample did not publish", () => {
    renderPanel({
      loaded: true,
      form: buildForm({
        home: {
          teamId: 3,
          samples: [
            {
              range: "last_6",
              scope: "overall",
              matchesCounted: 6,
              metrics: [{ metric: "win_share", value: 40, opposedValue: null }],
            },
          ],
        },
        away: {
          teamId: 4,
          samples: [buildSample("last_6", "overall", 6, 1)],
        },
      }),
    });

    expect(screen.getAllByText("—")).toHaveLength(2);
    expect(screen.getAllByText("not published")).toHaveLength(2);
  });

  /**
   * GIVEN a comparison bar whose length is the only visual channel it has
   * WHEN one metric's row is read
   * THEN both clubs are named beside their own figures and the bar is silent
   */
  it("speaks every figure the comparison bar draws", () => {
    const { container } = render(
      <FixtureFormPanel
        away={NOTTINGHAM_FOREST}
        home={LIVERPOOL}
        onRetry={vi.fn()}
        pending={false}
        requested
        result={{ loaded: true, form: buildForm() }}
      />,
    );

    const row = screen.getByText("Goals").closest("li");

    expect(row).not.toBeNull();

    expect(announcedText(row)).toBe(
      "Liverpool, 2.00 against 1.00 Goals Nottingham Forest, 1.00 against 1.00",
    );

    for (const track of container.querySelectorAll(
      '[data-slot="form-comparison-track"]',
    )) {
      expect(track).toHaveAttribute("aria-hidden", "true");
    }
  });

  /**
   * GIVEN two sides whose figures for one metric differ
   * WHEN the comparison bar is drawn
   * THEN the leading side takes the larger share of the track
   */
  it("splits the comparison bar in proportion to the two figures", () => {
    const { container } = render(
      <FixtureFormPanel
        away={NOTTINGHAM_FOREST}
        home={LIVERPOOL}
        onRetry={vi.fn()}
        pending={false}
        requested
        result={{ loaded: true, form: buildForm() }}
      />,
    );

    const homeFills = container.querySelectorAll(
      '[data-slot="form-comparison-home"]',
    );

    expect(homeFills[1]).toHaveStyle({ width: "66.66666666666667%" });
    expect(homeFills[2]).toHaveStyle({ width: "50%" });
  });
});
