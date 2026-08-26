"use client";

import { Button } from "@/components/ui/button";
import {
  FORM_RANGES,
  FORM_SCOPES,
  type FormRange,
  type FormScope,
  rangeLabel,
  scopeLabel,
} from "@/features/fixtures/domain/form-metrics";

const RANGE_GROUP_LABEL = "Matches counted";

const SCOPE_GROUP_LABEL = "Matches included";

/**
 * Props of {@link FormFilters}.
 */
export interface FormFiltersProps {
  /** Window the panel is currently drawing its figures from. */
  readonly range: FormRange;

  /** Scope the panel is currently drawing its figures from. */
  readonly scope: FormScope;

  /** Narrows the panel to another window. */
  readonly onRangeChange: (range: FormRange) => void;

  /** Narrows the panel to another scope. */
  readonly onScopeChange: (scope: FormScope) => void;
}

/**
 * Renders the two controls that choose which sample the panel shows.
 *
 * @remarks
 * The controls filter figures the panel already holds. Every window and scope
 * the vocabulary defines arrives in one response, so changing either of these
 * costs no request at all — which is the whole reason the backend publishes six
 * samples per side rather than the one the panel opens on.
 *
 * They are pressed buttons rather than a radio group, and that is a deliberate
 * trade rather than a shortcut. A radio group is the more precise role, but ARIA
 * requires it to be operated with the arrow keys and to carry a roving
 * `tabindex`, neither of which a `button` does on its own: adopting the role
 * without implementing both leaves a group that announces itself as a radio
 * group and then does not behave like one, which is worse than a plainer role
 * that behaves exactly as it announces. A pressed button is natively operable
 * with Enter and Space, is reached by Tab like everything else in the panel, and
 * announces its own selected state through `aria-pressed`, so nothing here
 * depends on a key handler this component would have had to write and test.
 *
 * The cost of that choice is five tab stops instead of two, which is the reason
 * the alternative exists. It is paid rather than avoided because this panel is
 * already inside a disclosure a visitor chose to open.
 *
 * Each group is named with `aria-label` rather than from hidden text inside it,
 * because a `group` takes its accessible name from an attribute and not from its
 * contents: a visually hidden span would have been announced as one more piece
 * of the group's text and named nothing. Two groups rather than one, because
 * "the last six matches" and "home matches only" are independent questions and a
 * single row of five buttons would imply they are alternatives.
 *
 * The selected button carries the `secondary` variant and the rest `ghost`, so
 * the state is painted as well as announced. `aria-pressed` alone would leave a
 * sighted visitor with no way to see which window they are reading.
 *
 * @returns The window and scope controls.
 */
export function FormFilters({
  range,
  scope,
  onRangeChange,
  onScopeChange,
}: FormFiltersProps) {
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
      <div
        aria-label={RANGE_GROUP_LABEL}
        className="flex items-center gap-1"
        role="group"
      >
        {FORM_RANGES.map((one) => (
          <Button
            aria-pressed={one === range}
            key={one}
            onClick={() => onRangeChange(one)}
            size="sm"
            type="button"
            variant={one === range ? "secondary" : "ghost"}
          >
            {rangeLabel(one)}
          </Button>
        ))}
      </div>

      <div
        aria-label={SCOPE_GROUP_LABEL}
        className="flex items-center gap-1"
        role="group"
      >
        {FORM_SCOPES.map((one) => (
          <Button
            aria-pressed={one === scope}
            key={one}
            onClick={() => onScopeChange(one)}
            size="sm"
            type="button"
            variant={one === scope ? "secondary" : "ghost"}
          >
            {scopeLabel(one)}
          </Button>
        ))}
      </div>
    </div>
  );
}
