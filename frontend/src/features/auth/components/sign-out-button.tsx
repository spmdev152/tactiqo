import { Button } from "@/components/ui/button";
import { signOutAction } from "@/features/auth/server/actions";

/**
 * Ends the current session.
 *
 * @remarks
 * A plain form posting to the Server Action rather than a Client Component:
 * there is no client state to hold, and a form keeps sign-out working before
 * hydration and with JavaScript disabled.
 */
export function SignOutButton() {
  return (
    <form action={signOutAction}>
      <Button size="sm" type="submit" variant="outline">
        Sign out
      </Button>
    </form>
  );
}
