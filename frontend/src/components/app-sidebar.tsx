import { SidebarAccountLink } from "@/components/sidebar-account-link";
import { SidebarBrand } from "@/components/sidebar-brand";
import { SidebarNavigation } from "@/components/sidebar-navigation";
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
 * A Server Component wrapping one client leaf. The brand and the sign-out form
 * are rendered on the server, so both keep working before hydration.
 *
 * The sidebar collapses to icons rather than off-canvas, so navigation survives
 * a collapse on a laptop instead of disappearing behind the trigger. Every
 * element that carries text therefore has an icon-mode counterpart, which each
 * leaf owns for itself.
 *
 * No link dismisses the mobile drawer itself. `SidebarNavigationDismissal`,
 * mounted beside this component in the shell layout, does it once the
 * navigation has landed, so one rule covers every link the sidebar will ever
 * grow and no animation runs while a request is in flight.
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
        <SidebarBrand />
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
