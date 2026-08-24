import "server-only";

import { readSessionToken } from "@/features/auth/server/session-cookie";
import { toLeagues } from "@/features/fixtures/mappers/league";
import type { LeaguesResult } from "@/features/fixtures/types/league";
import { getBackendApiBaseUrl } from "@/lib/env";

const LEAGUES_PATH = "/leagues";

const LEAGUES_TIMEOUT_MS = 5_000;

/**
 * Reads the competitions the platform covers.
 *
 * @remarks
 * Never throws. The competition filter is one control on a page whose subject
 * is the fixture list, so an unreachable API has to disable that control rather
 * than take the route down with it; every failure is therefore normalized into
 * the unavailable branch of {@link LeaguesResult}.
 *
 * `cache: "no-store"` even though the league list barely changes. The request
 * is authenticated, and a cached response would be a response to one visitor's
 * bearer token served to the next, which is not a trade worth making for a list
 * of five rows.
 *
 * @returns The covered competitions, or the reason they are unavailable.
 */
export async function getLeagues(): Promise<LeaguesResult> {
  const baseUrl = getBackendApiBaseUrl();

  if (baseUrl === null) {
    return {
      loaded: false,
      reason: "BACKEND_API_BASE_URL is not configured for this environment.",
    };
  }

  const token = await readSessionToken();

  if (token === null) {
    return {
      loaded: false,
      reason: "The request carries no session to read competitions with.",
    };
  }

  try {
    const response = await fetch(`${baseUrl}${LEAGUES_PATH}`, {
      cache: "no-store",
      headers: {
        accept: "application/json",
        authorization: `Bearer ${token}`,
      },
      signal: AbortSignal.timeout(LEAGUES_TIMEOUT_MS),
    });

    if (!response.ok) {
      return {
        loaded: false,
        reason: `The API answered the competitions request with HTTP ${response.status}.`,
      };
    }

    let payload: unknown;

    try {
      payload = await response.json();
    } catch {
      payload = undefined;
    }

    return toLeagues(payload);
  } catch {
    return {
      loaded: false,
      reason: "The API could not be reached.",
    };
  }
}
