import { z } from "zod";

import { leaguePayloadSchema } from "@/features/fixtures/schemas/leagues";

/**
 * Wire contract of one side of a fixture.
 */
export const fixtureTeamPayloadSchema = z.object({
  id: z.number().int().positive(),
  name: z.string().min(1),
  short_code: z.string(),
  crest_url: z.string(),
});

/**
 * Wire contract of one fixture in `GET /api/v1/fixtures`.
 *
 * @remarks
 * `kickoff_at` is validated as an ISO-8601 instant with an offset rather than
 * as a plain string, because the whole point of the field is that it names an
 * absolute moment. A value with no offset would be read differently by the
 * server and the browser, and the mismatch would surface as a kick-off time an
 * hour out rather than as an error.
 */
export const fixturePayloadSchema = z.object({
  id: z.number().int().positive(),
  kickoff_at: z.iso.datetime({ offset: true }),
  league: leaguePayloadSchema,
  home_team: fixtureTeamPayloadSchema,
  away_team: fixtureTeamPayloadSchema,
});

/**
 * Wire contract of the `GET /api/v1/fixtures` response body.
 */
export const fixtureListPayloadSchema = z.array(fixturePayloadSchema);

/**
 * Decoded shape of one fixture as the transport carries it.
 */
export type FixturePayload = z.infer<typeof fixturePayloadSchema>;

/**
 * Decoded shape of one fixture side as the transport carries it.
 */
export type FixtureTeamPayload = z.infer<typeof fixtureTeamPayloadSchema>;
