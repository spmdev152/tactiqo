import type { FixtureTeam } from "@/features/fixtures/types/fixture";

/**
 * Every prediction market the platform publishes, as the API serializes them.
 *
 * @remarks
 * A closed vocabulary the backend owns, kept here as one tuple so the wire
 * schema and the product type cannot drift apart: the schema validates against
 * it and the type is derived from it.
 *
 * The order is the order the API promises, which is also the order the panel
 * reads in: the three markets a visitor recognizes first, then the goal lines
 * ascending, then the long-tail markets whose selection lists are large. It is
 * preserved rather than re-derived, so the product decision lives in one place.
 *
 * The members are the platform's own names, not the provider's numeric type
 * ids. Sportmonks identifies a market by an integer, and that integer stops at
 * the provider boundary so nothing above it has to know that `235` and
 * `over_under_2_5` are the same thing.
 */
export const PREDICTION_MARKETS = [
  "fulltime_result",
  "double_chance",
  "both_teams_to_score",
  "over_under_1_5",
  "over_under_2_5",
  "over_under_3_5",
  "over_under_4_5",
  "team_to_score_first",
  "first_half_result",
  "half_time_full_time",
  "correct_score",
] as const;

/**
 * One market predictions are published for.
 */
export type PredictionMarket = (typeof PREDICTION_MARKETS)[number];

/**
 * Every selection a prediction market can be broken down into.
 *
 * @remarks
 * One flat vocabulary across every market rather than one per market, because
 * the wire carries a single `selection` field and a union per market would make
 * the schema depend on which market it happened to be decoding.
 *
 * Several members are shared by markets that mean different things by them,
 * which is why {@link selectionLabel} takes the market as well: `yes` is
 * `Over 2.5` in a goal-line market and `Yes` in both-teams-to-score. The
 * sharing is deliberate — the platform stores an outcome, and how that outcome
 * reads is product copy rather than data.
 */
export const PREDICTION_SELECTIONS = [
  "home",
  "draw",
  "away",
  "home_or_draw",
  "draw_or_away",
  "home_or_away",
  "no_goal",
  "yes",
  "no",
  "home_then_home",
  "home_then_draw",
  "home_then_away",
  "draw_then_home",
  "draw_then_draw",
  "draw_then_away",
  "away_then_home",
  "away_then_draw",
  "away_then_away",
  "score_0_0",
  "score_0_1",
  "score_0_2",
  "score_0_3",
  "score_1_0",
  "score_1_1",
  "score_1_2",
  "score_1_3",
  "score_2_0",
  "score_2_1",
  "score_2_2",
  "score_2_3",
  "score_3_0",
  "score_3_1",
  "score_3_2",
  "score_3_3",
  "any_other_home_win",
  "any_other_draw",
  "any_other_away_win",
] as const;

/**
 * One outcome inside a prediction market.
 */
export type PredictionSelection = (typeof PREDICTION_SELECTIONS)[number];

/**
 * How well the provider's model has historically graded a market.
 *
 * @remarks
 * Ordered worst to best, so the tuple doubles as the scale the interface reads
 * a grade against rather than needing a separate ranking.
 */
export const PREDICTION_RELIABILITIES = [
  "poor",
  "medium",
  "good",
  "high",
] as const;

/**
 * Historical quality grade of a market in one competition.
 */
export type PredictionReliability = (typeof PREDICTION_RELIABILITIES)[number];

/**
 * The two clubs a selection label is resolved against.
 *
 * @remarks
 * A selection names an outcome, not a club, so `home` alone reads as jargon.
 * Passing both sides is what turns the stored vocabulary into copy a visitor
 * recognizes, and passing them as a pair rather than as two arguments makes the
 * call site impossible to get the wrong way round.
 */
export interface PredictionSides {
  /** Side playing at home. */
  readonly home: FixtureTeam;

  /** Side playing away. */
  readonly away: FixtureTeam;
}

type SelectionLabeller = (sides: PredictionSides) => string;

type MatchOutcome = "home" | "draw" | "away";

const MARKET_LABELS: Record<PredictionMarket, string> = {
  fulltime_result: "Full-time result",
  double_chance: "Double chance",
  both_teams_to_score: "Both teams to score",
  over_under_1_5: "Over/under 1.5 goals",
  over_under_2_5: "Over/under 2.5 goals",
  over_under_3_5: "Over/under 3.5 goals",
  over_under_4_5: "Over/under 4.5 goals",
  team_to_score_first: "First team to score",
  first_half_result: "First-half result",
  half_time_full_time: "Half-time / full-time",
  correct_score: "Correct score",
};

/**
 * Reads the shortest name that still identifies a club.
 *
 * @remarks
 * A prediction panel puts a club name inside a bar that is already narrow, so
 * the abbreviation is preferred wherever there is one. The full name is the
 * fallback rather than the default because a club with no published short code
 * must still be readable, and a blank label would leave a bar naming nothing.
 *
 * @param team - Side to name.
 * @returns The club's short code, or its full name when it has none.
 */
function sideLabel(team: FixtureTeam): string {
  const shortCode = team.shortCode.trim();

  return shortCode.length > 0 ? shortCode : team.name;
}

/**
 * Reads one of the three outcomes of a match as copy.
 *
 * @param outcome - Outcome to name.
 * @param sides - Clubs the outcome is resolved against.
 * @returns The club abbreviation for a win, or `Draw`.
 */
function outcomeLabel(outcome: MatchOutcome, sides: PredictionSides): string {
  if (outcome === "draw") {
    return "Draw";
  }

  return sideLabel(sides[outcome]);
}

/**
 * Builds the labeller of a selection naming a half-time and a full-time
 * outcome at once.
 *
 * @remarks
 * The two outcomes are joined by a slash rather than by a word, because the
 * pair is read as a compound and nine of them sit in one list: `LIV / ARS` is
 * scannable at a glance where `Liverpool then Arsenal` is a sentence.
 *
 * @param half - Outcome standing at half-time.
 * @param full - Outcome standing at full-time.
 * @returns A labeller resolving both outcomes against a fixture's two sides.
 */
function sequenceLabeller(
  half: MatchOutcome,
  full: MatchOutcome,
): SelectionLabeller {
  return (sides) =>
    `${outcomeLabel(half, sides)} / ${outcomeLabel(full, sides)}`;
}

/**
 * Builds the yes/no labels of one goal-line market.
 *
 * @remarks
 * The stored selections are `yes` and `no`, which say nothing on their own in a
 * market whose question is the goal line. Naming the line in the label is what
 * lets three goal-line markets sit in the same panel without their bars being
 * indistinguishable.
 *
 * @param line - Goal line the market is settled on, such as `2.5`.
 * @returns The two labels that override the shared yes/no copy.
 */
function goalLineLabels(
  line: string,
): Partial<Record<PredictionSelection, SelectionLabeller>> {
  return {
    yes: () => `Over ${line}`,
    no: () => `Under ${line}`,
  };
}

const SHARED_SELECTION_LABELS: Record<PredictionSelection, SelectionLabeller> =
  {
    home: (sides) => outcomeLabel("home", sides),
    draw: (sides) => outcomeLabel("draw", sides),
    away: (sides) => outcomeLabel("away", sides),
    home_or_draw: (sides) => `${sideLabel(sides.home)} or draw`,
    draw_or_away: (sides) => `Draw or ${sideLabel(sides.away)}`,
    home_or_away: (sides) =>
      `${sideLabel(sides.home)} or ${sideLabel(sides.away)}`,
    no_goal: () => "No goal",
    yes: () => "Yes",
    no: () => "No",
    home_then_home: sequenceLabeller("home", "home"),
    home_then_draw: sequenceLabeller("home", "draw"),
    home_then_away: sequenceLabeller("home", "away"),
    draw_then_home: sequenceLabeller("draw", "home"),
    draw_then_draw: sequenceLabeller("draw", "draw"),
    draw_then_away: sequenceLabeller("draw", "away"),
    away_then_home: sequenceLabeller("away", "home"),
    away_then_draw: sequenceLabeller("away", "draw"),
    away_then_away: sequenceLabeller("away", "away"),
    score_0_0: () => "0-0",
    score_0_1: () => "0-1",
    score_0_2: () => "0-2",
    score_0_3: () => "0-3",
    score_1_0: () => "1-0",
    score_1_1: () => "1-1",
    score_1_2: () => "1-2",
    score_1_3: () => "1-3",
    score_2_0: () => "2-0",
    score_2_1: () => "2-1",
    score_2_2: () => "2-2",
    score_2_3: () => "2-3",
    score_3_0: () => "3-0",
    score_3_1: () => "3-1",
    score_3_2: () => "3-2",
    score_3_3: () => "3-3",
    any_other_home_win: () => "Any other home win",
    any_other_draw: () => "Any other draw",
    any_other_away_win: () => "Any other away win",
  };

const MARKET_SELECTION_LABELS: Record<
  PredictionMarket,
  Partial<Record<PredictionSelection, SelectionLabeller>> | null
> = {
  fulltime_result: null,
  double_chance: null,
  both_teams_to_score: null,
  over_under_1_5: goalLineLabels("1.5"),
  over_under_2_5: goalLineLabels("2.5"),
  over_under_3_5: goalLineLabels("3.5"),
  over_under_4_5: goalLineLabels("4.5"),
  team_to_score_first: null,
  first_half_result: null,
  half_time_full_time: null,
  correct_score: null,
};

/**
 * Reads the name of a prediction market.
 *
 * @remarks
 * The copy is a total map over the market union rather than a lookup with a
 * fallback, so adding a market to {@link PREDICTION_MARKETS} does not compile
 * until it has been named. A fallback would have shipped the wire value —
 * `over_under_4_5` — into the interface instead, and nothing would have
 * failed to warn about it.
 *
 * @param market - Market to name.
 * @returns The market's name as the interface shows it.
 */
export function marketLabel(market: PredictionMarket): string {
  return MARKET_LABELS[market];
}

/**
 * Reads the name of one selection inside a market.
 *
 * @remarks
 * The label depends on both the market and the fixture, which is why this is a
 * function rather than a constant. One stored selection means two different
 * things in two markets — `yes` reads `Over 2.5` in a goal-line market and
 * `Yes` in both-teams-to-score — and an outcome naming a club has to name
 * *that* club, so `home` reads `LIV` rather than the word `Home`.
 *
 * Both maps behind this are total over their union: every selection carries
 * shared copy, and every market states whether it overrides any of it, with
 * `null` for the majority that do not. A market or a selection added to the
 * vocabulary therefore fails to compile until it has been given copy, which is
 * the whole reason the lookup is not a `switch` with a `default`.
 *
 * @param market - Market the selection belongs to, which can change the copy.
 * @param selection - Selection to name.
 * @param sides - Clubs the selection is resolved against.
 * @returns The selection's name as the interface shows it.
 */
export function selectionLabel(
  market: PredictionMarket,
  selection: PredictionSelection,
  sides: PredictionSides,
): string {
  const overrides = MARKET_SELECTION_LABELS[market];
  const labeller = overrides?.[selection] ?? SHARED_SELECTION_LABELS[selection];

  return labeller(sides);
}
