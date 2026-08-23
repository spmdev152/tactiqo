import Link from "next/link";
import { redirect } from "next/navigation";

import { MatchIntelligencePanel } from "@/features/auth/components/match-intelligence-panel";
import { getCurrentUser } from "@/features/auth/server/get-current-user";

/**
 * Renders the account-request page.
 *
 * @remarks
 * This route exists because the sign-in page offers a way to create an account,
 * and an offer that leads nowhere is worse than no offer. Self-service
 * registration is not built: the backend exposes no endpoint for it, and issue
 * #1 scoped it out along with password reset and e-mail verification. So this
 * page states the real route to an account instead of pretending to be a form.
 *
 * It is public, which is why `src/proxy.ts` exempts it: somebody without a
 * session is exactly who needs to read it.
 *
 * @returns The account-request page tree.
 */
export default async function SignupPage() {
  const user = await getCurrentUser();

  if (user !== null) {
    redirect("/");
  }

  return (
    <div className="grid flex-1 lg:grid-cols-2">
      <main className="flex items-center justify-center px-6 py-16 sm:px-10">
        <div className="flex w-full max-w-sm flex-col gap-9">
          <header className="flex flex-col gap-3">
            <p className="font-mono text-[0.7rem] tracking-[0.2em] text-muted-foreground uppercase">
              Request access
            </p>

            <h1 className="font-display text-5xl leading-[0.95] font-bold tracking-tight text-balance uppercase">
              Get on the team sheet
            </h1>

            <p className="text-sm leading-relaxed text-muted-foreground">
              Tactiqo is invite-only while the platform is being built. Accounts
              are created by an administrator, who sets the e-mail address you
              will sign in with.
            </p>
          </header>

          <div className="flex flex-col gap-4 rounded-lg border border-border/60 bg-card/60 p-5">
            <p className="font-mono text-[0.62rem] tracking-[0.12em] text-muted-foreground uppercase">
              What happens next
            </p>

            <ol className="flex flex-col gap-3 text-sm text-muted-foreground">
              <li>
                <span className="font-mono text-foreground">01</span> Ask your
                administrator to provision an account for your e-mail address.
              </li>

              <li>
                <span className="font-mono text-foreground">02</span> They send
                you the address and the initial password.
              </li>

              <li>
                <span className="font-mono text-foreground">03</span> You sign
                in and the session is yours for fourteen days.
              </li>
            </ol>
          </div>

          <p className="text-sm text-muted-foreground">
            Already have an account?{" "}
            <Link
              className="font-medium text-foreground underline decoration-primary decoration-2 underline-offset-4 transition-colors hover:text-primary"
              href="/login"
            >
              Sign in
            </Link>
          </p>
        </div>
      </main>

      <MatchIntelligencePanel className="hidden lg:block" />
    </div>
  );
}
