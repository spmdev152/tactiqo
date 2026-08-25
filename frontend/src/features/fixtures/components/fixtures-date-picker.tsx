"use client";

import { useCallback, useState } from "react";

import { CalendarDays } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
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
  /** UTC calendar day currently staged, as `YYYY-MM-DD`. */
  readonly value: string;

  /** Called with the newly staged UTC calendar day. */
  readonly onChange: (day: string) => void;
}

/**
 * Renders the day picker of the fixture filters.
 *
 * @remarks
 * Choosing a day stages it and nothing else. The control neither reads the URL
 * nor navigates: {@link FixtureFilters} owns the staged scope and applies it.
 * That separation is the point rather than tidiness — while a navigation is in
 * flight React holds the previous tree on screen, and a popover that closed on
 * the same click could be caught in that window and painted open again. With
 * the navigation moved to a button, nothing is animating when it starts.
 *
 * The calendar lives in a popover rather than on the page. A permanently open
 * month costs a column of the layout to a control used once per visit, and it
 * pushed the list into a narrow gutter; the trigger states the staged day,
 * which is the only part worth showing all the time.
 *
 * `mode="single"` is `required` because clicking the highlighted day again must
 * not clear a value the route cannot render without.
 *
 * The popover is pinned to the trigger's own width and the calendar's cell size
 * is derived from it rather than fixed, so the seven columns plus the
 * calendar's own padding come to exactly that width at every breakpoint.
 * Leaving the calendar at its natural size hung a 212px month under a 240px
 * control on a laptop and under a full-width one on a phone.
 *
 * The trigger widens against the page container rather than the viewport, so it
 * matches the competition picker beside it whatever the sidebar is doing.
 *
 * The trigger label is formatted in UTC to match the day the URL names, so it
 * cannot disagree with the kick-off times below it west of Greenwich.
 *
 * @returns The day picker.
 */
export function FixturesDatePicker({
  value,
  onChange,
}: FixturesDatePickerProps) {
  const [open, setOpen] = useState(false);

  const selected = utcDayToLocalDate(value);

  const handleSelect = useCallback(
    (day: Date) => {
      setOpen(false);
      onChange(localDateToUtcDay(day));
    },
    [onChange],
  );

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          aria-label={TRIGGER_LABEL}
          className="w-full justify-start font-normal @xl:w-56"
          variant="outline"
        >
          <CalendarDays />

          {TRIGGER_DAY_FORMAT.format(new Date(`${value}T00:00:00Z`))}
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
