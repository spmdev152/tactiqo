/**
 * Every state the platform reports for a match, as the API serializes them.
 *
 * @remarks
 * A closed vocabulary the backend owns, kept here as one tuple so the wire
 * schema and the product type cannot drift apart: the schema validates against
 * it and the type is derived from it.
 *
 * The five members are the platform's own, not the provider's. Sportmonks
 * publishes twenty-five states, and collapsing them happens at the provider
 * boundary so nothing above it has to know that a match at half-time and a
 * match in a penalty break are both simply under way.
 */
export const FIXTURE_STATUSES = [
  "scheduled",
  "live",
  "finished",
  "postponed",
  "cancelled",
] as const;

/**
 * State of a match.
 */
export type FixtureStatus = (typeof FIXTURE_STATUSES)[number];

const KICKED_OFF_STATUSES: readonly FixtureStatus[] = ["live", "finished"];

/**
 * Reports whether the match has started, so anything read about it now is a
 * reading of a match already under way or over.
 *
 * @remarks
 * The question this answers is not "is the match over" but "has the match
 * happened", because that is what decides whether a figure about the two sides
 * is a forecast or a retrospective. Two of the five states qualify and the three
 * that do not each fail for their own reason.
 *
 * `finished` is the obvious member. `live` is the one worth stating: a match
 * under way is not over, but its pre-match form stopped counting at kick-off
 * just as a finished match's did, so every claim about what the two sides
 * brought into it is already settled and will not move again.
 *
 * `postponed` and `cancelled` are excluded even though their published kick-off
 * may be long past, and this is the case the rule exists for. Neither match was
 * played at that instant, so there is no moment "before it" to read anything up
 * to: a postponed match will be played on some later date and carry its sides'
 * form as it stands then, and a cancelled one never will. `scheduled` is
 * excluded for the same reason in a milder form, since a scheduled match whose
 * kick-off has passed is the platform lagging behind the football rather than a
 * match that was played.
 *
 * The status decides this and the clock is deliberately not consulted. Comparing
 * `kickoffAt` against `Date.now()` would make the answer depend on when a
 * component happened to render, which differs between the server pass and the
 * client one and changes under a visitor sitting on the page at kick-off, and it
 * would still need the status to tell a played match from an abandoned one. The
 * vocabulary already carries the fact.
 *
 * @param status - State the platform reports for the match.
 * @returns Whether the match has kicked off.
 */
export function hasKickedOff(status: FixtureStatus): boolean {
  return KICKED_OFF_STATUSES.includes(status);
}
