"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { LayoutDashboard, type LucideIcon } from "lucide-react";

import {
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
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
];

/**
 * Renders the primary navigation of the application sidebar.
 *
 * @remarks
 * The one client leaf of the shell, because marking the current entry needs
 * `usePathname` and nothing else in the sidebar needs the browser. Keeping the
 * boundary here leaves the header, the footer and the sign-out form on the
 * server.
 *
 * A nested route marks its section current, which is why the match is a prefix
 * rather than an equality. The root is the exception: every path starts with
 * `/`, so a prefix match there would light up the whole menu at once.
 *
 * @returns The navigation group.
 */
export function SidebarNavigation() {
  const pathname = usePathname();

  return (
    <SidebarGroup>
      <SidebarGroupLabel>Platform</SidebarGroupLabel>

      <SidebarGroupContent>
        <SidebarMenu>
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
                <Link href={entry.href}>
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
