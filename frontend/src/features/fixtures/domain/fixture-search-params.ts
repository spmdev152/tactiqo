/**
 * Search parameter carrying the calendar day the fixture list is scoped to.
 */
export const FIXTURE_DATE_PARAMETER = "date";

/**
 * Search parameter carrying the internal identifiers of the chosen leagues.
 *
 * @remarks
 * It repeats, once per competition, rather than carrying a delimited list. A
 * repeated parameter is what `URLSearchParams` reads and writes natively on
 * both sides of the boundary, so neither the browser nor the server has to
 * agree on a separator or escape one.
 */
export const FIXTURE_LEAGUE_PARAMETER = "league";

const UTC_DAY_PATTERN = /^\d{4}-\d{2}-\d{2}$/;

const LEAGUE_ID_PATTERN = /^\d+$/;

/**
 * Parses a raw search-parameter value into a UTC calendar day.
 *
 * @remarks
 * Two checks rather than one, because neither alone is enough. The pattern
 * states the accepted shape, and the round trip through `Date` rejects a
 * well-formed string that names no day: `2026-02-30` and `2026-13-01` both match
 * the pattern, and `Date` rolls them forward into a day the visitor never asked
 * for instead of refusing them.
 *
 * A repeated parameter arrives as an array and is rejected rather than resolved
 * to one of its values. Guessing which of two contradictory days was meant is
 * worse than falling back to a day the visitor can see is today.
 *
 * @param value - Raw parameter value, as `searchParams` supplies it.
 * @returns The day as `YYYY-MM-DD`, or `null` when the value names no day.
 */
export function parseUtcDay(
  value: string | string[] | undefined,
): string | null {
  if (typeof value !== "string" || !UTC_DAY_PATTERN.test(value)) {
    return null;
  }

  const instant = new Date(`${value}T00:00:00Z`);

  if (Number.isNaN(instant.getTime())) {
    return null;
  }

  return instant.toISOString().slice(0, 10) === value ? value : null;
}

/**
 * Resolves the UTC calendar day a fixture list should show.
 *
 * @remarks
 * An absent and a malformed value resolve identically, to today. A visitor
 * arriving at `/fixtures` with no query and a visitor arriving with a
 * hand-typed `date=yesterday` both want to see football, and there is nothing
 * useful to say about the difference. The resolved day is written back into the
 * address bar as soon as the calendar is used, so the fallback is visible
 * rather than hidden.
 *
 * @param value - Raw `date` parameter, as `searchParams` supplies it.
 * @param now - Instant standing for the present, injectable so a test does not
 * depend on the day it runs on.
 * @returns The day as `YYYY-MM-DD`.
 */
export function resolveUtcDay(
  value: string | string[] | undefined,
  now: Date = new Date(),
): string {
  return parseUtcDay(value) ?? now.toISOString().slice(0, 10);
}

/**
 * Resolves the competition filter a fixture list should apply.
 *
 * @remarks
 * The parameter repeats, once per chosen competition, so `searchParams` hands
 * over a string for one and an array for several. Both shapes and the absent
 * one collapse to a list here, which leaves the rest of the feature with a
 * single case to handle and makes "every competition" the empty list rather
 * than a second kind of nothing.
 *
 * Anything that is not a positive integer is dropped rather than failing, and
 * a repeat is dropped too. The identifiers are visitor-controllable, and once
 * the backend has answered, an unknown competition is indistinguishable from
 * one with no fixtures that day, so refusing to render would buy nothing.
 *
 * @param value - Raw `league` parameter, as `searchParams` supplies it.
 * @returns The chosen competition identifiers, empty for all of them.
 */
export function resolveLeagueIds(
  value: string | string[] | undefined,
): number[] {
  const raw = value === undefined ? [] : [value].flat();

  const identifiers = raw
    .filter((one) => LEAGUE_ID_PATTERN.test(one))
    .map(Number)
    .filter((one) => one > 0);

  return [...new Set(identifiers)];
}

/**
 * Builds the canonical key of one fixture scope.
 *
 * @remarks
 * A day and a set of competitions name a scope, and two places have to agree on
 * that name to the byte: the route keys its `Suspense` boundary with it, so a
 * new scope gets a fresh boundary and its skeleton, and the filter bar compares
 * the staged scope against the applied one with it, so the control that applies
 * a scope is offered only while there is something to apply. Written twice, the
 * two would drift and one of them would be subtly wrong.
 *
 * The comparator is explicit because the default one is lexicographic, which
 * orders `[9, 10]` as `10,9` and would leave the key depending on a detail of
 * `Array.prototype.sort` that nothing states. The identifiers are sorted at all
 * so that the same competitions chosen in a different order are one scope.
 *
 * @param day - UTC calendar day the list is scoped to, as `YYYY-MM-DD`.
 * @param leagueIds - Chosen competition identifiers, empty for all of them.
 * @returns The canonical scope key.
 */
export function fixtureScopeKey(
  day: string,
  leagueIds: readonly number[],
): string {
  const ordered = [...leagueIds].sort((one, other) => one - other);

  return `${day}|${ordered.join(",")}`;
}

/**
 * Converts a UTC calendar day into the local `Date` a day picker selects with.
 *
 * @remarks
 * `react-day-picker` reads and writes the local components of a `Date`, while
 * the URL names a UTC day, so handing it `new Date("2026-08-29")` would show
 * the 28th to anybody west of Greenwich. Rebuilding the same year, month and
 * day at local midnight turns the picker into a pure calendar-day control whose
 * output means the same thing in every timezone.
 *
 * @param day - Calendar day as `YYYY-MM-DD`, as {@link parseUtcDay} and
 * {@link resolveUtcDay} produce it.
 * @returns Local midnight of that calendar day.
 */
export function utcDayToLocalDate(day: string): Date {
  const [year, month, dayOfMonth] = day.split("-").map(Number);

  return new Date(year, month - 1, dayOfMonth);
}

/**
 * Converts a `Date` a day picker produced back into a UTC calendar day.
 *
 * @param date - Local date the picker selected.
 * @returns The day as `YYYY-MM-DD`.
 *
 * @see {@link utcDayToLocalDate} for why the local components are the ones read.
 */
export function localDateToUtcDay(date: Date): string {
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const dayOfMonth = String(date.getDate()).padStart(2, "0");

  return `${date.getFullYear()}-${month}-${dayOfMonth}`;
}
