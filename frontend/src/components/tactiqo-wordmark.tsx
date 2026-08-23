/**
 * Props of {@link TactiqoWordmark}.
 */
export interface TactiqoWordmarkProps {
  /** Utility classes sizing and colouring the wordmark. */
  readonly className?: string;
}

/**
 * Draws the Tactiqo wordmark with its final letter in the primary colour.
 *
 * @remarks
 * Set in the body typeface rather than the condensed display face, and always
 * lowercase, so the brand reads as a name instead of a headline competing with
 * the page's own heading.
 *
 * The tinted letter is a plain `span` rather than a graphic, which keeps the
 * whole wordmark one run of selectable, translatable text: a screen reader and
 * a text search both see "tactiqo" and nothing else.
 */
export function TactiqoWordmark({ className }: TactiqoWordmarkProps) {
  return (
    <span className={className}>
      tactiq<span className="text-primary">o</span>
    </span>
  );
}
