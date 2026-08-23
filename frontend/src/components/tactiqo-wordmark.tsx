/**
 * Props of {@link TactiqoWordmark}.
 */
export interface TactiqoWordmarkProps {
  /** Utility classes sizing and colouring the wordmark. */
  readonly className?: string;
}

/**
 * Draws the Tactiqo wordmark with a football in place of its final letter.
 *
 * @remarks
 * The ball is sized in `em` and nudged onto the cap line, so it tracks the font
 * size of whatever renders the wordmark instead of needing a matching pixel
 * value at every call site.
 *
 * Its panels are cut in the page background colour rather than a fixed dark, so
 * the same markup reads correctly in both themes without a second variant. The
 * seams stop short of the rim on purpose: run them all the way out and the cuts
 * dominate the circle, which stops reading as a ball and starts reading as an
 * asterisk.
 *
 * The letters and the ball are both decorative: the accessible name comes from
 * the visually hidden text, which is what keeps the wordmark a single readable
 * word for assistive technology instead of "TACTIQ" followed by an image.
 */
export function TactiqoWordmark({ className }: TactiqoWordmarkProps) {
  return (
    <span className={className}>
      <span className="sr-only">Tactiqo</span>

      <span aria-hidden="true" className="inline-flex items-center">
        Tactiq
        <svg
          className="ml-[0.06em] size-[0.78em] translate-y-[0.01em] text-primary"
          fill="none"
          viewBox="0 0 24 24"
          xmlns="http://www.w3.org/2000/svg"
        >
          <circle cx="12" cy="12" fill="currentColor" r="11" />

          <path
            className="fill-background"
            d="M12 7.4 16.37 10.58 14.7 15.7H9.3L7.63 10.58Z"
          />

          <path
            className="stroke-background"
            d="M12 7.4V5.4M16.37 10.58 18.28 9.96M14.7 15.7 15.88 17.34M9.3 15.7 8.12 17.34M7.63 10.58 5.72 9.96"
            strokeLinecap="round"
            strokeWidth="1.8"
          />
        </svg>
      </span>
    </span>
  );
}
