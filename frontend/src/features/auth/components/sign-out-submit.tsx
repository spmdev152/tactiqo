"use client";

import { Power } from "lucide-react";
import { useFormStatus } from "react-dom";

import { ButtonSpinner } from "@/components/button-spinner";
import { Button } from "@/components/ui/button";

/**
 * Renders the submit control of the sign-out form.
 *
 * @remarks
 * A client leaf so that `useFormStatus` can read the pending state of the form
 * above it. That hook only reports on an ancestor form, which is what keeps
 * {@link SignOutButton} a Server Component and the submit itself working before
 * hydration and with JavaScript disabled.
 *
 * The busy state matches the sign-in button deliberately: the label never
 * changes, only the icon becomes a spinner, and `aria-busy` reports what the
 * icon shows.
 *
 * The icon leads rather than trails, because this control now sits in the
 * sidebar footer under a column of navigation entries whose icons all lead. It
 * is 14 pixels, matching those entries, rather than the 16 the sign-in button
 * uses. The spinner has to state the same size because the registry hardcodes
 * its own.
 *
 * The variant is destructive because ending the session is the one irreversible
 * action in the shell: the token is revoked on the backend, so a mis-click
 * cannot be undone by navigating back. The variant is a tinted surface rather
 * than a solid red fill, which is what keeps a permanently visible footer
 * control from reading as the loudest thing in the sidebar.
 *
 * The collapsed-sidebar variant is expressed in classes rather than in state,
 * so the control needs no sidebar context and stays renderable on its own. The
 * label turns screen-reader-only rather than being removed, since removing it
 * would leave a button with no accessible name.
 */
export function SignOutSubmit() {
  const { pending } = useFormStatus();

  return (
    <Button
      aria-busy={pending}
      className="w-full justify-start group-data-[collapsible=icon]:justify-center group-data-[collapsible=icon]:px-0"
      disabled={pending}
      size="sm"
      type="submit"
      variant="destructive"
    >
      {pending ? (
        <ButtonSpinner className="size-3.5" />
      ) : (
        <Power className="size-3.5" />
      )}

      <span className="group-data-[collapsible=icon]:sr-only">Sign out</span>
    </Button>
  );
}
