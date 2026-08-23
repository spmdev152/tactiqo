"use client";

import { ThemeProvider as NextThemesProvider } from "next-themes";

/**
 * Props of {@link ThemeProvider}.
 */
export interface ThemeProviderProps {
  /** Application tree that may read and change the active colour theme. */
  readonly children: React.ReactNode;
}

/**
 * Makes the active colour theme available to the whole application.
 *
 * @remarks
 * A client leaf on purpose: `next-themes` needs `localStorage` and the
 * `prefers-color-scheme` media query, neither of which exists on the server.
 * Mounting it here keeps every page and layout above it a Server Component.
 *
 * The configuration is fixed rather than exposed as props, because it is a
 * product decision rather than a per-caller one: `attribute="class"` matches
 * the `@custom-variant dark (&:is(.dark *))` rule in `globals.css`,
 * `enableSystem` with `defaultTheme="system"` respects the operating system
 * until the visitor overrides it, and `disableTransitionOnChange` suppresses
 * the colour transitions that would otherwise animate every element at once
 * while the theme swaps.
 */
export function ThemeProvider({ children }: ThemeProviderProps) {
  return (
    <NextThemesProvider
      attribute="class"
      defaultTheme="system"
      enableSystem
      disableTransitionOnChange
    >
      {children}
    </NextThemesProvider>
  );
}
