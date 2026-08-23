/**
 * Props of {@link TactiqoMark}.
 */
export interface TactiqoMarkProps {
  /** Utility classes sizing and colouring the mark. */
  readonly className?: string;
}

/**
 * Draws the Tactiqo brand mark.
 *
 * @remarks
 * Inline SVG rather than an image file so the mark inherits `currentColor` and
 * needs no second asset for the dark theme, and so it costs no request.
 *
 * The geometry is the product in miniature: the circle and the vertical line are
 * a pitch seen from above, and the three ascending bars crossing them are the
 * analysis laid over the match. It is decorative, so it carries `aria-hidden`
 * and the wordmark beside it supplies the accessible name.
 */
export function TactiqoMark({ className }: TactiqoMarkProps) {
  return (
    <svg
      aria-hidden="true"
      className={className}
      fill="none"
      viewBox="0 0 32 32"
      xmlns="http://www.w3.org/2000/svg"
    >
      <rect
        height="30"
        rx="9"
        stroke="currentColor"
        strokeOpacity="0.25"
        width="30"
        x="1"
        y="1"
      />

      <path d="M16 5.5v21" stroke="currentColor" strokeOpacity="0.3" />

      <circle
        cx="16"
        cy="16"
        r="6.25"
        stroke="currentColor"
        strokeOpacity="0.3"
      />

      <path
        d="M9.5 21.5v-4M16 21.5v-8.5M22.5 21.5v-13"
        stroke="currentColor"
        strokeLinecap="round"
        strokeWidth="2.25"
      />
    </svg>
  );
}
