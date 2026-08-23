import { defineConfig } from "vitest/config";

export default defineConfig({
  resolve: { tsconfigPaths: true },
  test: {
    environment: "jsdom",
    include: ["src/tests/**/*.test.{ts,tsx}"],
    setupFiles: ["./src/tests/setup.ts"],
    restoreMocks: true,
  },
});
