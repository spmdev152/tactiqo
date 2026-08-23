import { Spinner } from "@/components/ui/spinner";

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
 */
export function ButtonSpinner() {
  return <Spinner aria-hidden="true" aria-label={undefined} role={undefined} />;
}
