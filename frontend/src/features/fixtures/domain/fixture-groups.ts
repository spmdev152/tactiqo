import type { Fixture } from "@/features/fixtures/types/fixture";
import type { League } from "@/features/fixtures/types/league";

/**
 * Matches of one competition on the day being shown.
 */
export interface FixtureGroup {
  /** Competition the matches belong to. */
  readonly league: League;

  /** Matches of that competition, earliest kick-off first. */
  readonly fixtures: readonly Fixture[];
}

interface CollectedGroup {
  readonly league: League;
  readonly fixtures: Fixture[];
  readonly firstKickoff: number;
}

/**
 * Groups a day's fixtures by competition.
 *
 * @remarks
 * The API answers a day ordered by kick-off across every competition, which is
 * the right order for one list and the wrong one for a list with headings: a
 * competition would reappear each time its next match came round. Grouping
 * happens here rather than in the query because it is a decision about how the
 * day reads, not about what the day contains.
 *
 * Groups run in order of their earliest kick-off, so the top of the page is the
 * competition playing next, and ties break on the competition name so the order
 * is stable rather than dependent on however the day happened to arrive. Within
 * a group the incoming order is kept, which is already by kick-off.
 *
 * @param fixtures - Fixtures of one day, ordered by kick-off.
 * @returns One group per competition present, in reading order.
 */
export function groupFixturesByLeague(
  fixtures: readonly Fixture[],
): FixtureGroup[] {
  const collected = new Map<number, CollectedGroup>();

  for (const fixture of fixtures) {
    const group = collected.get(fixture.league.id);

    if (group === undefined) {
      collected.set(fixture.league.id, {
        league: fixture.league,
        fixtures: [fixture],
        firstKickoff: fixture.kickoffAt.getTime(),
      });
    } else {
      group.fixtures.push(fixture);
    }
  }

  return [...collected.values()].sort((one, other) =>
    one.firstKickoff === other.firstKickoff
      ? one.league.name.localeCompare(other.league.name)
      : one.firstKickoff - other.firstKickoff,
  );
}
