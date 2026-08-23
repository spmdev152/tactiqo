import type { SignInFailureReason } from "@/features/auth/types/sign-in-result";

/**
 * Why the sign-in form is showing an error.
 *
 * @remarks
 * Widens {@link SignInFailureReason} with the one failure the form itself can
 * detect, before any request is made.
 */
export type SignInFormError = SignInFailureReason | "missing-credentials";

/**
 * State the sign-in Server Action returns to the form between attempts.
 *
 * @remarks
 * Carries a reason rather than a message so the copy stays in the component
 * that renders it. `email` is echoed back because React resets an uncontrolled
 * form once its action settles, and a visitor who mistyped a password should
 * not have to retype the address as well.
 */
export interface SignInFormState {
  readonly email: string;
  readonly error: SignInFormError | null;
}
