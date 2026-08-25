import { afterEach, describe, expect, it, vi } from "vitest";

import { getPlatformHealth } from "@/features/health/server/get-platform-health";

// The server-only marker throws outside the React Server condition, which Vitest does not set.
vi.mock("server-only", () => ({}));

describe("getPlatformHealth", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  /**
   * GIVEN a backend base URL configured as whitespace only
   * WHEN platform health is probed
   * THEN nothing is probed and the reason names no environment variable
   */
  it("reports nothing without probing when the backend URL is blank", async () => {
    const fetchStub = vi.fn();

    vi.stubEnv("BACKEND_API_BASE_URL", "   ");
    vi.stubGlobal("fetch", fetchStub);
    vi.stubGlobal("console", { ...console, error: vi.fn() });

    const health = await getPlatformHealth();

    expect(health.reported).toBe(false);
    expect(fetchStub).not.toHaveBeenCalled();
    expect(health.reported === false && health.reason).not.toContain(
      "BACKEND_API_BASE_URL",
    );
  });

  /**
   * GIVEN a reachable API answering the probe with a healthy payload
   * WHEN platform health is probed
   * THEN the health endpoint is probed uncached and the answer is normalized
   */
  it("probes the configured backend without caching and normalizes the answer", async () => {
    const fetchStub = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        status: "ok",
        version: "1.0.0",
        database: "ok",
        cache: "ok",
      }),
    });

    vi.stubEnv("BACKEND_API_BASE_URL", "http://api.test/api/v1//");
    vi.stubGlobal("fetch", fetchStub);

    const health = await getPlatformHealth();

    expect(health).toEqual({
      reported: true,
      status: "operational",
      version: "1.0.0",
      database: "operational",
      cache: "operational",
    });

    expect(fetchStub).toHaveBeenCalledWith(
      "http://api.test/api/v1/health",
      expect.objectContaining({ cache: "no-store" }),
    );
  });

  /**
   * GIVEN an API answering the health probe with a server error
   * WHEN platform health is probed
   * THEN health is unreported and the HTTP status reaches the reason
   */
  it("reports nothing and surfaces the status when the API answers an error", async () => {
    const fetchStub = vi.fn().mockResolvedValue({ ok: false, status: 503 });

    vi.stubEnv("BACKEND_API_BASE_URL", "http://api.test/api/v1");
    vi.stubGlobal("fetch", fetchStub);

    const health = await getPlatformHealth();

    expect(health).toEqual({
      reported: false,
      reason: expect.stringContaining("503"),
    });
  });

  /**
   * GIVEN a backend that cannot be reached at all
   * WHEN platform health is probed
   * THEN the probe resolves with an unreachable reason instead of throwing
   */
  it("resolves with unreported health when the API cannot be reached", async () => {
    const fetchStub = vi.fn().mockRejectedValue(new TypeError("fetch failed"));

    vi.stubEnv("BACKEND_API_BASE_URL", "http://api.test/api/v1");
    vi.stubGlobal("fetch", fetchStub);

    await expect(getPlatformHealth()).resolves.toEqual({
      reported: false,
      reason: expect.stringContaining("could not be reached"),
    });
  });

  /**
   * GIVEN an API answering the probe with a body that is not valid JSON
   * WHEN platform health is probed
   * THEN the answer is reported as a contract mismatch, not as unreachable
   */
  it("separates an undecodable body from an unreachable API", async () => {
    const fetchStub = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => {
        throw new SyntaxError("Unexpected token <");
      },
    });

    vi.stubEnv("BACKEND_API_BASE_URL", "http://api.test/api/v1");
    vi.stubGlobal("fetch", fetchStub);

    await expect(getPlatformHealth()).resolves.toEqual({
      reported: false,
      reason: expect.stringContaining("health contract"),
    });
  });
});
