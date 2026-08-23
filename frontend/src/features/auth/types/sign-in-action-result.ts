import type { SignInFailureReason } from "@/features/auth/types/sign-in-result";

/**
 * Why the sign-in Server Action returned instead of navigating.
 *
 * @remarks
 * Widens {@link SignInFailureReason} with the one failure the action itself
 * detects. `malformed-request` is deliberately distinct from
 * `invalid-credentials`: a payload that is not a credential pair never reached
 * the backend, and reporting it as a rejected password would be a lie.
 */
export type SignInActionError = SignInFailureReason | "malformed-request";

/**
 * Outcome of a sign-in attempt that produced no session.
 *
 * @remarks
 * There is no success shape, because a successful attempt redirects rather than
 * returning: the only thing the form ever receives back is a reason.
 */
export interface SignInActionResult {
  readonly error: SignInActionError;
}
