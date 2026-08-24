/**
 * Path of the sign-in page every session-loss redirect targets.
 */
export const LOGIN_PATH = "/login";

/**
 * Search parameter that carries why a visitor was sent to the sign-in page.
 *
 * @remarks
 * A search parameter rather than a cookie, because both redirecting sides have
 * to use the same channel and only one of them could set a cookie:
 * `NextResponse` can, a Server Component cannot set cookies at all.
 *
 * It is therefore visitor-controllable. That is acceptable because the value
 * only decides whether a toast appears, and {@link sessionLossMessage} answers
 * from a closed set, so a forged or unrecognised value produces no toast and
 * never reaches the DOM.
 */
export const SESSION_LOSS_PARAMETER = "session";

/**
 * Why a visitor lost their session without asking to.
 *
 * @remarks
 * Only involuntary arrivals are named. A deliberate sign-out and a first visit
 * to the sign-in page carry no reason, which is the whole point of the
 * parameter: three of the four ways to reach `/login` send no cookie, so the
 * absence of a cookie cannot tell them apart and the redirecting side has to
 * say.
 */
export type SessionLossReason = "expired" | "required";

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
 * Copy shown for each involuntary arrival.
 *
 * @remarks
 * `expired` deliberately collapses expired, revoked, forged, and unreachable
 * into one title. `getCurrentUser` cannot distinguish them, and naming which
 * one applied would leak backend state to an unauthenticated surface.
 *
 * `required` is not titled "Session expired", even though a browser dropping an
 * expired cookie is the likeliest cause. The branch also covers a link or a
 * bookmark followed by somebody who never had a session, and telling them one
 * expired would be the same class of lie as telling somebody who just signed
 * out to sign in again.
 */
const SESSION_LOSS_WARNINGS: Record<SessionLossReason, SessionLossWarning> = {
  expired: {
    title: "Session expired",
    description: "Sign in again to access the platform.",
  },
  required: {
    title: "Sign in required",
    description: "Sign in to access the platform.",
  },
};

/**
 * Narrows a raw parameter value to a reason the product recognises.
 *
 * @param value - Parameter value received from the visitor.
 * @returns Whether the value names a known reason.
 */
function isSessionLossReason(value: string): value is SessionLossReason {
  return Object.hasOwn(SESSION_LOSS_WARNINGS, value);
}

/**
 * Builds the sign-in destination for an involuntary session loss.
 *
 * @param reason - Why the visitor is being redirected.
 * @returns The login path carrying the reason.
 */
export function loginPathAfterSessionLoss(reason: SessionLossReason): string {
  return `${LOGIN_PATH}?${SESSION_LOSS_PARAMETER}=${reason}`;
}

/**
 * Resolves the warning an arrival at the sign-in page deserves.
 *
 * @remarks
 * `Object.hasOwn` rather than `in`, so an inherited key such as `toString`
 * cannot resolve to a warning. A repeated parameter arrives as an array and a
 * deliberate arrival carries nothing; both mean no toast.
 *
 * @param value - Raw parameter value, as `searchParams` supplies it.
 * @returns The warning to show, or `null` when no toast is warranted.
 */
export function sessionLossWarning(
  value: string | string[] | undefined,
): SessionLossWarning | null {
  if (typeof value !== "string" || !isSessionLossReason(value)) {
    return null;
  }

  return SESSION_LOSS_WARNINGS[value];
}
