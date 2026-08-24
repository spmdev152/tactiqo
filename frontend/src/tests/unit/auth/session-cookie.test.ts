import { randomUUID } from "node:crypto";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SESSION_COOKIE_NAME } from "@/features/auth/domain/session-cookie-name";
import {
  clearSessionCookie,
  readSessionToken,
  writeSessionCookie,
} from "@/features/auth/server/session-cookie";

// The server-only marker throws outside the React Server condition, which Vitest does not set.
vi.mock("server-only", () => ({}));

/**
 * Every option the session cookie is allowed to carry.
 *
 * @remarks
 * Spelled out in full so the whole options object can be asserted at once: a
 * flag that is silently added or dropped fails the assertion instead of slipping
 * past a per-key check. Each one is a security property of the session.
 */
interface SessionCookieOptions {
  httpOnly: boolean;
  sameSite: "lax" | "none" | "strict";
  secure: boolean;
  path: string;
  expires: Date;
}

const { cookieStore } = vi.hoisted(() => ({
  cookieStore: {
    set: vi.fn<
      (name: string, value: string, options: SessionCookieOptions) => void
    >(),
    get: vi.fn<(name: string) => { value: string } | undefined>(),
    delete: vi.fn<(name: string) => void>(),
  },
}));

vi.mock("next/headers", () => ({ cookies: async () => cookieStore }));

beforeEach(() => {
  cookieStore.set.mockReset();
  cookieStore.get.mockReset();
  cookieStore.delete.mockReset();
});

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("writeSessionCookie", () => {
  /**
   * GIVEN a token and the expiry the backend issued it with
   * WHEN the session cookie is written
   * THEN it carries exactly the http-only, lax, rooted, secure flags and that expiry
   */
  it("issues the session cookie with exactly its security flags", async () => {
    const token = randomUUID();
    const expiresAt = new Date("2026-09-01T12:00:00.000Z");

    await writeSessionCookie(token, expiresAt);

    expect(cookieStore.set).toHaveBeenCalledWith(SESSION_COOKIE_NAME, token, {
      httpOnly: true,
      sameSite: "lax",
      secure: true,
      path: "/",
      expires: expiresAt,
    });

    expect(cookieStore.set.mock.calls[0][2].expires).toBe(expiresAt);
  });

  /**
   * GIVEN a deployment that declares itself insecure through the environment
   * WHEN the session cookie is written
   * THEN only the secure flag is lifted and every other flag is unchanged
   */
  it("lifts the secure flag only on an explicit declaration", async () => {
    const token = randomUUID();
    const expiresAt = new Date("2026-09-01T12:00:00.000Z");

    vi.stubEnv("SESSION_COOKIE_INSECURE", "true");

    await writeSessionCookie(token, expiresAt);

    expect(cookieStore.set).toHaveBeenCalledWith(SESSION_COOKIE_NAME, token, {
      httpOnly: true,
      sameSite: "lax",
      secure: false,
      path: "/",
      expires: expiresAt,
    });
  });

  /**
   * GIVEN an environment that asks for an insecure cookie with anything but "true"
   * WHEN the session cookie is written
   * THEN it stays secure, because the opt-out is exact rather than truthy
   */
  it("keeps the cookie secure when the opt-out is not exactly true", async () => {
    const token = randomUUID();
    const expiresAt = new Date("2026-09-01T12:00:00.000Z");

    vi.stubEnv("SESSION_COOKIE_INSECURE", "True");

    await writeSessionCookie(token, expiresAt);

    expect(cookieStore.set).toHaveBeenCalledWith(
      SESSION_COOKIE_NAME,
      token,
      expect.objectContaining({ secure: true }),
    );
  });
});

describe("readSessionToken", () => {
  /**
   * GIVEN a request carrying the session cookie
   * WHEN the token is read
   * THEN the cookie is looked up by name and its value is returned
   */
  it("returns the value of the session cookie", async () => {
    const token = randomUUID();

    cookieStore.get.mockReturnValue({ value: token });

    await expect(readSessionToken()).resolves.toBe(token);
    expect(cookieStore.get).toHaveBeenCalledWith(SESSION_COOKIE_NAME);
  });

  /**
   * GIVEN a request carrying no session cookie
   * WHEN the token is read
   * THEN there is no token rather than an undefined value
   */
  it("returns no token when the cookie is absent", async () => {
    cookieStore.get.mockReturnValue(undefined);

    await expect(readSessionToken()).resolves.toBeNull();
  });
});

describe("clearSessionCookie", () => {
  /**
   * GIVEN a browser holding the session cookie
   * WHEN the cookie is cleared
   * THEN it is deleted by the one name the application ever sets
   */
  it("deletes the session cookie by name", async () => {
    await clearSessionCookie();

    expect(cookieStore.delete).toHaveBeenCalledWith(SESSION_COOKIE_NAME);
  });
});
