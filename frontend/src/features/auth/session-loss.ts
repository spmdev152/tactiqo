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
 * Copy shown for each involuntary arrival.
 *
 * @remarks
 * `expired` deliberately collapses expired, revoked, forged, and unreachable
 * into one sentence. `getCurrentUser` cannot distinguish them, and naming which
 * one applied would leak backend state to an unauthenticated surface.
 */
const SESSION_LOSS_MESSAGES: Record<SessionLossReason, string> = {
  expired: "Your session is no longer valid. Sign in again to continue.",
  required: "Sign in to open that page.",
};

/**
 * Narrows a raw parameter value to a reason the product recognises.
 *
 * @param value - Parameter value received from the visitor.
 * @returns Whether the value names a known reason.
 */
function isSessionLossReason(value: string): value is SessionLossReason {
  return Object.hasOwn(SESSION_LOSS_MESSAGES, value);
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
 * Resolves the warning copy an arrival at the sign-in page deserves.
 *
 * @remarks
 * `Object.hasOwn` rather than `in`, so an inherited key such as `toString`
 * cannot resolve to a message. A repeated parameter arrives as an array and a
 * deliberate arrival carries nothing; both mean no toast.
 *
 * @param value - Raw parameter value, as `searchParams` supplies it.
 * @returns The message to show, or `null` when no toast is warranted.
 */
export function sessionLossMessage(
  value: string | string[] | undefined,
): string | null {
  if (typeof value !== "string" || !isSessionLossReason(value)) {
    return null;
  }

  return SESSION_LOSS_MESSAGES[value];
}
