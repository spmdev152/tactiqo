import { render, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SessionLossToast } from "@/features/auth/components/session-loss-toast";

const { hookSearch, replace, router, warning } = vi.hoisted(() => {
  const replaceMock =
    vi.fn<(href: string, options?: { scroll?: boolean }) => void>();

  return {
    hookSearch: { value: null as string | null },
    replace: replaceMock,
    // Next memoizes the router, so a fresh object per render would re-run the
    // effect on every render and hide whether its dependencies are right.
    router: { replace: replaceMock },
    warning: vi.fn(),
  };
});

vi.mock("sonner", () => ({ toast: { warning } }));

vi.mock("next/navigation", () => ({
  useRouter: () => router,
  useSearchParams: () =>
    new URLSearchParams(hookSearch.value ?? window.location.search),
}));

/**
 * Places the browser on an arrival at the login page.
 *
 * @param query - Query string the arrival carries, without its leading marker.
 */
function arriveWith(query: string): void {
  hookSearch.value = null;

  window.history.replaceState(
    null,
    "",
    query === "" ? "/login" : `/login?${query}`,
  );
}

/**
 * Waits for the frame and the task the notice defers its request across.
 */
function settleDeferredRequest(): Promise<void> {
  const { promise, resolve } = Promise.withResolvers<void>();

  requestAnimationFrame(() => setTimeout(resolve, 0));

  return promise;
}

describe("SessionLossToast", () => {
  beforeEach(() => {
    replace.mockReset();
    warning.mockReset();
    arriveWith("session=lost");
  });

  /**
   * GIVEN the router reporting no parameters yet, as it does on a first client render
   * WHEN the notice mounts on a url that plainly carries the marker
   * THEN it warns anyway, because the address bar decides and the hook only re-arms
   */
  it("warns even when the router reports no parameters yet", async () => {
    hookSearch.value = "";

    render(<SessionLossToast sessionTokenPresent={false} />);

    await waitFor(() =>
      expect(warning).toHaveBeenCalledExactlyOnceWith(
        "Sign in required",
        expect.anything(),
      ),
    );

    expect(replace).toHaveBeenCalledExactlyOnceWith("/login", {
      scroll: false,
    });
  });

  /**
   * GIVEN an arrival that produces no React update at all, as a cached segment does
   * WHEN the address bar alone starts carrying the marker
   * THEN the warning still fires, because the watch reads the address bar rather than state
   */
  it("warns on an arrival that re-renders nothing", async () => {
    arriveWith("");

    render(<SessionLossToast sessionTokenPresent={false} />);

    await settleDeferredRequest();

    expect(warning).not.toHaveBeenCalled();

    window.history.replaceState(null, "", "/login?session=lost");

    await waitFor(() => expect(warning).toHaveBeenCalledOnce(), {
      timeout: 3000,
    });

    expect(replace).toHaveBeenCalledExactlyOnceWith("/login", {
      scroll: false,
    });
  });

  /**
   * GIVEN an involuntary arrival whose request still carried a session cookie
   * WHEN the notice mounts
   * THEN the expiry is reported as a themed warning under a stable identifier
   */
  it("reports an expired session when a token was sent", async () => {
    render(<SessionLossToast sessionTokenPresent />);

    await waitFor(() =>
      expect(warning).toHaveBeenCalledExactlyOnceWith("Session expired", {
        description: "Sign in again to access the platform.",
        id: "session-loss",
        richColors: true,
      }),
    );
  });

  /**
   * GIVEN an involuntary arrival carrying no session cookie at all
   * WHEN the notice mounts
   * THEN a sign-in is requested without claiming a session expired
   */
  it("requests a sign-in when no token was sent", async () => {
    render(<SessionLossToast sessionTokenPresent={false} />);

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
   * WHEN the notice mounts
   * THEN the cookie decides the copy, so no expiry is ever claimed
   */
  it("cannot be forged into claiming an expiry", async () => {
    render(<SessionLossToast sessionTokenPresent={false} />);

    await waitFor(() => expect(warning).toHaveBeenCalledOnce());

    expect(warning).not.toHaveBeenCalledWith(
      "Session expired",
      expect.anything(),
    );
  });

  /**
   * GIVEN an arrival the redirecting side did not mark, such as a sign-out or a first visit
   * WHEN the notice mounts, as it does on every render of the page
   * THEN nothing is requested and the address bar is left alone
   */
  it("stays silent on an unmarked arrival", async () => {
    arriveWith("");

    render(<SessionLossToast sessionTokenPresent={false} />);

    await settleDeferredRequest();

    expect(warning).not.toHaveBeenCalled();
    expect(replace).not.toHaveBeenCalled();
  });

  /**
   * GIVEN a marker value the product does not recognise, since a visitor can write any
   * WHEN the notice mounts
   * THEN nothing is requested
   */
  it("stays silent on an unrecognised marker", async () => {
    arriveWith("session=%3Cimg%20onerror%3Dalert(1)%3E");

    render(<SessionLossToast sessionTokenPresent />);

    await settleDeferredRequest();

    expect(warning).not.toHaveBeenCalled();
  });

  /**
   * GIVEN Sonner entering by transition from a state the browser has to paint first
   * WHEN the notice mounts
   * THEN the request waits for a frame, since asking inside the commit skips the entry animation
   */
  it("defers the request past the mounting commit", async () => {
    render(<SessionLossToast sessionTokenPresent />);

    expect(warning).not.toHaveBeenCalled();

    await waitFor(() => expect(warning).toHaveBeenCalledOnce());
  });

  /**
   * GIVEN the marker still present in the address bar
   * WHEN the toast has been requested
   * THEN the router drops it, so the address bar cannot desync from router state
   */
  it("cleans the marker out of the url through the router", async () => {
    render(<SessionLossToast sessionTokenPresent />);

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

    render(<SessionLossToast sessionTokenPresent />);

    await waitFor(() =>
      expect(replace).toHaveBeenCalledExactlyOnceWith("/login?email=ada", {
        scroll: false,
      }),
    );
  });

  /**
   * GIVEN a marked arrival already warned about and cleaned
   * WHEN the marker returns, as a repeated arrival at a protected path makes it
   * THEN the warning fires again rather than once per visit
   */
  it("warns again when the marker returns", async () => {
    render(<SessionLossToast sessionTokenPresent />);

    await waitFor(() => expect(warning).toHaveBeenCalledOnce());

    arriveWith("");

    await settleDeferredRequest();

    arriveWith("session=lost");

    await waitFor(() => expect(warning).toHaveBeenCalledTimes(2), {
      timeout: 3000,
    });
  });

  /**
   * GIVEN the shared toaster in the root layout owning the live region
   * WHEN the notice mounts
   * THEN it contributes no markup of its own
   */
  it("renders nothing itself", () => {
    const { container } = render(<SessionLossToast sessionTokenPresent />);

    expect(container).toBeEmptyDOMElement();
  });
});
