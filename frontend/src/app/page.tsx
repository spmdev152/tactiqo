import { redirect } from "next/navigation";

import { SignOutButton } from "@/features/auth/components/sign-out-button";
import { getCurrentUser } from "@/features/auth/server/get-current-user";
import { PlatformHealthCard } from "@/features/health/components/platform-health-card";
import { getPlatformHealth } from "@/features/health/server/get-platform-health";

/**
 * Opts the route out of prerendering.
 *
 * @remarks
 * Two independent reasons now apply. The page reports live backend health, so a
 * value captured at build time would be wrong from the moment it was written,
 * and it is rendered per session, so a shared prerendered copy would show one
 * visitor's identity to another. Forcing dynamic rendering also keeps
 * `next build` working while the API is unreachable, which is what happens in
 * CI and on a first checkout.
 */
export const dynamic = "force-dynamic";

/**
 * Renders the authenticated landing page with the current backend health.
 *
 * @remarks
 * A Server Component: the session check and the health probe both run on the
 * server, so the browser never talks to the API or the upstream provider, and
 * the session token never leaves the server. This check is authoritative, not
 * the proxy, which only knows whether a cookie exists.
 *
 * @returns The landing page tree.
 */
export default async function HomePage() {
  const user = await getCurrentUser();

  if (user === null) {
    redirect("/login");
  }

  const health = await getPlatformHealth();

  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col items-start gap-10 px-6 py-16">
      <header className="flex w-full flex-col gap-6">
        <div className="flex flex-col gap-3">
          <p className="font-mono text-[0.7rem] tracking-[0.2em] text-muted-foreground uppercase">
            Soccer intelligence
          </p>

          <h1 className="font-display text-5xl leading-[0.95] font-bold tracking-tight uppercase">
            Football intelligence for fixtures, statistics, odds and predictions
          </h1>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-4 border-t border-border/60 pt-5">
          <p className="font-mono text-xs tracking-wide text-muted-foreground">
            Signed in as <span className="text-foreground">{user.email}</span>
          </p>

          <SignOutButton />
        </div>
      </header>

      <PlatformHealthCard health={health} />
    </main>
  );
}
