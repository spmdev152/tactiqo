import "server-only";

import { redirect } from "next/navigation";

import { SESSION_LOSS_PATH } from "@/features/auth/domain/session-loss";
import { getCurrentUser } from "@/features/auth/server/get-current-user";
import type { AuthenticatedUser } from "@/features/auth/types/authenticated-user";

/**
 * Resolves the current user or sends the request to the sign-in page.
 *
 * @remarks
 * Every authenticated surface owes the same reaction to an unconfirmed session,
 * and the reaction carries an invariant worth stating once: an unconfirmed
 * session is an involuntary loss, whether the token expired, was revoked, was
 * forged, or the backend was unreachable, so the redirect marks the arrival as
 * such. Repeating that in each route invites one of them to redirect plainly and
 * leave the visitor with no explanation.
 *
 * It returns rather than narrowing a nullable value at the call site, because
 * `redirect` throws and TypeScript cannot see that on its own.
 *
 * @returns The user the request is authenticated as.
 */
export async function requireUser(): Promise<AuthenticatedUser> {
  const user = await getCurrentUser();

  if (user === null) {
    redirect(SESSION_LOSS_PATH);
  }

  return user;
}
