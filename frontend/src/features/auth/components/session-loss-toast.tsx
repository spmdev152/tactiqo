"use client";

import { useEffect } from "react";

import { useRouter } from "next/navigation";

import { toast } from "sonner";

import {
  SESSION_LOSS_PARAMETER,
  type SessionLossWarning,
} from "@/features/auth/domain/session-loss";

const TOAST_ID = "session-loss";

/**
 * Props of {@link SessionLossToast}.
 */
export interface SessionLossToastProps {
  /** Warning already resolved on the server from the parameter and the cookie. */
  readonly warning: SessionLossWarning;
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
 * The cleanup goes through the router, not `history.replaceState`. That is the
 * whole reliability argument of this component, and it was learned twice.
 * Keyed on the copy, a second involuntary arrival reconciled this component in
 * place and the effect never re-ran, because the copy is identical every time
 * and a search-param change does not remount a page subtree. Keying it on the
 * live parameter instead only moved the failure: `replaceState` writes the
 * address bar behind the router's back, so `useSearchParams` could keep
 * reporting the stale `lost` while the URL no longer carried it, and then the
 * next arrival changed no dependency at all — no toast, and a marker stuck in
 * the address bar until a full reload.
 *
 * A router navigation cannot desync, because the router performs it. The server
 * re-renders `/login` without the marker, the page stops rendering this
 * component, and the next arrival mounts a fresh one whose effect has never
 * run. That costs one extra render of a route that is dynamic anyway, and it
 * buys a component with no dependency on any state it does not own. Only the
 * marker is dropped, from a copy of the live URL, so an unrelated parameter
 * survives.
 *
 * Its reliability rests on this component mounting fresh per arrival, which
 * holds for the navigations the product actually offers: a `Link` click, a
 * redirect, a reload. It is known not to hold for every arrival typed into the
 * address bar, where the warning is sometimes missed and the marker is left in
 * the URL until the next navigation. That was chased through four progressively
 * more defensive designs — keying the effect on the live parameter, mounting
 * unconditionally, guarding on `window.location`, and finally polling it on a
 * timer — and each one traded a plain component for machinery that fought the
 * framework. The trade was judged not worth it: the copy is a courtesy, the
 * page is fully usable without it, and a stranded parameter only decides
 * whether a toast appears. Prefer leaving this simple over making it clever.
 *
 * It runs inside the frame, after the request, so the pair is atomic. Cleaning
 * first would lose the warning outright if the component unmounted before the
 * frame ran, rather than merely deferring it.
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
 * The fixed identifier is insurance against a real remount, not against React's
 * development double-invoke: the cleanup below cancels the first frame before it
 * can run, so only one request is ever made. Sonner updates a toast it already
 * shows rather than stacking a duplicate.
 *
 * The warning is deliberately not the only signal. The page it appears on is
 * the sign-in form, headed "Sign in to your account", so a visitor who never
 * sees the toast or dismisses it immediately loses an explanation, not the
 * ability to continue.
 */
export function SessionLossToast({ warning }: SessionLossToastProps) {
  const router = useRouter();
  const { title, description } = warning;

  useEffect(() => {
    const frame = requestAnimationFrame(() => {
      toast.warning(title, {
        description,
        id: TOAST_ID,
        richColors: true,
      });

      const url = new URL(window.location.href);

      url.searchParams.delete(SESSION_LOSS_PARAMETER);

      router.replace(`${url.pathname}${url.search}`, { scroll: false });
    });

    return () => cancelAnimationFrame(frame);
  }, [description, router, title]);

  return null;
}
