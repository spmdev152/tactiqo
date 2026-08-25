import { z } from "zod";

/**
 * Wire contract of one league in `GET /api/v1/leagues`.
 *
 * @remarks
 * Mirrors the transport payload and nothing else, snake_case included. Product
 * code consumes the normalized `League` contract instead, so a backend field
 * rename stops at the mapper.
 */
export const leaguePayloadSchema = z.object({
  id: z.number().int().positive(),
  name: z.string().min(1),
  short_code: z.string(),
  logo_url: z.string(),
  country_name: z.string(),
  country_flag_url: z.string(),
});

/**
 * Wire contract of the `GET /api/v1/leagues` response body.
 */
export const leagueListPayloadSchema = z.array(leaguePayloadSchema);

/**
 * Decoded shape of one league as the transport carries it.
 */
export type LeaguePayload = z.infer<typeof leaguePayloadSchema>;
