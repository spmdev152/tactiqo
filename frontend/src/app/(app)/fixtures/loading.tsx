import { Skeleton } from "@/components/ui/skeleton";

const PLACEHOLDER_ROWS = 6;

const PLACEHOLDER_ROW_KEYS = Array.from(
  { length: PLACEHOLDER_ROWS },
  (_unused, index) => `fixture-placeholder-${index}`,
);

/**
 * Renders the fixtures page while its data is still being fetched.
 *
 * @remarks
 * The placeholder mirrors the real layout, calendar column included, so the
 * page does not reflow once the fixtures arrive. Nothing here is announced: a
 * screen reader gains nothing from six empty rows, and the list that replaces
 * them carries the status role.
 *
 * @returns The loading skeleton of the fixtures page.
 */
export default function FixturesLoading() {
  return (
    <div
      aria-hidden="true"
      className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-8 px-6 py-12"
    >
      <div className="flex flex-col gap-3">
        <Skeleton className="h-3 w-24" />
        <Skeleton className="h-10 w-80 max-w-full" />
      </div>

      <div className="grid gap-8 lg:grid-cols-[280px_1fr]">
        <Skeleton className="h-72 w-full rounded-xl" />

        <div className="flex min-w-0 flex-col gap-4">
          <div className="flex flex-wrap items-center gap-3">
            <Skeleton className="h-8 w-full sm:w-60" />
            <Skeleton className="h-3 w-40" />
          </div>

          <div className="divide-y divide-border overflow-hidden rounded-xl border">
            {PLACEHOLDER_ROW_KEYS.map((key) => (
              <div className="flex items-center gap-4 px-4 py-3" key={key}>
                <Skeleton className="h-4 w-12 shrink-0" />

                <div className="flex flex-1 flex-col gap-1.5">
                  <Skeleton className="h-5 w-48 max-w-full" />
                  <Skeleton className="h-5 w-40 max-w-full" />
                </div>

                <Skeleton className="hidden h-3 w-28 shrink-0 sm:block" />
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
