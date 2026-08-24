import { requireUser } from "@/features/auth/server/require-user";
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
 * the proxy, which only knows whether a cookie exists, and not the shell layout
 * either, which Next.js does not re-render for a navigation that stays inside
 * it.
 *
 * The signed-in identity and the sign-out control are no longer rendered here.
 * They belong to the sidebar, which every authenticated route carries, so a
 * page repeating them would offer the same account twice.
 *
 * The page root is a `div` rather than a `main`, because `SidebarInset` is
 * itself the `main` element of the shell.
 *
 * @returns The landing page tree.
 */
export default async function HomePage() {
  await requireUser();

  const health = await getPlatformHealth();

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col items-start gap-10 px-6 py-16">
      <header className="flex w-full flex-col gap-6">
        <div className="flex flex-col gap-3">
          <p className="font-mono text-[0.7rem] tracking-[0.2em] text-muted-foreground uppercase">
            Soccer intelligence
          </p>

          <h1 className="font-display text-5xl leading-[0.95] font-bold tracking-tight uppercase">
            Football intelligence for fixtures, statistics, odds and predictions
          </h1>
        </div>
      </header>

      <PlatformHealthCard health={health} />
    </div>
  );
}
