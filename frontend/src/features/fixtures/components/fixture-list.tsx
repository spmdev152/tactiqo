import { CalendarX2, TriangleAlert } from "lucide-react";

import { FixtureRow } from "@/features/fixtures/components/fixture-row";
import { LeagueFlag } from "@/features/fixtures/components/league-flag";
import {
  type FixtureGroup,
  groupFixturesByLeague,
} from "@/features/fixtures/domain/fixture-groups";
import type { FixturesResult } from "@/features/fixtures/types/fixture";

const EMPTY_MESSAGE = "No fixtures on this day.";

const EMPTY_HINT = "Pick another day, or widen the competition filter.";

const ERROR_MESSAGE = "Fixtures are unavailable right now.";

/**
 * States a number of matches in the right number.
 *
 * @param count - Matches being counted.
 * @returns The count with its noun.
 */
function statedMatches(count: number): string {
  return count === 1 ? "1 match" : `${count} matches`;
}

/**
 * States what a loaded day holds, for the live region the list renders into.
 *
 * @remarks
 * The one statement a screen reader gets about a day that did load. The rows
 * themselves are opted out of the announcement, because reading thirty of them
 * after every filter is worse than reading none, so the count of each is the
 * whole message.
 *
 * @param groups - Competitions of the day and their matches.
 * @returns The spoken summary of the day.
 */
function statedDay(groups: readonly FixtureGroup[]): string {
  const matches = groups.reduce(
    (total, group) => total + group.fixtures.length,
    0,
  );

  const competitions =
    groups.length === 1 ? "1 competition" : `${groups.length} competitions`;

  return `${statedMatches(matches)} in ${competitions}.`;
}

/**
 * Props of {@link FixtureGroupSection}.
 */
interface FixtureGroupSectionProps {
  /** Competition and its matches on the day being shown. */
  readonly group: FixtureGroup;
}

/**
 * Renders one competition's matches under a heading naming it.
 *
 * @remarks
 * The heading is an `h2` under the page's own `h1`, so the day reads as a
 * document rather than as a striped table: a screen reader can jump between
 * competitions and a sighted reader can scan the same landmarks.
 *
 * The flag is decorative, as it is in the filter, because the name is right
 * beside it. The count is worth stating because it is the one fact the heading
 * can add that the rows below it do not already carry individually.
 *
 * @returns The competition section.
 */
function FixtureGroupSection({ group }: FixtureGroupSectionProps) {
  const { league, fixtures } = group;

  return (
    <section className="overflow-hidden rounded-xl border">
      <header className="flex items-center gap-2.5 border-b border-border bg-muted/40 px-4 py-2.5">
        <LeagueFlag className="h-[17px] w-6" league={league} />

        <h2 className="truncate text-sm font-medium">{league.name}</h2>

        <span className="ml-auto shrink-0 font-mono text-[0.68rem] tracking-[0.14em] text-muted-foreground uppercase">
          {statedMatches(fixtures.length)}
        </span>
      </header>

      <ul className="divide-y divide-border">
        {fixtures.map((fixture) => (
          <FixtureRow fixture={fixture} key={fixture.id} />
        ))}
      </ul>
    </section>
  );
}

/**
 * Props of {@link FixtureList}.
 */
export interface FixtureListProps {
  /** Fixtures of the selected day, or the reason they are unavailable. */
  readonly result: FixturesResult;
}

/**
 * Renders the fixtures of one day, grouped by competition.
 *
 * @remarks
 * Three outcomes, three surfaces, and the empty one is deliberately not the
 * error one. An answered request with nothing in it is a fact about the
 * calendar, so it invites the visitor to pick another day; a request that could
 * not be answered is a fact about the platform, so it says so and repeats the
 * reason instead of implying there is no football.
 *
 * The empty message names no competition, because this component is not told
 * how many are filtered. It once said "for this competition", which was wrong
 * in both directions once the filter became a multiple selection: singular for
 * several, and inventing a filter on a day with no football at all. Widening is
 * offered as a hint rather than asserted as the cause.
 *
 * All three outcomes are announced, and none of them carries a live region of
 * its own. The route renders this component inside a keyed `Suspense` boundary,
 * so every new scope unmounts and remounts the whole subtree; a region declared
 * here would arrive in the same commit as its own text, and a live region only
 * speaks when its content changes while it is already in the tree. The region
 * therefore lives on a wrapper above that boundary and survives the swap, and
 * what these three branches owe it is text that differs between them.
 *
 * The loaded branch owes it text at all, which is why the summary exists: a day
 * that produced rows used to announce nothing, so applying a filter that worked
 * was the one outcome a screen reader was never told about. The rows opt out of
 * the region rather than being read into it, because a filter that returns
 * thirty matches would otherwise announce all of them.
 *
 * @returns The grouped fixtures, the empty state, or the error state.
 */
export function FixtureList({ result }: FixtureListProps) {
  if (!result.loaded) {
    return (
      <div className="flex flex-col items-start gap-3 rounded-xl border border-destructive/40 bg-destructive/5 px-5 py-6">
        <TriangleAlert className="size-5 text-destructive" />

        <p className="font-medium">{ERROR_MESSAGE}</p>

        <p className="text-sm text-muted-foreground">{result.reason}</p>
      </div>
    );
  }

  if (result.fixtures.length === 0) {
    return (
      <div className="flex flex-col items-start gap-3 rounded-xl border border-dashed px-5 py-6">
        <CalendarX2 className="size-5 text-muted-foreground" />

        <p className="font-medium">{EMPTY_MESSAGE}</p>

        <p className="text-sm text-muted-foreground">{EMPTY_HINT}</p>
      </div>
    );
  }

  const groups = groupFixturesByLeague(result.fixtures);

  return (
    <>
      <p className="sr-only">{statedDay(groups)}</p>

      <div aria-live="off" className="flex flex-col gap-5">
        {groups.map((group) => (
          <FixtureGroupSection group={group} key={group.league.id} />
        ))}
      </div>
    </>
  );
}
