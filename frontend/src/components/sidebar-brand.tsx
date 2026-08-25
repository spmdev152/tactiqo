import Link from "next/link";

import { TactiqoWordmark } from "@/components/tactiqo-wordmark";

/**
 * Renders the brand of the sidebar, linking to the landing route.
 *
 * @remarks
 * A Server Component: it navigates and nothing else. The mobile drawer is
 * dismissed by `SidebarNavigationDismissal` once the navigation has landed,
 * rather than by every link that starts one.
 *
 * The brand mark and the wordmark swap places rather than sitting side by side,
 * since a mark repeating the initial of the word next to it says nothing twice,
 * and the mark is set in the wordmark's own typeface so the swap reads as one
 * brand rather than two. The wordmark turns screen-reader-only while collapsed
 * rather than being removed, which would leave the link with no accessible name
 * at all.
 *
 * Only the desktop sidebar carries the `group` those variants key off, so the
 * mobile sheet keeps the wordmark at its full width, which is what it has room
 * for.
 *
 * @returns The brand link.
 */
export function SidebarBrand() {
  return (
    <Link
      className="flex items-center gap-2 rounded-md px-2 py-1.5 outline-none group-data-[collapsible=icon]:justify-center group-data-[collapsible=icon]:px-0 focus-visible:ring-3 focus-visible:ring-sidebar-ring/50"
      href="/"
    >
      <span
        aria-hidden
        className="hidden size-7 shrink-0 items-center justify-center rounded-md bg-primary font-sans text-sm leading-none font-semibold tracking-tight text-primary-foreground group-data-[collapsible=icon]:flex"
      >
        t
      </span>

      <TactiqoWordmark className="font-sans text-lg leading-none font-semibold tracking-tight group-data-[collapsible=icon]:sr-only" />
    </Link>
  );
}
