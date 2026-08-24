import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import HomePage from "@/app/page";

const { getCurrentUser, redirect } = vi.hoisted(() => ({
  getCurrentUser: vi.fn(),
  redirect: vi.fn<(path: string) => never>(),
}));

// The server-only marker throws outside the React Server condition, which Vitest does not set.
vi.mock("server-only", () => ({}));

vi.mock("next/navigation", () => ({ redirect }));

vi.mock("@/features/auth/server/get-current-user", () => ({ getCurrentUser }));

describe("HomePage", () => {
  beforeEach(() => {
    getCurrentUser.mockReset();
    redirect.mockReset();

    redirect.mockImplementation(() => {
      throw new Error("NEXT_REDIRECT");
    });
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  /**
   * GIVEN a session cookie the backend refused to confirm, whether expired, revoked, forged or unreachable
   * WHEN the landing page renders
   * THEN the visitor is sent to the login page with the reason attached
   */
  it("sends an unusable session to the login page with a reason", async () => {
    getCurrentUser.mockResolvedValue(null);

    await expect(HomePage()).rejects.toThrow("NEXT_REDIRECT");

    expect(redirect).toHaveBeenCalledExactlyOnceWith("/login?session=expired");
  });

  /**
   * GIVEN a session the backend confirmed
   * WHEN the landing page renders
   * THEN nothing navigates
   */
  it("keeps a confirmed session on the landing page", async () => {
    getCurrentUser.mockResolvedValue({ email: "ada@example.com" });

    vi.stubEnv("BACKEND_API_BASE_URL", "");

    await HomePage();

    expect(redirect).not.toHaveBeenCalled();
  });
});
