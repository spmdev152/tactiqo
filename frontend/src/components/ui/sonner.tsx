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
         font instead of Geist.

         The three close-button properties are Sonner's own positioning API.
         They move the control from the top-left corner, where it straddles the
         edge as a bordered circle, to inside the top-right corner with room to
         breathe. Because it no longer overlaps the page background, the border
         token can stay the surface: nothing paints a control boundary against
         anything but the toast itself. The circle is stripped in `globals.css`,
         which is where a descendant of the toast has to be styled. */
      style={
        {
          "--normal-bg": "var(--popover)",
          "--normal-text": "var(--popover-foreground)",
          "--normal-border": "var(--border)",
          "--warning-bg": "var(--warning)",
          "--warning-text": "var(--warning-foreground)",
          "--warning-border": "var(--warning)",
          "--border-radius": "var(--radius)",
          "--toast-close-button-start": "unset",
          "--toast-close-button-end": "0.5rem",
          "--toast-close-button-transform": "translateY(0.5rem)",
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
