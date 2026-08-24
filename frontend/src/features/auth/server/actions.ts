"use server";

import { redirect } from "next/navigation";

import { credentialsSchema } from "@/features/auth/schemas/credentials";
import { writeSessionCookie } from "@/features/auth/server/session-cookie";
import { signIn } from "@/features/auth/server/sign-in";
import { signOut } from "@/features/auth/server/sign-out";
import type { SignInActionResult } from "@/features/auth/types/sign-in-action-result";

/**
 * Signs a visitor in from the login form and redirects to the application.
 *
 * @remarks
 * The credentials never reach the browser bundle: the backend call, the schema
 * validation, and the cookie write all happen here. The argument is typed
 * `unknown` on purpose, because a Server Action is a public endpoint and its
 * payload is whatever the caller chose to send, not whatever the form component
 * intended to send.
 *
 * `redirect` signals the navigation by throwing, so it deliberately sits after
 * every `try` in this function. Wrapping it would swallow the redirect and
 * return a failure instead of navigating.
 *
 * @param payload - Credentials submitted by the caller, validated here.
 * @returns The reason the attempt failed; a successful attempt redirects
 * instead of returning.
 */
export async function signInAction(
  payload: unknown,
): Promise<SignInActionResult> {
  const credentials = credentialsSchema.safeParse(payload);

  if (!credentials.success) {
    return { error: "malformed-request" };
  }

  const result = await signIn(
    credentials.data.email,
    credentials.data.password,
  );

  if (!result.ok) {
    return { error: result.reason };
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
