import { randomUUID } from "node:crypto";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { signIn } from "@/features/auth/server/sign-in";

// The server-only marker throws outside the React Server condition, which Vitest does not set.
vi.mock("server-only", () => ({}));

const { headers } = vi.hoisted(() => ({ headers: vi.fn() }));

vi.mock("next/headers", () => ({ headers }));

const FORWARDING_CHAIN = "198.51.100.7";

// Millisecond precision and the Z suffix are the shape the backend actually emits.
const EXPIRES_AT = "2026-09-06T19:03:51.915Z";

/**
 * Builds a throwaway credential so no secret is written into the test source.
 *
 * @returns A random value usable as a password or as an opaque token.
 */
function randomCredential(): string {
  return randomUUID();
}

describe("signIn", () => {
  beforeEach(() => {
    headers.mockResolvedValue(
      new Headers({ "x-forwarded-for": FORWARDING_CHAIN }),
    );
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  /**
   * GIVEN an API that accepts the credentials and returns a session payload
   * WHEN the credentials are submitted
   * THEN the login endpoint is posted to and the session material is normalized
   */
  it("posts the credentials and normalizes the issued session", async () => {
    const password = randomCredential();
    const token = randomCredential();

    const fetchStub = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        token,
        expires_at: EXPIRES_AT,
        user: { id: 1, email: "ada@example.com", full_name: "Ada Lovelace" },
      }),
    });

    vi.stubEnv("BACKEND_API_BASE_URL", "http://api.test/api/v1//");
    vi.stubGlobal("fetch", fetchStub);

    await expect(signIn("ada@example.com", password)).resolves.toEqual({
      ok: true,
      token,
      expiresAt: new Date(EXPIRES_AT),
      user: { id: 1, email: "ada@example.com", fullName: "Ada Lovelace" },
    });

    expect(fetchStub).toHaveBeenCalledWith(
      "http://api.test/api/v1/auth/login",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ email: "ada@example.com", password }),
      }),
    );
  });

  /**
   * GIVEN a request whose forwarding chain names the visitor
   * WHEN the credentials are submitted
   * THEN the chain travels with the call, so the backend can throttle per visitor
   */
  it("forwards the chain of the current request to the backend", async () => {
    const fetchStub = vi
      .fn()
      .mockResolvedValue({ ok: false, status: 401, json: vi.fn() });

    vi.stubEnv("BACKEND_API_BASE_URL", "http://api.test/api/v1");
    vi.stubGlobal("fetch", fetchStub);

    await signIn("ada@example.com", randomCredential());

    expect(fetchStub).toHaveBeenCalledWith(
      "http://api.test/api/v1/auth/login",
      expect.objectContaining({
        headers: expect.objectContaining({
          "x-forwarded-for": FORWARDING_CHAIN,
        }),
      }),
    );
  });

  /**
   * GIVEN an API that throttled the attempt
   * WHEN the credentials are submitted
   * THEN the attempt fails as rate limited rather than as invalid credentials
   */
  it("maps a throttled answer to a rate-limited failure", async () => {
    const fetchStub = vi
      .fn()
      .mockResolvedValue({ ok: false, status: 429, json: vi.fn() });

    vi.stubEnv("BACKEND_API_BASE_URL", "http://api.test/api/v1");
    vi.stubGlobal("fetch", fetchStub);

    await expect(
      signIn("ada@example.com", randomCredential()),
    ).resolves.toEqual({ ok: false, reason: "rate-limited" });
  });

  /**
   * GIVEN an API that rejects the credentials with an unauthorized answer
   * WHEN the credentials are submitted
   * THEN the attempt fails as invalid credentials and no body is read
   */
  it("maps an unauthorized answer to invalid credentials", async () => {
    const json = vi.fn();

    const fetchStub = vi
      .fn()
      .mockResolvedValue({ ok: false, status: 401, json });

    vi.stubEnv("BACKEND_API_BASE_URL", "http://api.test/api/v1");
    vi.stubGlobal("fetch", fetchStub);

    await expect(
      signIn("ada@example.com", randomCredential()),
    ).resolves.toEqual({ ok: false, reason: "invalid-credentials" });

    expect(json).not.toHaveBeenCalled();
  });

  /**
   * GIVEN a backend that cannot be reached at all
   * WHEN the credentials are submitted
   * THEN the attempt resolves as unreachable instead of throwing
   */
  it("resolves with an unreachable reason when the API cannot be reached", async () => {
    const fetchStub = vi.fn().mockRejectedValue(new TypeError("fetch failed"));

    vi.stubEnv("BACKEND_API_BASE_URL", "http://api.test/api/v1");
    vi.stubGlobal("fetch", fetchStub);

    await expect(
      signIn("ada@example.com", randomCredential()),
    ).resolves.toEqual({ ok: false, reason: "api-unreachable" });
  });

  /**
   * GIVEN an accepted sign-in whose payload omits the expiry timestamp
   * WHEN the credentials are submitted
   * THEN the attempt fails as a contract mismatch and issues no session
   */
  it("refuses a session whose payload does not match the contract", async () => {
    const fetchStub = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        token: randomCredential(),
        user: { id: 1, email: "ada@example.com", full_name: "Ada Lovelace" },
      }),
    });

    vi.stubEnv("BACKEND_API_BASE_URL", "http://api.test/api/v1");
    vi.stubGlobal("fetch", fetchStub);

    await expect(
      signIn("ada@example.com", randomCredential()),
    ).resolves.toEqual({ ok: false, reason: "contract-mismatch" });
  });
});
