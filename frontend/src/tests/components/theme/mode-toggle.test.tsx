import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ModeToggle } from "@/components/mode-toggle";

const { setTheme, useTheme } = vi.hoisted(() => ({
  setTheme: vi.fn(),
  useTheme: vi.fn(),
}));

vi.mock("next-themes", () => ({ useTheme }));

describe("ModeToggle", () => {
  beforeEach(() => {
    setTheme.mockReset();
    useTheme.mockReturnValue({ resolvedTheme: "light", setTheme });
  });

  /**
   * GIVEN a mounted toggle rendered against the light theme
   * WHEN the switch is queried by its accessible name
   * THEN the switch is found and is not checked
   */
  it("exposes an accessible name instead of a bare icon", () => {
    render(<ModeToggle />);

    expect(screen.getByRole("switch", { name: "Dark mode" })).not.toBeChecked();
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
});
