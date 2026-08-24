import { SignOutSubmit } from "@/features/auth/components/sign-out-submit";
import { signOutAction } from "@/features/auth/server/actions";

/**
 * Ends the current session.
 *
 * @remarks
 * The form stays a Server Component posting straight to the Server Action, so
 * signing out keeps working before hydration and with JavaScript disabled. Only
 * the submit control is a client leaf, because `useFormStatus` reports on the
 * form above it and therefore cannot live in the component that renders it.
 */
export function SignOutButton() {
  return (
    <form action={signOutAction}>
      <SignOutSubmit />
    </form>
  );
}
