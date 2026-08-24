import { Suspense } from "react";

import Link from "next/link";
import { redirect } from "next/navigation";

import { LoginForm } from "@/features/auth/components/login-form";
import { SessionLossToast } from "@/features/auth/components/session-loss-toast";
import { SignInPanel } from "@/features/auth/components/sign-in-panel";
import { getCurrentUser } from "@/features/auth/server/get-current-user";
import { readSessionToken } from "@/features/auth/server/session-cookie";

/**
 * Opts the route out of prerendering.
 *
 * @remarks
 * Already true implicitly, through the `cookies()` call `getCurrentUser`
 * reaches, and stated so the dependency on the request is visible rather than
 * inferred from a transitive call. The `Suspense` boundary below covers the
 * same ground from the other side: the notice reads `useSearchParams`, which
 * needs a boundary on any route that is not dynamic, so it keeps this page
 * building if either reason is ever removed.
 */
export const dynamic = "force-dynamic";

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
 * The notice is mounted on every render rather than only when a warning
 * applies, and it decides for itself from the live URL. Rendering it
 * conditionally made the toast depend on this function running per arrival,
 * which the client router's segment cache does not guarantee; the component
 * documents that failure. All the server owes it is whether this request
 * carried a session token, which is what makes one of the two messages true.
 *
 * @returns The sign-in page tree.
 */
export default async function LoginPage() {
  const user = await getCurrentUser();

  if (user !== null) {
    redirect("/");
  }

  const sessionTokenPresent = (await readSessionToken()) !== null;

  return (
    <div className="grid flex-1 lg:grid-cols-2">
      <Suspense>
        <SessionLossToast sessionTokenPresent={sessionTokenPresent} />
      </Suspense>

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
