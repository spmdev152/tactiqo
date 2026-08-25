"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { CalendarDays, LayoutDashboard, type LucideIcon } from "lucide-react";

import {
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar";

/**
 * One destination offered by the application sidebar.
 */
interface NavigationEntry {
  /** Route the entry navigates to. */
  readonly href: string;
  /** Label shown beside the icon, and the tooltip while collapsed. */
  readonly label: string;
  /** Icon standing in for the entry once the sidebar is collapsed to icons. */
  readonly icon: LucideIcon;
}

const NAVIGATION_ENTRIES: readonly NavigationEntry[] = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/fixtures", label: "Fixtures", icon: CalendarDays },
];

/**
 * Renders the primary navigation of the application sidebar.
 *
 * @remarks
 * A client leaf, because marking the current entry needs `usePathname` and
 * dismissing the drawer needs the sidebar context. Keeping the boundary here
 * leaves the header and the footer's own form on the server.
 *
 * A nested route marks its section current, which is why the match is a prefix
 * rather than an equality. The root is the exception: every path starts with
 * `/`, so a prefix match there would light up the whole menu at once.
 *
 * Choosing an entry dismisses the mobile drawer. On a phone the sidebar covers
 * the page it navigates to, so leaving it open would hide the answer to the
 * click that opened it. It is dismissed rather than unmounted, which is what
 * lets the sheet play its exit animation.
 *
 * @returns The navigation group.
 */
export function SidebarNavigation() {
  const pathname = usePathname();

  const { setOpenMobile } = useSidebar();

  return (
    <SidebarGroup>
      <SidebarGroupLabel>Platform</SidebarGroupLabel>

      <SidebarGroupContent>
        <SidebarMenu className="gap-1.5">
          {NAVIGATION_ENTRIES.map((entry) => (
            <SidebarMenuItem key={entry.href}>
              <SidebarMenuButton
                asChild
                isActive={
                  entry.href === "/"
                    ? pathname === "/"
                    : pathname.startsWith(entry.href)
                }
                tooltip={entry.label}
              >
                <Link href={entry.href} onClick={() => setOpenMobile(false)}>
                  <entry.icon />
                  <span>{entry.label}</span>
                </Link>
              </SidebarMenuButton>
            </SidebarMenuItem>
          ))}
        </SidebarMenu>
      </SidebarGroupContent>
    </SidebarGroup>
  );
}
