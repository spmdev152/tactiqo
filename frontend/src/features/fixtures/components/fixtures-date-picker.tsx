"use client";

import { useCallback, useState } from "react";

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
 * The trigger label is formatted in UTC to match the day the URL names, so the
 * control and the heading below it cannot disagree west of Greenwich.
 *
 * The existing query is copied before `date` is replaced, so choosing a day
 * keeps the chosen competition instead of quietly widening the list back to
 * every league.
 *
 * @returns The day picker.
 */
export function FixturesDatePicker({ selectedDay }: FixturesDatePickerProps) {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [open, setOpen] = useState(false);

  const selected = utcDayToLocalDate(selectedDay);

  const handleSelect = useCallback(
    (day: Date) => {
      const next = new URLSearchParams(searchParams);

      next.set(FIXTURE_DATE_PARAMETER, localDateToUtcDay(day));

      setOpen(false);
      router.push(`?${next.toString()}`, { scroll: false });
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

      <PopoverContent align="start" className="w-auto p-0">
        <Calendar
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
