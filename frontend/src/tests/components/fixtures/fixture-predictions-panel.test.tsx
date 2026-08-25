import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import {
  FixturePredictionsPanel,
  type FixturePredictionsPanelProps,
} from "@/features/fixtures/components/fixture-predictions-panel";
import type { PredictionSides } from "@/features/fixtures/domain/prediction-markets";
import type {
  FixturePredictionsResult,
  PredictionMarketProbabilities,
} from "@/features/fixtures/types/prediction";

const SIDES: PredictionSides = {
  home: { id: 3, name: "Liverpool", shortCode: "LIV", crestUrl: "" },
  away: { id: 4, name: "Nottingham Forest", shortCode: "NFO", crestUrl: "" },
};

const FULL_TIME_RESULT: PredictionMarketProbabilities = {
  market: "fulltime_result",
  reliability: null,
  hitRatio: null,
  selections: [
    { selection: "home", probability: 54 },
    { selection: "draw", probability: 25 },
    { selection: "away", probability: 21 },
  ],
};

const BOTH_TEAMS_TO_SCORE: PredictionMarketProbabilities = {
  market: "both_teams_to_score",
  reliability: null,
  hitRatio: null,
  selections: [
    { selection: "yes", probability: 61 },
    { selection: "no", probability: 39 },
  ],
};

const SYNCHRONIZED_AT = new Date("2026-08-26T14:30:00Z");

const SYNCHRONIZED_TEXT = "26 Aug, 14:30";

const TWO_MARKETS: FixturePredictionsResult = {
  loaded: true,
  predictions: {
    fixtureId: 41,
    synchronizedAt: SYNCHRONIZED_AT,
    markets: [FULL_TIME_RESULT, BOTH_TEAMS_TO_SCORE],
  },
};

const STAMPED_WITHOUT_MARKETS: FixturePredictionsResult = {
  loaded: true,
  predictions: { fixtureId: 41, synchronizedAt: SYNCHRONIZED_AT, markets: [] },
};

const UNAVAILABLE: FixturePredictionsResult = {
  loaded: false,
  reason: "The predictions service did not answer in time.",
};

const UNPUBLISHED_MESSAGE = "Predictions are not published yet.";

const UNAVAILABLE_MESSAGE =
  "Prediction probabilities are unavailable right now.";

const LOADING_MESSAGE = "Reading prediction probabilities.";

const LOADED_MESSAGE = "Prediction probabilities are ready.";

const RETRY_LABEL = "Try again";

/**
 * Renders the panel as the disclosure hands it over once a read was asked for.
 *
 * @param result - Outcome to render, or `null` while the read is unanswered.
 * @param overrides - Props the case under test states for itself.
 */
function renderPanel(
  result: FixturePredictionsResult | null,
  overrides: Partial<FixturePredictionsPanelProps> = {},
): void {
  render(
    <FixturePredictionsPanel
      onRetry={() => {}}
      pending={false}
      requested
      sides={SIDES}
      {...overrides}
      result={result}
    />,
  );
}

describe("FixturePredictionsPanel", () => {
  /**
   * GIVEN a read that produced two markets in the order the contract sent them
   * WHEN the panel renders that result
   * THEN both market headings are present and keep that order
   */
  it("renders every market the read produced, in order", () => {
    renderPanel(TWO_MARKETS);

    const headings = screen
      .getAllByRole("heading", { level: 3 })
      .map((heading) => heading.textContent);

    expect(headings).toEqual(["Full-time result", "Both teams to score"]);
  });

  /**
   * GIVEN two markets rendered as siblings of one multi-column flow
   * WHEN React reconciles them
   * THEN each has an identity of its own and no duplicate key is reported
   */
  it("gives every market a key of its own", () => {
    const reported = vi.spyOn(console, "error").mockImplementation(() => {});

    renderPanel(TWO_MARKETS);

    const collisions = reported.mock.calls.filter((call) =>
      call.join(" ").includes("same key"),
    );

    expect(collisions).toEqual([]);
  });

  /**
   * GIVEN a read the platform stamped with the instant it synchronized
   * WHEN the panel renders it
   * THEN the instant is machine-readable and its element holds no verb
   */
  it("states when the probabilities were last read", () => {
    renderPanel(TWO_MARKETS);

    const stamp = screen.getByText(SYNCHRONIZED_TEXT);

    expect(stamp.tagName).toBe("TIME");
    expect(stamp).toHaveAttribute("datetime", "2026-08-26T14:30:00.000Z");
    expect(screen.getByText(/Updated/)).not.toBe(stamp);
  });

  /**
   * GIVEN a fixture the platform has read but the provider has not modelled
   * WHEN the panel renders that stamped but empty result
   * THEN it reports an absence and dates nothing
   */
  it("reports an unmodelled fixture without dating the emptiness", () => {
    renderPanel(STAMPED_WITHOUT_MARKETS);

    expect(screen.getByText(UNPUBLISHED_MESSAGE)).toBeVisible();
    expect(screen.queryByText(SYNCHRONIZED_TEXT)).not.toBeInTheDocument();
    expect(document.querySelector("time")).toBeNull();
  });

  /**
   * GIVEN an absence that will read the same however often it is asked for
   * WHEN the panel renders it
   * THEN nothing invites the visitor to ask again
   */
  it("offers no retry for a fixture that is merely unmodelled", () => {
    renderPanel(STAMPED_WITHOUT_MARKETS);

    expect(
      screen.queryByRole("button", { name: RETRY_LABEL }),
    ).not.toBeInTheDocument();
  });

  /**
   * GIVEN a read that failed and could succeed on another attempt
   * WHEN the visitor presses the notice's retry control
   * THEN the panel asks its owner to read again
   */
  it("lets a failed read be asked for again", () => {
    const onRetry = vi.fn();

    renderPanel(UNAVAILABLE, { onRetry });

    expect(screen.getByText(UNAVAILABLE_MESSAGE)).toBeVisible();

    fireEvent.click(screen.getByRole("button", { name: RETRY_LABEL }));

    expect(onRetry).toHaveBeenCalledOnce();
  });

  /**
   * GIVEN a panel nested in a list that opted every row out of being announced
   * WHEN a read is in flight and then settles
   * THEN each of the two states is a live region of its own
   */
  it("announces both the read and its outcome", () => {
    const { rerender } = render(
      <FixturePredictionsPanel
        onRetry={() => {}}
        pending
        requested
        result={null}
        sides={SIDES}
      />,
    );

    expect(screen.getByRole("status")).toHaveTextContent(LOADING_MESSAGE);

    rerender(
      <FixturePredictionsPanel
        onRetry={() => {}}
        pending={false}
        requested
        result={TWO_MARKETS}
        sides={SIDES}
      />,
    );

    expect(screen.getByRole("status")).toHaveTextContent(LOADED_MESSAGE);
  });

  /**
   * GIVEN a failure the visitor has to be told about
   * WHEN the panel renders the notice
   * THEN the notice itself is the live region, with no hidden second copy
   */
  it("announces a failure through the notice it shows", () => {
    renderPanel(UNAVAILABLE);

    expect(screen.getByRole("status")).toHaveTextContent(UNAVAILABLE_MESSAGE);
  });

  /**
   * GIVEN a row whose panel nobody has asked for
   * WHEN the panel renders
   * THEN it puts nothing in the document, not even its own surface
   */
  it("renders nothing at all before a read is asked for", () => {
    const { container } = render(
      <FixturePredictionsPanel
        onRetry={() => {}}
        pending={false}
        requested={false}
        result={null}
        sides={SIDES}
      />,
    );

    expect(container).toBeEmptyDOMElement();
  });
});
