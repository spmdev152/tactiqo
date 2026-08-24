import { afterEach, describe, expect, it, vi } from "vitest";

import { forwardingHeaders } from "@/features/auth/server/forwarding-chain";

// The server-only marker throws outside the React Server condition, which Vitest does not set.
vi.mock("server-only", () => ({}));

const { headers } = vi.hoisted(() => ({ headers: vi.fn() }));

vi.mock("next/headers", () => ({ headers }));

/**
 * Stubs the headers of the current request.
 *
 * @param requestHeaders - Header pairs the request is treated as carrying.
 */
function givenRequestHeaders(requestHeaders: Record<string, string>): void {
  headers.mockResolvedValue(new Headers(requestHeaders));
}

describe("forwardingHeaders", () => {
  afterEach(() => {
    vi.resetAllMocks();
  });

  /**
   * GIVEN a request carrying a forwarding chain
   * WHEN the forwarding headers are built
   * THEN the chain is passed on verbatim for the backend to interpret
   */
  it("forwards the chain of the current request", async () => {
    givenRequestHeaders({ "x-forwarded-for": "198.51.100.7, 192.0.2.20" });

    await expect(forwardingHeaders()).resolves.toEqual({
      "x-forwarded-for": "198.51.100.7, 192.0.2.20",
    });
  });

  /**
   * GIVEN a request carrying no forwarding chain
   * WHEN the forwarding headers are built
   * THEN no header is produced rather than an empty one
   */
  it("produces no header when the request carries no chain", async () => {
    givenRequestHeaders({ accept: "text/html" });

    await expect(forwardingHeaders()).resolves.toEqual({});
  });
});
