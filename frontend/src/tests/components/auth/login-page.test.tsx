import { act, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import LoginPage from "@/app/login/page";

const { getCurrentUser, readSessionToken, redirect, warning } = vi.hoisted(
  () => ({
    getCurrentUser: vi.fn(),
    readSessionToken: vi.fn(),
    redirect: vi.fn<(path: string) => never>(),
    warning: vi.fn(),
  }),
);

// The server-only marker throws outside the React Server condition, which Vitest does not set.
vi.mock("server-only", () => ({}));

vi.mock("next/navigation", () => ({
  redirect,
  useSearchParams: () => new URLSearchParams(window.location.search),
}));

vi.mock("sonner", () => ({ toast: { warning } }));

vi.mock("@/features/auth/server/get-current-user", () => ({ getCurrentUser }));

vi.mock("@/features/auth/server/session-cookie", () => ({ readSessionToken }));

vi.mock("@/features/auth/server/actions", () => ({ signInAction: vi.fn() }));

/**
 * Renders the login page as a visitor with no usable session would receive it,
 * putting the browser on the matching URL as a real arrival would, then letting
 * the frame and the task the notice waits for elapse.
 *
 * @param query - Search parameters the arrival carries.
 */
async function renderArrival(query: Record<string, string>): Promise<void> {
  const search = new URLSearchParams(query).toString();

  window.history.replaceState(
    null,
    "",
    search === "" ? "/login" : `/login?${search}`,
  );

  render(await LoginPage({ searchParams: Promise.resolve(query) }));

  const { promise, resolve } = Promise.withResolvers<void>();

  await act(() => {
    requestAnimationFrame(() => setTimeout(resolve, 0));

    return promise;
  });
}

describe("LoginPage", () => {
  beforeEach(() => {
    getCurrentUser.mockReset();
    getCurrentUser.mockResolvedValue(null);
    readSessionToken.mockReset();
    readSessionToken.mockResolvedValue("stale-token");
    redirect.mockReset();

    redirect.mockImplementation(() => {
      throw new Error("NEXT_REDIRECT");
    });

    warning.mockReset();
    window.history.replaceState(null, "", "/login");
  });

  /**
   * GIVEN an involuntary arrival whose request still carries a session cookie
   * WHEN the login page renders
   * THEN the visitor is told the session expired
   */
  it("warns a visitor whose session was refused", async () => {
    await renderArrival({ session: "lost" });

    await waitFor(() =>
      expect(warning).toHaveBeenCalledExactlyOnceWith(
        "Session expired",
        expect.objectContaining({
          description: "Sign in again to access the platform.",
        }),
      ),
    );
  });

  /**
   * GIVEN an involuntary arrival carrying no session cookie at all
   * WHEN the login page renders
   * THEN a sign-in is requested without claiming a session expired
   */
  it("warns a visitor who followed a link into the application", async () => {
    readSessionToken.mockResolvedValue(null);

    await renderArrival({ session: "lost" });

    await waitFor(() =>
      expect(warning).toHaveBeenCalledExactlyOnceWith(
        "Sign in required",
        expect.objectContaining({
          description: "Sign in to access the platform.",
        }),
      ),
    );
  });

  /**
   * GIVEN a marker forged into a link sent to somebody who never held a session
   * WHEN the login page renders
   * THEN they are never told a session expired
   */
  it("never claims an expiry for a visitor carrying no cookie", async () => {
    readSessionToken.mockResolvedValue(null);

    await renderArrival({ session: "lost" });

    await waitFor(() => expect(warning).toHaveBeenCalledOnce());

    expect(warning).not.toHaveBeenCalledWith(
      "Session expired",
      expect.anything(),
    );
  });

  /**
   * GIVEN an arrival after a deliberate sign-out, which marks nothing
   * WHEN the login page renders
   * THEN nothing is reported, because the visitor asked for this
   */
  it("stays silent after a deliberate sign-out", async () => {
    readSessionToken.mockResolvedValue(null);

    await renderArrival({});

    expect(warning).not.toHaveBeenCalled();
  });

  /**
   * GIVEN a direct visit carrying a marker the product does not recognise
   * WHEN the login page renders
   * THEN nothing is reported and the value reaches neither text nor markup
   */
  it("stays silent on an unrecognised marker without echoing it", async () => {
    await renderArrival({ session: "sign-in-immediately" });

    expect(warning).not.toHaveBeenCalled();
    expect(document.body.innerHTML).not.toContain("sign-in-immediately");
  });

  /**
   * GIVEN a visitor whose session the backend confirmed
   * WHEN the login page renders
   * THEN they are sent into the application instead of shown the form
   */
  it("turns an authenticated visitor away", async () => {
    getCurrentUser.mockResolvedValue({ email: "ada@example.com" });

    await expect(
      LoginPage({ searchParams: Promise.resolve({}) }),
    ).rejects.toThrow("NEXT_REDIRECT");

    expect(redirect).toHaveBeenCalledExactlyOnceWith("/");
  });

  /**
   * GIVEN any arrival at all, whether it was marked or not
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
