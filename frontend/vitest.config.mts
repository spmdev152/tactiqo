import { defineConfig } from "vitest/config";

export default defineConfig({
  resolve: { tsconfigPaths: true },
  test: {
    environment: "jsdom",
    // A UTC runner cannot fail a timezone test: the two that prove a kick-off
    // and a fallback day are not read in the renderer's zone assert exactly
    // what a local-components implementation would produce there. Both use a
    // late-evening UTC instant, so the zone has to be east of Greenwich for
    // the local day to differ from the UTC one, and the half hour catches a
    // minute-level slip an hour-aligned zone would hide.
    env: { TZ: "Asia/Kolkata" },
    include: ["src/tests/**/*.test.{ts,tsx}"],
    setupFiles: ["./src/tests/setup.ts"],
    restoreMocks: true,
  },
});
