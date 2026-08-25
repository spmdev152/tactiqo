"use client";

import { useCallback, useState, useTransition } from "react";

import { useRouter, useSearchParams } from "next/navigation";

import { ListFilter } from "lucide-react";

import { ButtonSpinner } from "@/components/button-spinner";
import { Button } from "@/components/ui/button";
import { FixturesDatePicker } from "@/features/fixtures/components/fixtures-date-picker";
import { LeagueSelect } from "@/features/fixtures/components/league-select";
import {
  FIXTURE_DATE_PARAMETER,
  FIXTURE_LEAGUE_PARAMETER,
} from "@/features/fixtures/domain/fixture-search-params";
import type { League } from "@/features/fixtures/types/league";

const APPLY_LABEL = "Filter";

/**
 * Scope the visitor has staged but not yet applied.
 *
 * @remarks
 * `from` records the applied scope the staging was made against, which is what
 * lets a staged scope expire on its own. A back or forward navigation moves the
 * applied scope without this component doing anything, and a staging that no
 * longer describes what is on screen has to be abandoned rather than left
 * offering to re-apply a day the visitor has already navigated away from.
 */
interface StagedScope {
  /** Applied scope this staging was made against. */
  readonly from: string;

  /** Staged UTC calendar day, as `YYYY-MM-DD`. */
  readonly day: string;

  /** Staged competitions, empty for all of them. */
  readonly leagueIds: readonly number[];
}

/**
 * Props of {@link FixtureFilters}.
 */
export interface FixtureFiltersProps {
  /** Competitions the platform covers, already ordered by name. */
  readonly leagues: readonly League[];

  /** UTC calendar day the list currently shows, as `YYYY-MM-DD`. */
  readonly appliedDay: string;

  /** Competitions the list is currently filtered to, empty for all. */
  readonly appliedLeagueIds: readonly number[];
}

/**
 * Renders the fixture filters and the control that applies them.
 *
 * @remarks
 * The two pickers stage a scope; this component applies it. Choosing a day or a
 * competition changes local state and navigates nowhere, so the popover and the
 * option list open and close against a page that is doing nothing else.
 *
 * That is the fix for a defect the previous shape could not shake off. When a
 * picker navigated on selection, the navigation began while the primitive was
 * still animating its exit; React holds the previous tree on screen for the
 * duration of a pending transition, and the list was repeatedly caught in that
 * window and painted open again after it had closed. Applying the scope from a
 * plain button removes the overlap rather than trying to time it: by the time
 * the request starts there is nothing left to animate.
 *
 * The bar lays itself out against the page container rather than the viewport.
 * The two differ by the width of the sidebar, so a viewport breakpoint put the
 * three controls in a row while the pane was still too narrow for them.
 *
 * Staging both values before applying them is worth having on its own. Changing
 * the day and the competition used to cost two round trips and two skeletons;
 * it now costs one.
 *
 * The staged scope is not seeded from the props. It starts absent and the
 * controls fall back to the applied scope, so there is no copy of a prop to go
 * stale and no remount needed to refresh one. It also carries the applied scope
 * it was staged against, which is what makes it expire when the URL moves
 * underneath it.
 *
 * The button is disabled while the staged scope equals the applied one, so the
 * control states whether there is anything to apply and a second press cannot
 * re-request the list already on screen. It reports the request through the same
 * busy pattern as the rest of the application: the label stays, the icon becomes
 * a spinner, and `aria-busy` reports what the icon shows.
 *
 * @returns The filter bar.
 */
export function FixtureFilters({
  leagues,
  appliedDay,
  appliedLeagueIds,
}: FixtureFiltersProps) {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [isPending, startTransition] = useTransition();

  const [staged, setStaged] = useState<StagedScope | null>(null);

  const applied = `${appliedDay}|${[...appliedLeagueIds].sort().join(",")}`;

  const scope =
    staged !== null && staged.from === applied
      ? staged
      : { from: applied, day: appliedDay, leagueIds: appliedLeagueIds };

  const stageDay = useCallback(
    (day: string) => {
      setStaged({ from: applied, day, leagueIds: scope.leagueIds });
    },
    [applied, scope.leagueIds],
  );

  const stageLeagues = useCallback(
    (leagueIds: number[]) => {
      setStaged({ from: applied, day: scope.day, leagueIds });
    },
    [applied, scope.day],
  );

  const apply = useCallback(() => {
    const next = new URLSearchParams(searchParams);

    next.set(FIXTURE_DATE_PARAMETER, scope.day);

    next.delete(FIXTURE_LEAGUE_PARAMETER);

    for (const leagueId of scope.leagueIds) {
      next.append(FIXTURE_LEAGUE_PARAMETER, String(leagueId));
    }

    startTransition(() => {
      router.push(`?${next.toString()}`, { scroll: false });
    });
  }, [router, scope.day, scope.leagueIds, searchParams]);

  const appliedIdentifiers = new Set(appliedLeagueIds);

  const isApplied =
    scope.day === appliedDay &&
    scope.leagueIds.length === appliedIdentifiers.size &&
    scope.leagueIds.every((one) => appliedIdentifiers.has(one));

  return (
    <div className="flex flex-col gap-3 @xl:flex-row @xl:items-center">
      <FixturesDatePicker onChange={stageDay} value={scope.day} />

      <LeagueSelect
        leagues={leagues}
        onChange={stageLeagues}
        value={scope.leagueIds}
      />

      <Button
        aria-busy={isPending}
        className="w-full @xl:w-auto"
        disabled={isApplied || isPending}
        onClick={apply}
        type="button"
      >
        {isPending ? <ButtonSpinner /> : <ListFilter />}
        {APPLY_LABEL}
      </Button>
    </div>
  );
}
