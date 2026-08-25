import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import { AppSidebar } from "@/components/app-sidebar";
import { SidebarNavigationDismissal } from "@/components/sidebar-navigation-dismissal";
import { SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { TooltipProvider } from "@/components/ui/tooltip";

const { usePathname, useIsMobile } = vi.hoisted(() => ({
  usePathname: vi.fn(),
  useIsMobile: vi.fn(),
}));

vi.mock("next/navigation", () => ({ usePathname }));

vi.mock("@/hooks/use-mobile", () => ({ useIsMobile }));

vi.mock("@/features/auth/server/actions", () => ({ signOutAction: vi.fn() }));

/**
 * Teaches jsdom the layout and pointer APIs the drawer measures itself with.
 * None of them exist there, and the dialog throws on mount without them.
 */
function installDrawerEnvironment(): void {
  globalThis.ResizeObserver = class {
    observe(): void {}
    unobserve(): void {}
    disconnect(): void {}
  };

  Element.prototype.scrollIntoView = () => {};
  Element.prototype.hasPointerCapture = () => false;
  Element.prototype.releasePointerCapture = () => {};
  Element.prototype.setPointerCapture = () => {};
}

/**
 * The shell as a phone renders it, with the dismissal effect mounted.
 *
 * @returns The shell tree.
 */
function shell() {
  return (
    <TooltipProvider>
      <SidebarProvider>
        <SidebarNavigationDismissal />
        <SidebarTrigger />
        <AppSidebar />
      </SidebarProvider>
    </TooltipProvider>
  );
}

/**
 * Renders the shell on a phone and opens its drawer.
 *
 * @returns The render result, so a test can land a navigation on it.
 */
function renderOpenDrawer() {
  const rendered = render(shell());

  fireEvent.click(screen.getByRole("button", { name: "Toggle Sidebar" }));

  return rendered;
}

describe("AppSidebar on a phone", () => {
  beforeAll(installDrawerEnvironment);

  beforeEach(() => {
    usePathname.mockReturnValue("/");
    useIsMobile.mockReturnValue(true);
  });

  /**
   * GIVEN the sidebar opened as a drawer on a phone
   * WHEN a navigation entry is chosen but the route has not changed yet
   * THEN the drawer stays open, so nothing animates while the request is in flight
   */
  it("keeps the drawer open until the navigation lands", async () => {
    renderOpenDrawer();

    expect(await screen.findByRole("dialog")).toBeVisible();

    fireEvent.click(screen.getByRole("link", { name: "Fixtures" }));

    expect(screen.getByRole("dialog")).toBeVisible();
  });

  /**
   * GIVEN a drawer left open by a navigation started from it
   * WHEN the new route lands
   * THEN the drawer is dismissed
   */
  it("dismisses the drawer once the route has changed", async () => {
    const { rerender } = renderOpenDrawer();

    expect(await screen.findByRole("dialog")).toBeVisible();

    usePathname.mockReturnValue("/fixtures");

    rerender(shell());

    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });

  /**
   * GIVEN a drawer dismissed because a navigation landed
   * WHEN the document is inspected afterwards
   * THEN the marker that suppressed the exit animation has been cleared
   */
  it("leaves no dismissal marker behind", async () => {
    const { rerender } = renderOpenDrawer();

    expect(await screen.findByRole("dialog")).toBeVisible();

    usePathname.mockReturnValue("/account");

    rerender(shell());

    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());

    await waitFor(() =>
      expect(document.body).not.toHaveAttribute("data-sidebar-dismissing"),
    );
  });
});
