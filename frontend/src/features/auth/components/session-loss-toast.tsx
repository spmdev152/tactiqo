"use client";

import { useEffect } from "react";

import { useRouter, useSearchParams } from "next/navigation";

import { toast } from "sonner";

import {
  SESSION_LOSS_PARAMETER,
  SESSION_LOSS_VALUE,
  sessionLossWarning,
} from "@/features/auth/domain/session-loss";

const TOAST_ID = "session-loss";

/**
 * Props of {@link SessionLossToast}.
 */
export interface SessionLossToastProps {
  /**
   * Whether the request that rendered the page carried a session token, which
   * is what decides which of the two warnings is true.
   */
  readonly sessionTokenPresent: boolean;
}

/**
 * Warns a visitor who lost their session that they have to sign in again.
 *
 * @remarks
 * Renders nothing. Sonner's own `Toaster`, mounted in the root layout, owns the
 * markup and the polite live region that announces it, so this only asks for
 * the toast and then removes the marker from the address bar. Without that
 * cleanup a refresh would re-fire the warning and a bookmark would carry it
 * forever.
 *
 * Three properties make it fire on every arrival, and each one replaced a
 * version that did not.
 *
 * It is mounted on every render of the login page, not only when a warning
 * applies. Mounting it conditionally made the toast depend on the server
 * re-rendering per arrival, and the client router is entitled to answer a
 * navigation from its cached segment: that cache key excludes search params, so
 * `/login` and `/login?session=lost` can share an entry. When it did, the page
 * function never ran, the component never mounted, and the arrival passed in
 * silence with the marker left in the address bar until a full reload.
 *
 * The address bar decides whether to fire; `useSearchParams` only says when to
 * look again. That split is the fix for the last and longest-lived failure.
 * Next lets the hook return an empty set on the first client render of a
 * boundary and fill it in on a later one, so an effect that *guarded* on the
 * hook could run once with no marker and, if that later render never came,
 * never look again — no toast, no cleanup, marker stranded, and a reload the
 * only cure. A screen recording pinned it: the same navigation, repeated,
 * warned at 13.5s and stayed silent at 8s and 16.5s. `window.location` cannot
 * be empty when the browser is showing the URL, so the guard reads that, while
 * the hook stays in the dependency list to re-arm the effect on the next
 * arrival.
 *
 * Keying it on the copy instead was an earlier version of the same mistake: the
 * copy is identical on every arrival for the same cause, and a search-param
 * change does not remount a page subtree, so the effect ran once and never
 * again.
 *
 * The write is the router's, which is what keeps it from disagreeing with the
 * hook. `history.replaceState` writes the address bar behind the router's back,
 * so the marker could stay `lost` in React's view after the URL had lost it,
 * and then the next arrival changed no dependency and fired nothing.
 *
 * The copy arrives as a boolean rather than as resolved text so that a cached
 * segment cannot withhold it. That boolean is server state and could in
 * principle be one navigation stale, which would swap two truthful messages;
 * unlike the parameter, nothing a visitor sends can influence it.
 *
 * `richColors` is set per toast rather than on the shared `Toaster`, because
 * `--warning` is the only semantic colour the theme defines: a future success
 * or error toast should fall back to the themed neutral surface instead of
 * Sonner's stock palette.
 *
 * The request waits for the next animation frame, which is what makes the toast
 * animate in. Sonner enters by transition rather than by keyframes: a toast is
 * inserted with `data-mounted="false"` and flipped to `true` from its own
 * effect. Asking for it directly from this effect puts both steps inside one
 * React commit cycle, so the browser first paints the toast already mounted,
 * the transition has no start value to interpolate from, and only the exit
 * animates. Leaving the effect flush first gives the pre-mount state a paint.
 *
 * The cleanup runs inside the frame, after the request, so the pair is atomic.
 * Cleaning first would lose the warning outright if the component unmounted
 * before the frame ran, rather than merely deferring it.
 *
 * The fixed identifier is insurance against a real remount, not against React's
 * development double-invoke: the cleanup cancels the first frame before it can
 * run, so only one request is ever made. Sonner updates a toast it already
 * shows rather than stacking a duplicate.
 *
 * The warning is deliberately not the only signal. The page it appears on is
 * the sign-in form, headed "Sign in to your account", so a visitor who never
 * sees the toast or dismisses it immediately loses an explanation, not the
 * ability to continue.
 */
export function SessionLossToast({
  sessionTokenPresent,
}: SessionLossToastProps) {
  const router = useRouter();
  const marker = useSearchParams().get(SESSION_LOSS_PARAMETER);

  useEffect(() => {
    const url = new URL(window.location.href);

    if (url.searchParams.get(SESSION_LOSS_PARAMETER) !== SESSION_LOSS_VALUE) {
      return;
    }

    const frame = requestAnimationFrame(() => {
      const { title, description } = sessionLossWarning(sessionTokenPresent);

      toast.warning(title, {
        description,
        id: TOAST_ID,
        richColors: true,
      });

      url.searchParams.delete(SESSION_LOSS_PARAMETER);

      router.replace(`${url.pathname}${url.search}`, { scroll: false });
    });

    return () => cancelAnimationFrame(frame);
  }, [marker, router, sessionTokenPresent]);

  return null;
}
