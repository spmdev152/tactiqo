import { describe, expect, it } from "vitest";

import {
  loginPathAfterSessionLoss,
  sessionLossMessage,
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

describe("sessionLossMessage", () => {
  /**
   * GIVEN an arrival caused by a session the backend refused to confirm
   * WHEN the warning copy is resolved
   * THEN a message asking the visitor to sign in again is returned
   */
  it("asks an involuntarily signed-out visitor to sign in again", () => {
    expect(sessionLossMessage("expired")).toBe(
      "Your session is no longer valid. Sign in again to continue.",
    );
  });

  /**
   * GIVEN an arrival caused by following a link into the application uncredentialed
   * WHEN the warning copy is resolved
   * THEN a message asking the visitor to sign in is returned
   */
  it("asks an uncredentialed visitor to sign in", () => {
    expect(sessionLossMessage("required")).toBe("Sign in to open that page.");
  });

  /**
   * GIVEN a deliberate arrival, whether a sign-out or a first visit, which sets no parameter
   * WHEN the warning copy is resolved
   * THEN there is nothing to report
   */
  it("stays silent when no reason was given", () => {
    expect(sessionLossMessage(undefined)).toBeNull();
  });

  /**
   * GIVEN a parameter value the product does not recognise, since a visitor can write any
   * WHEN the warning copy is resolved
   * THEN there is nothing to report
   */
  it("stays silent on an unrecognised reason", () => {
    expect(sessionLossMessage("<img onerror=alert(1)>")).toBeNull();
  });

  /**
   * GIVEN a reason inherited from the object prototype rather than declared
   * WHEN the warning copy is resolved
   * THEN there is nothing to report
   */
  it("stays silent on an inherited property name", () => {
    expect(sessionLossMessage("toString")).toBeNull();
    expect(sessionLossMessage("constructor")).toBeNull();
  });

  /**
   * GIVEN the parameter repeated, which arrives as a list
   * WHEN the warning copy is resolved
   * THEN there is nothing to report
   */
  it("stays silent on a repeated parameter", () => {
    expect(sessionLossMessage(["expired", "required"])).toBeNull();
  });
});
