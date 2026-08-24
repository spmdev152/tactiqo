import { CalendarX2, TriangleAlert } from "lucide-react";

import { FixtureRow } from "@/features/fixtures/components/fixture-row";
import type { FixturesResult } from "@/features/fixtures/types/fixture";

const EMPTY_MESSAGE = "No fixtures on this day for this competition.";

const EMPTY_HINT = "Pick another day, or widen the filter to all competitions.";

const ERROR_MESSAGE = "Fixtures are unavailable right now.";

/**
 * Props of {@link FixtureList}.
 */
export interface FixtureListProps {
  /** Fixtures of the selected day, or the reason they are unavailable. */
  readonly result: FixturesResult;
}

/**
 * Renders the fixtures of one day, including the empty and error states.
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
 * @returns The fixture list, its empty state, or its error state.
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

  return (
    <ul className="divide-y divide-border overflow-hidden rounded-xl border">
      {result.fixtures.map((fixture) => (
        <FixtureRow fixture={fixture} key={fixture.id} />
      ))}
    </ul>
  );
}
