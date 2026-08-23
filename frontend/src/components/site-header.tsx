import Link from "next/link";

import { ModeToggle } from "@/components/mode-toggle";
import { TactiqoWordmark } from "@/components/tactiqo-wordmark";

/**
 * Renders the application header shared by every route.
 *
 * @remarks
 * A Server Component wrapping one client leaf. The header is mounted in the root
 * layout rather than per page so the theme control exists on every route,
 * including before anyone has signed in, and so no page can forget it.
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
          <TactiqoWordmark className="font-display text-3xl leading-none font-bold tracking-tight uppercase" />
        </Link>

        <ModeToggle />
      </div>
    </header>
  );
}
