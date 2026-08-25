import { z } from "zod";

import { FIXTURE_STATUSES } from "@/features/fixtures/domain/fixture-status";
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
 *
 * The two goal counts are independently nullable here even though the API
 * promises they move together, because a schema states what the transport may
 * carry and the mapper is where the pair is enforced. Validating the pair here
 * would reject the whole day's list over one malformed match.
 */
export const fixturePayloadSchema = z.object({
  id: z.number().int().positive(),
  kickoff_at: z.iso.datetime({ offset: true }),
  status: z.enum(FIXTURE_STATUSES),
  home_goals: z.number().int().min(0).nullable(),
  away_goals: z.number().int().min(0).nullable(),
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
