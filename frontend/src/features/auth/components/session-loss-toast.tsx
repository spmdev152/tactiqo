"use client";

import { useEffect } from "react";

import { useRouter } from "next/navigation";

import { toast } from "sonner";

import {
  SESSION_LOSS_PARAMETER,
  SESSION_LOSS_VALUE,
  sessionLossWarning,
} from "@/features/auth/domain/session-loss";

const TOAST_ID = "session-loss";

const POLL_INTERVAL_MS = 150;

const REARM_DELAY_MS = 750;

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
 * It watches the address bar on a timer, which is the boring answer after four
 * clever ones failed. Every signal React and the router can offer proved able
 * to go stale, and each failure looked identical from the outside: the marker
 * stranded in the url, no toast, and a full reload the only cure.
 *
 * - Keyed on the resolved copy, the effect ran once. The copy is identical on
 *   every arrival for the same cause, and a search-param change does not remount
 *   a page subtree.
 * - Mounted only when a warning applied, the component depended on the page
 *   function running per arrival, which the router does not promise.
 * - Guarded on `useSearchParams`, it could run once against an empty set, since
 *   Next may report that on a boundary's first client render and fill it in
 *   later.
 * - Triggered by `useSearchParams` or by a prop from the server, it went quiet
 *   for good after a handful of client-side navigations. Both channels can
 *   freeze: the router stops publishing a fresh context, and the segment cache
 *   key excludes search params, so `/login` and `/login?session=lost` share an
 *   entry and the props stop changing with them.
 *
 * `window.location` is the one source none of that can stale, because it is
 * whatever the browser is showing. Reading it on an interval also covers
 * arrivals that fire no React update at all, including a back-forward cache
 * restore. The cost is a string comparison a few times a second, on one route,
 * and it replaces every assumption about framework internals with an
 * observation.
 *
 * One arrival gives one toast because the watch ignores the marker for a short
 * window after acting, which is what stops it re-firing while the cleanup
 * navigation is still in flight. A window rather than a flag cleared on seeing a
 * clean url, because that flag made re-arming depend on a tick landing between
 * two arrivals: an arrival closer than one interval would have been swallowed
 * for good. With a window the worst case is a marker that lingers for the rest
 * of it and is then picked up by the next tick, so the page always heals.
 *
 * The write is still the router's. `history.replaceState` writes the address bar
 * behind the router's back, which desynchronised it from the router's own view
 * of the url.
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
 * effect. Asking for it directly from the watch puts both steps inside one
 * React commit cycle, so the browser first paints the toast already mounted,
 * the transition has no start value to interpolate from, and only the exit
 * animates.
 *
 * The cleanup runs inside the frame, after the request, so the pair is atomic.
 * Cleaning first would lose the warning outright if the component unmounted
 * before the frame ran, rather than merely deferring it.
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

  useEffect(() => {
    let frame = 0;
    let firedAt = 0;

    const watch = () => {
      const url = new URL(window.location.href);

      if (url.searchParams.get(SESSION_LOSS_PARAMETER) !== SESSION_LOSS_VALUE) {
        return;
      }

      if (Date.now() - firedAt < REARM_DELAY_MS) {
        return;
      }

      firedAt = Date.now();

      frame = requestAnimationFrame(() => {
        const { title, description } = sessionLossWarning(sessionTokenPresent);

        toast.warning(title, {
          description,
          id: TOAST_ID,
          richColors: true,
        });

        url.searchParams.delete(SESSION_LOSS_PARAMETER);

        router.replace(`${url.pathname}${url.search}`, { scroll: false });
      });
    };

    watch();

    const timer = setInterval(watch, POLL_INTERVAL_MS);

    return () => {
      clearInterval(timer);
      cancelAnimationFrame(frame);
    };
  }, [router, sessionTokenPresent]);

  return null;
}
