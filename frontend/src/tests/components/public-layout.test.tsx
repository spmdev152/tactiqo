import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import PublicLayout from "@/app/(public)/layout";

const STUB_CHILD_TEXT = "Public page";

/**
 * Renders the public layout around a stub page, as a public route would.
 *
 * @returns The rendered container, for the queries a role cannot express.
 */
function renderPublicLayout(): HTMLElement {
  const { container } = render(
    <PublicLayout>
      <p>{STUB_CHILD_TEXT}</p>
    </PublicLayout>,
  );

  return container;
}

describe("PublicLayout", () => {
  /**
   * GIVEN a visitor with no session on a public route
   * WHEN the layout wraps the page
   * THEN the plain header and the page itself are all it renders
   */
  it("wraps a public page in the plain header", () => {
    renderPublicLayout();

    expect(screen.getByRole("banner")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "tactiqo" })).toHaveAttribute(
      "href",
      "/",
    );
    expect(screen.getByText(STUB_CHILD_TEXT)).toBeVisible();
  });

  /**
   * GIVEN a visitor with no session, who has nowhere inside the application to go
   * WHEN the layout wraps the page
   * THEN no sidebar and none of its navigation is rendered
   */
  it("keeps the application shell out of the unauthenticated group", () => {
    const container = renderPublicLayout();

    expect(container.querySelector('[data-slot="sidebar"]')).toBeNull();
    expect(
      screen.queryByRole("link", { name: "Overview" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: "Fixtures" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Toggle Sidebar" }),
    ).not.toBeInTheDocument();
  });
});
