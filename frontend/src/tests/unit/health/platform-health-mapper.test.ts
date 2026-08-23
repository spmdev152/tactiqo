import { describe, expect, it } from "vitest";

import { toPlatformHealth } from "@/features/health/mappers/platform-health";

describe("toPlatformHealth", () => {
  /**
   * GIVEN a backend health payload where the status and every dependency are ok
   * WHEN the payload is normalized for the product
   * THEN the platform is reported as operational with operational dependencies
   */
  it("normalizes a fully healthy payload", () => {
    const health = toPlatformHealth({
      status: "ok",
      version: "1.0.0",
      database: "ok",
      cache: "ok",
    });

    expect(health).toEqual({
      reported: true,
      status: "operational",
      version: "1.0.0",
      database: "operational",
      cache: "operational",
    });
  });

  /**
   * GIVEN a degraded backend health payload whose cache is unavailable
   * WHEN the payload is normalized for the product
   * THEN the platform is reported as degraded and the cache stays unavailable
   */
  it("normalizes a degraded payload without losing the failing dependency", () => {
    const health = toPlatformHealth({
      status: "degraded",
      version: "1.0.0",
      database: "ok",
      cache: "unavailable",
    });

    expect(health).toEqual({
      reported: true,
      status: "degraded",
      version: "1.0.0",
      database: "operational",
      cache: "unavailable",
    });
  });

  /**
   * GIVEN a backend health payload that omits both dependency fields
   * WHEN the payload is normalized for the product
   * THEN the platform health is not reported
   */
  it("reports nothing when the payload does not match the health contract", () => {
    const health = toPlatformHealth({ status: "ok", version: "1.0.0" });

    expect(health.reported).toBe(false);
  });

  /**
   * GIVEN a backend health payload whose database state is outside the contract
   * WHEN the payload is normalized for the product
   * THEN the platform health is not reported
   */
  it("reports nothing when a dependency state is outside the contract", () => {
    const health = toPlatformHealth({
      status: "ok",
      version: "1.0.0",
      database: "maybe",
      cache: "ok",
    });

    expect(health.reported).toBe(false);
  });

  /**
   * GIVEN a decoded body that is text rather than a health object
   * WHEN the body is normalized for the product
   * THEN the platform health is not reported
   */
  it("reports nothing when the body is not an object", () => {
    expect(toPlatformHealth("<html>502 Bad Gateway</html>").reported).toBe(
      false,
    );
  });
});
