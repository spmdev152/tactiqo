import "server-only";

import { cookies } from "next/headers";

import { SESSION_COOKIE_NAME } from "@/features/auth/domain/session-cookie-name";
import { isSessionCookieInsecure } from "@/lib/env";

/**
 * Reads the session token carried by the current request.
 *
 * @remarks
 * An empty value counts as no token. `tactiqo_session=` is a cookie the
 * browser still sends and `cookies().get` reports as `""`, so returning it
 * verbatim would spend a backend round trip on a token that cannot
 * authenticate anything, and would tell the login page a session was lost when
 * none was ever held.
 *
 * @returns The opaque session token, or `null` when the request carries no
 * usable session cookie.
 */
export async function readSessionToken(): Promise<string | null> {
  const cookieStore = await cookies();

  const value = cookieStore.get(SESSION_COOKIE_NAME)?.value;

  return value === undefined || value === "" ? null : value;
}

/**
 * Stores a session token in the browser until the backend expires it.
 *
 * @remarks
 * `httpOnly` keeps the token out of reach of browser JavaScript, which is the
 * whole reason the token never travels to a Client Component: an XSS payload
 * cannot read a cookie it is not allowed to see. `sameSite: "lax"` blocks the
 * cookie on cross-site subrequests while still allowing a normal top-level
 * navigation into the application.
 *
 * `secure` is on unless {@link isSessionCookieInsecure} says otherwise, so an
 * insecure cookie is now a deliberate declaration in the environment rather
 * than a side effect of which command built the bundle. Deriving it from
 * `NODE_ENV` tied a transport control to a build mode, and the `Dockerfile`
 * pins that mode to `development`.
 *
 * `path` is `/` and no `domain` is set, which is exactly the shape the
 * `__Host-` cookie prefix requires. Renaming the cookie to claim that
 * guarantee stays available later without changing anything else here.
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
    secure: !isSessionCookieInsecure(),
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
