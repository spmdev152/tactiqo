import { describe, expect, it } from "vitest";

import {
  SESSION_LOSS_PATH,
  sessionLossWarning,
} from "@/features/auth/domain/session-loss";

const EXPIRED = {
  title: "Session expired",
  description: "Sign in again to access the platform.",
};

const REQUIRED = {
  title: "Sign in required",
  description: "Sign in to access the platform.",
};

describe("SESSION_LOSS_PATH", () => {
  /**
   * GIVEN a visitor whose session was lost rather than surrendered
   * WHEN the redirect target is read
   * THEN it points at the login page and marks the arrival involuntary
   */
  it("marks the login destination as an involuntary arrival", () => {
    expect(SESSION_LOSS_PATH).toBe("/login?session=lost");
  });
});

describe("sessionLossWarning", () => {
  /**
   * GIVEN an involuntary arrival whose request still carries a session token
   * WHEN the warning is resolved
   * THEN the session is reported expired, which the surviving cookie makes true
   */
  it("reports an expired session when a token was still sent", () => {
    expect(sessionLossWarning("lost", true)).toEqual(EXPIRED);
  });

  /**
   * GIVEN an involuntary arrival whose request carries no session token
   * WHEN the warning is resolved
   * THEN a sign-in is required without claiming a session ever existed
   */
  it("requires a sign-in when no token was sent", () => {
    expect(sessionLossWarning("lost", false)).toEqual(REQUIRED);
  });

  /**
   * GIVEN a forged marker sent to somebody who never held a session
   * WHEN the warning is resolved
   * THEN they are not told a session expired, because the cookie decides the copy
   */
  it("cannot be forged into claiming a session expired", () => {
    expect(sessionLossWarning("lost", false)).not.toEqual(EXPIRED);
    expect(sessionLossWarning("expired", false)).toBeNull();
  });

  /**
   * GIVEN a deliberate arrival, whether a sign-out or a first visit, which marks nothing
   * WHEN the warning is resolved
   * THEN there is nothing to report, whatever the cookie says
   */
  it("stays silent when the arrival is unmarked", () => {
    expect(sessionLossWarning(undefined, true)).toBeNull();
    expect(sessionLossWarning(undefined, false)).toBeNull();
  });

  /**
   * GIVEN a marker value the product does not recognise, since a visitor can write any
   * WHEN the warning is resolved
   * THEN there is nothing to report
   */
  it("stays silent on an unrecognised marker", () => {
    expect(sessionLossWarning("<img onerror=alert(1)>", true)).toBeNull();
  });

  /**
   * GIVEN a marker inherited from the object prototype rather than declared
   * WHEN the warning is resolved
   * THEN there is nothing to report
   */
  it("stays silent on an inherited property name", () => {
    expect(sessionLossWarning("toString", true)).toBeNull();
    expect(sessionLossWarning("constructor", true)).toBeNull();
  });

  /**
   * GIVEN the parameter repeated, which arrives as a list
   * WHEN the warning is resolved
   * THEN there is nothing to report
   */
  it("stays silent on a repeated parameter", () => {
    expect(sessionLossWarning(["lost", "lost"], true)).toBeNull();
  });
});
