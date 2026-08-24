import { beforeEach, describe, expect, it, vi } from "vitest";

import { requireUser } from "@/features/auth/server/require-user";

const { getCurrentUser, redirect } = vi.hoisted(() => ({
  getCurrentUser: vi.fn(),
  redirect: vi.fn<(path: string) => never>(),
}));

// The server-only marker throws outside the React Server condition, which Vitest does not set.
vi.mock("server-only", () => ({}));

vi.mock("next/navigation", () => ({ redirect }));

vi.mock("@/features/auth/server/get-current-user", () => ({ getCurrentUser }));

describe("requireUser", () => {
  beforeEach(() => {
    getCurrentUser.mockReset();
    redirect.mockReset();

    redirect.mockImplementation(() => {
      throw new Error("NEXT_REDIRECT");
    });
  });

  /**
   * GIVEN a session cookie the backend refused to confirm, whether expired, revoked, forged or unreachable
   * WHEN an authenticated surface resolves the current user
   * THEN the visitor is sent to a login page marked as an involuntary arrival
   */
  it("sends an unusable session to a marked login page", async () => {
    getCurrentUser.mockResolvedValue(null);

    await expect(requireUser()).rejects.toThrow("NEXT_REDIRECT");

    expect(redirect).toHaveBeenCalledExactlyOnceWith("/login?session=lost");
  });

  /**
   * GIVEN a session the backend confirmed
   * WHEN an authenticated surface resolves the current user
   * THEN the user is returned and nothing navigates
   */
  it("returns the confirmed user", async () => {
    getCurrentUser.mockResolvedValue({ email: "ada@example.com" });

    await expect(requireUser()).resolves.toStrictEqual({
      email: "ada@example.com",
    });

    expect(redirect).not.toHaveBeenCalled();
  });
});
