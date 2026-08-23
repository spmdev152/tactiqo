import "server-only";

import { toPlatformHealth } from "@/features/health/mappers/platform-health";
import type { PlatformHealth } from "@/features/health/types/platform-health";
import { getBackendApiBaseUrl } from "@/lib/env";

const HEALTH_PATH = "/health";

const PROBE_TIMEOUT_MS = 3_000;

/**
 * Probes backend platform health from the server.
 *
 * @remarks
 * A health probe is never cached: a stale "operational" answer would be worse
 * than no answer. A transport failure is normalized into the unreported branch
 * of {@link PlatformHealth}, and a body that cannot be decoded is reported as a
 * contract mismatch rather than as an unreachable API, so rendering this feature
 * cannot break a page or a production build when the API misbehaves.
 *
 * @returns The normalized platform health for the configured backend.
 */
export async function getPlatformHealth(): Promise<PlatformHealth> {
  const baseUrl = getBackendApiBaseUrl();

  if (baseUrl === null) {
    return {
      reported: false,
      reason: "BACKEND_API_BASE_URL is not configured for this environment.",
    };
  }

  try {
    const response = await fetch(`${baseUrl}${HEALTH_PATH}`, {
      cache: "no-store",
      headers: { accept: "application/json" },
      signal: AbortSignal.timeout(PROBE_TIMEOUT_MS),
    });

    if (!response.ok) {
      return {
        reported: false,
        reason: `The API answered the health probe with HTTP ${response.status}.`,
      };
    }

    let payload: unknown;

    try {
      payload = await response.json();
    } catch {
      payload = undefined;
    }

    return toPlatformHealth(payload);
  } catch {
    return {
      reported: false,
      reason: "The API could not be reached.",
    };
  }
}
