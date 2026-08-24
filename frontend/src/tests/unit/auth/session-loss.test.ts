import { describe, expect, it } from "vitest";

import {
  loginPathAfterSessionLoss,
  sessionLossWarning,
} from "@/features/auth/session-loss";

describe("loginPathAfterSessionLoss", () => {
  /**
   * GIVEN a session the backend refused to confirm
   * WHEN the redirect target is built
   * THEN it points at the login page and carries the reason
   */
  it("carries an expired session to the login page", () => {
    expect(loginPathAfterSessionLoss("expired")).toBe("/login?session=expired");
  });

  /**
   * GIVEN a request for a protected path with no session cookie
   * WHEN the redirect target is built
   * THEN it points at the login page and carries the reason
   */
  it("carries a missing session to the login page", () => {
    expect(loginPathAfterSessionLoss("required")).toBe(
      "/login?session=required",
    );
  });
});

describe("sessionLossWarning", () => {
  /**
   * GIVEN an arrival caused by a session the backend refused to confirm
   * WHEN the warning is resolved
   * THEN the session is reported as expired and the visitor told to sign in again
   */
  it("reports an expired session", () => {
    expect(sessionLossWarning("expired")).toEqual({
      title: "Session expired",
      description: "Sign in again to access the platform.",
    });
  });

  /**
   * GIVEN an arrival caused by following a link into the application uncredentialed
   * WHEN the warning is resolved
   * THEN a sign-in is required without claiming a session ever existed
   */
  it("requires a sign-in without claiming a session expired", () => {
    expect(sessionLossWarning("required")).toEqual({
      title: "Sign in required",
      description: "Sign in to access the platform.",
    });
  });

  /**
   * GIVEN a deliberate arrival, whether a sign-out or a first visit, which sets no parameter
   * WHEN the warning is resolved
   * THEN there is nothing to report
   */
  it("stays silent when no reason was given", () => {
    expect(sessionLossWarning(undefined)).toBeNull();
  });

  /**
   * GIVEN a parameter value the product does not recognise, since a visitor can write any
   * WHEN the warning is resolved
   * THEN there is nothing to report
   */
  it("stays silent on an unrecognised reason", () => {
    expect(sessionLossWarning("<img onerror=alert(1)>")).toBeNull();
  });

  /**
   * GIVEN a reason inherited from the object prototype rather than declared
   * WHEN the warning is resolved
   * THEN there is nothing to report
   */
  it("stays silent on an inherited property name", () => {
    expect(sessionLossWarning("toString")).toBeNull();
    expect(sessionLossWarning("constructor")).toBeNull();
  });

  /**
   * GIVEN the parameter repeated, which arrives as a list
   * WHEN the warning is resolved
   * THEN there is nothing to report
   */
  it("stays silent on a repeated parameter", () => {
    expect(sessionLossWarning(["expired", "required"])).toBeNull();
  });
});
