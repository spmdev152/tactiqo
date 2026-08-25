import Image from "next/image";

import type { Fixture, FixtureTeam } from "@/features/fixtures/types/fixture";
import { cn } from "@/lib/utils";

const CREST_SIZE = 24;

const KICKOFF_TIME_FORMAT = new Intl.DateTimeFormat("en-GB", {
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
  timeZone: "UTC",
});

/**
 * Props of {@link TeamCrest}.
 */
interface TeamCrestProps {
  /** Team whose crest is shown. */
  readonly team: FixtureTeam;
}

/**
 * Renders a club crest, or a neutral placeholder when none is published.
 *
 * @remarks
 * An empty URL is a normal answer from the provider, not an error, so the
 * placeholder is a plain shape rather than a fallback image: passing an empty
 * `src` to `next/image` would produce a broken image and a request to the
 * application's own optimizer for nothing.
 *
 * The placeholder names itself with `data-slot`, as the registry primitives do,
 * so the branch is identifiable by what it is rather than by the utility class
 * that happens to paint it.
 *
 * @returns The crest, or its placeholder.
 */
function TeamCrest({ team }: TeamCrestProps) {
  if (team.crestUrl === "") {
    return (
      <span
        aria-hidden="true"
        className="size-6 shrink-0 rounded-full bg-muted"
        data-slot="crest-placeholder"
      />
    );
  }

  return (
    <Image
      alt=""
      className="size-6 shrink-0 object-contain"
      height={CREST_SIZE}
      src={team.crestUrl}
      width={CREST_SIZE}
    />
  );
}

/**
 * Props of {@link TeamName}.
 */
interface TeamNameProps {
  /** Team whose name is shown. */
  readonly team: FixtureTeam;

  /** Utility classes aligning the name within its side of the row. */
  readonly className?: string;
}

/**
 * Renders a club name, abbreviated in a narrow row.
 *
 * @remarks
 * Both forms are in the markup and one of them is hidden, because the choice
 * depends on the width of the list and the server cannot know it.
 *
 * A screen reader honours `display: none`, so announcing whichever form is
 * visible would announce an abbreviation below the `@lg` width — a row read as
 * "11:30, LIV, 2 - 1, NFO". Both visual forms are therefore hidden from the
 * accessibility tree and the full name is announced from a third, visually
 * hidden copy, so the announcement does not depend on the width at all. A
 * `span` has role `generic`, which cannot take `aria-label`, so the copy is a
 * node rather than an attribute.
 *
 * A club with no published abbreviation falls back to its full name rather than
 * to an empty cell.
 *
 * @returns The club name in both widths, and once for a screen reader.
 */
function TeamName({ team, className }: TeamNameProps) {
  return (
    <>
      <span className="sr-only">{team.name}</span>

      <span
        aria-hidden="true"
        className={cn("truncate font-medium @lg:hidden", className)}
      >
        {team.shortCode === "" ? team.name : team.shortCode}
      </span>

      <span
        aria-hidden="true"
        className={cn("hidden truncate font-medium @lg:inline", className)}
      >
        {team.name}
      </span>
    </>
  );
}

/**
 * Props of {@link FixtureRow}.
 */
export interface FixtureRowProps {
  /** Match to render. */
  readonly fixture: Fixture;
}

/**
 * Renders one match: both sides, the kick-off time and the result once there is
 * one.
 *
 * @remarks
 * The kick-off is formatted in UTC on the server. The visitor's timezone is not
 * knowable while rendering there, so the alternatives are to guess one, which is
 * wrong for most visitors and silently so, or to render a placeholder and
 * correct it after hydration, which flashes the wrong time and mismatches on
 * every row of the list. One timezone every visitor reads the same way is the
 * honest option, and it keeps the row renderable on the server.
 *
 * The zone is no longer written beside the list, so the only statement of it is
 * the machine-readable `dateTime` each row carries. Resolving it properly needs
 * the visitor's own zone, which needs a stored preference and a product
 * decision; until then the displayed time is UTC and unlabelled.
 *
 * The widths respond to the page container rather than to the viewport,
 * because the sidebar takes 16rem of the window when it is expanded and the row
 * therefore has less space than the window suggests.
 *
 * The kick-off is the only fixed-width cell, and the two sides split the rest
 * evenly, so the marker between them lands on the same pixel column in every
 * row of the list.
 *
 * That marker carries the result of a match that has been played and `vs`
 * otherwise, which is why it has a floor on its width: a group holding both
 * kinds would otherwise put its centre column in two places. The floor fits a
 * single-digit score, and a freak double-digit one widens its own row rather
 * than being clipped.
 *
 * The marker is announced from a visually hidden sibling rather than read as
 * written. `vs` depends on `text-transform` to look like an abbreviation and
 * the score's separator is a hyphen-minus, which assistive technology
 * verbalizes inconsistently or drops, so a screen reader is given the words
 * instead and the visible glyphs are hidden from it.
 *
 * A score shows only for a finished match, even though a match under way can
 * carry one. The platform synchronizes every few hours, so a score read mid-match
 * is stale by the time anybody sees it, and a stale score presented as a result
 * is worse than no score at all.
 *
 * The competition is no longer named on the row. The heading above the group
 * says it once for every match under it, and repeating it cost the widest
 * column in the row for a fact that no longer varies within a group.
 *
 * @returns The match row.
 */
export function FixtureRow({ fixture }: FixtureRowProps) {
  const result = fixture.status === "finished" ? fixture.score : null;

  return (
    <li className="flex items-center gap-3 px-4 py-3 @lg:gap-4">
      <time
        className="w-12 shrink-0 font-mono text-sm text-muted-foreground tabular-nums"
        dateTime={fixture.kickoffAt.toISOString()}
      >
        {KICKOFF_TIME_FORMAT.format(fixture.kickoffAt)}
      </time>

      <div className="flex min-w-0 flex-1 items-center gap-2 @lg:gap-3">
        <div className="flex min-w-0 flex-1 items-center justify-end gap-2">
          <TeamName className="text-right" team={fixture.homeTeam} />
          <TeamCrest team={fixture.homeTeam} />
        </div>

        <span className="sr-only">
          {result === null ? "versus" : `${result.home} to ${result.away}`}
        </span>

        <span
          aria-hidden="true"
          className={cn(
            "min-w-11 shrink-0 text-center font-mono",
            result === null
              ? "text-[0.7rem] tracking-[0.12em] text-muted-foreground uppercase"
              : "text-sm font-medium tabular-nums",
          )}
        >
          {result === null ? "vs" : `${result.home} - ${result.away}`}
        </span>

        <div className="flex min-w-0 flex-1 items-center gap-2">
          <TeamCrest team={fixture.awayTeam} />
          <TeamName team={fixture.awayTeam} />
        </div>
      </div>
    </li>
  );
}
