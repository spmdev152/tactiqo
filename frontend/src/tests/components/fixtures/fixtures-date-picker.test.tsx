import { fireEvent, render, screen } from "@testing-library/react";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import { FixturesDatePicker } from "@/features/fixtures/components/fixtures-date-picker";

const { push, useSearchParams } = vi.hoisted(() => ({
  push: vi.fn(),
  useSearchParams: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
  useSearchParams,
}));

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

describe("FixturesDatePicker", () => {
  beforeAll(installPopupEnvironment);

  beforeEach(() => {
    push.mockReset();
    useSearchParams.mockReturnValue(new URLSearchParams());
  });

  /**
   * GIVEN a resolved match day
   * WHEN the picker is rendered
   * THEN the calendar stays closed and the trigger states the day in UTC
   */
  it("states the chosen day without opening a calendar", () => {
    render(<FixturesDatePicker selectedDay="2026-08-29" />);

    expect(screen.getByRole("button", { name: "Match day" })).toHaveTextContent(
      "Sat, 29 Aug 2026",
    );

    expect(screen.queryByRole("grid")).toBeNull();
  });

  /**
   * GIVEN a competition already chosen in the query
   * WHEN another day is picked from the opened calendar
   * THEN only the day is replaced and the competition survives
   */
  it("keeps the competition when the day changes", () => {
    useSearchParams.mockReturnValue(new URLSearchParams("league=2"));

    render(<FixturesDatePicker selectedDay="2026-08-29" />);

    fireEvent.click(screen.getByRole("button", { name: "Match day" }));

    fireEvent.click(
      screen.getByRole("button", { name: "Monday, August 31st, 2026" }),
    );

    expect(push).toHaveBeenCalledExactlyOnceWith("?league=2&date=2026-08-31", {
      scroll: false,
    });
  });
});
