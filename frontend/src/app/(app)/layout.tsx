import { cookies } from "next/headers";

import { AppHeader } from "@/components/app-header";
import { AppSidebar } from "@/components/app-sidebar";
import { SidebarNavigationDismissal } from "@/components/sidebar-navigation-dismissal";
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar";
import { TooltipProvider } from "@/components/ui/tooltip";
import { requireUser } from "@/features/auth/server/require-user";
import {
  SIDEBAR_COLLAPSED_STATE,
  SIDEBAR_STATE_COOKIE_NAME,
} from "@/lib/sidebar-state";

/**
 * Props of {@link AuthenticatedLayout}.
 */
interface AuthenticatedLayoutProps {
  /** Authenticated route subtree rendered inside the shell. */
  readonly children: React.ReactNode;
}

/**
 * Wraps every authenticated route in the sidebar shell.
 *
 * @remarks
 * The route group exists so the shell has a boundary. A sidebar on the sign-in
 * page would offer navigation to a visitor with no session, so `/login` and
 * `/signup` stay in the public group and keep the plain header.
 *
 * The session is resolved here as the shell's own gate, not for the sidebar,
 * which no longer states the address. A layout is not re-rendered when
 * navigation stays inside it, so a page that reached this shell once would keep
 * rendering after its session was revoked. Every page therefore gates on its
 * own, and `getCurrentUser` is memoized per request, so doing both costs one
 * backend round trip rather than two.
 *
 * The collapsed state is read from the cookie the primitive writes, because the
 * server otherwise renders the sidebar expanded and hydration snaps it shut in
 * front of the visitor.
 *
 * `TooltipProvider` is mounted here rather than in the root layout: the
 * collapsed sidebar labels its icons through tooltips, and no public route has
 * a tooltip to show.
 *
 * `SidebarInset` is given `min-w-0` because it is a flex item beside a
 * fixed-width sidebar, and a flex item defaults to a minimum size of its
 * content. Without it the widest fixture row set the floor for the whole pane,
 * which overflowed the viewport horizontally from around 853px: the row could
 * not shrink, so it pushed the pane past the space the sidebar left it.
 *
 * @returns The authenticated shell tree.
 */
export default async function AuthenticatedLayout({
  children,
}: AuthenticatedLayoutProps) {
  const [, cookieStore] = await Promise.all([requireUser(), cookies()]);

  const storedState = cookieStore.get(SIDEBAR_STATE_COOKIE_NAME)?.value;

  return (
    <TooltipProvider>
      <SidebarProvider defaultOpen={storedState !== SIDEBAR_COLLAPSED_STATE}>
        <SidebarNavigationDismissal />

        <AppSidebar />

        <SidebarInset className="min-w-0">
          <AppHeader />

          {children}
        </SidebarInset>
      </SidebarProvider>
    </TooltipProvider>
  );
}
