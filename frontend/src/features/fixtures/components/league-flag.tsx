import Image from "next/image";

import type { League } from "@/features/fixtures/types/league";
import { cn } from "@/lib/utils";

const FLAG_WIDTH = 24;

const FLAG_HEIGHT = 17;

/**
 * Props of {@link LeagueFlag}.
 */
export interface LeagueFlagProps {
  /** Competition whose country flag is shown. */
  readonly league: League;

  /** Utility classes sizing the chip; it is 20 by 14 pixels by default. */
  readonly className?: string;
}

/**
 * Renders the country flag of a competition as a uniform chip.
 *
 * @remarks
 * Shared by the filter and the group headings so the treatment is defined once,
 * because getting a set of flags to read as a set takes more than a fixed box.
 *
 * The ring is the part that does the work. Germany and Spain reach their own
 * edges, but France, Italy and England carry white at or near theirs, so on a
 * light surface they lose their boundary and read as two bars or a floating
 * cross beside neighbours that look solid. A hairline edge gives every flag the
 * same silhouette whatever it contains.
 *
 * The provider publishes two aspect ratios, 5:3 and 3:2, so `object-cover`
 * trims each to the same box rather than letting the heights disagree. It trims
 * a little more from the wider ones, which is invisible on a horizontal
 * tricolour and is the price of a set that lines up.
 *
 * The flag carries an empty `alt` on purpose. Wherever it appears the
 * competition name is beside it, so announcing the country would be noise. A
 * competition with no published flag renders nothing rather than an empty `src`
 * that would request a broken image.
 *
 * @returns The flag chip, or nothing.
 */
export function LeagueFlag({ league, className }: LeagueFlagProps) {
  if (league.countryFlagUrl === "") {
    return null;
  }

  return (
    <Image
      alt=""
      className={cn(
        "h-3.5 w-5 shrink-0 rounded-[2px] object-cover ring-1 ring-foreground/25 ring-inset",
        className,
      )}
      height={FLAG_HEIGHT}
      src={league.countryFlagUrl}
      width={FLAG_WIDTH}
    />
  );
}
