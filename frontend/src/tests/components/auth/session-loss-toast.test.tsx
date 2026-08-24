import { render } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SessionLossToast } from "@/features/auth/components/session-loss-toast";

const WARNING = {
  title: "Session expired",
  description: "Sign in again to access the platform.",
};

const { warning } = vi.hoisted(() => ({ warning: vi.fn() }));

vi.mock("sonner", () => ({ toast: { warning } }));

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
    arriveWith("session=expired");
  });

  /**
   * GIVEN a visitor who arrived at the login page having lost their session
   * WHEN the notice mounts
   * THEN title and description are requested as a themed warning under a stable identifier
   */
  it("requests a warning toast for the resolved copy", () => {
    render(<SessionLossToast warning={WARNING} />);

    expect(warning).toHaveBeenCalledExactlyOnceWith("Session expired", {
      description: "Sign in again to access the platform.",
      id: "session-loss",
      richColors: true,
    });
  });

  /**
   * GIVEN the reason still present in the address bar
   * WHEN the toast has been requested
   * THEN the parameter is dropped so a refresh cannot repeat the warning
   */
  it("cleans the reason out of the url", () => {
    render(<SessionLossToast warning={WARNING} />);

    expect(window.location.pathname).toBe("/login");
    expect(window.location.search).toBe("");
  });

  /**
   * GIVEN a query carrying the reason alongside an unrelated parameter
   * WHEN the toast has been requested
   * THEN only the reason is dropped
   */
  it("keeps every other parameter while cleaning the reason", () => {
    arriveWith("session=required&email=ada");

    render(<SessionLossToast warning={WARNING} />);

    expect(window.location.search).toBe("?email=ada");
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
