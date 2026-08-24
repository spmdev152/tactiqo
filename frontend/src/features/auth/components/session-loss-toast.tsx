"use client";

import { useEffect } from "react";

import { useSearchParams } from "next/navigation";

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
 * The effect keys off the live parameter rather than off the copy, because the
 * copy is identical on every arrival for the same cause and a search-param
 * change does not remount a page subtree. Keyed off the props, a second
 * involuntary arrival in the same client session reconciled this component in
 * place, the effect never re-ran, and the visitor got no toast and a parameter
 * that stayed in the address bar. Reading it through `useSearchParams` re-arms
 * the effect, since the cleanup below dispatches a router restore that clears
 * the value and the next arrival sets it again. The raw value is only ever a
 * dependency here; the server resolved the copy.
 *
 * The cleanup rewrites the address bar through `history.replaceState` rather
 * than through the router. It is not a navigation: nothing on the page has to
 * re-render, and `router.replace` would pay for a server round trip to
 * re-render the page it is already on. Only the marker is dropped, from a copy
 * of the live URL, so an unrelated parameter and any fragment survive.
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
  const { title, description } = warning;
  const marker = useSearchParams().get(SESSION_LOSS_PARAMETER);

  useEffect(() => {
    if (marker === null) {
      return;
    }

    const frame = requestAnimationFrame(() => {
      toast.warning(title, {
        description,
        id: TOAST_ID,
        richColors: true,
      });

      const url = new URL(window.location.href);

      url.searchParams.delete(SESSION_LOSS_PARAMETER);

      window.history.replaceState(null, "", url);
    });

    return () => cancelAnimationFrame(frame);
  }, [description, marker, title]);

  return null;
}
