"use client"

import { useTheme } from "next-themes"
import { Toaster as Sonner, type ToasterProps } from "sonner"
import { CircleCheckIcon, InfoIcon, TriangleAlertIcon, OctagonXIcon, Loader2Icon } from "lucide-react"

const Toaster = ({ ...props }: ToasterProps) => {
  const { theme = "system" } = useTheme()

  return (
    <Sonner
      theme={theme as ToasterProps["theme"]}
      className="toaster group"
      icons={{
        success: (
          <CircleCheckIcon className="size-4" />
        ),
        info: (
          <InfoIcon className="size-4" />
        ),
        warning: (
          <TriangleAlertIcon className="size-4" />
        ),
        error: (
          <OctagonXIcon className="size-4" />
        ),
        loading: (
          <Loader2Icon className="size-4 animate-spin" />
        ),
      }}
      /* Project-owned divergence from the registry output; re-adding this
         component reverts it silently. Every entry has to be inline: Sonner
         declares its own defaults on this same element via
         `[data-sonner-toaster][data-sonner-theme='light'|'dark']` and appends
         its stylesheet after Next's, so only an inline property wins
         independently of sheet order. `fontFamily` is the same problem in
         reverse — Sonner sets a `ui-sans-serif` stack on this element, which
         defeats inheritance from `html`, so every toast would render in the OS
         font instead of Geist. `--warning-border` is deliberately the
         foreground rather than the surface, because Sonner paints the close
         button from these three variables and it sits half outside the toast,
         where an amber edge on the page background falls under the 3:1 minimum
         for a control boundary. */
      style={
        {
          "--normal-bg": "var(--popover)",
          "--normal-text": "var(--popover-foreground)",
          "--normal-border": "var(--border)",
          "--warning-bg": "var(--warning)",
          "--warning-text": "var(--warning-foreground)",
          "--warning-border": "var(--warning-foreground)",
          "--border-radius": "var(--radius)",
          fontFamily: "var(--font-sans)",
        } as React.CSSProperties
      }
      toastOptions={{
        classNames: {
          toast: "cn-toast",
        },
      }}
      {...props}
    />
  )
}

export { Toaster }
