import { render, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SessionLossToast } from "@/features/auth/components/session-loss-toast";

const WARNING = {
  title: "Session expired",
  description: "Sign in again to access the platform.",
};

const { replace, warning } = vi.hoisted(() => ({
  replace: vi.fn<(href: string, options?: { scroll?: boolean }) => void>(),
  warning: vi.fn(),
}));

vi.mock("sonner", () => ({ toast: { warning } }));

vi.mock("next/navigation", () => ({ useRouter: () => ({ replace }) }));

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
    replace.mockReset();
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
   * THEN the router drops it, so the address bar cannot desync from router state
   */
  it("cleans the marker out of the url through the router", async () => {
    render(<SessionLossToast warning={WARNING} />);

    await waitFor(() =>
      expect(replace).toHaveBeenCalledExactlyOnceWith("/login", {
        scroll: false,
      }),
    );
  });

  /**
   * GIVEN a query carrying the marker alongside an unrelated parameter
   * WHEN the toast has been requested
   * THEN only the marker is dropped
   */
  it("keeps every other parameter while cleaning the marker", async () => {
    arriveWith("session=lost&email=ada");

    render(<SessionLossToast warning={WARNING} />);

    await waitFor(() =>
      expect(replace).toHaveBeenCalledExactlyOnceWith("/login?email=ada", {
        scroll: false,
      }),
    );
  });

  /**
   * GIVEN a warning requested and its marker already cleaned
   * WHEN the same notice is mounted again, as a repeated arrival does
   * THEN it warns again, because nothing about the first arrival is remembered
   */
  it("warns again on every fresh mount", async () => {
    const first = render(<SessionLossToast warning={WARNING} />);

    await waitFor(() => expect(warning).toHaveBeenCalledOnce());

    first.unmount();
    arriveWith("session=lost");

    render(<SessionLossToast warning={WARNING} />);

    await waitFor(() => expect(warning).toHaveBeenCalledTimes(2));
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
