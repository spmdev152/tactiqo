"use client";

import { useSyncExternalStore } from "react";

import { Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";

import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";

const MODE_SWITCH_ID = "colour-mode-switch";

const subscribeToMount = () => () => {};

const readMountedOnClient = () => true;

const readMountedOnServer = () => false;

/**
 * Switches the application between the light and the dark colour theme.
 *
 * @remarks
 * Both icons live inside the track, one at each end, and the thumb occludes the
 * one it is parked over. So the icon on show is always the mode a click would
 * move to: parked on the left over the sun in light mode, revealing the moon,
 * and parked on the right over the moon in dark mode, revealing the sun. The
 * icons need no state of their own for this, because the thumb is opaque and
 * paints above them; the switch's own position does the reveal.
 *
 * Each icon is coloured for the one track it is ever seen against, which is why
 * they do not share a class. The sun is only revealed while the switch is
 * checked, over the primary track, and the moon only while it is unchecked, over
 * the input track. Colouring the sun `muted-foreground` put it at the same
 * lightness as the amethyst beneath it and made it invisible.
 *
 * They are also `pointer-events-none` and the label wraps the whole control.
 * That combination is deliberate: the icons used to flank the switch as separate
 * elements a few pixels outside its 32 by 18 pixel hit area, so the parts that
 * looked like the control did nothing at all.
 *
 * The switch is never disabled. Gating it on hydration meant a single failed
 * hydration left the only theme control permanently dead, which is a far worse
 * failure than losing a click in the sub-second window before hydration.
 *
 * `useSyncExternalStore` supplies the mounted flag because its third argument is
 * the snapshot React is required to use while hydrating. Server and client
 * therefore agree on unchecked and nothing mismatches, while the page itself is
 * already correct: `next-themes` applies the stored theme to the document before
 * this component renders at all. Its three callbacks are module constants rather
 * than inline arrows because React resubscribes whenever `subscribe` changes
 * identity, so an inline function would resubscribe on every render.
 *
 * That unchecked first render is also why the switch carries a `key` derived
 * from the mounted flag. The server cannot know the resolved theme, so a stored
 * dark theme makes the switch correct itself from unchecked to checked the
 * moment React takes over, and with transitions live the visitor watched the
 * thumb slide across on every single reload. Changing the key makes that
 * correction a remount instead of a state change, and a freshly inserted element
 * has no previous value to animate from, so the correction is instant while a
 * real click still animates. Animation should express what somebody did, not a
 * correction they had no part in.
 *
 * Suppressing the transition instead does not work, because the flag and the
 * checked value flip in the same commit: whatever re-enables transitions does so
 * in the very render that changes the state, and the browser animates it anyway.
 */
export function ModeToggle() {
  const { resolvedTheme, setTheme } = useTheme();

  const isMounted = useSyncExternalStore(
    subscribeToMount,
    readMountedOnClient,
    readMountedOnServer,
  );

  const isDark = isMounted && resolvedTheme === "dark";

  return (
    <Label
      className="flex cursor-pointer items-center rounded-full"
      htmlFor={MODE_SWITCH_ID}
    >
      <span className="sr-only">Dark mode</span>

      <Switch
        checked={isDark}
        id={MODE_SWITCH_ID}
        key={isMounted ? "resolved" : "initial"}
        onCheckedChange={(checked) => setTheme(checked ? "dark" : "light")}
        size="lg"
      >
        <Sun
          aria-hidden="true"
          className="pointer-events-none absolute left-[6px] size-[0.9rem] text-primary-foreground"
        />

        <Moon
          aria-hidden="true"
          className="pointer-events-none absolute right-[6px] size-[0.9rem] text-muted-foreground"
        />
      </Switch>
    </Label>
  );
}
