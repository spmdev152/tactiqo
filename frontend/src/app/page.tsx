import { PlatformHealthCard } from "@/features/health/components/platform-health-card";
import { getPlatformHealth } from "@/features/health/server/get-platform-health";

/**
 * Opts the route out of prerendering.
 *
 * @remarks
 * The page reports live backend health, so a value captured at build time would
 * be wrong from the moment it was written. Forcing dynamic rendering also keeps
 * `next build` working while the API is unreachable, which is what happens in CI
 * and on a first checkout.
 */
export const dynamic = "force-dynamic";

/**
 * Renders the landing page with the current backend platform health.
 *
 * @remarks
 * A Server Component: the health probe runs on the server, so the browser never
 * talks to the API or the upstream provider. `getPlatformHealth` never throws, so
 * an unreachable backend renders an explicit unavailable state instead of an
 * error boundary.
 *
 * @returns The landing page tree.
 */
export default async function HomePage() {
  const health = await getPlatformHealth();

  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col items-start gap-8 px-6 py-16">
      <header className="flex flex-col gap-2">
        <h1 className="font-heading text-3xl font-semibold tracking-tight">
          Tactiqo
        </h1>

        <p className="text-sm text-muted-foreground">
          Football intelligence for fixtures, statistics, odds, and predictions.
        </p>
      </header>

      <PlatformHealthCard health={health} />
    </main>
  );
}
