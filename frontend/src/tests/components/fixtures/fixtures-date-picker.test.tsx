import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import { FixturesDatePicker } from "@/features/fixtures/components/fixtures-date-picker";

const onChange = vi.fn();

/**
 * Teaches jsdom the layout and pointer APIs the popover measures itself with.
 * None of them exist there, and the popover throws on mount without them.
 */
function installPopupEnvironment(): void {
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
 * Reads the picker's trigger, whatever day it currently states.
 *
 * @returns The trigger button.
 */
function dayTrigger(): HTMLElement {
  return screen.getByRole("button", { name: /^Match day/ });
}

describe("FixturesDatePicker", () => {
  beforeAll(installPopupEnvironment);

  beforeEach(() => {
    onChange.mockReset();
  });

  /**
   * GIVEN a staged match day
   * WHEN the picker is rendered
   * THEN the calendar stays closed and the trigger states the day in UTC
   */
  it("states the staged day without opening a calendar", () => {
    render(<FixturesDatePicker onChange={onChange} value="2026-08-29" />);

    expect(dayTrigger()).toHaveTextContent("Sat, 29 Aug 2026");

    expect(screen.queryByRole("grid")).toBeNull();
  });

  /**
   * GIVEN a trigger whose visible content is the staged day
   * WHEN its accessible name is computed
   * THEN the name carries the label and the day, not the label alone
   */
  it("announces the staged day beside its own label", () => {
    render(<FixturesDatePicker onChange={onChange} value="2026-08-29" />);

    expect(dayTrigger()).toHaveAccessibleName(/^Match day/);
    expect(dayTrigger()).toHaveAccessibleName(/Sat, 29 Aug 2026$/);
  });

  /**
   * GIVEN the calendar opened from the trigger
   * WHEN another day is chosen
   * THEN that UTC day is staged and the calendar dismisses itself
   */
  it("stages the chosen day and closes", async () => {
    render(<FixturesDatePicker onChange={onChange} value="2026-08-29" />);

    fireEvent.click(dayTrigger());

    fireEvent.click(
      screen.getByRole("button", { name: "Monday, August 31st, 2026" }),
    );

    expect(onChange).toHaveBeenCalledExactlyOnceWith("2026-08-31");

    await waitFor(() => expect(screen.queryByRole("grid")).toBeNull());
  });
});
