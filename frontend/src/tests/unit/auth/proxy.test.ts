import { NextRequest } from "next/server";

import { describe, expect, it } from "vitest";

import { SESSION_COOKIE_NAME } from "@/features/auth/domain/session-cookie-name";
import { proxy } from "@/proxy";

const ORIGIN = "https://tactiqo.test";

const TEMPORARY_REDIRECT = 307;

/**
 * Builds a navigation request, optionally carrying a session cookie.
 *
 * @param path - Path being requested.
 * @param token - Session token to send, or `null` to send no cookie.
 * @returns The request the proxy receives.
 */
function navigationTo(path: string, token: string | null = null): NextRequest {
  const request = new NextRequest(new URL(path, ORIGIN));

  if (token !== null) {
    request.cookies.set(SESSION_COOKIE_NAME, token);
  }

  return request;
}

describe("proxy", () => {
  /**
   * GIVEN a request for a protected path without a session cookie
   * WHEN the proxy handles it
   * THEN it is redirected to the login page, told why, so the form is not unexplained
   */
  it("sends an uncredentialed request to the login page with a reason", () => {
    const response = proxy(navigationTo("/"));

    expect(response.status).toBe(TEMPORARY_REDIRECT);
    expect(response.headers.get("location")).toBe(
      `${ORIGIN}/login?session=required`,
    );
  });

  /**
   * GIVEN a request for the login page without a session cookie
   * WHEN the proxy handles it
   * THEN it continues, because the login page is the redirect target itself
   */
  it("lets an uncredentialed request reach the login page", () => {
    const response = proxy(navigationTo("/login"));

    expect(response.headers.get("location")).toBeNull();
  });

  /**
   * GIVEN a request for the account-request page without a session cookie
   * WHEN the proxy handles it
   * THEN it continues, because the page exists for people with no session
   */
  it("lets an uncredentialed request reach the account-request page", () => {
    const response = proxy(navigationTo("/signup"));

    expect(response.headers.get("location")).toBeNull();
  });

  /**
   * GIVEN a request for the login page carrying a stale session cookie
   * WHEN the proxy handles it
   * THEN it continues, because bouncing it to a page that bounces back loops
   */
  it("never redirects a cookie away from the login page", () => {
    const response = proxy(navigationTo("/login", "stale-token"));

    expect(response.status).not.toBe(TEMPORARY_REDIRECT);
    expect(response.headers.get("location")).toBeNull();
  });

  /**
   * GIVEN a request for the account-request page carrying a stale session cookie
   * WHEN the proxy handles it
   * THEN it continues, because it is as much a loop target as the login page
   */
  it("never redirects a cookie away from the account-request page", () => {
    const response = proxy(navigationTo("/signup", "stale-token"));

    expect(response.status).not.toBe(TEMPORARY_REDIRECT);
    expect(response.headers.get("location")).toBeNull();
  });

  /**
   * GIVEN a request for a protected path carrying a session cookie
   * WHEN the proxy handles it
   * THEN it continues, leaving the page to verify the token
   */
  it("defers a credentialed request to the page", () => {
    const response = proxy(navigationTo("/", "some-token"));

    expect(response.headers.get("location")).toBeNull();
  });
});
