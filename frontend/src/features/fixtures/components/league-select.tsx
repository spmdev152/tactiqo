"use client";

import { useCallback } from "react";

import { ChevronDown, Globe } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { LeagueFlag } from "@/features/fixtures/components/league-flag";
import type { League } from "@/features/fixtures/types/league";

const ALL_COMPETITIONS_LABEL = "All competitions";

const COMPETITION_LABEL = "Competitions";

const SUMMARISED_FLAG_LIMIT = 3;

/**
 * Props of {@link TriggerLabel}.
 */
interface TriggerLabelProps {
  /** Competitions currently staged, in the order they are offered. */
  readonly selected: readonly League[];
}

/**
 * Renders what the trigger says about the current selection.
 *
 * @remarks
 * Three states, because a list of names does not survive a 14rem control. None
 * chosen is the unfiltered day and says so with a globe. One chosen is worth
 * naming. Several are summarised as a count behind their flags, capped so the
 * trigger cannot grow past its neighbour: five flags and a count overflow it,
 * three and a count do not.
 *
 * @returns The trigger contents.
 */
function TriggerLabel({ selected }: TriggerLabelProps) {
  if (selected.length === 0) {
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

  const [only] = selected;

  if (selected.length === 1 && only !== undefined) {
    return (
      <>
        <LeagueFlag league={only} />
        <span className="truncate">{only.name}</span>
      </>
    );
  }

  return (
    <>
      <span aria-hidden className="flex shrink-0 items-center gap-1">
        {selected.slice(0, SUMMARISED_FLAG_LIMIT).map((league) => (
          <LeagueFlag key={league.id} league={league} />
        ))}
      </span>
      {selected.length} competitions
    </>
  );
}

/**
 * Props of {@link LeagueSelect}.
 */
export interface LeagueSelectProps {
  /** Competitions the platform covers, already ordered by name. */
  readonly leagues: readonly League[];

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
 * The trigger widens against the page container rather than the viewport, so it
 * matches the day picker beside it whatever the sidebar is doing.
 *
 * @returns The competition picker.
 */
export function LeagueSelect({ leagues, value, onChange }: LeagueSelectProps) {
  const staged = new Set(value);

  const selected = leagues.filter((league) => staged.has(league.id));

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

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          aria-label={COMPETITION_LABEL}
          className="w-full justify-start font-normal @xl:w-56"
          disabled={leagues.length === 0}
          variant="outline"
        >
          <TriggerLabel selected={selected} />

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

        {leagues.map((league) => (
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
