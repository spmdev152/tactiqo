"use client";

import { Suspense, use, useCallback, useState, useTransition } from "react";

import { useRouter, useSearchParams } from "next/navigation";

import { ListFilter } from "lucide-react";

import { ButtonSpinner } from "@/components/button-spinner";
import { Button } from "@/components/ui/button";
import { FixturesDatePicker } from "@/features/fixtures/components/fixtures-date-picker";
import { LeagueSelect } from "@/features/fixtures/components/league-select";
import {
  FIXTURE_DATE_PARAMETER,
  FIXTURE_LEAGUE_PARAMETER,
  fixtureScopeKey,
} from "@/features/fixtures/domain/fixture-search-params";
import type { LeaguesResult } from "@/features/fixtures/types/league";

const APPLY_LABEL = "Filter";

/**
 * Scope the visitor has staged but not yet applied.
 */
interface StagedScope {
  /** Staged UTC calendar day, as `YYYY-MM-DD`. */
  readonly day: string;

  /** Staged competitions, empty for all of them. */
  readonly leagueIds: readonly number[];
}

/**
 * Props of {@link ReadLeagueSelect}.
 */
interface ReadLeagueSelectProps {
  /** Competitions the platform covers, as the route started reading them. */
  readonly leagues: Promise<LeaguesResult>;

  /** Competitions currently staged, empty for all of them. */
  readonly value: readonly number[];

  /** Called with the newly staged competitions, empty to clear the filter. */
  readonly onChange: (leagueIds: number[]) => void;
}

/**
 * Renders the competition picker once the competitions have been read.
 *
 * @remarks
 * The read is unwrapped one level below the bar rather than in it, so only the
 * picker waits for it. The day and the competitions are already in the URL, so
 * the day picker and the apply button owe the API nothing and must not be held
 * behind a round trip; suspending the whole bar would have replaced two correct
 * controls with a placeholder.
 *
 * @returns The competition picker.
 */
function ReadLeagueSelect({ leagues, value, onChange }: ReadLeagueSelectProps) {
  return (
    <LeagueSelect leagues={use(leagues)} onChange={onChange} value={value} />
  );
}

/**
 * Props of {@link FixtureFilters}.
 */
export interface FixtureFiltersProps {
  /**
   * Competitions the platform covers, or the reason they are unavailable, as
   * the route started reading them.
   */
  readonly leagues: Promise<LeaguesResult>;

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
 * stale.
 *
 * It is discarded whenever the applied scope changes, by comparing this render's
 * canonical scope key against the last one's. The comparison has to be of the
 * change, not of the value: an earlier version recorded the scope a staging was
 * made against and kept it while that scope still matched, which meant returning
 * to a scope the visitor had once staged from resurrected the staging. Choosing a
 * day and a competition, applying them, then following the sidebar back to the
 * unfiltered page left the controls showing the abandoned choice over a list that
 * no longer matched it.
 *
 * The same key decides whether there is anything to apply, and it is built by
 * the domain rather than here, because the route keys its `Suspense` boundary
 * with it and the two have to agree to the byte.
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

  const applied = fixtureScopeKey(appliedDay, appliedLeagueIds);

  const [lastApplied, setLastApplied] = useState(applied);

  if (lastApplied !== applied) {
    setLastApplied(applied);
    setStaged(null);
  }

  const scope = staged ?? { day: appliedDay, leagueIds: appliedLeagueIds };

  const stageDay = useCallback(
    (day: string) => {
      setStaged({ day, leagueIds: scope.leagueIds });
    },
    [scope.leagueIds],
  );

  const stageLeagues = useCallback(
    (leagueIds: number[]) => {
      setStaged({ day: scope.day, leagueIds });
    },
    [scope.day],
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

  const isApplied = fixtureScopeKey(scope.day, scope.leagueIds) === applied;

  return (
    <div className="flex flex-col gap-3 @xl:flex-row @xl:items-center">
      <FixturesDatePicker onChange={stageDay} value={scope.day} />

      <Suspense
        fallback={
          <LeagueSelect
            leagues={null}
            onChange={stageLeagues}
            value={scope.leagueIds}
          />
        }
      >
        <ReadLeagueSelect
          leagues={leagues}
          onChange={stageLeagues}
          value={scope.leagueIds}
        />
      </Suspense>

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
