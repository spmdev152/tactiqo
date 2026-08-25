"use client";

import { useCallback, useState, useTransition } from "react";

import { useRouter, useSearchParams } from "next/navigation";

import { CalendarDays } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  FIXTURE_DATE_PARAMETER,
  localDateToUtcDay,
  utcDayToLocalDate,
} from "@/features/fixtures/domain/fixture-search-params";

const TRIGGER_LABEL = "Match day";

const TRIGGER_DAY_FORMAT = new Intl.DateTimeFormat("en-GB", {
  weekday: "short",
  day: "numeric",
  month: "short",
  year: "numeric",
  timeZone: "UTC",
});

/**
 * Props of {@link FixturesDatePicker}.
 */
export interface FixturesDatePickerProps {
  /** UTC calendar day the fixture list currently shows, as `YYYY-MM-DD`. */
  readonly selectedDay: string;
}

/**
 * Renders the day picker that scopes the fixture list.
 *
 * @remarks
 * The calendar lives in a popover rather than on the page. A permanently open
 * month costs a column of the layout to a control used once per visit, and it
 * pushed the list into a narrow gutter; the trigger states the chosen day, which
 * is the only part worth showing all the time.
 *
 * The selected day lives in the URL and nowhere else, so the picker holds no
 * state of its own beyond whether the popover is open: it renders the day the
 * server resolved and navigates to write a new one. That is what makes a day
 * linkable and survive a reload, and it is also why `mode="single"` is
 * `required` — clicking the highlighted day again must not clear a value the
 * route cannot render without.
 *
 * The popover is pinned to the trigger's own width and the calendar's cell size
 * is derived from it rather than fixed, so the seven columns plus the
 * calendar's own padding come to exactly that width at every breakpoint.
 * Leaving the calendar at its natural size hung a 212px month under a 240px
 * control on a laptop and under a full-width one on a phone.
 *
 * The trigger label is formatted in UTC to match the day the URL names, so it
 * cannot disagree with the kick-off times below it west of Greenwich. It is
 * also the only place the chosen day is stated.
 *
 * The existing query is copied before `date` is replaced, so choosing a day
 * keeps the chosen competition instead of quietly widening the list back to
 * every league.
 *
 * The navigation runs inside a transition. Without one, React commits the
 * pending state before the replacement page is ready and the control repaints
 * against a half-rendered tree, which is the flash a visitor sees on picking a
 * day. A transition keeps the current tree on screen until the new one is
 * ready, while the fixture list still shows its skeleton, because its boundary
 * is keyed to the scope and therefore mounts fresh rather than being reused.
 *
 * @returns The day picker.
 */
export function FixturesDatePicker({ selectedDay }: FixturesDatePickerProps) {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [, startTransition] = useTransition();

  const [open, setOpen] = useState(false);

  const selected = utcDayToLocalDate(selectedDay);

  const handleSelect = useCallback(
    (day: Date) => {
      const next = new URLSearchParams(searchParams);

      next.set(FIXTURE_DATE_PARAMETER, localDateToUtcDay(day));

      setOpen(false);

      startTransition(() => {
        router.push(`?${next.toString()}`, { scroll: false });
      });
    },
    [router, searchParams],
  );

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          aria-label={TRIGGER_LABEL}
          className="w-full justify-start font-normal sm:w-60"
          variant="outline"
        >
          <CalendarDays />

          {TRIGGER_DAY_FORMAT.format(new Date(`${selectedDay}T00:00:00Z`))}
        </Button>
      </PopoverTrigger>

      <PopoverContent
        align="start"
        className="w-(--radix-popover-trigger-width) p-0"
      >
        <Calendar
          className="[--cell-size:calc((var(--radix-popover-trigger-width)-1rem)/7)]"
          mode="single"
          required
          selected={selected}
          defaultMonth={selected}
          onSelect={handleSelect}
        />
      </PopoverContent>
    </Popover>
  );
}
