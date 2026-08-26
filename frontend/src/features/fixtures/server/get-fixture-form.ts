import "server-only";

import { readSessionToken } from "@/features/auth/server/session-cookie";
import { toFixtureForm } from "@/features/fixtures/mappers/form";
import type { FixtureFormResult } from "@/features/fixtures/types/form";
import { getBackendApiBaseUrl } from "@/lib/env";

const FIXTURES_PATH = "/fixtures";

const FORM_PATH = "form";

const FORM_TIMEOUT_MS = 8_000;

const UNSENDABLE_REASON = "The form request could not be sent.";

const UNCONFIGURED_LOG =
  "BACKEND_API_BASE_URL is not configured; the form request was not attempted.";

/**
 * Reads the pre-match form the platform holds for one fixture.
 *
 * @remarks
 * Never throws, for the reason the predictions read gives: this is not the
 * subject of the route, but it is on the critical path of an interaction the
 * visitor started and is waiting on, so a failure still has to render. An
 * unreachable API, an error status, an undecodable body and a payload that does
 * not match the contract all become the unavailable branch of
 * {@link FixtureFormResult}, and the panel turns that into a state the visitor
 * can act on.
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
 * The deadline is the longest in the codebase, matching the day's fixture list
 * rather than the predictions read's six seconds. The payload is an order of
 * magnitude larger — two sides, six windows each, twenty-five figures per
 * window — and the backend assembles it from stored match rows rather than
 * reading one prepared row per market, so a response that would have been worth
 * waiting for is not worth abandoning two seconds early.
 *
 * `cache: "no-store"` because the request is authenticated and carries a bearer
 * token, so a stored response is one visitor's answer waiting to be served to
 * another.
 *
 * @param fixtureId - Internal identifier of the fixture to read.
 * @returns The fixture's form, or the reason it is unavailable.
 */
export async function getFixtureForm(
  fixtureId: number,
): Promise<FixtureFormResult> {
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
      reason: "The request carries no session to read form with.",
    };
  }

  try {
    const response = await fetch(
      `${baseUrl}${FIXTURES_PATH}/${fixtureId}/${FORM_PATH}`,
      {
        cache: "no-store",
        headers: {
          accept: "application/json",
          authorization: `Bearer ${token}`,
        },
        signal: AbortSignal.timeout(FORM_TIMEOUT_MS),
      },
    );

    if (!response.ok) {
      return {
        loaded: false,
        reason: `The API answered the form request with HTTP ${response.status}.`,
      };
    }

    let payload: unknown;

    try {
      payload = await response.json();
    } catch {
      payload = undefined;
    }

    return toFixtureForm(payload);
  } catch {
    return {
      loaded: false,
      reason: "The API could not be reached.",
    };
  }
}
