"use client";

import { useCallback } from "react";

import Image from "next/image";
import { useRouter, useSearchParams } from "next/navigation";

import { Globe } from "lucide-react";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { FIXTURE_LEAGUE_PARAMETER } from "@/features/fixtures/domain/fixture-search-params";
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

  /** Competition the fixture list is filtered to, or `null` for all of them. */
  readonly selectedLeagueId: number | null;
}

/**
 * Renders the competition filter that scopes the fixture list.
 *
 * @remarks
 * The clear option carries the sentinel value `all` rather than an empty
 * string, because the underlying primitive reserves the empty string for "no
 * selection" and an item declaring it would never become selectable. Choosing
 * it removes the parameter instead of writing a value, so an unfiltered list
 * has one address rather than two.
 *
 * The trigger is given its own children rather than left to mirror the selected
 * option. The primitive unmounts its option list while closed, so there is no
 * option text to mirror until the visitor opens the control, and the trigger
 * would otherwise render empty on arrival. Supplying the children also tells
 * the primitive to stop portalling the option text in, so the label is not
 * rendered twice once the list has been opened.
 *
 * The existing query is copied before `league` is replaced, so changing
 * competition keeps the chosen day.
 *
 * @returns The competition filter.
 */
export function LeagueSelect({ leagues, selectedLeagueId }: LeagueSelectProps) {
  const router = useRouter();
  const searchParams = useSearchParams();

  const handleValueChange = useCallback(
    (value: string) => {
      const next = new URLSearchParams(searchParams);

      if (value === ALL_COMPETITIONS_VALUE) {
        next.delete(FIXTURE_LEAGUE_PARAMETER);
      } else {
        next.set(FIXTURE_LEAGUE_PARAMETER, value);
      }

      router.push(`?${next.toString()}`, { scroll: false });
    },
    [router, searchParams],
  );

  const selectedLeague = leagues.find(
    (league) => league.id === selectedLeagueId,
  );

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
      <SelectTrigger aria-label={COMPETITION_LABEL} className="w-full sm:w-60">
        <SelectValue>
          {selectedLeague === undefined ? (
            <AllCompetitionsLabel />
          ) : (
            <LeagueLabel league={selectedLeague} />
          )}
        </SelectValue>
      </SelectTrigger>

      <SelectContent>
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
