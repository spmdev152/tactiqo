"use client";

import { useCallback } from "react";

import { useRouter, useSearchParams } from "next/navigation";

import { Calendar } from "@/components/ui/calendar";
import {
  FIXTURE_DATE_PARAMETER,
  localDateToUtcDay,
  utcDayToLocalDate,
} from "@/features/fixtures/domain/fixture-search-params";

/**
 * Props of {@link FixturesCalendar}.
 */
export interface FixturesCalendarProps {
  /** UTC calendar day the fixture list currently shows, as `YYYY-MM-DD`. */
  readonly selectedDay: string;
}

/**
 * Renders the day picker that scopes the fixture list.
 *
 * @remarks
 * The selected day lives in the URL and nowhere else, so the picker holds no
 * state of its own: it renders the day the server resolved and navigates to
 * write a new one. That is what makes a day linkable and survive a reload, and
 * it is also why `mode="single"` is `required` — clicking the highlighted day
 * again must not clear a value the route cannot render without.
 *
 * The existing query is copied before `date` is replaced, so choosing a day
 * keeps the chosen competition instead of quietly widening the list back to
 * every league.
 *
 * @returns The day picker.
 */
export function FixturesCalendar({ selectedDay }: FixturesCalendarProps) {
  const router = useRouter();
  const searchParams = useSearchParams();

  const selected = utcDayToLocalDate(selectedDay);

  const handleSelect = useCallback(
    (day: Date) => {
      const next = new URLSearchParams(searchParams);

      next.set(FIXTURE_DATE_PARAMETER, localDateToUtcDay(day));

      router.push(`?${next.toString()}`, { scroll: false });
    },
    [router, searchParams],
  );

  return (
    <Calendar
      className="w-full rounded-xl border"
      mode="single"
      required
      selected={selected}
      defaultMonth={selected}
      onSelect={handleSelect}
    />
  );
}
