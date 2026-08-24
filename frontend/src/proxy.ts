import { type NextRequest, NextResponse } from "next/server";

import { SESSION_COOKIE_NAME } from "@/features/auth/domain/session-cookie-name";
import {
  LOGIN_PATH,
  SESSION_LOSS_PATH,
} from "@/features/auth/domain/session-loss";

const PUBLIC_PATHS: Record<string, true> = {
  [LOGIN_PATH]: true,
  "/signup": true,
};

/**
 * Limits the proxy to page navigations.
 *
 * @remarks
 * The pattern excludes every Next.js internal path, the API routes, and any
 * path with a file extension, so static assets, images, and the development
 * hot-reload channel are served without paying for a proxy invocation and
 * without ever being redirected to the login page. Nothing under `_next` is a
 * product surface, so narrowing the exclusion to `_next/static` and
 * `_next/image` would gate framework traffic on a session for no benefit.
 */
export const config = {
  matcher: ["/((?!_next|api|.*\\.).*)"],
};

/**
 * Sends a request with no session cookie to the login page.
 *
 * @remarks
 * Named `proxy` rather than `middleware` because Next.js 16 deprecated the
 * `middleware` file convention in favour of `proxy`, and building with the old
 * name emits a deprecation warning.
 *
 * Optimistic on purpose. This runs on every navigation, and validating a session
 * token here would mean a backend round trip before any page could start
 * rendering. It therefore only asks whether a session cookie exists, which is
 * enough to spare an unauthenticated visitor a redirect rendered by the page
 * itself.
 *
 * It deliberately does the opposite redirect not at all. Sending a request that
 * carries a cookie away from a public path looks symmetrical and is a redirect
 * loop: the login page would bounce it to `/`, `HomePage` would find the session
 * unusable and bounce it back, and neither side can break the tie because only
 * one of them can verify the token. A revoked session, an expired token, or an
 * unreachable API therefore used to end in `ERR_TOO_MANY_REDIRECTS` instead of
 * the login form. This direction is monotonic and cannot loop, since every
 * target is itself a public path.
 *
 * The pages remain the authoritative check: a cookie holding an expired,
 * revoked, or forged token passes this filter and is rejected by
 * `getCurrentUser`, which asks the backend. Never grant access on the strength
 * of this function alone.
 *
 * The redirect marks the arrival involuntary, because a visitor who followed a
 * link or a bookmark into the application has to be told why the sign-in form
 * appeared. It says only that, never which message to show: the login page
 * derives that from the cookie the request carries, so the marker cannot be
 * forged into a false statement. Only this branch adds it, since letting a
 * request through must stay silent, as must the sign-out redirect the action
 * itself performs.
 *
 * @param request - Incoming navigation request.
 * @returns A redirect marking an involuntary arrival when no session cookie is
 * present, otherwise an instruction to continue.
 */
export function proxy(request: NextRequest) {
  const hasSessionCookie = request.cookies.has(SESSION_COOKIE_NAME);
  const isPublicRoute = PUBLIC_PATHS[request.nextUrl.pathname] === true;

  if (!hasSessionCookie && !isPublicRoute) {
    return NextResponse.redirect(new URL(SESSION_LOSS_PATH, request.url));
  }

  return NextResponse.next();
}
