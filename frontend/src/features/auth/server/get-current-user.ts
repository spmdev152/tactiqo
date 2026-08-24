import "server-only";

import { cache } from "react";

import { toAuthenticatedUser } from "@/features/auth/mappers/authenticated-user";
import { authenticatedUserPayloadSchema } from "@/features/auth/schemas/authenticated-user";
import { readSessionToken } from "@/features/auth/server/session-cookie";
import type { AuthenticatedUser } from "@/features/auth/types/authenticated-user";
import { getBackendApiBaseUrl } from "@/lib/env";

const CURRENT_USER_PATH = "/auth/me";

const CURRENT_USER_TIMEOUT_MS = 5_000;

/**
 * Resolves the user the current request is authenticated as.
 *
 * @remarks
 * The backend is the authority: a cookie proves nothing until `/auth/me`
 * accepts the token, which is why an expired or revoked session is discovered
 * here and not in the proxy. A `401` is a normal answer meaning the
 * session is gone, so it produces `null` rather than an error, and every other
 * failure produces `null` as well: no page may render authenticated content on
 * the strength of a session this function could not confirm.
 *
 * `cache: "no-store"` and React's `cache` answer different questions and
 * compose rather than fight. `no-store` forbids reusing the backend's response
 * across requests, because a stored answer would keep a revoked session alive
 * for the lifetime of the entry. The memo forbids asking twice inside one
 * request, so the next navigation still asks the backend and still discovers a
 * session revoked in between. Each route is its own only caller today, so the
 * memo saves nothing yet; it is here so that a second reader, a layout
 * greeting the visitor above a page that gates on the session, cannot quietly
 * double the round trips.
 *
 * @returns The authenticated user, or `null` when there is no usable session.
 */
export const getCurrentUser = cache(
  async function getCurrentUser(): Promise<AuthenticatedUser | null> {
    const token = await readSessionToken();

    if (token === null) {
      return null;
    }

    const baseUrl = getBackendApiBaseUrl();

    if (baseUrl === null) {
      return null;
    }

    try {
      const response = await fetch(`${baseUrl}${CURRENT_USER_PATH}`, {
        cache: "no-store",
        headers: {
          accept: "application/json",
          authorization: `Bearer ${token}`,
        },
        signal: AbortSignal.timeout(CURRENT_USER_TIMEOUT_MS),
      });

      if (!response.ok) {
        return null;
      }

      const decoded = authenticatedUserPayloadSchema.safeParse(
        await response.json(),
      );

      if (!decoded.success) {
        return null;
      }

      return toAuthenticatedUser(decoded.data);
    } catch {
      return null;
    }
  },
);
