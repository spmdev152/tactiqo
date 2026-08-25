import Link from "next/link";

import { SidebarAccountLink } from "@/components/sidebar-account-link";
import { SidebarNavigation } from "@/components/sidebar-navigation";
import { TactiqoWordmark } from "@/components/tactiqo-wordmark";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuItem,
  SidebarRail,
  SidebarSeparator,
} from "@/components/ui/sidebar";
import { SignOutButton } from "@/features/auth/components/sign-out-button";

/**
 * Renders the navigation shell of the authenticated application.
 *
 * @remarks
 * A Server Component wrapping two client leaves. The sign-out form is rendered
 * on the server, so it keeps working before hydration.
 *
 * The sidebar collapses to icons rather than off-canvas, so navigation survives
 * a collapse on a laptop instead of disappearing behind the trigger. Every
 * element that carries text therefore has an icon-mode counterpart. The brand
 * mark and the wordmark swap places rather than sitting side by side, since a
 * mark repeating the initial of the word next to it says nothing twice; the
 * mark is set in the same typeface as the wordmark so the swap reads as one
 * brand rather than two. The wordmark turns screen-reader-only rather than
 * being removed, which would leave the link with no accessible name at all.
 *
 * Only the desktop sidebar carries the `group` those variants key off, so the
 * mobile sheet keeps the wordmark at its full width, which is what it has room
 * for.
 *
 * The footer holds what belongs to the session rather than to the platform: the
 * account the visitor is signed in as, and the control that ends it. The
 * signed-in address itself lives on the account page, because a sidebar this
 * narrow truncates an e-mail address to the point of uselessness and a
 * collapsed sidebar cannot show it at all.
 *
 * @returns The sidebar tree.
 */
export function AppSidebar() {
  return (
    <Sidebar collapsible="icon">
      <SidebarHeader>
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
      </SidebarHeader>

      <SidebarContent>
        <SidebarNavigation />
      </SidebarContent>

      <SidebarSeparator />

      <SidebarFooter>
        <SidebarMenu className="gap-1.5">
          <SidebarAccountLink />

          <SidebarMenuItem>
            <SignOutButton />
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>

      <SidebarRail />
    </Sidebar>
  );
}
