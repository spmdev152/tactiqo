import "server-only";

import { cookies } from "next/headers";

import { SESSION_COOKIE_NAME } from "@/features/auth/session-cookie-name";

/**
 * Reads the session token carried by the current request.
 *
 * @returns The opaque session token, or `null` when the request carries no
 * session cookie.
 */
export async function readSessionToken(): Promise<string | null> {
  const cookieStore = await cookies();

  return cookieStore.get(SESSION_COOKIE_NAME)?.value ?? null;
}

/**
 * Stores a session token in the browser until the backend expires it.
 *
 * @remarks
 * `httpOnly` keeps the token out of reach of browser JavaScript, which is the
 * whole reason the token never travels to a Client Component: an XSS payload
 * cannot read a cookie it is not allowed to see. `sameSite: "lax"` blocks the
 * cookie on cross-site subrequests while still allowing a normal top-level
 * navigation into the application, and `secure` is lifted only in development,
 * where the application is served over plain HTTP.
 *
 * The expiry mirrors the backend's own `expires_at` rather than a duration
 * chosen here, so the cookie cannot outlive the session row it points at.
 *
 * @param token - Opaque session token issued by the backend.
 * @param expiresAt - Instant at which the backend stops accepting the token.
 */
export async function writeSessionCookie(
  token: string,
  expiresAt: Date,
): Promise<void> {
  const cookieStore = await cookies();

  cookieStore.set(SESSION_COOKIE_NAME, token, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV !== "development",
    path: "/",
    expires: expiresAt,
  });
}

/**
 * Removes the session cookie from the browser.
 */
export async function clearSessionCookie(): Promise<void> {
  const cookieStore = await cookies();

  cookieStore.delete(SESSION_COOKIE_NAME);
}
