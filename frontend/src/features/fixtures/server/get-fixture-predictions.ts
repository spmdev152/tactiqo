import "server-only";

import { readSessionToken } from "@/features/auth/server/session-cookie";
import { toFixturePredictions } from "@/features/fixtures/mappers/prediction";
import type { FixturePredictionsResult } from "@/features/fixtures/types/prediction";
import { getBackendApiBaseUrl } from "@/lib/env";

const FIXTURES_PATH = "/fixtures";

const PREDICTIONS_PATH = "predictions";

const PREDICTIONS_TIMEOUT_MS = 6_000;

const UNSENDABLE_REASON = "The predictions request could not be sent.";

const UNCONFIGURED_LOG =
  "BACKEND_API_BASE_URL is not configured; the predictions request was not attempted.";

/**
 * Reads the prediction probabilities the platform holds for one fixture.
 *
 * @remarks
 * Never throws. This is not the subject of the route, but it is on the critical
 * path of an interaction the visitor started and is waiting on, so a failure
 * still has to render: an unreachable API, an error status, an undecodable body
 * and a payload that does not match the contract all become the unavailable
 * branch of {@link FixturePredictionsResult}, and the panel turns that into a
 * state the visitor can act on.
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
 * The timeout sits between the fixtures read's eight seconds and the leagues
 * read's five. The day's list is what the page is for and is worth waiting
 * longest for; the competition filter is a small, cacheable lookup. This is
 * neither: nobody arrives to see it, but somebody has already clicked and is
 * watching a spinner, and a visitor who opened the wrong row wants the answer or
 * the failure quickly rather than eventually.
 *
 * `cache: "no-store"` because the request is authenticated and carries a bearer
 * token, so a stored response is one visitor's answer waiting to be served to
 * another.
 *
 * @param fixtureId - Internal identifier of the fixture to read.
 * @returns The fixture's predictions, or the reason they are unavailable.
 */
export async function getFixturePredictions(
  fixtureId: number,
): Promise<FixturePredictionsResult> {
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
      reason: "The request carries no session to read predictions with.",
    };
  }

  try {
    const response = await fetch(
      `${baseUrl}${FIXTURES_PATH}/${fixtureId}/${PREDICTIONS_PATH}`,
      {
        cache: "no-store",
        headers: {
          accept: "application/json",
          authorization: `Bearer ${token}`,
        },
        signal: AbortSignal.timeout(PREDICTIONS_TIMEOUT_MS),
      },
    );

    if (!response.ok) {
      return {
        loaded: false,
        reason: `The API answered the predictions request with HTTP ${response.status}.`,
      };
    }

    let payload: unknown;

    try {
      payload = await response.json();
    } catch {
      payload = undefined;
    }

    return toFixturePredictions(payload);
  } catch {
    return {
      loaded: false,
      reason: "The API could not be reached.",
    };
  }
}
