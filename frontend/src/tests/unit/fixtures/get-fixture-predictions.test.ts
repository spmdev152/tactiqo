import { afterEach, describe, expect, it, vi } from "vitest";

import { SESSION_COOKIE_NAME } from "@/features/auth/domain/session-cookie-name";
import { getFixturePredictions } from "@/features/fixtures/server/get-fixture-predictions";

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

const FIXTURE_ID = 41;

const PREDICTIONS_PAYLOAD = {
  fixture_id: FIXTURE_ID,
  synchronized_at: "2026-08-25T20:00:00Z",
  markets: [
    {
      market: "fulltime_result",
      reliability: "medium",
      hit_ratio: 0.5,
      selections: [
        { selection: "home", probability: 26.96 },
        { selection: "draw", probability: 24.82 },
        { selection: "away", probability: 48.18 },
      ],
    },
  ],
};

describe("getFixturePredictions", () => {
  afterEach(() => {
    requestCookies.sessionToken = "session-token";
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  /**
   * GIVEN no configured backend base URL
   * WHEN a fixture's predictions are read
   * THEN no request is attempted and the variable is logged rather than shown
   */
  it("reports nothing without requesting when the backend URL is blank", async () => {
    const fetchStub = vi.fn();

    const logged = vi.spyOn(console, "error").mockImplementation(() => {});

    vi.stubEnv("BACKEND_API_BASE_URL", "   ");
    vi.stubGlobal("fetch", fetchStub);

    const result = await getFixturePredictions(FIXTURE_ID);

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
   * WHEN a fixture's predictions are read
   * THEN no unauthenticated request is sent to the API
   */
  it("reports nothing without requesting when there is no session", async () => {
    const fetchStub = vi.fn();

    requestCookies.sessionToken = null;
    vi.stubEnv("BACKEND_API_BASE_URL", "http://api.test/api/v1");
    vi.stubGlobal("fetch", fetchStub);

    const result = await getFixturePredictions(FIXTURE_ID);

    expect(result.loaded).toBe(false);
    expect(fetchStub).not.toHaveBeenCalled();
  });

  /**
   * GIVEN an API answering the predictions request with a server error
   * WHEN a fixture's predictions are read
   * THEN the result is unavailable and the HTTP status reaches the reason
   */
  it("normalizes a non-OK status into the unavailable result", async () => {
    const fetchStub = vi.fn().mockResolvedValue({ ok: false, status: 503 });

    vi.stubEnv("BACKEND_API_BASE_URL", "http://api.test/api/v1");
    vi.stubGlobal("fetch", fetchStub);

    await expect(getFixturePredictions(FIXTURE_ID)).resolves.toEqual({
      loaded: false,
      reason: expect.stringContaining("503"),
    });
  });

  /**
   * GIVEN an API answering the predictions request with a body that is not JSON
   * WHEN a fixture's predictions are read
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

    await expect(getFixturePredictions(FIXTURE_ID)).resolves.toEqual({
      loaded: false,
      reason: expect.stringContaining("predictions contract"),
    });
  });

  /**
   * GIVEN a backend that cannot be reached at all
   * WHEN a fixture's predictions are read
   * THEN the call resolves with an unreachable reason instead of throwing
   */
  it("normalizes a transport failure into the unavailable result", async () => {
    const fetchStub = vi.fn().mockRejectedValue(new TypeError("fetch failed"));

    vi.stubEnv("BACKEND_API_BASE_URL", "http://api.test/api/v1");
    vi.stubGlobal("fetch", fetchStub);

    await expect(getFixturePredictions(FIXTURE_ID)).resolves.toEqual({
      loaded: false,
      reason: expect.stringContaining("could not be reached"),
    });
  });

  /**
   * GIVEN an API answering with a body whose shape is not the published one
   * WHEN a fixture's predictions are read
   * THEN it is refused rather than read as a fixture with nothing predicted
   */
  it("refuses a decodable body that breaks the contract", async () => {
    const fetchStub = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        ...PREDICTIONS_PAYLOAD,
        markets: { fulltime_result: PREDICTIONS_PAYLOAD.markets[0] },
      }),
    });

    vi.stubEnv("BACKEND_API_BASE_URL", "http://api.test/api/v1");
    vi.stubGlobal("fetch", fetchStub);

    await expect(getFixturePredictions(FIXTURE_ID)).resolves.toEqual({
      loaded: false,
      reason: expect.stringContaining("predictions contract"),
    });
  });

  /**
   * GIVEN a reachable API holding predictions for the fixture
   * WHEN a fixture's predictions are read
   * THEN the fixture's address is requested with the token and a deadline
   */
  it("reads the fixture's predictions with the session token", async () => {
    const fetchStub = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => PREDICTIONS_PAYLOAD,
    });

    vi.stubEnv("BACKEND_API_BASE_URL", "http://api.test/api/v1");
    vi.stubGlobal("fetch", fetchStub);

    await expect(getFixturePredictions(FIXTURE_ID)).resolves.toEqual({
      loaded: true,
      predictions: {
        fixtureId: FIXTURE_ID,
        synchronizedAt: new Date("2026-08-25T20:00:00Z"),
        markets: [
          {
            market: "fulltime_result",
            reliability: "medium",
            hitRatio: 0.5,
            selections: [
              { selection: "home", probability: 26.96 },
              { selection: "draw", probability: 24.82 },
              { selection: "away", probability: 48.18 },
            ],
          },
        ],
      },
    });

    expect(fetchStub).toHaveBeenCalledWith(
      "http://api.test/api/v1/fixtures/41/predictions",
      expect.objectContaining({
        cache: "no-store",
        headers: expect.objectContaining({
          authorization: "Bearer session-token",
        }),
        signal: expect.any(AbortSignal),
      }),
    );
  });
});
