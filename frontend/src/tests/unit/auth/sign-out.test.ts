import { randomUUID } from "node:crypto";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { signOut } from "@/features/auth/server/sign-out";

// The server-only marker throws outside the React Server condition, which Vitest does not set.
vi.mock("server-only", () => ({}));

const { clearSessionCookie, readSessionToken } = vi.hoisted(() => ({
  clearSessionCookie: vi.fn<() => Promise<void>>(),
  readSessionToken: vi.fn<() => Promise<string | null>>(),
}));

vi.mock("@/features/auth/server/session-cookie", () => ({
  clearSessionCookie,
  readSessionToken,
}));

const BASE_URL = "http://api.test/api/v1";

beforeEach(() => {
  clearSessionCookie.mockReset();
  readSessionToken.mockReset();
});

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

describe("signOut", () => {
  /**
   * GIVEN a request carrying a session token the backend accepts
   * WHEN the visitor signs out
   * THEN the token is revoked as a bearer credential and the cookie is cleared
   */
  it("revokes the session on the backend and clears the cookie", async () => {
    const token = randomUUID();

    const fetchStub = vi.fn().mockResolvedValue({ ok: true, status: 204 });

    readSessionToken.mockResolvedValue(token);
    vi.stubEnv("BACKEND_API_BASE_URL", BASE_URL);
    vi.stubGlobal("fetch", fetchStub);

    await signOut();

    expect(fetchStub).toHaveBeenCalledWith(
      `${BASE_URL}/auth/logout`,
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          authorization: `Bearer ${token}`,
        }),
      }),
    );

    expect(clearSessionCookie).toHaveBeenCalledOnce();
  });

  /**
   * GIVEN a backend that cannot be reached to revoke the session
   * WHEN the visitor signs out
   * THEN the cookie is still cleared, so nobody is stranded signed in
   */
  it("clears the cookie even when revocation fails", async () => {
    const fetchStub = vi.fn().mockRejectedValue(new Error("api unreachable"));

    readSessionToken.mockResolvedValue(randomUUID());
    vi.stubEnv("BACKEND_API_BASE_URL", BASE_URL);
    vi.stubGlobal("fetch", fetchStub);

    await expect(signOut()).resolves.toBeUndefined();

    expect(fetchStub).toHaveBeenCalledOnce();
    expect(clearSessionCookie).toHaveBeenCalledOnce();
  });

  /**
   * GIVEN a request carrying no session cookie
   * WHEN the visitor signs out
   * THEN nothing is sent to the backend and the cookie is cleared regardless
   */
  it("clears the cookie without calling the backend when there is no token", async () => {
    const fetchStub = vi.fn();

    readSessionToken.mockResolvedValue(null);
    vi.stubEnv("BACKEND_API_BASE_URL", BASE_URL);
    vi.stubGlobal("fetch", fetchStub);

    await signOut();

    expect(fetchStub).not.toHaveBeenCalled();
    expect(clearSessionCookie).toHaveBeenCalledOnce();
  });
});
