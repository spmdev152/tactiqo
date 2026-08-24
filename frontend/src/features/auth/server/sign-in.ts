import "server-only";

import { toAuthenticatedUser } from "@/features/auth/mappers/authenticated-user";
import { signInPayloadSchema } from "@/features/auth/schemas/sign-in";
import type { SignInResult } from "@/features/auth/types/sign-in-result";
import { getBackendApiBaseUrl } from "@/lib/env";

const LOGIN_PATH = "/auth/login";

const LOGIN_TIMEOUT_MS = 5_000;

const UNAUTHORIZED_STATUS = 401;

/**
 * Exchanges credentials for a backend session.
 *
 * @remarks
 * Never throws and never returns the backend's own response. Whatever goes
 * wrong is narrowed to a {@link SignInResult} failure reason, so the interface
 * can pick its own copy and an unreachable API cannot take down the route with
 * an unhandled rejection. The backend answers every rejected credential with
 * the same `401`, and this function preserves that: it does not attempt to read
 * the error body, so nothing here can turn an unknown e-mail into a different
 * message than a wrong password.
 *
 * @param email - E-mail address typed by the visitor.
 * @param password - Password typed by the visitor.
 * @returns The session material on success, or the reason it failed.
 */
export async function signIn(
  email: string,
  password: string,
): Promise<SignInResult> {
  const baseUrl = getBackendApiBaseUrl();

  if (baseUrl === null) {
    return { ok: false, reason: "backend-not-configured" };
  }

  let response: Response;

  try {
    response = await fetch(`${baseUrl}${LOGIN_PATH}`, {
      method: "POST",
      cache: "no-store",
      headers: {
        accept: "application/json",
        "content-type": "application/json",
      },
      body: JSON.stringify({ email, password }),
      signal: AbortSignal.timeout(LOGIN_TIMEOUT_MS),
    });
  } catch {
    return { ok: false, reason: "api-unreachable" };
  }

  if (response.status === UNAUTHORIZED_STATUS) {
    return { ok: false, reason: "invalid-credentials" };
  }

  if (!response.ok) {
    return { ok: false, reason: "unexpected-status" };
  }

  let payload: unknown;

  try {
    payload = await response.json();
  } catch {
    return { ok: false, reason: "undecodable-body" };
  }

  const decoded = signInPayloadSchema.safeParse(payload);

  if (!decoded.success) {
    return { ok: false, reason: "contract-mismatch" };
  }

  return {
    ok: true,
    token: decoded.data.token,
    expiresAt: new Date(decoded.data.expires_at),
    user: toAuthenticatedUser(decoded.data.user),
  };
}
