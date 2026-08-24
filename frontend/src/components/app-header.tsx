import { ModeToggle } from "@/components/mode-toggle";
import { SidebarTrigger } from "@/components/ui/sidebar";

/**
 * Renders the header bar of the authenticated application.
 *
 * @remarks
 * The authenticated counterpart of `SiteHeader`, which stays on the public
 * routes. The wordmark moved into the sidebar, so this bar carries only
 * the two controls that have nowhere else to live: the sidebar trigger, which
 * is the sole way to reopen the sidebar on a phone, and the theme switch, which
 * has to exist on every route.
 *
 * @returns The header tree.
 */
export function AppHeader() {
  return (
    <header className="sticky top-0 z-20 flex items-center justify-between gap-4 border-b border-border/60 bg-background/80 px-4 py-3 backdrop-blur-md sm:px-6">
      <SidebarTrigger />

      <ModeToggle />
    </header>
  );
}
