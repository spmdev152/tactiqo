import Image from "next/image";

import { CalendarX2, TriangleAlert } from "lucide-react";

import { FixtureRow } from "@/features/fixtures/components/fixture-row";
import {
  type FixtureGroup,
  groupFixturesByLeague,
} from "@/features/fixtures/domain/fixture-groups";
import type { FixturesResult } from "@/features/fixtures/types/fixture";

const EMPTY_MESSAGE = "No fixtures on this day for this competition.";

const EMPTY_HINT = "Pick another day, or widen the filter to all competitions.";

const ERROR_MESSAGE = "Fixtures are unavailable right now.";

const FLAG_WIDTH = 24;

const FLAG_HEIGHT = 17;

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
        {league.countryFlagUrl !== "" && (
          <Image
            alt=""
            className="h-[17px] w-6 shrink-0 rounded-[2px] object-cover"
            height={FLAG_HEIGHT}
            src={league.countryFlagUrl}
            width={FLAG_WIDTH}
          />
        )}

        <h2 className="truncate text-sm font-medium">{league.name}</h2>

        <span className="ml-auto shrink-0 font-mono text-[0.68rem] tracking-[0.14em] text-muted-foreground uppercase">
          {fixtures.length === 1 ? "1 match" : `${fixtures.length} matches`}
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
 * Both non-list states are announced through `role="status"`, because a visitor
 * who changed day or competition receives no rows and would otherwise be told
 * nothing at all.
 *
 * @returns The grouped fixtures, the empty state, or the error state.
 */
export function FixtureList({ result }: FixtureListProps) {
  if (!result.loaded) {
    return (
      <div
        className="flex flex-col items-start gap-3 rounded-xl border border-destructive/40 bg-destructive/5 px-5 py-6"
        role="status"
      >
        <TriangleAlert className="size-5 text-destructive" />

        <p className="font-medium">{ERROR_MESSAGE}</p>

        <p className="text-sm text-muted-foreground">{result.reason}</p>
      </div>
    );
  }

  if (result.fixtures.length === 0) {
    return (
      <div
        className="flex flex-col items-start gap-3 rounded-xl border border-dashed px-5 py-6"
        role="status"
      >
        <CalendarX2 className="size-5 text-muted-foreground" />

        <p className="font-medium">{EMPTY_MESSAGE}</p>

        <p className="text-sm text-muted-foreground">{EMPTY_HINT}</p>
      </div>
    );
  }

  const groups = groupFixturesByLeague(result.fixtures);

  return (
    <div className="flex flex-col gap-5">
      {groups.map((group) => (
        <FixtureGroupSection group={group} key={group.league.id} />
      ))}
    </div>
  );
}
