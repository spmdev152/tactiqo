import Image from "next/image";

import { ChevronDown } from "lucide-react";

import { FixtureDisclosure } from "@/features/fixtures/components/fixture-disclosure";
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
 * Props of {@link FixtureRowContent}.
 */
interface FixtureRowContentProps {
  /** Match whose cells are rendered. */
  readonly fixture: Fixture;
}

/**
 * Renders the cells of one match: both sides, the kick-off time and the result
 * once there is one.
 *
 * @remarks
 * Built entirely from phrasing content, `span` and `time` rather than `div`,
 * because every row renders these cells inside the `button` that opens its
 * panel and a `button` may not contain a `div`. The layout is unaffected — a
 * `span` carrying `flex` is a flex container like any other.
 *
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
 * The trailing chevron rotates from the state of the control it sits inside
 * rather than from a prop, which is what lets these cells stay server-rendered:
 * the class matches the `group/fixture-row` that {@link FixtureDisclosure}
 * declares on its button, and reads that button's own `aria-expanded`. It
 * animates `rotate` and not `transform`, because that is the property Tailwind
 * writes for `rotate-180` and a transition naming the other one would leave the
 * chevron snapping.
 *
 * @returns The cells of the match row.
 */
function FixtureRowContent({ fixture }: FixtureRowContentProps) {
  const result = fixture.status === "finished" ? fixture.score : null;

  return (
    <span className="flex w-full items-center gap-3 px-4 py-3 @lg:gap-4">
      <time
        className="w-12 shrink-0 font-mono text-sm text-muted-foreground tabular-nums"
        dateTime={fixture.kickoffAt.toISOString()}
      >
        {KICKOFF_TIME_FORMAT.format(fixture.kickoffAt)}
      </time>

      <span className="flex min-w-0 flex-1 items-center gap-2 @lg:gap-3">
        <span className="flex min-w-0 flex-1 items-center justify-end gap-2">
          <TeamName className="text-right" team={fixture.homeTeam} />
          <TeamCrest team={fixture.homeTeam} />
        </span>

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

        <span className="flex min-w-0 flex-1 items-center gap-2">
          <TeamCrest team={fixture.awayTeam} />
          <TeamName team={fixture.awayTeam} />
        </span>
      </span>

      <ChevronDown
        aria-hidden="true"
        className="size-4 shrink-0 text-muted-foreground transition-[rotate] group-aria-expanded/fixture-row:rotate-180"
      />
    </span>
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
 * Renders one match, and the panel of insights behind it.
 *
 * @remarks
 * One shape for every row. The row used to have two, offering the toggle only
 * where the platform held probabilities, on the argument that a chevron pointing
 * at an empty drawer is worse than no chevron. That argument was right while
 * probabilities were the only thing behind the toggle and is wrong now: form is
 * drawn from matches already played, so it exists for nearly every fixture the
 * list can show — including every fixture too far out for a model to have run on,
 * which is exactly the set the old branch removed the control from. What
 * `hasPredictions` decides now is which tab opens first, and
 * {@link FixtureDisclosure} owns that.
 *
 * Collapsing the two shapes also removes the reserved cell the trailing chevron
 * used to need. Every row now draws a real one, so there is no longer a mix of
 * rows with and without it to keep on the same grid.
 *
 * The `li` is the unit the list divides on, which is why the row and its panel
 * are nested inside one rather than being two siblings. `FixtureGroupSection`
 * separates its children with `divide-y`, so a panel of its own would be given a
 * rule above it and the list would read as separating a match from its own
 * insights instead of one match from the next.
 *
 * The `li` itself carries no layout. The cells own their spacing, so the row is
 * laid out identically whether it sits directly in the list item or inside the
 * button that expands it, and the skeleton has one shape to mirror rather than
 * two.
 *
 * @returns The match row and its disclosure.
 */
export function FixtureRow({ fixture }: FixtureRowProps) {
  return (
    <li>
      <FixtureDisclosure fixture={fixture}>
        <FixtureRowContent fixture={fixture} />
      </FixtureDisclosure>
    </li>
  );
}
