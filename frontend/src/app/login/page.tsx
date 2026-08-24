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

/**
 * Opts the route out of prerendering.
 *
 * @remarks
 * Already true implicitly, through the `cookies()` call `getCurrentUser`
 * reaches, and now for a second reason: the page reads `searchParams` to decide
 * whether an involuntary session loss has to be reported. Stating it keeps the
 * dependency on the request visible instead of leaving it to be inferred from a
 * transitive call.
 */
export const dynamic = "force-dynamic";

/**
 * Props of {@link LoginPage}.
 */
interface LoginPageProps {
  /**
   * Query the visitor arrived with. It may carry a session-loss reason, which
   * is visitor-controllable and therefore only ever resolved against a closed
   * set rather than rendered.
   */
  readonly searchParams: Promise<Record<string, string | string[] | undefined>>;
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
 * The warning for an involuntary arrival is resolved here, on the server, so
 * the page hands its client child copy from a closed set and the
 * visitor-controllable parameter never reaches the DOM.
 *
 * @returns The sign-in page tree.
 */
export default async function LoginPage({ searchParams }: LoginPageProps) {
  const user = await getCurrentUser();

  if (user !== null) {
    redirect("/");
  }

  const query = await searchParams;

  const warning = sessionLossWarning(query[SESSION_LOSS_PARAMETER]);

  return (
    <div className="grid flex-1 lg:grid-cols-2">
      {warning !== null && <SessionLossToast warning={warning} />}

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
