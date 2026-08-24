import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import LoginPage from "@/app/login/page";

const { getCurrentUser, warning } = vi.hoisted(() => ({
  getCurrentUser: vi.fn(),
  warning: vi.fn(),
}));

// The server-only marker throws outside the React Server condition, which Vitest does not set.
vi.mock("server-only", () => ({}));

vi.mock("next/navigation", () => ({ redirect: vi.fn() }));

vi.mock("sonner", () => ({ toast: { warning } }));

vi.mock("@/features/auth/server/get-current-user", () => ({ getCurrentUser }));

vi.mock("@/features/auth/server/actions", () => ({ signInAction: vi.fn() }));

/**
 * Renders the login page as a visitor with no session would receive it.
 *
 * @param query - Search parameters the arrival carries.
 */
async function renderArrival(
  query: Record<string, string | string[] | undefined>,
): Promise<void> {
  render(await LoginPage({ searchParams: Promise.resolve(query) }));
}

describe("LoginPage", () => {
  beforeEach(() => {
    getCurrentUser.mockReset();
    getCurrentUser.mockResolvedValue(null);
    warning.mockReset();
  });

  /**
   * GIVEN an arrival redirected because a session cookie could not be confirmed
   * WHEN the login page renders
   * THEN a warning naming the lost session is requested
   */
  it("warns a visitor whose session was refused", async () => {
    await renderArrival({ session: "expired" });

    expect(warning).toHaveBeenCalledExactlyOnceWith(
      "Your session is no longer valid. Sign in again to continue.",
      expect.anything(),
    );
  });

  /**
   * GIVEN an arrival redirected because a protected path was requested with no cookie
   * WHEN the login page renders
   * THEN a warning asking the visitor to sign in is requested
   */
  it("warns a visitor who followed a link into the application", async () => {
    await renderArrival({ session: "required" });

    expect(warning).toHaveBeenCalledExactlyOnceWith(
      "Sign in to open that page.",
      expect.anything(),
    );
  });

  /**
   * GIVEN an arrival after a deliberate sign-out, which sets no parameter
   * WHEN the login page renders
   * THEN nothing is reported, because the visitor asked for this
   */
  it("stays silent after a deliberate sign-out", async () => {
    await renderArrival({});

    expect(warning).not.toHaveBeenCalled();
  });

  /**
   * GIVEN a direct visit carrying a reason the product does not recognise
   * WHEN the login page renders
   * THEN nothing is reported and the value never reaches the document
   */
  it("stays silent on an unrecognised reason without echoing it", async () => {
    await renderArrival({ session: "sign-in-immediately" });

    expect(warning).not.toHaveBeenCalled();
    expect(document.body.textContent).not.toContain("sign-in-immediately");
  });

  /**
   * GIVEN any arrival at all, whether it was announced or not
   * WHEN the login page renders
   * THEN the sign-in form is present, so the toast is never the only signal
   */
  it("remains usable without the warning", async () => {
    await renderArrival({});

    expect(
      screen.getByRole("heading", { name: "Sign in to your account" }),
    ).toBeVisible();
    expect(screen.getByRole("button", { name: /sign in/i })).toBeVisible();
  });
});
