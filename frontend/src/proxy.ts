import { type NextRequest, NextResponse } from "next/server";

import { SESSION_COOKIE_NAME } from "@/features/auth/session-cookie-name";

const LOGIN_PATH = "/login";

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
 * carries a cookie away from `/login` looks symmetrical and is a redirect loop:
 * the login page would bounce it to `/`, `HomePage` would find the session
 * unusable and bounce it back, and neither side can break the tie because only
 * one of them can verify the token. A revoked session, an expired token, or an
 * unreachable API therefore used to end in `ERR_TOO_MANY_REDIRECTS` instead of
 * the login form. This direction is monotonic and cannot loop, since `/login`
 * is the only exempt path and the only target.
 *
 * The pages remain the authoritative check: a cookie holding an expired,
 * revoked, or forged token passes this filter and is rejected by
 * `getCurrentUser`, which asks the backend. Never grant access on the strength
 * of this function alone.
 *
 * @param request - Incoming navigation request.
 * @returns A redirect to the login page when no session cookie is present,
 * otherwise an instruction to continue.
 */
export function proxy(request: NextRequest) {
  const hasSessionCookie = request.cookies.has(SESSION_COOKIE_NAME);
  const isLoginRoute = request.nextUrl.pathname === LOGIN_PATH;

  if (!hasSessionCookie && !isLoginRoute) {
    return NextResponse.redirect(new URL(LOGIN_PATH, request.url));
  }

  return NextResponse.next();
}
