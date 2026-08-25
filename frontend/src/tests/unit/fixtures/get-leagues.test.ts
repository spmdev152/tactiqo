import { afterEach, describe, expect, it, vi } from "vitest";

import { SESSION_COOKIE_NAME } from "@/features/auth/domain/session-cookie-name";
import { getLeagues } from "@/features/fixtures/server/get-leagues";

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

const LEAGUE_PAYLOAD = {
  id: 1,
  name: "Premier League",
  short_code: "UK PL",
  logo_url: "https://cdn.sportmonks.com/images/soccer/leagues/8.png",
  country_name: "England",
  country_flag_url:
    "https://cdn.sportmonks.com/images/countries/png/short/en.png",
};

describe("getLeagues", () => {
  afterEach(() => {
    requestCookies.sessionToken = "session-token";
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  /**
   * GIVEN no configured backend base URL
   * WHEN the covered competitions are read
   * THEN no request is attempted and the variable is logged rather than shown
   */
  it("reports nothing without requesting when the backend URL is blank", async () => {
    const fetchStub = vi.fn();

    const logged = vi.spyOn(console, "error").mockImplementation(() => {});

    vi.stubEnv("BACKEND_API_BASE_URL", "   ");
    vi.stubGlobal("fetch", fetchStub);

    const result = await getLeagues();

    expect(result).toEqual({
      loaded: false,
      reason: expect.not.stringContaining("BACKEND_API_BASE_URL"),
    });

    expect(fetchStub).not.toHaveBeenCalled();

    expect(logged).toHaveBeenCalledExactlyOnceWith(
      expect.stringContaining("BACKEND_API_BASE_URL"),
    );
  });

  /**
   * GIVEN a request carrying no session cookie
   * WHEN the covered competitions are read
   * THEN no unauthenticated request is sent to the API
   */
  it("reports nothing without requesting when there is no session", async () => {
    const fetchStub = vi.fn();

    requestCookies.sessionToken = null;
    vi.stubEnv("BACKEND_API_BASE_URL", "http://api.test/api/v1");
    vi.stubGlobal("fetch", fetchStub);

    const result = await getLeagues();

    expect(result.loaded).toBe(false);
    expect(fetchStub).not.toHaveBeenCalled();
  });

  /**
   * GIVEN an API answering the competitions request with a server error
   * WHEN the covered competitions are read
   * THEN the result is unavailable and the HTTP status reaches the reason
   */
  it("normalizes a non-OK status into the unavailable result", async () => {
    const fetchStub = vi.fn().mockResolvedValue({ ok: false, status: 503 });

    vi.stubEnv("BACKEND_API_BASE_URL", "http://api.test/api/v1");
    vi.stubGlobal("fetch", fetchStub);

    await expect(getLeagues()).resolves.toEqual({
      loaded: false,
      reason: expect.stringContaining("503"),
    });
  });

  /**
   * GIVEN an API answering the competitions request with a body that is not JSON
   * WHEN the covered competitions are read
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

    await expect(getLeagues()).resolves.toEqual({
      loaded: false,
      reason: expect.stringContaining("leagues contract"),
    });
  });

  /**
   * GIVEN a backend that cannot be reached at all
   * WHEN the covered competitions are read
   * THEN the call resolves with an unreachable reason instead of throwing
   */
  it("normalizes a transport failure into the unavailable result", async () => {
    const fetchStub = vi.fn().mockRejectedValue(new TypeError("fetch failed"));

    vi.stubEnv("BACKEND_API_BASE_URL", "http://api.test/api/v1");
    vi.stubGlobal("fetch", fetchStub);

    await expect(getLeagues()).resolves.toEqual({
      loaded: false,
      reason: expect.stringContaining("could not be reached"),
    });
  });

  /**
   * GIVEN a reachable API and a confirmed session
   * WHEN the covered competitions are read
   * THEN the visitor's own token is forwarded and the payload is normalized
   */
  it("forwards the session token and normalizes the competitions", async () => {
    const fetchStub = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => [LEAGUE_PAYLOAD],
    });

    vi.stubEnv("BACKEND_API_BASE_URL", "http://api.test/api/v1");
    vi.stubGlobal("fetch", fetchStub);

    await expect(getLeagues()).resolves.toEqual({
      loaded: true,
      leagues: [expect.objectContaining({ id: 1, name: "Premier League" })],
    });

    expect(fetchStub).toHaveBeenCalledWith(
      "http://api.test/api/v1/leagues",
      expect.objectContaining({
        cache: "no-store",
        headers: expect.objectContaining({
          authorization: "Bearer session-token",
        }),
      }),
    );
  });
});
