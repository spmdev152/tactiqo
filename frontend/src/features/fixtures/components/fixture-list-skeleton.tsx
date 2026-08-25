import { Skeleton } from "@/components/ui/skeleton";

const PLACEHOLDER_GROUPS = [
  { key: "fixture-placeholder-group-0", rows: 4 },
  { key: "fixture-placeholder-group-1", rows: 3 },
];

/**
 * Renders the fixture list while the selected day is still being fetched.
 *
 * @remarks
 * Only the list. The heading, the day picker and the competition filter are
 * rendered from the URL and do not wait for the API, so covering them would
 * replace text that is already correct with a shimmer, and the toolbar would
 * jump the moment the fixtures arrived.
 *
 * The shape mirrors the real list, headings included, so it does not reflow
 * either. Two groups of differing length are a truer guess than one long list:
 * a day with fixtures almost always spans more than one competition, and the
 * uneven counts stop the placeholder reading as a table.
 *
 * The trailing square is the chevron column every real row reserves, whether or
 * not that match has predictions to open. Leaving it out would have moved both
 * sides of every row sideways by a chevron and a gap at the moment the list
 * arrived, which is the one thing this component exists to prevent.
 *
 * Nothing here is announced: a screen reader gains nothing from seven empty
 * rows, and there is nothing to hold a status role for either, because the
 * region that announces the outcome lives above the `Suspense` boundary and
 * survives the swap rather than arriving with the list.
 *
 * @returns The placeholder groups.
 */
export function FixtureListSkeleton() {
  return (
    <div aria-hidden="true" className="flex flex-col gap-5">
      {PLACEHOLDER_GROUPS.map((group) => (
        <div className="overflow-hidden rounded-xl border" key={group.key}>
          <div className="flex items-center gap-2.5 border-b border-border bg-muted/40 px-4 py-2.5">
            <Skeleton className="h-[17px] w-6 shrink-0 rounded-[2px]" />

            <Skeleton className="h-4 w-32" />

            <Skeleton className="ml-auto h-3 w-16 shrink-0" />
          </div>

          <div className="divide-y divide-border">
            {Array.from({ length: group.rows }, (_unused, index) => (
              <div
                className="flex items-center gap-3 px-4 py-3 @lg:gap-4"
                key={`${group.key}-row-${index}`}
              >
                <Skeleton className="h-4 w-12 shrink-0" />

                <div className="flex min-w-0 flex-1 items-center gap-2 @lg:gap-3">
                  <Skeleton className="h-5 flex-1" />

                  <Skeleton className="h-3 w-11 shrink-0" />

                  <Skeleton className="h-5 flex-1" />
                </div>

                <Skeleton className="size-4 shrink-0 rounded-sm" />
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
