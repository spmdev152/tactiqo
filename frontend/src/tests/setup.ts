import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// jsdom implements no media-query API, and the sidebar primitive subscribes to one on mount.
Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  }),
});

/**
 * Stands in for the observer the tooltip arrow measures itself with.
 *
 * @remarks
 * Reporting no size at all is exactly right here: the arrow reads its own
 * measurements to place itself, and jsdom lays nothing out, so a stub that
 * called its subscriber back would be inventing a geometry no assertion can
 * depend on.
 */
class ResizeObserverStub {
  observe(): void {}

  unobserve(): void {}

  disconnect(): void {}
}

// jsdom implements no resize-observation API, and the tooltip arrow constructs one on mount.
Object.defineProperty(window, "ResizeObserver", {
  writable: true,
  value: ResizeObserverStub,
});

afterEach(cleanup);
