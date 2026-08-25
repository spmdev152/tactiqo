import { FixtureList } from "@/features/fixtures/components/fixture-list";
import type { FixturesResult } from "@/features/fixtures/types/fixture";

/**
 * Props of {@link FixtureListSection}.
 */
export interface FixtureListSectionProps {
  /** Fixtures of the scope being shown, as the route started reading them. */
  readonly fixtures: Promise<FixturesResult>;
}

/**
 * Waits for the fixtures of one scope and renders them.
 *
 * @remarks
 * The only part of the page that waits for the fixture query, which is what
 * lets the route suspend the rows alone and keep the heading and the two
 * controls on screen while a new day loads. Splitting it out of the page is the
 * whole mechanism: a `Suspense` boundary can only defer a child, so the await
 * has to live below one.
 *
 * The request is started by the page and only awaited here, so it leaves for the
 * API at the same moment the competition list does instead of queueing behind
 * it.
 *
 * @returns The fixture list for the requested scope.
 */
export async function FixtureListSection({
  fixtures,
}: FixtureListSectionProps) {
  return <FixtureList result={await fixtures} />;
}
