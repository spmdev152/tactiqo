import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SiteHeader } from "@/components/site-header";

const { useTheme } = vi.hoisted(() => ({ useTheme: vi.fn() }));

vi.mock("next-themes", () => ({ useTheme }));

describe("SiteHeader", () => {
  beforeEach(() => {
    useTheme.mockReturnValue({ resolvedTheme: "light", setTheme: vi.fn() });
  });

  /**
   * GIVEN the application header
   * WHEN it is rendered
   * THEN the wordmark reads as one lowercase word and links to the landing route
   */
  it("links the wordmark to the landing route", () => {
    render(<SiteHeader />);

    expect(screen.getByRole("link", { name: "tactiqo" })).toHaveAttribute(
      "href",
      "/",
    );
  });

  /**
   * GIVEN the application header
   * WHEN it is rendered
   * THEN the theme switch is part of it, so every route carries the control
   */
  it("carries the theme switch", () => {
    render(<SiteHeader />);

    expect(screen.getByRole("switch", { name: "Dark mode" })).toBeVisible();
  });
});
