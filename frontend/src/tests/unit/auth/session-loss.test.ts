import { describe, expect, it } from "vitest";

import {
  SESSION_LOSS_PATH,
  sessionLossWarning,
} from "@/features/auth/domain/session-loss";

describe("SESSION_LOSS_PATH", () => {
  /**
   * GIVEN a visitor whose session was lost rather than surrendered
   * WHEN the redirect target is read
   * THEN it points at the login page and marks the arrival involuntary
   */
  it("marks the login destination as an involuntary arrival", () => {
    expect(SESSION_LOSS_PATH).toBe("/login?session=lost");
  });

  /**
   * GIVEN a marker the login page decides copy from rather than trusting
   * WHEN the destination is read
   * THEN it names no reason, so nothing it carries can be forged into a claim
   */
  it("carries no claim about why the session was lost", () => {
    expect(SESSION_LOSS_PATH).not.toContain("expired");
    expect(SESSION_LOSS_PATH).not.toContain("required");
  });
});

describe("sessionLossWarning", () => {
  /**
   * GIVEN a request that still carries a session token the backend refused
   * WHEN the warning is chosen
   * THEN the session is reported expired, which the surviving cookie makes true
   */
  it("reports an expired session when a token was sent", () => {
    expect(sessionLossWarning(true)).toEqual({
      title: "Session expired",
      description: "Sign in again to access the platform.",
    });
  });

  /**
   * GIVEN a request carrying no session token at all
   * WHEN the warning is chosen
   * THEN a sign-in is required without claiming a session ever existed
   */
  it("requires a sign-in when no token was sent", () => {
    expect(sessionLossWarning(false)).toEqual({
      title: "Sign in required",
      description: "Sign in to access the platform.",
    });
  });
});
