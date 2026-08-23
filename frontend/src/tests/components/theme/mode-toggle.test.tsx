import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ModeToggle } from "@/components/mode-toggle";

const { setTheme, useTheme } = vi.hoisted(() => ({
  setTheme: vi.fn(),
  useTheme: vi.fn(),
}));

vi.mock("next-themes", () => ({ useTheme }));

/**
 * Returns the label that owns the whole toggle, icons included.
 *
 * @returns The label element bound to the mode switch.
 */
function modeToggleLabel(): HTMLLabelElement {
  const label = screen
    .getByRole("switch", { name: "Dark mode" })
    .closest("label");

  if (label === null) {
    throw new Error("The mode switch is not wrapped in a label.");
  }

  return label as HTMLLabelElement;
}

describe("ModeToggle", () => {
  beforeEach(() => {
    setTheme.mockReset();
    useTheme.mockReturnValue({ resolvedTheme: "light", setTheme });
  });

  /**
   * GIVEN a mounted toggle rendered against the light theme
   * WHEN the switch is queried by its accessible name
   * THEN the switch is found, is enabled, and is not checked
   */
  it("exposes an enabled switch with an accessible name", () => {
    render(<ModeToggle />);

    const control = screen.getByRole("switch", { name: "Dark mode" });

    expect(control).not.toBeChecked();
    expect(control).toBeEnabled();
  });

  /**
   * GIVEN a resolved theme of dark
   * WHEN the toggle is rendered
   * THEN the switch is checked, because checked means dark
   */
  it("reflects the resolved theme", () => {
    useTheme.mockReturnValue({ resolvedTheme: "dark", setTheme });

    render(<ModeToggle />);

    expect(screen.getByRole("switch", { name: "Dark mode" })).toBeChecked();
  });

  /**
   * GIVEN a resolved theme of dark
   * WHEN the switch is toggled
   * THEN the light theme is requested
   */
  it("requests the opposite theme when toggled", () => {
    useTheme.mockReturnValue({ resolvedTheme: "dark", setTheme });

    render(<ModeToggle />);
    fireEvent.click(screen.getByRole("switch", { name: "Dark mode" }));

    expect(setTheme).toHaveBeenCalledWith("light");
  });

  /**
   * GIVEN a toggle whose icons used to sit outside the hit area of the switch
   * WHEN the label wrapping the whole control is clicked
   * THEN the theme still changes, so no part of the control is a dead zone
   */
  it("toggles from anywhere in the label", () => {
    render(<ModeToggle />);
    fireEvent.click(modeToggleLabel());

    expect(setTheme).toHaveBeenCalledWith("dark");
  });

  /**
   * GIVEN a rendered toggle
   * WHEN the icons are located
   * THEN both sit inside the track, where the thumb can occlude one of them
   */
  it("keeps both icons inside the switch track", () => {
    const { container } = render(<ModeToggle />);

    const icons = container.querySelectorAll("svg");
    const track = screen.getByRole("switch", { name: "Dark mode" });

    expect(icons).toHaveLength(2);
    icons.forEach((icon) => expect(track).toContainElement(icon));
  });

  /**
   * GIVEN a rendered toggle
   * WHEN the icons are inspected for pointer handling
   * THEN neither can swallow a click meant for the switch beneath them
   */
  it("never lets an icon intercept a click", () => {
    const { container } = render(<ModeToggle />);

    container.querySelectorAll("svg").forEach((icon) => {
      expect(icon).toHaveClass("pointer-events-none");
    });
  });
});
