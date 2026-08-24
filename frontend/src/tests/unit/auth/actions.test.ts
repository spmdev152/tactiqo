import { randomUUID } from "node:crypto";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SESSION_LOSS_PARAMETER } from "@/features/auth/domain/session-loss";
import { signInAction, signOutAction } from "@/features/auth/server/actions";
import type { SignInResult } from "@/features/auth/types/sign-in-result";

const EMAIL = "ada@example.com";

const { redirect, signIn, signOut, writeSessionCookie } = vi.hoisted(() => ({
  redirect: vi.fn<(path: string) => void>(),
  signIn: vi.fn<(email: string, password: string) => Promise<SignInResult>>(),
  signOut: vi.fn<() => Promise<void>>(),
  writeSessionCookie:
    vi.fn<(token: string, expiresAt: Date) => Promise<void>>(),
}));

vi.mock("next/navigation", () => ({ redirect }));

vi.mock("@/features/auth/server/sign-in", () => ({ signIn }));

vi.mock("@/features/auth/server/sign-out", () => ({ signOut }));

vi.mock("@/features/auth/server/session-cookie", () => ({
  writeSessionCookie,
}));

beforeEach(() => {
  redirect.mockReset();
  signIn.mockReset();
  signOut.mockReset();
  writeSessionCookie.mockReset();
});

describe("signInAction", () => {
  /**
   * GIVEN credentials the backend accepts
   * WHEN the sign-in action runs
   * THEN the issued session is stored with the backend's own expiry and the visitor is sent to the application
   */
  it("stores the issued session and redirects into the application", async () => {
    const token = randomUUID();

    const expiresAt = new Date("2026-09-01T12:00:00.000Z");

    signIn.mockResolvedValue({
      ok: true,
      token,
      expiresAt,
      user: { id: 1, email: EMAIL, fullName: "Ada Lovelace" },
    });

    await signInAction({ email: EMAIL, password: randomUUID() });

    expect(writeSessionCookie).toHaveBeenCalledWith(token, expiresAt);
    expect(writeSessionCookie.mock.calls[0][1]).toBe(expiresAt);
    expect(redirect).toHaveBeenCalledWith("/");
  });

  /**
   * GIVEN a payload that is not a credential pair, because a Server Action argument is attacker-controlled
   * WHEN the sign-in action runs
   * THEN it reports a malformed request and never reaches the backend
   */
  it("refuses a payload that is not a credential pair", async () => {
    await expect(signInAction({ email: EMAIL })).resolves.toEqual({
      error: "malformed-request",
    });

    expect(signIn).not.toHaveBeenCalled();
    expect(writeSessionCookie).not.toHaveBeenCalled();
    expect(redirect).not.toHaveBeenCalled();
  });

  /**
   * GIVEN credentials the backend rejects
   * WHEN the sign-in action runs
   * THEN the transport's reason is returned, no cookie is written, and nothing navigates
   */
  it("returns the transport reason without writing a cookie", async () => {
    signIn.mockResolvedValue({ ok: false, reason: "invalid-credentials" });

    await expect(
      signInAction({ email: EMAIL, password: randomUUID() }),
    ).resolves.toEqual({ error: "invalid-credentials" });

    expect(writeSessionCookie).not.toHaveBeenCalled();
    expect(redirect).not.toHaveBeenCalled();
  });
});

describe("signOutAction", () => {
  /**
   * GIVEN a signed-in visitor
   * WHEN the sign-out action runs
   * THEN the session is ended and the visitor is returned to the login page
   */
  it("ends the session and returns to the login page", async () => {
    await signOutAction();

    expect(signOut).toHaveBeenCalledOnce();
    expect(redirect).toHaveBeenCalledWith("/login");
  });

  /**
   * GIVEN a visitor who asked to sign out rather than losing the session
   * WHEN the sign-out action runs
   * THEN the redirect carries no session-loss reason, so nothing warns them to sign in again
   */
  it("returns to a login page that says nothing about a lost session", async () => {
    await signOutAction();

    const [target] = redirect.mock.calls[0] ?? [];

    expect(target).not.toContain(SESSION_LOSS_PARAMETER);
  });
});
