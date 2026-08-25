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
