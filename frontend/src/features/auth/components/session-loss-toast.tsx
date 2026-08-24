"use client";

import { useEffect } from "react";

import { toast } from "sonner";

import {
  SESSION_LOSS_PARAMETER,
  type SessionLossWarning,
} from "@/features/auth/session-loss";

const TOAST_ID = "session-loss";

/**
 * Props of {@link SessionLossToast}.
 */
export interface SessionLossToastProps {
  /** Warning already resolved from the closed set of known reasons. */
  readonly warning: SessionLossWarning;
}

/**
 * Warns a visitor who lost their session that they have to sign in again.
 *
 * @remarks
 * Renders nothing. Sonner's own `Toaster`, mounted in the root layout, owns the
 * markup and the polite live region that announces it, so this only asks for
 * the toast and then removes the reason from the address bar. Without that
 * cleanup a refresh would re-fire the warning and a bookmark would carry it
 * forever.
 *
 * The cleanup rewrites the address bar through `history.replaceState` rather
 * than through the router. It is not a navigation: nothing needs re-rendering
 * once the toast exists, and `router.replace` would pay for a server round trip
 * to re-render the page it is already on. Only the reason is dropped, from a
 * copy of the live query, so an unrelated parameter survives.
 *
 * `richColors` is set per toast rather than on the shared `Toaster`, because
 * `--warning` is the only semantic colour the theme defines: a future success
 * or error toast should fall back to the themed neutral surface instead of
 * Sonner's stock palette.
 *
 * The fixed identifier makes the request idempotent. React invokes an effect
 * twice in development, and Sonner updates a toast it already shows rather than
 * stacking a duplicate.
 *
 * The warning is deliberately not the only signal. The page it appears on is
 * the sign-in form, headed "Sign in to your account", so a visitor who never
 * sees the toast or dismisses it immediately loses an explanation, not the
 * ability to continue.
 */
export function SessionLossToast({ warning }: SessionLossToastProps) {
  const { title, description } = warning;

  useEffect(() => {
    toast.warning(title, {
      description,
      id: TOAST_ID,
      richColors: true,
    });

    const url = new URL(window.location.href);

    url.searchParams.delete(SESSION_LOSS_PARAMETER);

    window.history.replaceState(null, "", `${url.pathname}${url.search}`);
  }, [description, title]);

  return null;
}
