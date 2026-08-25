import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AppSidebar } from "@/components/app-sidebar";
import { SidebarProvider } from "@/components/ui/sidebar";
import { TooltipProvider } from "@/components/ui/tooltip";

const { requireUser, usePathname } = vi.hoisted(() => ({
  requireUser: vi.fn(),
  usePathname: vi.fn().mockReturnValue("/"),
}));

// The server-only marker throws outside the React Server condition, which Vitest does not set.
vi.mock("server-only", () => ({}));

vi.mock("next/navigation", () => ({ usePathname }));

vi.mock("@/features/auth/server/require-user", () => ({ requireUser }));

vi.mock("@/features/auth/server/actions", () => ({ signOutAction: vi.fn() }));

const SIGNED_IN_EMAIL = "alexandra.fernandez@example.com";

/**
 * Renders the sidebar inside the providers the shell mounts around it.
 *
 * @remarks
 * The sidebar is an async Server Component, so it is awaited into an element
 * before the client providers wrap it, exactly as the shell layout does.
 */
async function renderSidebar(): Promise<void> {
  const sidebar = await AppSidebar();

  render(
    <TooltipProvider>
      <SidebarProvider>{sidebar}</SidebarProvider>
    </TooltipProvider>,
  );
}

describe("AppSidebar", () => {
  beforeEach(() => {
    requireUser.mockResolvedValue({
      id: 7,
      email: SIGNED_IN_EMAIL,
      fullName: "Alexandra Fernández",
    });
    usePathname.mockReturnValue("/");
  });

  /**
   * GIVEN a confirmed session
   * WHEN the sidebar is rendered
   * THEN the footer states the signed-in address and links to the account page
   */
  it("states the signed-in address in the footer", async () => {
    await renderSidebar();

    const account = screen.getByRole("link", {
      name: `Account ${SIGNED_IN_EMAIL}`,
    });

    expect(account).toHaveAttribute("href", "/account");
    expect(account.closest("[data-slot=sidebar-footer]")).not.toBeNull();
  });

  /**
   * GIVEN an address too long for a sidebar this narrow
   * WHEN the account entry is rendered
   * THEN the truncated label keeps the whole address reachable on hover
   */
  it("keeps the truncated address available in full", async () => {
    await renderSidebar();

    const label = screen.getByTitle(SIGNED_IN_EMAIL);

    expect(label).toHaveTextContent(SIGNED_IN_EMAIL);
  });

  /**
   * GIVEN a visitor already on the account page
   * WHEN the sidebar is rendered
   * THEN the account entry is the one marked active
   */
  it("marks the account entry active on its own route", async () => {
    usePathname.mockReturnValue("/account");

    await renderSidebar();

    expect(
      screen.getByRole("link", { name: `Account ${SIGNED_IN_EMAIL}` }),
    ).toHaveAttribute("data-active", "true");
  });

  /**
   * GIVEN a confirmed session
   * WHEN the sidebar is rendered
   * THEN the last control of the sidebar submits the sign-out form
   */
  it("ends the sidebar with the sign-out form", async () => {
    await renderSidebar();

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
  it("marks the current route active", async () => {
    usePathname.mockReturnValue("/");

    await renderSidebar();

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
  it("links the brand to the landing route", async () => {
    await renderSidebar();

    expect(screen.getByRole("link", { name: "tactiqo" })).toHaveAttribute(
      "href",
      "/",
    );
  });
});
