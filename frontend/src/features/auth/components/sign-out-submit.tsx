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
 * changes, only the trailing icon becomes a spinner, and `aria-busy` reports
 * what the icon shows.
 *
 * Both icons are 12 pixels rather than the 16 the sign-in button uses, and
 * rather than the 14 an `sm` button gives its own unsized icons. A power symbol
 * is a full-height circle, so anything above the roughly 9 pixel cap height of
 * the 12.8 pixel label beside it reads as the dominant element of the control.
 * The spinner has to state the same size because the registry hardcodes its own.
 */
export function SignOutSubmit() {
  const { pending } = useFormStatus();

  return (
    <Button
      aria-busy={pending}
      disabled={pending}
      size="sm"
      type="submit"
      variant="outline"
    >
      Sign out
      {pending ? (
        <ButtonSpinner className="size-3" />
      ) : (
        <Power className="size-3" />
      )}
    </Button>
  );
}
