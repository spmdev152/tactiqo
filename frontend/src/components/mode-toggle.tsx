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
 * The checked state means dark. The switch stays disabled until hydration has
 * finished, because `next-themes` resolves `system` from a media query that
 * does not exist during server rendering: rendering the switch as unchecked and
 * inert is a stable placeholder both renderers agree on, whereas guessing the
 * resolved theme would produce a hydration mismatch. Only the control lags, not
 * the page, since `next-themes` applies the stored class before hydration.
 *
 * Mounting is observed through `useSyncExternalStore`, whose third argument is
 * the server snapshot React is required to use while hydrating. Setting state
 * from an effect would reach the same result through a cascading render that
 * the React Compiler rightly rejects.
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
    <div className="flex items-center gap-2">
      <Sun aria-hidden="true" className="size-4 text-muted-foreground" />

      <Label className="sr-only" htmlFor={MODE_SWITCH_ID}>
        Dark mode
      </Label>

      <Switch
        checked={isDark}
        disabled={!isMounted}
        id={MODE_SWITCH_ID}
        onCheckedChange={(checked) => setTheme(checked ? "dark" : "light")}
      />

      <Moon aria-hidden="true" className="size-4 text-muted-foreground" />
    </div>
  );
}
