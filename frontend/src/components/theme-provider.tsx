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
 * `disableTransitionOnChange` makes the swap abrupt. It injects a document-wide
 * `transition: none !important` rule for the duration of the change, so text,
 * borders, inputs and surfaces jump straight to their new colours instead of
 * fading between two themes.
 *
 * That blanket rule would also freeze the theme switch mid-slide, which is the
 * one animation that has to survive because it belongs to the control somebody
 * just operated rather than to the swap. Two rules in `globals.css` re-assert it
 * by selector, which outranks the `*` the injected style uses.
 */
export function ThemeProvider({ children }: ThemeProviderProps) {
  return (
    <NextThemesProvider
      attribute="class"
      defaultTheme="system"
      disableTransitionOnChange
      enableSystem
    >
      {children}
    </NextThemesProvider>
  );
}
