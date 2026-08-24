import { requireUser } from "@/features/auth/server/require-user";

/**
 * Opts the route out of prerendering.
 *
 * @remarks
 * The page states who the request is signed in as, so a prerendered copy would
 * show one visitor's identity to another.
 */
export const dynamic = "force-dynamic";

/**
 * Renders the account the current session belongs to.
 *
 * @remarks
 * The destination of the sidebar's account entry, and the one place the
 * signed-in address is stated in full. It moved off the sidebar because a
 * 16rem column truncates an e-mail address and a collapsed sidebar cannot show
 * one at all.
 *
 * There is nothing to change here yet. Accounts are provisioned by an
 * administrator, and the backend exposes no endpoint for a self-service profile
 * or password change, so the page states what is true rather than offering a
 * form that would post nowhere.
 *
 * The page root is a `div` rather than a `main`, because `SidebarInset` is
 * itself the `main` element of the shell.
 *
 * @returns The account page tree.
 */
export default async function AccountPage() {
  const user = await requireUser();

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-1 flex-col gap-8 px-6 py-12">
      <header className="flex flex-col gap-3">
        <p className="font-mono text-[0.7rem] tracking-[0.2em] text-muted-foreground uppercase">
          Account
        </p>

        <h1 className="font-display text-4xl leading-[0.95] font-bold tracking-tight uppercase">
          {user.fullName === "" ? "Your account" : user.fullName}
        </h1>
      </header>

      <dl className="flex flex-col gap-4 rounded-lg border border-border/60 bg-card/60 p-5">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <dt className="font-mono text-[0.62rem] tracking-[0.12em] text-muted-foreground uppercase">
            E-mail
          </dt>

          <dd className="text-sm">{user.email}</dd>
        </div>

        <div className="flex flex-wrap items-baseline justify-between gap-2 border-t border-border/60 pt-4">
          <dt className="font-mono text-[0.62rem] tracking-[0.12em] text-muted-foreground uppercase">
            Display name
          </dt>

          <dd className="text-sm">
            {user.fullName === "" ? (
              <span className="text-muted-foreground">Not set</span>
            ) : (
              user.fullName
            )}
          </dd>
        </div>
      </dl>

      <p className="text-sm text-muted-foreground">
        Accounts are provisioned by an administrator. Ask yours to change the
        address you sign in with or to reset your password.
      </p>
    </div>
  );
}
