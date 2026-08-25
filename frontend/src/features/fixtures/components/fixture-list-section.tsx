import { FixtureList } from "@/features/fixtures/components/fixture-list";
import { getFixtures } from "@/features/fixtures/server/get-fixtures";

/**
 * Props of {@link FixtureListSection}.
 */
export interface FixtureListSectionProps {
  /** UTC calendar day to list, as `YYYY-MM-DD`. */
  readonly day: string;

  /** Internal league identifiers, empty for every competition. */
  readonly leagueIds: readonly number[];
}

/**
 * Fetches and renders the fixtures of one day.
 *
 * @remarks
 * The only part of the page that waits for the fixture query, which is what
 * lets the route suspend the rows alone and keep the heading and the two
 * controls on screen while a new day loads. Splitting it out of the page is the
 * whole mechanism: a `Suspense` boundary can only defer a child, so the await
 * has to live below one.
 *
 * @returns The fixture list for the requested scope.
 */
export async function FixtureListSection({
  day,
  leagueIds,
}: FixtureListSectionProps) {
  const fixtures = await getFixtures({ day, leagueIds });

  return <FixtureList result={fixtures} />;
}
