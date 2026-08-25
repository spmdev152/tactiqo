import { Skeleton } from "@/components/ui/skeleton";

const PLACEHOLDER_ROWS = 8;

const PLACEHOLDER_ROW_KEYS = Array.from(
  { length: PLACEHOLDER_ROWS },
  (_unused, index) => `fixture-placeholder-${index}`,
);

/**
 * Renders the fixture list while the selected day is still being fetched.
 *
 * @remarks
 * Only the rows. The heading, the day picker and the competition filter are
 * rendered from the URL and do not wait for the API, so covering them would
 * replace text that is already correct with a shimmer, and the toolbar would
 * jump the moment the fixtures arrived. This shape mirrors a real row so the
 * list does not reflow either.
 *
 * Nothing here is announced: a screen reader gains nothing from eight empty
 * rows, and the list that replaces them carries the status role.
 *
 * @returns The placeholder rows.
 */
export function FixtureListSkeleton() {
  return (
    <div
      aria-hidden="true"
      className="divide-y divide-border overflow-hidden rounded-xl border"
    >
      {PLACEHOLDER_ROW_KEYS.map((key) => (
        <div className="flex items-center gap-3 px-4 py-3 sm:gap-4" key={key}>
          <Skeleton className="h-4 w-12 shrink-0" />

          <div className="flex min-w-0 flex-1 items-center gap-2 sm:gap-3">
            <Skeleton className="h-5 flex-1" />

            <Skeleton className="h-3 w-5 shrink-0" />

            <Skeleton className="h-5 flex-1" />
          </div>

          <Skeleton className="hidden h-3 w-28 shrink-0 sm:block" />

          <Skeleton className="h-3 w-14 shrink-0 sm:hidden" />
        </div>
      ))}
    </div>
  );
}
