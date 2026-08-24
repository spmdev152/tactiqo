import { render, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SessionLossToast } from "@/features/auth/components/session-loss-toast";

const WARNING = {
  title: "Session expired",
  description: "Sign in again to access the platform.",
};

const { warning } = vi.hoisted(() => ({ warning: vi.fn() }));

vi.mock("sonner", () => ({ toast: { warning } }));

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(window.location.search),
}));

/**
 * Waits for the frame and the task the notice defers its request across.
 */
function settleDeferredRequest(): Promise<void> {
  const { promise, resolve } = Promise.withResolvers<void>();

  requestAnimationFrame(() => setTimeout(resolve, 0));

  return promise;
}

/**
 * Places the browser on an arrival at the login page.
 *
 * @param query - Query string the arrival carries, without its leading marker.
 */
function arriveWith(query: string): void {
  window.history.replaceState(null, "", `/login?${query}`);
}

describe("SessionLossToast", () => {
  beforeEach(() => {
    warning.mockReset();
    arriveWith("session=lost");
  });

  /**
   * GIVEN a visitor who arrived at the login page having lost their session
   * WHEN the notice mounts
   * THEN title and description are requested as a themed warning under a stable identifier
   */
  it("requests a warning toast for the resolved copy", async () => {
    render(<SessionLossToast warning={WARNING} />);

    await waitFor(() =>
      expect(warning).toHaveBeenCalledExactlyOnceWith("Session expired", {
        description: "Sign in again to access the platform.",
        id: "session-loss",
        richColors: true,
      }),
    );
  });

  /**
   * GIVEN Sonner entering by transition from a state the browser has to paint first
   * WHEN the notice mounts
   * THEN the request waits for a frame, since asking inside the commit skips the entry animation
   */
  it("defers the request past the mounting commit", async () => {
    render(<SessionLossToast warning={WARNING} />);

    expect(warning).not.toHaveBeenCalled();

    await waitFor(() => expect(warning).toHaveBeenCalledOnce());
  });

  /**
   * GIVEN the marker still present in the address bar
   * WHEN the toast has been requested
   * THEN the parameter is dropped so a refresh cannot repeat the warning
   */
  it("cleans the marker out of the url", async () => {
    render(<SessionLossToast warning={WARNING} />);

    await waitFor(() => expect(window.location.search).toBe(""));

    expect(window.location.pathname).toBe("/login");
  });

  /**
   * GIVEN a query carrying the marker alongside an unrelated parameter
   * WHEN the toast has been requested
   * THEN only the marker is dropped
   */
  it("keeps every other parameter while cleaning the marker", async () => {
    arriveWith("session=lost&email=ada");

    render(<SessionLossToast warning={WARNING} />);

    await waitFor(() => expect(window.location.search).toBe("?email=ada"));
  });

  /**
   * GIVEN the marker already cleaned, as it is after the first arrival
   * WHEN the notice re-renders without it
   * THEN nothing is requested, because only a marked arrival warrants a toast
   */
  it("requests nothing once the arrival is no longer marked", async () => {
    window.history.replaceState(null, "", "/login");

    render(<SessionLossToast warning={WARNING} />);

    await settleDeferredRequest();

    expect(warning).not.toHaveBeenCalled();
  });

  /**
   * GIVEN the shared toaster in the root layout owning the live region
   * WHEN the notice mounts
   * THEN it contributes no markup of its own
   */
  it("renders nothing itself", () => {
    const { container } = render(<SessionLossToast warning={WARNING} />);

    expect(container).toBeEmptyDOMElement();
  });
});
