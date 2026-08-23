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
 * the `@custom-variant dark (&:is(.dark *))` rule in `globals.css`, and
 * `enableSystem` with `defaultTheme="system"` respects the operating system
 * until the visitor overrides it.
 *
 * `disableTransitionOnChange` is deliberately absent. It injects a document-wide
 * `transition: none !important` rule for the duration of the swap, and the swap
 * is exactly when the theme switch's thumb is sliding, so it made the shadcn
 * switch look like it had no animation at all: the thumb moved, but the track
 * colour and the whole page snapped around it. The flag exists for applications
 * that put a `transition` on every element; this one only transitions the few
 * components that ask for it, so letting those play is the better trade.
 */
export function ThemeProvider({ children }: ThemeProviderProps) {
  return (
    <NextThemesProvider attribute="class" defaultTheme="system" enableSystem>
      {children}
    </NextThemesProvider>
  );
}
