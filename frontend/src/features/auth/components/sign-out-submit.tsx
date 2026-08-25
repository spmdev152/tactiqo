"use client";

import { Power } from "lucide-react";
import { useFormStatus } from "react-dom";

import { ButtonSpinner } from "@/components/button-spinner";
import { SidebarMenuButton } from "@/components/ui/sidebar";

const SIGN_OUT_LABEL = "Sign out";

/**
 * Renders the submit control of the sign-out form.
 *
 * @remarks
 * A client leaf so that `useFormStatus` can read the pending state of the form
 * above it. That hook only reports on an ancestor form, which is what keeps
 * {@link SignOutButton} a Server Component and the submit itself working before
 * hydration and with JavaScript disabled.
 *
 * It is built from `SidebarMenuButton` rather than from a plain button, because
 * it is a sidebar menu entry and has to share the height, padding, radius, icon
 * size and collapsed behaviour of every other one. Restating those measurements
 * on a generic button is how they drift apart, and the collapsed variant then
 * comes for free instead of being re-derived in classes here. The primitive
 * needs the sidebar context, so this component is no longer renderable on its
 * own; there is exactly one sign-out control and it lives in the sidebar.
 *
 * Only the colour is overridden, from the destructive variant of the button
 * primitive. Ending the session is the one irreversible action in the shell —
 * the token is revoked on the backend, so a mis-click cannot be undone by
 * navigating back — and a tinted surface says so without a solid red fill
 * becoming the loudest thing in a permanently visible footer.
 *
 * The busy state matches the sign-in button deliberately: the label never
 * changes, only the icon becomes a spinner, and `aria-busy` reports what the
 * icon shows.
 */
export function SignOutSubmit() {
  const { pending } = useFormStatus();

  return (
    <SidebarMenuButton
      aria-busy={pending}
      className="bg-destructive/10 text-destructive hover:bg-destructive/20 hover:text-destructive active:bg-destructive/20 active:text-destructive dark:bg-destructive/20 dark:hover:bg-destructive/30"
      disabled={pending}
      tooltip={SIGN_OUT_LABEL}
      type="submit"
    >
      {pending ? <ButtonSpinner className="size-4" /> : <Power />}

      <span>{SIGN_OUT_LABEL}</span>
    </SidebarMenuButton>
  );
}
