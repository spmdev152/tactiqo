"use client";

import { useCallback } from "react";

import { ChevronDown, Globe, TriangleAlert } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import { LeagueFlag } from "@/features/fixtures/components/league-flag";
import type { League, LeaguesResult } from "@/features/fixtures/types/league";

const ALL_COMPETITIONS_LABEL = "All competitions";

const COMPETITION_LABEL = "Competitions";

const UNAVAILABLE_LABEL = "Competitions unavailable";

const UNCOVERED_LABEL = "No competitions covered";

const UNCOVERED_DETAIL = "The platform lists no competition to filter by.";

const SUMMARISED_FLAG_LIMIT = 3;

/**
 * States a number of competitions in words the trigger can hold.
 *
 * @param count - Competitions staged in the filter.
 * @returns The count with its noun, in the right number.
 */
function statedCount(count: number): string {
  return count === 1 ? "1 competition" : `${count} competitions`;
}

/**
 * Props of {@link TriggerLabel}.
 */
interface TriggerLabelProps {
  /** Competitions staged in the filter, named or not. */
  readonly stagedCount: number;

  /** Staged competitions the platform named, in the order they are offered. */
  readonly named: readonly League[];
}

/**
 * Renders what the trigger says about the current selection.
 *
 * @remarks
 * Three states, because a list of names does not survive a 14rem control. None
 * staged is the unfiltered day and says so with a globe. One staged is worth
 * naming. Several are summarised as a count behind their flags, capped so the
 * trigger cannot grow past its neighbour: five flags and a count overflow it,
 * three and a count do not.
 *
 * The count comes from what is staged rather than from what could be named, so
 * an identifier the platform does not know still counts. A URL carrying
 * `league=999` used to intersect to nothing and read "all competitions" over a
 * list filtered to nothing; it now reads as one staged competition, which
 * disagrees with the empty list visibly instead of silently.
 *
 * @returns The trigger contents.
 */
function TriggerLabel({ stagedCount, named }: TriggerLabelProps) {
  if (stagedCount === 0) {
    return (
      <>
        <Globe
          aria-hidden
          className="h-3.5 w-5 shrink-0 text-muted-foreground"
        />

        {ALL_COMPETITIONS_LABEL}
      </>
    );
  }

  const [only] = named;

  if (stagedCount === 1 && only !== undefined) {
    return (
      <>
        <LeagueFlag league={only} />

        <span className="truncate">{only.name}</span>
      </>
    );
  }

  return (
    <>
      {named.length > 0 && (
        <span aria-hidden className="flex shrink-0 items-center gap-1">
          {named.slice(0, SUMMARISED_FLAG_LIMIT).map((league) => (
            <LeagueFlag key={league.id} league={league} />
          ))}
        </span>
      )}

      {statedCount(stagedCount)}
    </>
  );
}

/**
 * Props of {@link LeagueSelectNotice}.
 */
interface LeagueSelectNoticeProps {
  /** What is wrong, in the visitor's terms. */
  readonly label: string;

  /** Why it is wrong, as the platform reported it. */
  readonly detail: string;
}

/**
 * Renders, in the picker's place, why there is nothing to pick from.
 *
 * @remarks
 * Static text rather than a disabled trigger. A trigger that reads "all
 * competitions" and refuses to open says nothing about why, offers no tooltip
 * and cannot be focused, so a keyboard or screen-reader visitor met a control
 * that was simply inert. Text in the same slot is in the reading order and needs
 * no focus to reach.
 *
 * It is deliberately not a live region. It arrives with the competitions
 * themselves, so a region and its content would be created in the same commit
 * and announce nothing; the fixture list has the one live region on this page,
 * and it lives above its own boundary for exactly that reason.
 *
 * @returns The stated unavailable state.
 */
function LeagueSelectNotice({ label, detail }: LeagueSelectNoticeProps) {
  return (
    <p className="flex w-full flex-col gap-0.5 rounded-lg border border-dashed border-destructive/40 px-2.5 py-1.5 text-sm @xl:w-56">
      <span className="flex items-center gap-1.5 font-medium">
        <TriangleAlert
          aria-hidden
          className="size-3.5 shrink-0 text-destructive"
        />

        {label}
      </span>

      <span className="text-xs text-muted-foreground">{detail}</span>
    </p>
  );
}

/**
 * Props of {@link LeagueSelect}.
 */
export interface LeagueSelectProps {
  /**
   * Competitions the platform covers, or the reason they are unavailable;
   * `null` while they are still being read.
   */
  readonly leagues: LeaguesResult | null;

  /** Competitions currently staged, empty for all of them. */
  readonly value: readonly number[];

  /** Called with the newly staged competitions, empty to clear the filter. */
  readonly onChange: (leagueIds: number[]) => void;
}

/**
 * Renders the competition picker of the fixture filters.
 *
 * @remarks
 * Choosing competitions stages them and nothing else. The control neither reads
 * the URL nor navigates: {@link FixtureFilters} owns the staged scope and
 * applies it. That separation is the point rather than tidiness — while a
 * navigation is in flight React holds the previous tree on screen, and a list
 * that closed on the same click could be caught in that window and painted open
 * again. With the navigation moved to a button, nothing is animating when it
 * starts.
 *
 * It is a menu of checkboxes rather than a select, because a select carries one
 * value and this filter carries several. The menu also stays open across a
 * click, which is what makes choosing three competitions three clicks instead
 * of three round trips through the trigger.
 *
 * The clear entry is a checkbox rather than a command, so the menu reads as one
 * column of states: it is the one that is ticked while nothing else is, and
 * ticking it empties the rest. Emptying is spelled as the empty list, so
 * "every competition" has one representation everywhere.
 *
 * Four outcomes, and none of them is an inert control. The competitions are
 * still in flight, and the slot holds a placeholder of the control's own shape;
 * they could not be read, or the platform covers none, and the slot states which
 * of the two it was; otherwise the picker is offered.
 *
 * The label is inside the trigger as a hidden prefix rather than on it as an
 * `aria-label`. A name attribute wins over the contents it sits on, so the
 * button announced "competitions" and withheld the one thing it exists to state,
 * which competitions are staged. Composed from the contents, the name carries
 * both.
 *
 * The trigger widens against the page container rather than the viewport, so it
 * matches the day picker beside it whatever the sidebar is doing.
 *
 * @returns The competition picker, its placeholder, or why there is none.
 */
export function LeagueSelect({ leagues, value, onChange }: LeagueSelectProps) {
  const toggle = useCallback(
    (leagueId: number) => {
      onChange(
        value.includes(leagueId)
          ? value.filter((one) => one !== leagueId)
          : [...value, leagueId],
      );
    },
    [onChange, value],
  );

  const clear = useCallback(() => {
    onChange([]);
  }, [onChange]);

  if (leagues === null) {
    return (
      <div
        aria-hidden="true"
        className="flex h-8 w-full items-center gap-1.5 rounded-lg border border-border px-2.5 @xl:w-56"
      >
        <Skeleton className="h-3.5 w-5 shrink-0 rounded-[2px]" />

        <Skeleton className="h-4 w-28" />
      </div>
    );
  }

  if (!leagues.loaded) {
    return (
      <LeagueSelectNotice detail={leagues.reason} label={UNAVAILABLE_LABEL} />
    );
  }

  if (leagues.leagues.length === 0) {
    return (
      <LeagueSelectNotice detail={UNCOVERED_DETAIL} label={UNCOVERED_LABEL} />
    );
  }

  const staged = new Set(value);

  const named = leagues.leagues.filter((league) => staged.has(league.id));

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          className="w-full justify-start font-normal @xl:w-56"
          variant="outline"
        >
          <span className="sr-only">{COMPETITION_LABEL}</span>

          <TriggerLabel named={named} stagedCount={value.length} />

          <ChevronDown aria-hidden className="ml-auto size-4 opacity-50" />
        </Button>
      </DropdownMenuTrigger>

      <DropdownMenuContent
        align="start"
        className="w-(--radix-dropdown-menu-trigger-width)"
      >
        <DropdownMenuCheckboxItem
          checked={value.length === 0}
          onSelect={(event) => {
            event.preventDefault();
            clear();
          }}
        >
          <Globe
            aria-hidden
            className="h-3.5 w-5 shrink-0 text-muted-foreground"
          />

          {ALL_COMPETITIONS_LABEL}
        </DropdownMenuCheckboxItem>

        <DropdownMenuSeparator />

        {leagues.leagues.map((league) => (
          <DropdownMenuCheckboxItem
            checked={staged.has(league.id)}
            key={league.id}
            onSelect={(event) => {
              event.preventDefault();
              toggle(league.id);
            }}
          >
            <LeagueFlag league={league} />

            {league.name}
          </DropdownMenuCheckboxItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
