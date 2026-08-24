import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

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
 */
function renderSidebar() {
  render(
    <TooltipProvider>
      <SidebarProvider>
        <AppSidebar />
      </SidebarProvider>
    </TooltipProvider>,
  );
}

describe("AppSidebar", () => {
  beforeEach(() => {
    usePathname.mockReturnValue("/");
  });

  /**
   * GIVEN a confirmed session
   * WHEN the sidebar is rendered
   * THEN the footer offers the account page rather than stating the address
   */
  it("offers the account page from the footer", () => {
    renderSidebar();

    const account = screen.getByRole("link", { name: "Account" });

    expect(account).toHaveAttribute("href", "/account");
    expect(account.closest("[data-slot=sidebar-footer]")).not.toBeNull();
  });

  /**
   * GIVEN a visitor already on the account page
   * WHEN the sidebar is rendered
   * THEN the account entry is the one marked active
   */
  it("marks the account entry active on its own route", () => {
    usePathname.mockReturnValue("/account");

    renderSidebar();

    expect(screen.getByRole("link", { name: "Account" })).toHaveAttribute(
      "data-active",
      "true",
    );
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
