import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SidebarProvider } from "@/components/ui/sidebar";
import { TooltipProvider } from "@/components/ui/tooltip";
import { SignOutButton } from "@/features/auth/components/sign-out-button";

const { signOutAction } = vi.hoisted(() => ({ signOutAction: vi.fn() }));

vi.mock("@/features/auth/server/actions", () => ({ signOutAction }));

/**
 * Renders the sign-out form inside the sidebar context its submit needs.
 *
 * @returns The render result, for the container queries a test needs.
 */
function renderSignOut() {
  return render(
    <TooltipProvider>
      <SidebarProvider>
        <SignOutButton />
      </SidebarProvider>
    </TooltipProvider>,
  );
}

describe("SignOutButton", () => {
  beforeEach(() => {
    signOutAction.mockReset();
    signOutAction.mockResolvedValue(undefined);
  });

  /**
   * GIVEN a signed-in visitor
   * WHEN the control is rendered
   * THEN it submits a form and carries a single trailing icon
   */
  it("renders a submit control with one icon", () => {
    const { container } = renderSignOut();

    const submit = screen.getByRole("button", { name: "Sign out" });

    expect(submit).toHaveAttribute("type", "submit");
    expect(submit.closest("form")).not.toBeNull();
    expect(container.querySelectorAll("svg")).toHaveLength(1);
  });

  /**
   * GIVEN a sign-out request still in flight
   * WHEN the submit control is inspected
   * THEN it keeps its label, reports itself busy, and shows a spinner
   */
  it("swaps only the icon for a spinner while submitting", async () => {
    const { promise, resolve } = Promise.withResolvers<void>();

    signOutAction.mockReturnValue(promise);

    const { container } = renderSignOut();

    fireEvent.click(screen.getByRole("button", { name: "Sign out" }));

    const submit = await screen.findByRole("button", { name: "Sign out" });

    await waitFor(() => expect(submit).toBeDisabled());

    expect(submit).toHaveAttribute("aria-busy", "true");
    expect(container.querySelector("[data-slot=spinner]")).toBeVisible();

    resolve();

    await waitFor(() => expect(submit).not.toBeDisabled());

    expect(container.querySelector("[data-slot=spinner]")).toBeNull();
  });
});
