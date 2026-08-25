"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { UserRound } from "lucide-react";

import { SidebarMenuButton, SidebarMenuItem } from "@/components/ui/sidebar";

const ACCOUNT_PATH = "/account";

const ACCOUNT_LABEL = "Account";

/**
 * Props of {@link SidebarAccountLink}.
 */
interface SidebarAccountLinkProps {
  /** Address of the account the visitor is signed in as. */
  readonly email: string;
}

/**
 * Renders the account entry pinned to the bottom of the sidebar.
 *
 * @remarks
 * Separate from {@link SidebarNavigation} because it is not one of the
 * platform's sections: it is where the visitor goes to manage the account they
 * are signed in as, which is why it sits in the footer beside the sign-out
 * control rather than in the menu above. The outline variant is what states
 * that difference — a bordered surface against the ghost entries above it,
 * pairing with the tinted sign-out button below.
 *
 * The address is the label, because the footer is where a visitor looks to see
 * which account they are signed in as. A sidebar this narrow truncates a long
 * address, so the untruncated value is on the element's `title`; the icon-mode
 * tooltip stays "Account", which is all there is room to say beside a
 * collapsed rail.
 *
 * That leaves the visible text naming a person rather than a destination, so
 * `aria-label` states the destination first and the address second. It is an
 * attribute rather than a visually hidden word because the accessible name is
 * concatenated from the children without a separator, and "Account" welded to
 * an address is not a name anybody would read out. The visible text is
 * contained in the label, so the name still matches what is on screen.
 *
 * It returns a menu item rather than its own menu, so the footer holds one list
 * and both footer entries share its spacing and its geometry.
 *
 * @returns The account entry.
 */
export function SidebarAccountLink({ email }: SidebarAccountLinkProps) {
  const pathname = usePathname();

  return (
    <SidebarMenuItem>
      <SidebarMenuButton
        asChild
        isActive={pathname.startsWith(ACCOUNT_PATH)}
        tooltip={ACCOUNT_LABEL}
        variant="outline"
      >
        <Link aria-label={`${ACCOUNT_LABEL} ${email}`} href={ACCOUNT_PATH}>
          <UserRound />

          <span title={email}>{email}</span>
        </Link>
      </SidebarMenuButton>
    </SidebarMenuItem>
  );
}
