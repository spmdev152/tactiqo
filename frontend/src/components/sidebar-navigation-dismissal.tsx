"use client";

import { useEffect, useRef } from "react";

import { usePathname } from "next/navigation";

import { useSidebar } from "@/components/ui/sidebar";

const INSTANT_DISMISSAL_ATTRIBUTE = "data-sidebar-dismissing";

/**
 * Dismisses the mobile drawer once a navigation started from it has landed.
 *
 * @remarks
 * Renders nothing. It exists so that no client-side animation is ever in flight
 * while a navigation is pending, which is the one rule that has reliably kept
 * this application free of the repaint artifacts that dogged the fixture
 * filters. Dismissing on click began the exit animation and the request in the
 * same tick, and React holds the previous tree on screen while a transition is
 * pending, so the drawer could be caught mid-exit and painted open again.
 *
 * Waiting for `usePathname` to change moves the dismissal after the commit, so
 * the two never overlap. The exit animation is then suppressed as well, through
 * an attribute the stylesheet keys off: a drawer that slid away over a page
 * already painted underneath it would only be a second thing to watch. Dismissed
 * by hand, through the overlay or the Escape key, it still animates, because
 * nothing is loading then.
 *
 * The attribute is written to the document rather than passed as a prop because
 * the primitive portals the drawer to `document.body`, out of this tree. It is
 * removed on the next frame, by which time the primitive has read the computed
 * style and unmounted.
 *
 * @returns Nothing; this component only reacts to navigation.
 */
export function SidebarNavigationDismissal() {
  const pathname = usePathname();

  const { openMobile, setOpenMobile } = useSidebar();

  const settledPathname = useRef(pathname);

  useEffect(() => {
    if (settledPathname.current === pathname) {
      return;
    }

    settledPathname.current = pathname;

    if (!openMobile) {
      return;
    }

    document.body.setAttribute(INSTANT_DISMISSAL_ATTRIBUTE, "");
    setOpenMobile(false);

    const frame = requestAnimationFrame(() => {
      document.body.removeAttribute(INSTANT_DISMISSAL_ATTRIBUTE);
    });

    return () => {
      cancelAnimationFrame(frame);
      document.body.removeAttribute(INSTANT_DISMISSAL_ATTRIBUTE);
    };
  }, [openMobile, pathname, setOpenMobile]);

  return null;
}
