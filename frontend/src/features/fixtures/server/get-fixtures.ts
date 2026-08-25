import "server-only";

import { readSessionToken } from "@/features/auth/server/session-cookie";
import { toFixtures } from "@/features/fixtures/mappers/fixture";
import type { FixturesResult } from "@/features/fixtures/types/fixture";
import { getBackendApiBaseUrl } from "@/lib/env";

const FIXTURES_PATH = "/fixtures";

const FIXTURES_DAY_QUERY = "date";

const FIXTURES_LEAGUE_QUERY = "league_id";

const FIXTURES_TIMEOUT_MS = 8_000;

const UNSENDABLE_REASON = "The fixtures request could not be sent.";

const UNCONFIGURED_LOG =
  "BACKEND_API_BASE_URL is not configured; the fixtures request was not attempted.";

/**
 * Scope of one fixture-list request.
 */
export interface FixtureQuery {
  /** UTC calendar day to list, as `YYYY-MM-DD`. */
  readonly day: string;

  /** Internal league identifiers, empty for every competition. */
  readonly leagueIds: readonly number[];
}

/**
 * Reads the fixtures kicking off on one UTC calendar day.
 *
 * @remarks
 * Never throws. This is the subject of the route, so a failure still has to
 * render: an unreachable API, an error status, an undecodable body and a payload
 * that does not match the contract all become the unavailable branch of
 * {@link FixturesResult}, and the list component turns that into an error state
 * the visitor can act on.
 *
 * The two failure shapes are kept apart deliberately. A body that cannot be
 * decoded is a contract problem and is reported as one by the mapper, while only
 * a genuine transport failure claims the API could not be reached; conflating
 * them would send somebody to check the network for a schema change.
 *
 * Every reason reaches the visitor, so none of them names a server-side
 * variable. A misconfigured deployment is reported to the operator through the
 * server log, where the name of the missing variable is useful, and to the
 * visitor as a request that could not be sent, which is all they can act on.
 *
 * `cache: "no-store"` because the request is authenticated and carries a bearer
 * token, so a stored response is one visitor's answer waiting to be served to
 * another.
 *
 * The query names are declared here rather than imported from `domain/`. Two
 * vocabularies happen to overlap: the route's own search parameters are `date`
 * and `league`, while the backend accepts `date` and `league_id`. Sharing a
 * constant across them would make the API contract change whenever the address
 * bar was tidied up.
 *
 * @param query - Day and competition the list is scoped to.
 * @returns The fixtures of that day, or the reason they are unavailable.
 */
export async function getFixtures(
  query: FixtureQuery,
): Promise<FixturesResult> {
  const baseUrl = getBackendApiBaseUrl();

  if (baseUrl === null) {
    console.error(UNCONFIGURED_LOG);

    return {
      loaded: false,
      reason: UNSENDABLE_REASON,
    };
  }

  const token = await readSessionToken();

  if (token === null) {
    return {
      loaded: false,
      reason: "The request carries no session to read fixtures with.",
    };
  }

  const search = new URLSearchParams({ [FIXTURES_DAY_QUERY]: query.day });

  for (const leagueId of query.leagueIds) {
    search.append(FIXTURES_LEAGUE_QUERY, String(leagueId));
  }

  try {
    const response = await fetch(
      `${baseUrl}${FIXTURES_PATH}?${search.toString()}`,
      {
        cache: "no-store",
        headers: {
          accept: "application/json",
          authorization: `Bearer ${token}`,
        },
        signal: AbortSignal.timeout(FIXTURES_TIMEOUT_MS),
      },
    );

    if (!response.ok) {
      return {
        loaded: false,
        reason: `The API answered the fixtures request with HTTP ${response.status}.`,
      };
    }

    let payload: unknown;

    try {
      payload = await response.json();
    } catch {
      payload = undefined;
    }

    return toFixtures(payload);
  } catch {
    return {
      loaded: false,
      reason: "The API could not be reached.",
    };
  }
}
