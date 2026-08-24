import {
  leagueListPayloadSchema,
  type LeaguePayload,
} from "@/features/fixtures/schemas/leagues";
import type { League, LeaguesResult } from "@/features/fixtures/types/league";

const CONTRACT_MISMATCH_REASON =
  "The API returned a payload that does not match the leagues contract.";

/**
 * Normalizes one decoded league payload into the product contract.
 *
 * @param payload - League as the transport carries it.
 * @returns The normalized competition.
 */
export function toLeague(payload: LeaguePayload): League {
  return {
    id: payload.id,
    name: payload.name,
    shortCode: payload.short_code,
    logoUrl: payload.logo_url,
    countryName: payload.country_name,
    countryFlagUrl: payload.country_flag_url,
  };
}

/**
 * Normalizes a raw leagues response body into the product result.
 *
 * @remarks
 * An unrecognized payload becomes the unavailable branch rather than an empty
 * list. A silently empty competition filter would tell the visitor the platform
 * covers nothing, which is a stronger and falser claim than admitting the
 * answer could not be read.
 *
 * @param payload - Decoded JSON body returned by `GET /api/v1/leagues`.
 * @returns The normalized competitions, or the reason they are unavailable.
 */
export function toLeagues(payload: unknown): LeaguesResult {
  const decoded = leagueListPayloadSchema.safeParse(payload);

  if (!decoded.success) {
    return { loaded: false, reason: CONTRACT_MISMATCH_REASON };
  }

  return { loaded: true, leagues: decoded.data.map(toLeague) };
}
