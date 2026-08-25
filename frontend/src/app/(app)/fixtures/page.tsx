import { Suspense } from "react";

import { requireUser } from "@/features/auth/server/require-user";
import { FixtureFilters } from "@/features/fixtures/components/fixture-filters";
import { FixtureListSection } from "@/features/fixtures/components/fixture-list-section";
import { FixtureListSkeleton } from "@/features/fixtures/components/fixture-list-skeleton";
import {
  FIXTURE_DATE_PARAMETER,
  FIXTURE_LEAGUE_PARAMETER,
  fixtureScopeKey,
  resolveLeagueIds,
  resolveUtcDay,
} from "@/features/fixtures/domain/fixture-search-params";
import { getFixtures } from "@/features/fixtures/server/get-fixtures";
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
 * Neither read is awaited here. The session gate is the only round trip above
 * the boundaries, and both requests are started on the same line of this
 * function and handed down as promises, so they leave for the API together and
 * the tree returns while both are still in flight. Awaiting the competitions
 * here — which is what this page used to do — held the heading and both controls
 * behind a request they do not need, delayed the fixture request until that one
 * had answered, and left the previous page on screen for the whole round trip,
 * since there is no route-level loading state to show instead.
 *
 * The heading, the day picker and the apply button therefore render from the URL
 * alone. Each read is awaited below a boundary of its own: the rows behind one
 * keyed to the scope, so a new day gets its skeleton, and the competition
 * picker's options behind one inside the bar, so a picker still filling in
 * cannot hold back the two controls beside it.
 *
 * The polite live region wraps the fixtures boundary rather than sitting inside
 * it. The boundary is keyed to the scope, so applying a filter unmounts and
 * remounts everything below it; a region declared down there would be created in
 * the same commit as its own text and would announce nothing at all. Declared
 * above it, the region is already in the tree when the outcome changes, which is
 * the condition for it to speak.
 *
 * The chosen day is stated once, by the picker itself. A heading repeating it
 * cost a line of the viewport to say what the control beside it already said.
 *
 * The day and the competition are URL state and nothing else, which is what
 * makes a view linkable and lets it survive a reload. The filter bar stages a
 * scope locally and applies it in one navigation, so the server stays the
 * single place either value is resolved.
 *
 * The page is a size container, and the filters and the rows lay themselves out
 * against it rather than against the viewport. The two are not the same width:
 * the sidebar takes 16rem of the window when it is expanded, so a viewport-based
 * breakpoint switches to the wide layout while the pane is still too narrow for
 * it. That is what pushed a horizontal scrollbar onto the document from around
 * 853px.
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
  const leagueIds = resolveLeagueIds(query[FIXTURE_LEAGUE_PARAMETER]);

  const leagues = getLeagues();
  const fixtures = getFixtures({ day, leagueIds });

  const scope = fixtureScopeKey(day, leagueIds);

  return (
    <div className="@container mx-auto flex w-full max-w-5xl flex-1 flex-col gap-6 px-6 py-12">
      <h1 className="font-mono text-[0.7rem] tracking-[0.2em] text-muted-foreground uppercase">
        Fixtures
      </h1>

      <div className="flex min-w-0 flex-col gap-4">
        <FixtureFilters
          appliedDay={day}
          appliedLeagueIds={leagueIds}
          leagues={leagues}
        />

        <div aria-live="polite" className="flex min-w-0 flex-col">
          <Suspense fallback={<FixtureListSkeleton />} key={scope}>
            <FixtureListSection fixtures={fixtures} />
          </Suspense>
        </div>
      </div>
    </div>
  );
}
