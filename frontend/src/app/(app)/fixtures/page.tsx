import { Suspense } from "react";

import { requireUser } from "@/features/auth/server/require-user";
import { FixtureFilters } from "@/features/fixtures/components/fixture-filters";
import { FixtureListSection } from "@/features/fixtures/components/fixture-list-section";
import { FixtureListSkeleton } from "@/features/fixtures/components/fixture-list-skeleton";
import {
  FIXTURE_DATE_PARAMETER,
  FIXTURE_LEAGUE_PARAMETER,
  resolveLeagueId,
  resolveUtcDay,
} from "@/features/fixtures/domain/fixture-search-params";
import { getLeagues } from "@/features/fixtures/server/get-leagues";

/**
 * Opts the route out of prerendering.
 *
 * @remarks
 * The page is rendered per session and per query: it gates on the session, it
 * reads `searchParams` for the day and the competition, and it forwards the
 * visitor's own bearer token to the API. A prerendered copy would be one
 * visitor's fixtures served to another, and forcing dynamic rendering also keeps
 * `next build` working while the API is unreachable, which is what happens in CI
 * and on a first checkout.
 */
export const dynamic = "force-dynamic";

/**
 * Props of {@link FixturesPage}.
 */
interface FixturesPageProps {
  /**
   * Query the visitor arrived with. It carries the day and the competition, both
   * visitor-controllable and therefore resolved rather than trusted. Bound to
   * Next's own generated type so a framework change cannot drift past a
   * restatement of it.
   */
  readonly searchParams: PageProps<"/fixtures">["searchParams"];
}

/**
 * Renders the fixtures of one day for one competition.
 *
 * @remarks
 * A Server Component: the session check and both API reads happen on the
 * server, so the session token never leaves it and the browser never talks to
 * the provider. The session is confirmed here rather than relied upon from the
 * shell layout, because Next.js does not re-render a layout for a navigation
 * that stays inside it, so a page that reached the shell once would keep
 * rendering after its session was revoked.
 *
 * Only the fixture query is deferred. The label and the filters resolve without
 * it, so they render immediately and stay on screen while a new scope loads
 * behind a `Suspense` boundary keyed to it. A whole-page loading state used to
 * replace them with a shimmer, which meant covering text that was already
 * correct and jumping the toolbar the moment the rows arrived.
 *
 * The chosen day is stated once, by the picker itself. A heading repeating it
 * cost a line of the viewport to say what the control beside it already said.
 *
 * The day and the competition are URL state and nothing else, which is what
 * makes a view linkable and lets it survive a reload. The filter bar stages a
 * scope locally and applies it in one navigation, so the server stays the
 * single place either value is resolved.
 *
 * The page root is a `div` rather than a `main`, because `SidebarInset` is
 * itself the `main` element of the shell.
 *
 * @returns The fixtures page tree.
 */
export default async function FixturesPage({
  searchParams,
}: FixturesPageProps) {
  await requireUser();

  const query = await searchParams;

  const day = resolveUtcDay(query[FIXTURE_DATE_PARAMETER]);
  const leagueId = resolveLeagueId(query[FIXTURE_LEAGUE_PARAMETER]);

  const leagues = await getLeagues();

  const scope = `${day}|${leagueId}`;

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-6 px-6 py-12">
      <h1 className="font-mono text-[0.7rem] tracking-[0.2em] text-muted-foreground uppercase">
        Fixtures
      </h1>

      <div className="flex min-w-0 flex-col gap-4">
        <FixtureFilters
          appliedDay={day}
          appliedLeagueId={leagueId}
          leagues={leagues.loaded ? leagues.leagues : []}
        />

        <Suspense fallback={<FixtureListSkeleton />} key={scope}>
          <FixtureListSection day={day} leagueId={leagueId} />
        </Suspense>
      </div>
    </div>
  );
}
