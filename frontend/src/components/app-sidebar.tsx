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
 * A Server Component wrapping three client leaves. The sign-out form is
 * rendered on the server, so it keeps working before hydration.
 *
 * The sidebar collapses to icons rather than off-canvas, so navigation survives
 * a collapse on a laptop instead of disappearing behind the trigger. Every
 * element that carries text therefore has an icon-mode counterpart, which each
 * leaf owns for itself.
 *
 * Every link the sidebar offers dismisses the mobile drawer, which is why the
 * brand is a leaf of its own rather than markup here: it navigates, so it needs
 * the sidebar context that only a client component can read.
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
