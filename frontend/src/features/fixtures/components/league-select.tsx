"use client";

import { useCallback } from "react";

import Image from "next/image";

import { Globe } from "lucide-react";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { League } from "@/features/fixtures/types/league";

const ALL_COMPETITIONS_VALUE = "all";

const ALL_COMPETITIONS_LABEL = "All competitions";

const COMPETITION_LABEL = "Competition";

const FLAG_WIDTH = 20;

const FLAG_HEIGHT = 14;

/**
 * Props of {@link LeagueLabel}.
 */
interface LeagueLabelProps {
  /** Competition to label. */
  readonly league: League;
}

/**
 * Renders the label of the option that clears the competition filter.
 *
 * @remarks
 * The globe stands where a country flag stands on every other option, so the
 * list reads as one column of marks rather than one indented item among five
 * aligned ones. It is decorative for the same reason the flags are: the label
 * beside it already says what it means.
 *
 * @returns The clear-filter label.
 */
function AllCompetitionsLabel() {
  return (
    <>
      <Globe aria-hidden className="h-3.5 w-5 shrink-0 text-muted-foreground" />

      {ALL_COMPETITIONS_LABEL}
    </>
  );
}

/**
 * Renders a competition as its country flag followed by its name.
 *
 * @remarks
 * The flag carries an empty `alt` on purpose. It repeats what the name beside
 * it already says, so announcing the country twice would be noise; the name is
 * the accessible content. A competition with no published flag simply renders
 * its name, rather than an empty `src` that would request a broken image.
 *
 * @returns The competition label.
 */
function LeagueLabel({ league }: LeagueLabelProps) {
  return (
    <>
      {league.countryFlagUrl !== "" && (
        <Image
          alt=""
          className="h-3.5 w-5 shrink-0 rounded-[2px] object-cover"
          height={FLAG_HEIGHT}
          src={league.countryFlagUrl}
          width={FLAG_WIDTH}
        />
      )}

      {league.name}
    </>
  );
}

/**
 * Props of {@link LeagueSelect}.
 */
export interface LeagueSelectProps {
  /** Competitions the platform covers, already ordered by name. */
  readonly leagues: readonly League[];

  /** Competition currently staged, or `null` for all of them. */
  readonly value: number | null;

  /** Called with the newly staged competition, or `null` to clear the filter. */
  readonly onChange: (leagueId: number | null) => void;
}

/**
 * Renders the competition picker of the fixture filters.
 *
 * @remarks
 * Choosing a competition stages it and nothing else. The control neither reads
 * the URL nor navigates: {@link FixtureFilters} owns the staged scope and
 * applies it. That separation is the point rather than tidiness — while a
 * navigation is in flight React holds the previous tree on screen, and a list
 * that closed on the same click could be caught in that window and painted open
 * again. With the navigation moved to a button, nothing is animating when it
 * starts.
 *
 * The clear option carries the sentinel value `all` rather than an empty
 * string, because the underlying primitive reserves the empty string for "no
 * selection" and an item declaring it would never become selectable.
 *
 * The trigger is given its own children rather than left to mirror the selected
 * option. The primitive unmounts its option list while closed, so there is no
 * option text to mirror until the visitor opens the control, and the trigger
 * would otherwise render empty on arrival. Supplying the children also tells
 * the primitive to stop portalling the option text in, so the label is not
 * rendered twice once the list has been opened.
 *
 * The list is positioned below the trigger and pinned to its width. The
 * primitive's default aligns the selected option over the trigger instead,
 * which overlaps the control it belongs to and leaves the list free to size
 * itself to its widest option. That default also suppresses the open
 * animation, which is a second reason to leave it.
 *
 * @returns The competition picker.
 */
export function LeagueSelect({ leagues, value, onChange }: LeagueSelectProps) {
  const handleValueChange = useCallback(
    (chosen: string) => {
      onChange(chosen === ALL_COMPETITIONS_VALUE ? null : Number(chosen));
    },
    [onChange],
  );

  const selectedLeague = leagues.find((league) => league.id === value);

  return (
    <Select
      value={
        selectedLeague === undefined
          ? ALL_COMPETITIONS_VALUE
          : String(selectedLeague.id)
      }
      onValueChange={handleValueChange}
      disabled={leagues.length === 0}
    >
      <SelectTrigger aria-label={COMPETITION_LABEL} className="w-full @xl:w-56">
        <SelectValue>
          {selectedLeague === undefined ? (
            <AllCompetitionsLabel />
          ) : (
            <LeagueLabel league={selectedLeague} />
          )}
        </SelectValue>
      </SelectTrigger>

      <SelectContent
        className="w-(--radix-select-trigger-width)"
        position="popper"
      >
        <SelectItem value={ALL_COMPETITIONS_VALUE}>
          <AllCompetitionsLabel />
        </SelectItem>

        {leagues.map((league) => (
          <SelectItem key={league.id} value={String(league.id)}>
            <LeagueLabel league={league} />
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
