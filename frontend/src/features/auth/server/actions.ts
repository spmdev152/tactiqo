"use server";

import { redirect } from "next/navigation";

import { writeSessionCookie } from "@/features/auth/server/session-cookie";
import { signIn } from "@/features/auth/server/sign-in";
import { signOut } from "@/features/auth/server/sign-out";
import type { SignInFormState } from "@/features/auth/types/sign-in-form-state";

/**
 * Signs a visitor in from the login form and redirects to the application.
 *
 * @remarks
 * The credentials never reach the browser bundle: the form posts to this action
 * and the backend call, the schema validation, and the cookie write all happen
 * on the server. Empty fields are rejected here rather than trusted to the
 * `required` attributes, which a client can remove.
 *
 * `redirect` signals the navigation by throwing, so it deliberately sits after
 * every `try` in this function. Wrapping it would swallow the redirect and
 * return the form state instead of navigating.
 *
 * @param previousState - Form state returned by the previous attempt.
 * @param formData - Submitted login form.
 * @returns The state of the failed attempt; a successful attempt redirects
 * instead of returning.
 */
export async function signInAction(
  previousState: SignInFormState,
  formData: FormData,
): Promise<SignInFormState> {
  const email = String(formData.get("email") ?? "").trim();
  const password = String(formData.get("password") ?? "");

  if (email.length === 0 || password.length === 0) {
    return { email, error: "missing-credentials" };
  }

  const result = await signIn(email, password);

  if (!result.ok) {
    return { email, error: result.reason };
  }

  await writeSessionCookie(result.token, result.expiresAt);

  redirect("/");
}

/**
 * Signs the current visitor out and returns them to the login page.
 */
export async function signOutAction(): Promise<void> {
  await signOut();

  redirect("/login");
}
