import { Spinner } from "@/components/ui/spinner";

/**
 * Props of {@link ButtonSpinner}.
 */
export interface ButtonSpinnerProps {
  /** Utility classes sizing the spinner to match the icon it replaces. */
  readonly className?: string;
}

/**
 * Renders the progress spinner of a button that keeps its own label.
 *
 * @remarks
 * The registry spinner ships as a standalone live region, carrying
 * `role="status"` and `aria-label="Loading"`. Inside a labelled control those
 * make it part of the control's accessible name, so a button reading "Sign in"
 * silently becomes "Sign in Loading" for the duration of a request. Stripping
 * them here means no button has to remember the same three overrides, and the
 * button reports the state with `aria-busy` instead.
 *
 * The size is a caller's choice because the spinner replaces an icon and has to
 * match it. The registry spinner hardcodes `size-4`, which also opts it out of
 * the size a button applies to its own unsized icons, so a small button has to
 * say so to keep the swap from changing size.
 */
export function ButtonSpinner({ className }: ButtonSpinnerProps) {
  return (
    <Spinner
      aria-hidden="true"
      aria-label={undefined}
      className={className}
      role={undefined}
    />
  );
}
