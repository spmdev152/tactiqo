import { Suspense } from "react";

import Link from "next/link";
import { redirect } from "next/navigation";

import { LoginForm } from "@/features/auth/components/login-form";
import { SessionLossToast } from "@/features/auth/components/session-loss-toast";
import { SignInPanel } from "@/features/auth/components/sign-in-panel";
import {
  SESSION_LOSS_PARAMETER,
  sessionLossWarning,
} from "@/features/auth/domain/session-loss";
import { getCurrentUser } from "@/features/auth/server/get-current-user";
import { readSessionToken } from "@/features/auth/server/session-cookie";

/**
 * Opts the route out of prerendering.
 *
 * @remarks
 * Already true implicitly, through the `cookies()` call `getCurrentUser`
 * reaches, and now for a second reason: the page reads `searchParams` to decide
 * whether an involuntary session loss has to be reported. Stating it keeps the
 * dependency on the request visible instead of leaving it to be inferred from a
 * transitive call. The `Suspense` boundary around the notice below covers the
 * same ground from the other side: `useSearchParams` needs one on any route
 * that is not dynamic, so the boundary is what keeps this page building if
 * either of those two implicit reasons is ever removed.
 */
export const dynamic = "force-dynamic";

/**
 * Props of {@link LoginPage}.
 */
interface LoginPageProps {
  /**
   * Query the visitor arrived with. It may mark the arrival involuntary, which
   * is visitor-controllable and therefore never rendered and never trusted to
   * say more than that. Bound to Next's own generated type so a framework
   * change cannot drift past a restatement of it.
   */
  readonly searchParams: PageProps<"/login">["searchParams"];
}

/**
 * Renders the sign-in page and turns an already-authenticated visitor away.
 *
 * @remarks
 * The proxy redirects on cookie presence alone, so a stale cookie still
 * lands here; confirming the session against the backend is what makes the
 * redirect trustworthy.
 *
 * The illustrated panel is dropped rather than stacked below the form under
 * `lg`, because a decorative half screen pushed above the fold on a phone would
 * bury the only thing the page exists for.
 *
 * The warning is resolved here, on the server, from two inputs: the parameter
 * says whether to speak, and the request's own cookie decides which of the two
 * messages is true. Resolving it server-side also means the client child
 * receives copy rather than the parameter, which is never rendered.
 *
 * @returns The sign-in page tree.
 */
export default async function LoginPage({ searchParams }: LoginPageProps) {
  const user = await getCurrentUser();

  if (user !== null) {
    redirect("/");
  }

  const [query, token] = await Promise.all([searchParams, readSessionToken()]);

  const warning = sessionLossWarning(
    query[SESSION_LOSS_PARAMETER],
    token !== null,
  );

  return (
    <div className="grid flex-1 lg:grid-cols-2">
      {warning !== null && (
        <Suspense>
          <SessionLossToast warning={warning} />
        </Suspense>
      )}

      <main className="flex items-center justify-center px-6 py-16 sm:px-10">
        <div className="flex w-full max-w-sm flex-col gap-9">
          <header className="flex flex-col gap-3">
            <p className="font-mono text-[0.7rem] tracking-[0.2em] text-muted-foreground uppercase">
              Welcome back
            </p>

            <h1 className="font-display text-5xl leading-[0.95] font-bold tracking-tight text-balance uppercase">
              Sign in to your account
            </h1>

            <p className="text-sm text-muted-foreground">
              Access and analyse fixtures, statistics, bookmaker odds, and
              predictions across the five leagues you follow.
            </p>
          </header>

          <LoginForm />

          <p className="text-sm text-muted-foreground">
            Do not have an account?{" "}
            <Link
              className="font-medium text-foreground underline decoration-primary decoration-2 underline-offset-4 transition-colors hover:text-primary"
              href="/signup"
            >
              Create one
            </Link>
          </p>
        </div>
      </main>

      <SignInPanel className="hidden lg:block" />
    </div>
  );
}
