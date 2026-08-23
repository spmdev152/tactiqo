const LIGHT_ORBS = [
  "-top-24 -right-16 size-[26rem] bg-primary opacity-40 animate-drift",
  "-bottom-28 -left-20 size-[22rem] bg-chart-2 opacity-35 animate-drift-slow",
  "top-1/3 -right-32 size-[18rem] bg-chart-5 opacity-25 animate-drift-late",
] as const;

/**
 * Props of {@link MatchIntelligencePanel}.
 */
export interface MatchIntelligencePanelProps {
  /** Utility classes controlling where the panel appears and at which breakpoints. */
  readonly className?: string;
}

/**
 * Renders the atmospheric half of the sign-in screen.
 *
 * @remarks
 * Light and a single line of type, nothing else. An earlier version drew a
 * passing network over a pitch with probability read-outs beside it, which put
 * fabricated statistics on the one screen that has no session and therefore no
 * right to ask the backend for real ones. The orbs carry the mood and the
 * headline carries the meaning.
 *
 * The orbs are blurred solid circles rather than background gradients so each
 * one can drift on its own timing. They are tinted from the chart tokens, which
 * are the only palette entries that stay vivid in both themes: `--accent` is a
 * surface colour in the dark theme and would disappear.
 *
 * Every decorative layer sits in one absolutely positioned wrapper and the
 * content is `relative`, so paint order comes from document order alone. The
 * earlier version stacked negative z-indices inside an `isolate` container,
 * which put animated `filter: blur` layers and the text in the same stacking
 * context and made the headline disappear from rendered output.
 *
 * Decorative throughout, so the wrapper carries `aria-hidden` and the panel
 * contributes nothing but the headline to the accessible page.
 *
 * @returns The illustrated panel tree.
 */
export function MatchIntelligencePanel({
  className,
}: MatchIntelligencePanelProps) {
  return (
    <aside className={className}>
      <div className="relative h-full overflow-hidden bg-sidebar">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 overflow-hidden"
        >
          {LIGHT_ORBS.map((orb) => (
            <div
              className={`absolute rounded-full blur-[90px] ${orb}`}
              key={orb}
            />
          ))}

          <div className="absolute inset-0 grain text-foreground opacity-[0.07]" />
        </div>

        <div className="relative flex h-full flex-col justify-between gap-10 p-10 xl:p-14">
          <p className="animate-rise font-mono text-[0.7rem] tracking-[0.2em] text-muted-foreground uppercase">
            Matchday intelligence
          </p>

          <div className="flex flex-col gap-6">
            <span
              aria-hidden="true"
              className="h-px w-24 animate-rise bg-primary [animation-delay:120ms]"
            />

            <p className="animate-rise font-display text-4xl leading-[0.92] font-bold tracking-tight text-balance uppercase [animation-delay:200ms] xl:text-6xl">
              Read the evidence before the whistle
            </p>
          </div>
        </div>
      </div>
    </aside>
  );
}
