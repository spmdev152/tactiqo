"use client";

import { useSyncExternalStore } from "react";

import { Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";

import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { cn } from "@/lib/utils";

const MODE_SWITCH_ID = "colour-mode-switch";

const subscribeToMount = () => () => {};

const readMountedOnClient = () => true;

const readMountedOnServer = () => false;

/**
 * Switches the application between the light and the dark colour theme.
 *
 * @remarks
 * The icons sit inside the label bound to the switch, so a pointer landing on
 * the sun or the moon toggles the theme. That is a fix rather than a detail: the
 * switch itself is 32 by 18 pixels plus a small pseudo-element margin, so an
 * icon a few pixels outside it looked exactly like the affordance while being
 * completely inert, and the control read as broken.
 *
 * The switch is never disabled either. Gating it on hydration meant a single
 * failed hydration left the only theme control permanently dead, which is a far
 * worse failure than losing a click in the sub-second window before hydration.
 *
 * `useSyncExternalStore` supplies the mounted flag because its third argument is
 * the snapshot React is required to use while hydrating. Server and client
 * therefore agree on unchecked and nothing mismatches, while the page itself is
 * already correct: `next-themes` applies the stored theme to the document before
 * this component renders at all. Its three callbacks are module constants rather
 * than inline arrows because React resubscribes whenever `subscribe` changes
 * identity, so an inline function would resubscribe on every render.
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
      className="flex cursor-pointer items-center gap-2.5 rounded-full border border-border/70 bg-card/50 px-3 py-2 shadow-2xs transition-colors hover:border-border hover:bg-card"
      htmlFor={MODE_SWITCH_ID}
    >
      <Sun
        aria-hidden="true"
        className={cn(
          "size-4 transition-colors",
          isDark ? "text-muted-foreground" : "text-foreground",
        )}
      />

      <span className="sr-only">Dark mode</span>

      <Switch
        checked={isDark}
        id={MODE_SWITCH_ID}
        onCheckedChange={(checked) => setTheme(checked ? "dark" : "light")}
      />

      <Moon
        aria-hidden="true"
        className={cn(
          "size-4 transition-colors",
          isDark ? "text-foreground" : "text-muted-foreground",
        )}
      />
    </Label>
  );
}
