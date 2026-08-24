import { randomUUID } from "node:crypto";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SESSION_COOKIE_NAME } from "@/features/auth/domain/session-cookie-name";
import { getCurrentUser } from "@/features/auth/server/get-current-user";

// The server-only marker throws outside the React Server condition, which Vitest does not set.
vi.mock("server-only", () => ({}));

const { requestCookies } = vi.hoisted(() => ({
  requestCookies: { sessionToken: null as string | null },
}));

vi.mock("next/headers", () => ({
  cookies: async () => ({
    get: (name: string) =>
      name === SESSION_COOKIE_NAME && requestCookies.sessionToken !== null
        ? { value: requestCookies.sessionToken }
        : undefined,
  }),
}));

describe("getCurrentUser", () => {
  afterEach(() => {
    requestCookies.sessionToken = null;
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  /**
   * GIVEN a session cookie the API accepts
   * WHEN the current user is resolved
   * THEN the token is presented as a bearer credential and the user is returned
   */
  it("returns the user the backend associates with the session token", async () => {
    const token = randomUUID();

    const fetchStub = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        id: 1,
        email: "ada@example.com",
        full_name: "Ada Lovelace",
      }),
    });

    requestCookies.sessionToken = token;
    vi.stubEnv("BACKEND_API_BASE_URL", "http://api.test/api/v1");
    vi.stubGlobal("fetch", fetchStub);

    await expect(getCurrentUser()).resolves.toEqual({
      id: 1,
      email: "ada@example.com",
      fullName: "Ada Lovelace",
    });

    expect(fetchStub).toHaveBeenCalledWith(
      "http://api.test/api/v1/auth/me",
      expect.objectContaining({
        cache: "no-store",
        headers: expect.objectContaining({
          authorization: `Bearer ${token}`,
        }),
      }),
    );
  });

  /**
   * GIVEN a request that carries no session cookie
   * WHEN the current user is resolved
   * THEN there is no user and the API is not called
   */
  it("resolves to no user without calling the API when the cookie is absent", async () => {
    const fetchStub = vi.fn();

    vi.stubEnv("BACKEND_API_BASE_URL", "http://api.test/api/v1");
    vi.stubGlobal("fetch", fetchStub);

    await expect(getCurrentUser()).resolves.toBeNull();
    expect(fetchStub).not.toHaveBeenCalled();
  });

  /**
   * GIVEN a session cookie the API rejects as unauthorized
   * WHEN the current user is resolved
   * THEN there is no user and the rejection is not treated as an error
   */
  it("treats an unauthorized answer as a finished session", async () => {
    const fetchStub = vi.fn().mockResolvedValue({ ok: false, status: 401 });

    requestCookies.sessionToken = randomUUID();
    vi.stubEnv("BACKEND_API_BASE_URL", "http://api.test/api/v1");
    vi.stubGlobal("fetch", fetchStub);

    await expect(getCurrentUser()).resolves.toBeNull();
  });
});
