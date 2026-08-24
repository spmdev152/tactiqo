import "server-only";

import {
  clearSessionCookie,
  readSessionToken,
} from "@/features/auth/server/session-cookie";
import { getBackendApiBaseUrl } from "@/lib/env";

const LOGOUT_PATH = "/auth/logout";

const LOGOUT_TIMEOUT_MS = 5_000;

/**
 * Ends the current session on the backend and in the browser.
 *
 * @remarks
 * Revoking server-side comes first, so a token that was copied out of the
 * process stops working rather than merely becoming unreachable from this
 * browser. Clearing the cookie is unconditional: if the backend call fails, the
 * visitor must still end up signed out locally instead of stranded with a
 * cookie the interface keeps sending. That leaves a session row alive until it
 * expires, which the backend's own expiry already bounds, and is the lesser of
 * the two failures.
 */
export async function signOut(): Promise<void> {
  const token = await readSessionToken();
  const baseUrl = getBackendApiBaseUrl();

  if (token !== null && baseUrl !== null) {
    try {
      await fetch(`${baseUrl}${LOGOUT_PATH}`, {
        method: "POST",
        cache: "no-store",
        headers: { authorization: `Bearer ${token}` },
        signal: AbortSignal.timeout(LOGOUT_TIMEOUT_MS),
      });
    } catch {}
  }

  await clearSessionCookie();
}
