import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AppSidebar } from "@/components/app-sidebar";
import { SidebarProvider } from "@/components/ui/sidebar";
import { TooltipProvider } from "@/components/ui/tooltip";

const { usePathname } = vi.hoisted(() => ({
  usePathname: vi.fn().mockReturnValue("/"),
}));

vi.mock("next/navigation", () => ({ usePathname }));

vi.mock("@/features/auth/server/actions", () => ({ signOutAction: vi.fn() }));

/**
 * Renders the sidebar inside the providers the shell mounts around it.
 *
 * @param email - Address the rendered session is signed in as.
 */
function renderSidebar(email = "ada@example.com") {
  render(
    <TooltipProvider>
      <SidebarProvider>
        <AppSidebar email={email} />
      </SidebarProvider>
    </TooltipProvider>,
  );
}

describe("AppSidebar", () => {
  /**
   * GIVEN a confirmed session
   * WHEN the sidebar is rendered
   * THEN the account it is signed in as is stated in the footer
   */
  it("states the signed-in account", () => {
    renderSidebar("grace@example.com");

    expect(screen.getByText("grace@example.com")).toBeVisible();
  });

  /**
   * GIVEN a confirmed session
   * WHEN the sidebar is rendered
   * THEN the last control of the sidebar submits the sign-out form
   */
  it("ends the sidebar with the sign-out form", () => {
    renderSidebar();

    const submit = screen.getByRole("button", { name: "Sign out" });

    expect(submit).toHaveAttribute("type", "submit");
    expect(submit.closest("form")).not.toBeNull();
    expect(submit.closest("[data-slot=sidebar-footer]")).not.toBeNull();
  });

  /**
   * GIVEN the sidebar navigation on the landing route
   * WHEN the entries are inspected
   * THEN the current route is the one marked active
   */
  it("marks the current route active", () => {
    usePathname.mockReturnValue("/");

    renderSidebar();

    expect(screen.getByRole("link", { name: "Overview" })).toHaveAttribute(
      "data-active",
      "true",
    );
  });

  /**
   * GIVEN the sidebar brand
   * WHEN it is rendered
   * THEN it keeps an accessible name and links to the landing route
   */
  it("links the brand to the landing route", () => {
    renderSidebar();

    expect(screen.getByRole("link", { name: "tactiqo" })).toHaveAttribute(
      "href",
      "/",
    );
  });
});
