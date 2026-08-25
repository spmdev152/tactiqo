"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { UserRound } from "lucide-react";

import { SidebarMenuButton, SidebarMenuItem } from "@/components/ui/sidebar";

const ACCOUNT_PATH = "/account";

const ACCOUNT_LABEL = "Account";

/**
 * Renders the account entry pinned to the bottom of the sidebar.
 *
 * @remarks
 * Separate from {@link SidebarNavigation} because it is not one of the
 * platform's sections: it is where the visitor goes to see who they are signed
 * in as, which is why it sits in the footer beside the sign-out control rather
 * than in the menu above. The outline variant is what states that difference —
 * a bordered surface against the ghost entries above it, pairing with the
 * tinted sign-out button below.
 *
 * It returns a menu item rather than its own menu, so the footer holds one list
 * and both footer entries share its spacing and its geometry.
 *
 * A client leaf for the same single reason the navigation is: marking the
 * current entry needs `usePathname`.
 *
 * @returns The account entry.
 */
export function SidebarAccountLink() {
  const pathname = usePathname();

  return (
    <SidebarMenuItem>
      <SidebarMenuButton
        asChild
        isActive={pathname.startsWith(ACCOUNT_PATH)}
        tooltip={ACCOUNT_LABEL}
        variant="outline"
      >
        <Link href={ACCOUNT_PATH}>
          <UserRound />
          <span>{ACCOUNT_LABEL}</span>
        </Link>
      </SidebarMenuButton>
    </SidebarMenuItem>
  );
}
