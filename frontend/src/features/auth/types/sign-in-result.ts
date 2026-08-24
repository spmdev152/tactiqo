import type { AuthenticatedUser } from "@/features/auth/types/authenticated-user";

/**
 * Why a sign-in attempt did not produce a session.
 *
 * @remarks
 * Every reason is distinguishable on purpose. `invalid-credentials` is the only
 * one the visitor can act on by retyping, and it deliberately covers an unknown
 * e-mail, a wrong password, and a deactivated account alike, because the
 * backend refuses to tell those apart. The remaining reasons describe a broken
 * environment rather than a broken attempt, and separating them is what makes
 * an unreachable API distinguishable from an API that answered with something
 * this application cannot read.
 */
export type SignInFailureReason =
  | "backend-not-configured"
  | "api-unreachable"
  | "invalid-credentials"
  | "unexpected-status"
  | "undecodable-body"
  | "contract-mismatch";

/**
 * Session material returned by a successful sign-in.
 */
export interface SignInSuccess {
  readonly ok: true;
  readonly token: string;
  readonly expiresAt: Date;
  readonly user: AuthenticatedUser;
}

/**
 * Outcome of a sign-in attempt that produced no session.
 */
export interface SignInFailure {
  readonly ok: false;
  readonly reason: SignInFailureReason;
}

/**
 * Outcome of a sign-in attempt.
 *
 * @remarks
 * A discriminated union rather than a nullable token, so a caller cannot read
 * the session material without having handled the failure branch first.
 */
export type SignInResult = SignInSuccess | SignInFailure;
