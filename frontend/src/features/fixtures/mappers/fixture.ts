import { toLeague } from "@/features/fixtures/mappers/league";
import {
  fixtureListPayloadSchema,
  type FixtureTeamPayload,
} from "@/features/fixtures/schemas/fixtures";
import type {
  Fixture,
  FixturesResult,
  FixtureTeam,
} from "@/features/fixtures/types/fixture";

const CONTRACT_MISMATCH_REASON =
  "The API returned a payload that does not match the fixtures contract.";

/**
 * Normalizes one decoded team payload into the product contract.
 *
 * @param payload - Fixture side as the transport carries it.
 * @returns The normalized side.
 */
function toFixtureTeam(payload: FixtureTeamPayload): FixtureTeam {
  return {
    id: payload.id,
    name: payload.name,
    shortCode: payload.short_code,
    crestUrl: payload.crest_url,
  };
}

/**
 * Normalizes a raw fixtures response body into the product result.
 *
 * @remarks
 * The kick-off is turned into a `Date` here and stays one from this point on,
 * so no component ever parses a timestamp of its own and no component can
 * mistake the transport format for the value.
 *
 * The backend already orders the list by kick-off and then by identifier, and
 * that order is preserved rather than re-derived: sorting again would be a
 * second, silently divergent definition of the same product decision.
 *
 * @param payload - Decoded JSON body returned by `GET /api/v1/fixtures`.
 * @returns The normalized fixtures, or the reason they are unavailable.
 */
export function toFixtures(payload: unknown): FixturesResult {
  const decoded = fixtureListPayloadSchema.safeParse(payload);

  if (!decoded.success) {
    return { loaded: false, reason: CONTRACT_MISMATCH_REASON };
  }

  const fixtures: Fixture[] = decoded.data.map((fixture) => ({
    id: fixture.id,
    kickoffAt: new Date(fixture.kickoff_at),
    league: toLeague(fixture.league),
    homeTeam: toFixtureTeam(fixture.home_team),
    awayTeam: toFixtureTeam(fixture.away_team),
  }));

  return { loaded: true, fixtures };
}
