import Link from "next/link";
import { redirect } from "next/navigation";

import { LoginForm } from "@/features/auth/components/login-form";
import { MatchIntelligencePanel } from "@/features/auth/components/match-intelligence-panel";
import { getCurrentUser } from "@/features/auth/server/get-current-user";

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
 * @returns The sign-in page tree.
 */
export default async function LoginPage() {
  const user = await getCurrentUser();

  if (user !== null) {
    redirect("/");
  }

  return (
    <div className="grid flex-1 lg:grid-cols-2">
      <main className="flex items-center justify-center px-6 py-16 sm:px-10">
        <div className="flex w-full max-w-sm flex-col gap-9">
          <header className="flex flex-col gap-3">
            <p className="animate-rise font-mono text-[0.7rem] tracking-[0.2em] text-muted-foreground uppercase">
              Welcome back
            </p>

            <h1 className="animate-rise font-display text-5xl leading-[0.95] font-bold tracking-tight text-balance uppercase [animation-delay:80ms]">
              Sign in to your account
            </h1>

            <p className="animate-rise text-sm text-muted-foreground [animation-delay:160ms]">
              Access and analyse fixtures, statistics, bookmaker odds, and
              predictions across the five leagues you follow.
            </p>
          </header>

          <div className="animate-rise [animation-delay:240ms]">
            <LoginForm />
          </div>

          <p className="animate-rise text-sm text-muted-foreground [animation-delay:320ms]">
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

      <MatchIntelligencePanel className="hidden lg:block" />
    </div>
  );
}
