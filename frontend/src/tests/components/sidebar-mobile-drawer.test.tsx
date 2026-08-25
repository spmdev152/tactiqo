import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import { AppSidebar } from "@/components/app-sidebar";
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
 * Renders the shell on a phone and opens its drawer.
 */
function renderOpenDrawer(): void {
  render(
    <TooltipProvider>
      <SidebarProvider>
        <SidebarTrigger />
        <AppSidebar />
      </SidebarProvider>
    </TooltipProvider>,
  );

  fireEvent.click(screen.getByRole("button", { name: "Toggle Sidebar" }));
}

describe("AppSidebar on a phone", () => {
  beforeAll(installDrawerEnvironment);

  beforeEach(() => {
    usePathname.mockReturnValue("/");
    useIsMobile.mockReturnValue(true);
  });

  /**
   * GIVEN the sidebar opened as a drawer on a phone
   * WHEN a navigation entry is chosen
   * THEN the drawer dismisses itself instead of covering the page it opened
   */
  it("dismisses the drawer when a section is chosen", async () => {
    renderOpenDrawer();

    expect(await screen.findByRole("dialog")).toBeVisible();

    fireEvent.click(screen.getByRole("link", { name: "Fixtures" }));

    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });

  /**
   * GIVEN the sidebar opened as a drawer on a phone
   * WHEN the account entry is chosen
   * THEN the drawer dismisses itself as well
   */
  it("dismisses the drawer when the account entry is chosen", async () => {
    renderOpenDrawer();

    expect(await screen.findByRole("dialog")).toBeVisible();

    fireEvent.click(screen.getByRole("link", { name: "Account" }));

    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });
});
