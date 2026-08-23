import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";

import "./globals.css";

const geistSans = Geist({
  variable: "--font-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
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
 * `suppressHydrationWarning` on `<body>` is deliberate and must stay scoped to
 * that element. Browser extensions such as ColorZilla stamp attributes like
 * `cz-shortcut-listen` onto `<body>` before React hydrates, which React reports
 * as an unfixable attribute mismatch even though the application renders
 * identically on both sides. The flag only covers this element's own
 * attributes and text, so a real mismatch anywhere inside the tree is still
 * reported. Do not widen it to `<html>` and do not add it to child components.
 */
export default function RootLayout({ children }: RootLayoutProps) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="flex min-h-full flex-col" suppressHydrationWarning>
        {children}
      </body>
    </html>
  );
}
