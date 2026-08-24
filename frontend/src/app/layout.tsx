import type { Metadata } from "next";
import { Antonio, Fira_Code, Geist } from "next/font/google";

import { SiteHeader } from "@/components/site-header";
import { ThemeProvider } from "@/components/theme-provider";
import { Toaster } from "@/components/ui/sonner";

import "./globals.css";

const geistSans = Geist({
  variable: "--font-sans",
  subsets: ["latin"],
});

const antonio = Antonio({
  variable: "--font-display",
  subsets: ["latin"],
  weight: ["600", "700"],
});

const firaCode = Fira_Code({
  variable: "--font-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Tactiqo",
  description:
    "Football intelligence for fixtures, statistics, odds, and predictions.",
};

/**
 * Props of {@link RootLayout}.
 */
interface RootLayoutProps {
  /** Route subtree Next.js renders inside the document body. */
  readonly children: React.ReactNode;
}

/**
 * Root document shell shared by every route.
 *
 * @remarks
 * `suppressHydrationWarning` is deliberate on both elements, for two unrelated
 * reasons, and must not be widened any further or added to child components.
 * The flag only covers an element's own attributes and text, so a real mismatch
 * anywhere inside the tree is still reported.
 *
 * On `<html>` it covers `next-themes`, which runs a blocking script before
 * hydration to stamp the stored theme onto `class` and `style`. That is what
 * prevents a flash of the wrong theme, and it necessarily means the markup
 * React hydrates differs from the markup the server sent.
 *
 * On `<body>` it covers browser extensions such as ColorZilla, which stamp
 * attributes like `cz-shortcut-listen` onto the element before React hydrates.
 * React reports that as an unfixable attribute mismatch even though the
 * application renders identically on both sides.
 *
 * `Toaster` is mounted once, here and inside `ThemeProvider`, because Sonner
 * reads `useTheme` to pick its own light or dark surface and a second host
 * would render every toast twice.
 */
export default function RootLayout({ children }: RootLayoutProps) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${antonio.variable} ${firaCode.variable} h-full antialiased`}
      suppressHydrationWarning
    >
      <body className="flex min-h-full flex-col" suppressHydrationWarning>
        <ThemeProvider>
          <SiteHeader />

          {children}

          <Toaster />
        </ThemeProvider>
      </body>
    </html>
  );
}
