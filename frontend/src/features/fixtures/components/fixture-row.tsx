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
 * @returns The crest, or its placeholder.
 */
function TeamCrest({ team }: TeamCrestProps) {
  if (team.crestUrl === "") {
    return (
      <span
        aria-hidden="true"
        className="size-6 shrink-0 rounded-full bg-muted"
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
 * Renders a club name, abbreviated on a narrow viewport.
 *
 * @remarks
 * Both forms are in the markup and one of them is hidden, because the choice
 * depends on the viewport and the server cannot know it. Only the visible form
 * is announced, since a screen reader honours `display: none`.
 *
 * A club with no published abbreviation falls back to its full name rather than
 * to an empty cell.
 *
 * @returns The club name in both widths.
 */
function TeamName({ team, className }: TeamNameProps) {
  return (
    <>
      <span className={cn("truncate font-medium sm:hidden", className)}>
        {team.shortCode === "" ? team.name : team.shortCode}
      </span>

      <span className={cn("hidden truncate font-medium sm:inline", className)}>
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
 * Renders one match: both sides, the kick-off time and the competition.
 *
 * @remarks
 * The kick-off is formatted in UTC on the server, and the surrounding toolbar
 * says so. This is a deliberate trade rather than an omission. The visitor's
 * timezone is not knowable while rendering on the server, so the alternatives
 * are to guess one, which is wrong for most visitors and silently so, or to
 * render a placeholder and correct it after hydration, which flashes the wrong
 * time and produces a server/client mismatch on every fixture in the list. One
 * stated timezone that every visitor reads the same way is the honest option,
 * and it also keeps the row renderable on the server.
 *
 * @returns The match row.
 */
export function FixtureRow({ fixture }: FixtureRowProps) {
  return (
    <li className="flex items-center gap-3 px-4 py-3 sm:gap-4">
      <time
        className="w-12 shrink-0 font-mono text-sm text-muted-foreground tabular-nums"
        dateTime={fixture.kickoffAt.toISOString()}
      >
        {KICKOFF_TIME_FORMAT.format(fixture.kickoffAt)}
      </time>

      <div className="flex min-w-0 flex-1 items-center gap-2 sm:gap-3">
        <div className="flex min-w-0 flex-1 items-center justify-end gap-2">
          <TeamName className="text-right" team={fixture.homeTeam} />
          <TeamCrest team={fixture.homeTeam} />
        </div>

        <span className="shrink-0 font-mono text-[0.7rem] tracking-[0.12em] text-muted-foreground uppercase">
          vs
        </span>

        <div className="flex min-w-0 flex-1 items-center gap-2">
          <TeamCrest team={fixture.awayTeam} />
          <TeamName team={fixture.awayTeam} />
        </div>
      </div>

      <span className="hidden shrink-0 text-xs text-muted-foreground sm:inline">
        {fixture.league.name}
      </span>

      <span className="shrink-0 font-mono text-[0.7rem] tracking-[0.12em] text-muted-foreground uppercase sm:hidden">
        {fixture.league.shortCode === ""
          ? fixture.league.name
          : fixture.league.shortCode}
      </span>
    </li>
  );
}
