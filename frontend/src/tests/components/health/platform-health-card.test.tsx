import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PlatformHealthCard } from "@/features/health/components/platform-health-card";

describe("PlatformHealthCard", () => {
  /**
   * GIVEN a reported platform health with an operational database and cache
   * WHEN the card is rendered
   * THEN the version, both dependencies and their operational badges are shown
   */
  it("shows the reported version and every dependency state", () => {
    render(
      <PlatformHealthCard
        health={{
          reported: true,
          status: "operational",
          version: "1.0.0",
          database: "operational",
          cache: "operational",
        }}
      />,
    );

    expect(screen.getByText("Version 1.0.0")).toBeInTheDocument();
    expect(screen.getByText("Database")).toBeInTheDocument();
    expect(screen.getByText("Cache")).toBeInTheDocument();
    expect(screen.getAllByText("Operational")).toHaveLength(3);
    expect(screen.queryByText("Unavailable")).not.toBeInTheDocument();
  });

  /**
   * GIVEN a reported platform health that is degraded by an unavailable cache
   * WHEN the card is rendered
   * THEN the degraded platform, the operational database and the unavailable cache are shown
   */
  it("distinguishes a degraded platform from its failing dependency", () => {
    render(
      <PlatformHealthCard
        health={{
          reported: true,
          status: "degraded",
          version: "1.0.0",
          database: "operational",
          cache: "unavailable",
        }}
      />,
    );

    expect(screen.getByText("Degraded")).toBeInTheDocument();
    expect(screen.getByText("Operational")).toBeInTheDocument();
    expect(screen.getByText("Unavailable")).toBeInTheDocument();
  });

  /**
   * GIVEN an unreported platform health carrying an unreachable API reason
   * WHEN the card is rendered
   * THEN the reason is shown and no dependency state is invented
   */
  it("explains why health is unknown instead of inventing dependency states", () => {
    render(
      <PlatformHealthCard
        health={{
          reported: false,
          reason: "The API could not be reached.",
        }}
      />,
    );

    expect(screen.getByRole("status")).toHaveTextContent(
      "The API could not be reached.",
    );

    expect(screen.getByText("Unavailable")).toBeInTheDocument();
    expect(screen.queryByText("Database")).not.toBeInTheDocument();
    expect(screen.queryByText("Cache")).not.toBeInTheDocument();
    expect(screen.queryByText("Operational")).not.toBeInTheDocument();
  });
});
