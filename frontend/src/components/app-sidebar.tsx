import Link from "next/link";

import { UserRound } from "lucide-react";

import { SidebarNavigation } from "@/components/sidebar-navigation";
import { TactiqoWordmark } from "@/components/tactiqo-wordmark";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarRail,
  SidebarSeparator,
} from "@/components/ui/sidebar";
import { SignOutButton } from "@/features/auth/components/sign-out-button";

/**
 * Props of {@link AppSidebar}.
 */
export interface AppSidebarProps {
  /** E-mail address the current session is signed in as. */
  readonly email: string;
}

/**
 * Renders the navigation shell of the authenticated application.
 *
 * @remarks
 * A Server Component wrapping one client leaf. The identity and the sign-out
 * form are rendered on the server, so the session's e-mail address never
 * travels as client state and the form keeps working before hydration.
 *
 * The sidebar collapses to icons rather than off-canvas, so navigation survives
 * a collapse on a laptop instead of disappearing behind the trigger. Every
 * element that carries text therefore has an icon-mode counterpart: the brand
 * mark stands in for the wordmark, and the wordmark and the e-mail address turn
 * screen-reader-only rather than being removed, which would leave the link and
 * the button with no accessible name at all.
 *
 * The e-mail address is deliberately not a control. It states which account is
 * signed in, and there is no account page for it to lead to.
 *
 * @returns The sidebar tree.
 */
export function AppSidebar({ email }: AppSidebarProps) {
  return (
    <Sidebar collapsible="icon">
      <SidebarHeader>
        <Link
          className="flex items-center gap-2 rounded-md px-2 py-1.5 outline-none group-data-[collapsible=icon]:justify-center group-data-[collapsible=icon]:px-0 focus-visible:ring-3 focus-visible:ring-sidebar-ring/50"
          href="/"
        >
          <span
            aria-hidden
            className="flex size-7 shrink-0 items-center justify-center rounded-md bg-primary font-display text-sm font-bold text-primary-foreground"
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
        <p className="flex items-center gap-2 px-2 py-1 text-xs text-sidebar-foreground/70 group-data-[collapsible=icon]:justify-center group-data-[collapsible=icon]:px-0">
          <UserRound aria-hidden className="size-3.5 shrink-0" />

          <span className="truncate group-data-[collapsible=icon]:sr-only">
            {email}
          </span>
        </p>

        <SignOutButton />
      </SidebarFooter>

      <SidebarRail />
    </Sidebar>
  );
}
