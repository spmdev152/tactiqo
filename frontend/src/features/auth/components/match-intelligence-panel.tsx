const PASSING_LANES = [
  "M180 498 L135 432",
  "M180 498 L225 432",
  "M135 432 L60 418",
  "M225 432 L300 418",
  "M135 432 L225 432",
  "M135 432 L110 318",
  "M225 432 L250 318",
  "M60 418 L110 318",
  "M300 418 L250 318",
  "M110 318 L180 348",
  "M250 318 L180 348",
  "M110 318 L70 188",
  "M250 318 L290 188",
  "M110 318 L180 148",
  "M250 318 L180 148",
  "M70 188 L180 148",
  "M290 188 L180 148",
] as const;

const OUTFIELD_POSITIONS = [
  { cx: 60, cy: 418 },
  { cx: 135, cy: 432 },
  { cx: 225, cy: 432 },
  { cx: 300, cy: 418 },
  { cx: 110, cy: 318 },
  { cx: 180, cy: 348 },
  { cx: 250, cy: 318 },
  { cx: 70, cy: 188 },
  { cx: 290, cy: 188 },
] as const;

const READOUTS = [
  { label: "Home win", value: "61%", delay: "[animation-delay:280ms]" },
  { label: "Expected goals", value: "2.14", delay: "[animation-delay:400ms]" },
  {
    label: "Both teams score",
    value: "1.72",
    delay: "[animation-delay:520ms]",
  },
] as const;

/**
 * Props of {@link MatchIntelligencePanel}.
 */
export interface MatchIntelligencePanelProps {
  /** Utility classes controlling where the panel appears and at which breakpoints. */
  readonly className?: string;
}

/**
 * Renders the illustrated half of the sign-in screen.
 *
 * @remarks
 * A drawn passing network over a pitch rather than a photograph. The reasons are
 * concrete: a licensed stadium image would add a binary asset and a licence
 * obligation to the repository, it would need a second variant to survive the
 * dark theme, and it would say nothing about a product whose subject is
 * probabilities rather than scenery. Vector geometry inherits the theme tokens,
 * costs no request, and scales to any viewport.
 *
 * The figures are illustrative rather than live data, which is why they are
 * static markup here instead of a fetch: the sign-in screen has no session yet,
 * so it has no right to ask the backend for anything.
 *
 * Decorative throughout, so the pitch carries `aria-hidden` and the panel
 * contributes nothing to the accessible name of the page.
 *
 * @returns The illustrated panel tree.
 */
export function MatchIntelligencePanel({
  className,
}: MatchIntelligencePanelProps) {
  return (
    <aside className={className}>
      <div className="relative isolate h-full overflow-hidden bg-sidebar">
        <div
          aria-hidden="true"
          className="absolute inset-0 -z-10 bg-[radial-gradient(120%_90%_at_80%_0%,var(--color-primary)_0%,transparent_55%),radial-gradient(90%_70%_at_10%_100%,var(--color-chart-2)_0%,transparent_60%)] opacity-25"
        />

        <div
          aria-hidden="true"
          className="absolute inset-0 -z-10 grain text-foreground opacity-[0.07]"
        />

        <div className="flex h-full flex-col gap-7 p-10 xl:p-12">
          <p className="animate-rise font-mono text-[0.7rem] tracking-[0.2em] text-muted-foreground uppercase">
            Matchday intelligence
          </p>

          <div className="flex min-h-0 flex-1 items-center justify-center">
            <svg
              aria-hidden="true"
              className="max-h-[min(46vh,28rem)] w-auto text-primary"
              fill="none"
              viewBox="0 0 360 540"
              xmlns="http://www.w3.org/2000/svg"
            >
              <g stroke="currentColor" strokeOpacity="0.28">
                <rect height="520" rx="4" width="340" x="10" y="10" />
                <path d="M10 270h340" />
                <circle cx="180" cy="270" r="52" />
                <rect height="95" width="190" x="85" y="10" />
                <rect height="95" width="190" x="85" y="435" />
                <rect height="34" width="80" x="140" y="10" />
                <rect height="34" width="80" x="140" y="496" />
              </g>

              <g fill="currentColor" fillOpacity="0.4">
                <circle cx="180" cy="270" r="3" />
                <circle cx="180" cy="76" r="3" />
                <circle cx="180" cy="464" r="3" />
              </g>

              <g
                className="animate-draw"
                stroke="currentColor"
                strokeLinecap="round"
                strokeOpacity="0.55"
                strokeWidth="1.25"
              >
                {PASSING_LANES.map((lane) => (
                  <path d={lane} key={lane} pathLength="1" />
                ))}
              </g>

              <g>
                {OUTFIELD_POSITIONS.map((position) => (
                  <circle
                    className="fill-primary stroke-sidebar"
                    cx={position.cx}
                    cy={position.cy}
                    key={`${position.cx}-${position.cy}`}
                    r="7"
                    strokeWidth="2.5"
                  />
                ))}

                <circle
                  className="fill-chart-2 stroke-sidebar"
                  cx="180"
                  cy="148"
                  r="10"
                  strokeWidth="2.5"
                />

                <circle
                  className="fill-muted-foreground stroke-sidebar"
                  cx="180"
                  cy="498"
                  r="7"
                  strokeWidth="2.5"
                />
              </g>
            </svg>
          </div>

          <div className="flex flex-col gap-8">
            <p className="max-w-md animate-rise font-display text-4xl leading-[0.95] font-bold tracking-tight text-balance uppercase [animation-delay:160ms] xl:text-5xl">
              Read the evidence before the whistle
            </p>

            <dl className="grid grid-cols-3 gap-3">
              {READOUTS.map((readout) => (
                <div
                  className={`animate-rise ${readout.delay} flex flex-col gap-1 rounded-lg border border-border/60 bg-card/60 px-3 py-2.5 shadow-2xs backdrop-blur-sm`}
                  key={readout.label}
                >
                  <dt className="font-mono text-[0.62rem] leading-tight tracking-[0.12em] text-muted-foreground uppercase">
                    {readout.label}
                  </dt>

                  <dd className="font-mono text-lg leading-none tabular-nums">
                    {readout.value}
                  </dd>
                </div>
              ))}
            </dl>
          </div>
        </div>
      </div>
    </aside>
  );
}
