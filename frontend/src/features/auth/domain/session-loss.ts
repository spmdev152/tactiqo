/**
 * Path of the sign-in page, and the one public route the proxy redirects to.
 */
export const LOGIN_PATH = "/login";

/**
 * Search parameter that marks an arrival at the sign-in page as involuntary.
 *
 * @remarks
 * A search parameter rather than a cookie, because both redirecting sides have
 * to use the same channel and only one of them could set a cookie:
 * `NextResponse` can, a Server Component cannot set cookies at all.
 */
export const SESSION_LOSS_PARAMETER = "session";

/**
 * The only value the parameter may carry.
 *
 * @remarks
 * It says *that* the visitor was redirected, never *what* to tell them. The
 * parameter is visitor-controllable, so anything it asserted could be forged;
 * {@link sessionLossWarning} therefore derives the copy from the request's own
 * cookie instead, and this value survives as the one bit a forger cannot lie
 * with. A deliberate sign-out and a first visit set nothing, which is the bit
 * the page cannot recover on its own: three of the four ways to reach `/login`
 * send no cookie, so the absence of one cannot tell them apart.
 */
export const SESSION_LOSS_VALUE = "lost";

/**
 * Destination for a visitor whose session was lost rather than surrendered.
 */
export const SESSION_LOSS_PATH = `${LOGIN_PATH}?${SESSION_LOSS_PARAMETER}=${SESSION_LOSS_VALUE}`;

/**
 * Warning shown for an involuntary arrival at the sign-in page.
 */
export interface SessionLossWarning {
  /** Short statement of what happened, read first and often alone. */
  readonly title: string;
  /** What the visitor has to do about it. */
  readonly description: string;
}

/**
 * Copy for an arrival that still carries a session cookie.
 *
 * @remarks
 * Deliberately collapses expired, revoked, forged, and unreachable into one
 * title. `getCurrentUser` cannot distinguish them, and naming which one applied
 * would leak backend state to an unauthenticated surface.
 */
const EXPIRED_WARNING: SessionLossWarning = {
  title: "Session expired",
  description: "Sign in again to access the platform.",
};

/**
 * Copy for an arrival that carries no session cookie at all.
 *
 * @remarks
 * Not titled "Session expired", even though a browser dropping an expired
 * cookie is the likeliest cause. This also covers a link or a bookmark followed
 * by somebody who never had a session, and telling them one expired would be
 * the same class of lie as telling somebody who just signed out to sign in
 * again.
 */
const REQUIRED_WARNING: SessionLossWarning = {
  title: "Sign in required",
  description: "Sign in to access the platform.",
};

/**
 * Resolves the warning an arrival at the sign-in page deserves.
 *
 * @remarks
 * Two independent inputs, and neither alone would do. The parameter decides
 * whether to speak at all, because a deliberate sign-out must stay silent and
 * looks identical to an involuntary arrival from the cookie alone. The cookie
 * decides what is said, because the parameter is visitor-controllable and a
 * forged `expired` would otherwise let anybody show "Session expired" to
 * somebody who never had a session — the same lie the copy above refuses to
 * tell.
 *
 * Both statements are true by construction at the point of rendering. The page
 * only reaches this after `getCurrentUser` returned `null`, so a request that
 * still carries a token carries an unusable one, and a request that carries
 * none genuinely needs a sign-in.
 *
 * A repeated parameter arrives as an array and a deliberate arrival carries
 * nothing; comparing against the single known value rejects both, along with
 * every forged string.
 *
 * @param value - Raw parameter value, as `searchParams` supplies it.
 * @param sessionTokenPresent - Whether the request still carries a session
 * token, which is what makes one of the two titles true rather than plausible.
 * @returns The warning to show, or `null` when no toast is warranted.
 */
export function sessionLossWarning(
  value: string | string[] | undefined,
  sessionTokenPresent: boolean,
): SessionLossWarning | null {
  if (value !== SESSION_LOSS_VALUE) {
    return null;
  }

  return sessionTokenPresent ? EXPIRED_WARNING : REQUIRED_WARNING;
}
