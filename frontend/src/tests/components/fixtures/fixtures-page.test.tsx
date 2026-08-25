import { act, render, type RenderResult, screen } from "@testing-library/react";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import FixturesPage from "@/app/(app)/fixtures/page";

// The server-only marker throws outside the React Server condition, which Vitest does not set.
vi.mock("server-only", () => ({}));

const { getFixtures, getLeagues, push, requireUser, useSearchParams } =
  vi.hoisted(() => ({
    getFixtures: vi.fn(),
    getLeagues: vi.fn(),
    push: vi.fn(),
    requireUser: vi.fn(),
    useSearchParams: vi.fn(),
  }));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
  useSearchParams,
}));

vi.mock("@/features/auth/server/require-user", () => ({ requireUser }));

vi.mock("@/features/fixtures/server/get-fixtures", () => ({ getFixtures }));

vi.mock("@/features/fixtures/server/get-leagues", () => ({ getLeagues }));

// The section awaits its promise, which no client renderer can do; the route's placement of it is what matters here.
vi.mock("@/features/fixtures/components/fixture-list-section", () => ({
  FixtureListSection: () => <p>Fixture rows</p>,
}));

const PENDING_FOREVER = new Promise<never>(() => {});

type Query = Record<string, string | string[] | undefined>;

/**
 * Teaches jsdom the layout and pointer APIs the filter popups measure
 * themselves with. None of them exist there, and both throw on mount without
 * them.
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
 * Renders the page as an arrival on a given query receives it.
 *
 * @remarks
 * The render is awaited because the competition picker suspends on mount, and
 * both reads are left in flight, which is the state the shell has to be
 * renderable in.
 *
 * @param query - Search parameters the arrival carries.
 * @returns The render result.
 */
async function renderArrival(query: Query = {}): Promise<RenderResult> {
  const tree = await FixturesPage({ searchParams: Promise.resolve(query) });

  let rendered!: RenderResult;

  await act(async () => {
    rendered = render(tree);
  });

  return rendered;
}

describe("FixturesPage", () => {
  beforeAll(installPopupEnvironment);

  beforeEach(() => {
    requireUser.mockReset();
    requireUser.mockResolvedValue({ email: "ada@example.com" });
    getLeagues.mockReset();
    getLeagues.mockReturnValue(PENDING_FOREVER);
    getFixtures.mockReset();
    getFixtures.mockReturnValue(PENDING_FOREVER);
    useSearchParams.mockReturnValue(
      new URLSearchParams({ date: "2026-08-29" }),
    );
  });

  /**
   * GIVEN two API reads that never answer
   * WHEN the page renders for a query naming a day and two competitions
   * THEN it returns its tree with both reads started and neither awaited
   */
  it("starts both reads and returns without waiting for either", async () => {
    const tree = await FixturesPage({
      searchParams: Promise.resolve({
        date: "2026-08-29",
        league: ["2", "999"],
      }),
    });

    expect(tree).not.toBeNull();

    expect(getLeagues).toHaveBeenCalledOnce();

    expect(getFixtures).toHaveBeenCalledExactlyOnceWith({
      day: "2026-08-29",
      leagueIds: [2, 999],
    });
  });

  /**
   * GIVEN a request whose session the backend refuses
   * WHEN the page renders
   * THEN neither read is started, so the gate is not raced by the two requests
   */
  it("starts no read for a refused session", async () => {
    requireUser.mockRejectedValue(new Error("NEXT_REDIRECT"));

    await expect(
      FixturesPage({ searchParams: Promise.resolve({}) }),
    ).rejects.toThrow("NEXT_REDIRECT");

    expect(getLeagues).not.toHaveBeenCalled();
    expect(getFixtures).not.toHaveBeenCalled();
  });

  /**
   * GIVEN both reads still in flight
   * WHEN the page is rendered
   * THEN the heading, the day and the apply control are already on screen
   */
  it("paints the shell from the URL while the API is still answering", async () => {
    await renderArrival({ date: "2026-08-29" });

    expect(
      screen.getByRole("heading", { level: 1, name: "Fixtures" }),
    ).toBeVisible();

    expect(
      screen.getByRole("button", { name: /^Match day/ }),
    ).toHaveTextContent("Sat, 29 Aug 2026");

    expect(screen.getByRole("button", { name: "Filter" })).toBeInTheDocument();
  });

  /**
   * GIVEN a list whose whole subtree is replaced on every new scope
   * WHEN the page is rendered
   * THEN the polite region sits above that boundary rather than inside it
   */
  it("keeps the live region above the boundary it announces", async () => {
    const { container } = await renderArrival({ date: "2026-08-29" });

    const region = container.querySelector("[aria-live='polite']");

    expect(region).toContainElement(screen.getByText("Fixture rows"));

    expect(region).not.toContainElement(
      screen.getByRole("button", { name: "Filter" }),
    );
  });
});
