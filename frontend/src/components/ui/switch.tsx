"use client"

import * as React from "react"
import { Switch as SwitchPrimitive } from "radix-ui"

import { cn } from "@/lib/utils"

// Local fix, deliberately diverging from the shadcn radix-nova registry: the
// registry styles this component with `data-checked:` and `data-unchecked:`
// variants, which Tailwind compiles to `[data-checked]` and `[data-unchecked]`.
// `@radix-ui/react-switch` only ever emits `data-state="checked" | "unchecked"`,
// so every one of those variants was dead: the track stayed transparent and the
// thumb never translated, leaving a switch that changed state without showing
// it. The registry also wrote the thumb travel as `calc(100%-2px)`, which is
// invalid CSS because `calc` needs whitespace around its operator, so Tailwind
// emitted no rule at all for it. Re-adding this component from the registry will
// reintroduce both bugs.
//
// The `lg` size and the `children` slot are additions rather than fixes. They
// exist so a caller can place content inside the track and have the thumb
// occlude it, which is what the theme toggle does with its two icons; the thumb
// is `relative` so it paints above absolutely positioned children.
function Switch({
  children,
  className,
  size = "default",
  ...props
}: React.ComponentProps<typeof SwitchPrimitive.Root> & {
  size?: "sm" | "default" | "lg"
}) {
  return (
    <SwitchPrimitive.Root
      data-slot="switch"
      data-size={size}
      className={cn(
        "peer group/switch relative inline-flex shrink-0 items-center rounded-full border border-transparent transition-all outline-none group-has-[:focus-visible]/field-label:border-transparent group-has-[:focus-visible]/field-label:ring-0 after:absolute after:-inset-x-3 after:-inset-y-2 focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 aria-invalid:border-destructive aria-invalid:ring-3 aria-invalid:ring-destructive/20 data-[size=default]:h-[18.4px] data-[size=default]:w-[32px] data-[size=lg]:h-7 data-[size=lg]:w-[3.25rem] data-[size=lg]:px-[3px] data-[size=sm]:h-[14px] data-[size=sm]:w-[24px] dark:aria-invalid:border-destructive/50 dark:aria-invalid:ring-destructive/40 data-[state=checked]:bg-primary data-[state=unchecked]:bg-input dark:data-[state=unchecked]:bg-input/80 data-disabled:cursor-not-allowed data-disabled:opacity-50",
        className
      )}
      {...props}
    >
      {children}

      <SwitchPrimitive.Thumb
        data-slot="switch-thumb"
        className="pointer-events-none relative block rounded-full bg-background ring-0 transition-transform group-data-[size=default]/switch:size-4 group-data-[size=lg]/switch:size-[1.375rem] group-data-[size=sm]/switch:size-3 group-data-[size=default]/switch:data-[state=checked]:translate-x-[calc(100%_-_2px)] group-data-[size=lg]/switch:data-[state=checked]:translate-x-[calc(100%_+_2px)] group-data-[size=sm]/switch:data-[state=checked]:translate-x-[calc(100%_-_2px)] dark:data-[state=checked]:bg-primary-foreground group-data-[size=default]/switch:data-[state=unchecked]:translate-x-0 group-data-[size=lg]/switch:data-[state=unchecked]:translate-x-0 group-data-[size=sm]/switch:data-[state=unchecked]:translate-x-0 dark:data-[state=unchecked]:bg-foreground"
      />
    </SwitchPrimitive.Root>
  )
}

export { Switch }
