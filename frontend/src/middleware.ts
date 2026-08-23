import { type NextRequest, NextResponse } from "next/server";

import { SESSION_COOKIE_NAME } from "@/features/auth/session-cookie-name";

const LOGIN_PATH = "/login";

const HOME_PATH = "/";

/**
 * Limits the middleware to page navigations.
 *
 * @remarks
 * The pattern excludes every Next.js internal path, the API routes, and any
 * path with a file extension, so static assets, images, and the development
 * hot-reload channel are served without paying for a middleware invocation and
 * without ever being redirected to the login page. Nothing under `_next` is a
 * product surface, so narrowing the exclusion to `_next/static` and
 * `_next/image` would gate framework traffic on a session for no benefit.
 */
export const config = {
  matcher: ["/((?!_next|api|.*\\.).*)"],
};

/**
 * Steers a request towards the login page or the application by cookie alone.
 *
 * @remarks
 * Optimistic on purpose. The middleware runs on every navigation, and
 * validating a session token there would mean a backend round trip before any
 * page could start rendering. It therefore only asks whether a session cookie
 * exists, which is enough to spare an unauthenticated visitor a redirect
 * rendered by the page itself.
 *
 * The pages remain the authoritative check: a cookie holding an expired,
 * revoked, or forged token passes this filter and is rejected by
 * `getCurrentUser`, which asks the backend. Never grant access on the strength
 * of this function alone.
 *
 * @param request - Incoming navigation request.
 * @returns A redirect when the cookie and the target path disagree, otherwise
 * an instruction to continue.
 */
export function middleware(request: NextRequest) {
  const hasSessionCookie = request.cookies.has(SESSION_COOKIE_NAME);
  const isLoginRoute = request.nextUrl.pathname === LOGIN_PATH;

  if (!hasSessionCookie && !isLoginRoute) {
    return NextResponse.redirect(new URL(LOGIN_PATH, request.url));
  }

  if (hasSessionCookie && isLoginRoute) {
    return NextResponse.redirect(new URL(HOME_PATH, request.url));
  }

  return NextResponse.next();
}
