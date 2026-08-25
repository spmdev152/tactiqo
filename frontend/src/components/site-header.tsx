import Link from "next/link";

import { ModeToggle } from "@/components/mode-toggle";
import { TactiqoWordmark } from "@/components/tactiqo-wordmark";

/**
 * Renders the application header shared by every public route.
 *
 * @remarks
 * A Server Component wrapping one client leaf. It is mounted in the public
 * group's layout rather than per page, so the theme control exists on every
 * route a visitor can reach without a session and no page can forget it. The
 * authenticated group mounts `AppHeader` instead, which carries the
 * sidebar trigger in place of the wordmark, because the wordmark moved into the
 * sidebar.
 *
 * @returns The header tree.
 */
export function SiteHeader() {
  return (
    <header className="sticky top-0 z-20 border-b border-border/60 bg-background/80 backdrop-blur-md">
      <div className="mx-auto flex w-full max-w-7xl items-center justify-between gap-4 px-6 py-3.5">
        <Link
          className="rounded-md outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
          href="/"
        >
          <TactiqoWordmark className="font-sans text-2xl leading-none font-semibold tracking-tight" />
        </Link>

        <ModeToggle />
      </div>
    </header>
  );
}
