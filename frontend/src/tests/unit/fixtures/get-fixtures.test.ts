import { afterEach, describe, expect, it, vi } from "vitest";

import { SESSION_COOKIE_NAME } from "@/features/auth/domain/session-cookie-name";
import { getFixtures } from "@/features/fixtures/server/get-fixtures";

// The server-only marker throws outside the React Server condition, which Vitest does not set.
vi.mock("server-only", () => ({}));

const { requestCookies } = vi.hoisted(() => ({
  requestCookies: { sessionToken: "session-token" as string | null },
}));

vi.mock("next/headers", () => ({
  cookies: async () => ({
    get: (name: string) =>
      name === SESSION_COOKIE_NAME && requestCookies.sessionToken !== null
        ? { value: requestCookies.sessionToken }
        : undefined,
  }),
}));

const QUERY = { day: "2026-08-29", leagueId: null };

describe("getFixtures", () => {
  afterEach(() => {
    requestCookies.sessionToken = "session-token";
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  /**
   * GIVEN an API answering the fixtures request with a server error
   * WHEN the fixtures of a day are read
   * THEN the result is unavailable and the HTTP status reaches the reason
   */
  it("normalizes a non-OK status into the unavailable result", async () => {
    const fetchStub = vi.fn().mockResolvedValue({ ok: false, status: 503 });

    vi.stubEnv("BACKEND_API_BASE_URL", "http://api.test/api/v1");
    vi.stubGlobal("fetch", fetchStub);

    await expect(getFixtures(QUERY)).resolves.toEqual({
      loaded: false,
      reason: expect.stringContaining("503"),
    });
  });

  /**
   * GIVEN a backend that cannot be reached at all
   * WHEN the fixtures of a day are read
   * THEN the call resolves with an unreachable reason instead of throwing
   */
  it("normalizes a transport failure into the unavailable result", async () => {
    const fetchStub = vi.fn().mockRejectedValue(new TypeError("fetch failed"));

    vi.stubEnv("BACKEND_API_BASE_URL", "http://api.test/api/v1");
    vi.stubGlobal("fetch", fetchStub);

    await expect(getFixtures(QUERY)).resolves.toEqual({
      loaded: false,
      reason: expect.stringContaining("could not be reached"),
    });
  });

  /**
   * GIVEN an API answering the fixtures request with a body that is not JSON
   * WHEN the fixtures of a day are read
   * THEN it is reported as a contract mismatch, not as an unreachable API
   */
  it("separates an undecodable body from an unreachable API", async () => {
    const fetchStub = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => {
        throw new SyntaxError("Unexpected token < in JSON at position 0");
      },
    });

    vi.stubEnv("BACKEND_API_BASE_URL", "http://api.test/api/v1");
    vi.stubGlobal("fetch", fetchStub);

    await expect(getFixtures(QUERY)).resolves.toEqual({
      loaded: false,
      reason: expect.stringContaining("fixtures contract"),
    });
  });

  /**
   * GIVEN no configured backend base URL
   * WHEN the fixtures of a day are read
   * THEN the result is unavailable and no request is attempted
   */
  it("reports nothing without requesting when the backend URL is blank", async () => {
    const fetchStub = vi.fn();

    vi.stubEnv("BACKEND_API_BASE_URL", "   ");
    vi.stubGlobal("fetch", fetchStub);

    const result = await getFixtures(QUERY);

    expect(result.loaded).toBe(false);
    expect(fetchStub).not.toHaveBeenCalled();
  });

  /**
   * GIVEN a request carrying no session cookie
   * WHEN the fixtures of a day are read
   * THEN no unauthenticated request is sent to the API
   */
  it("reports nothing without requesting when there is no session", async () => {
    const fetchStub = vi.fn();

    requestCookies.sessionToken = null;
    vi.stubEnv("BACKEND_API_BASE_URL", "http://api.test/api/v1");
    vi.stubGlobal("fetch", fetchStub);

    const result = await getFixtures(QUERY);

    expect(result.loaded).toBe(false);
    expect(fetchStub).not.toHaveBeenCalled();
  });

  /**
   * GIVEN a reachable API and a request filtered to one competition
   * WHEN the fixtures of a day are read
   * THEN the day and the competition are sent as the API's own query names
   */
  it("sends the day and the competition uncached with a bearer credential", async () => {
    const fetchStub = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => [],
    });

    vi.stubEnv("BACKEND_API_BASE_URL", "http://api.test/api/v1");
    vi.stubGlobal("fetch", fetchStub);

    await expect(
      getFixtures({ day: "2026-08-29", leagueId: 1 }),
    ).resolves.toEqual({ loaded: true, fixtures: [] });

    expect(fetchStub).toHaveBeenCalledWith(
      "http://api.test/api/v1/fixtures?date=2026-08-29&league_id=1",
      expect.objectContaining({
        cache: "no-store",
        headers: expect.objectContaining({
          authorization: "Bearer session-token",
        }),
      }),
    );
  });

  /**
   * GIVEN a request that applies no competition filter
   * WHEN the fixtures of a day are read
   * THEN the competition query is omitted rather than sent empty
   */
  it("omits the competition query when no filter applies", async () => {
    const fetchStub = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => [],
    });

    vi.stubEnv("BACKEND_API_BASE_URL", "http://api.test/api/v1");
    vi.stubGlobal("fetch", fetchStub);

    await getFixtures(QUERY);

    expect(fetchStub).toHaveBeenCalledWith(
      "http://api.test/api/v1/fixtures?date=2026-08-29",
      expect.anything(),
    );
  });
});
