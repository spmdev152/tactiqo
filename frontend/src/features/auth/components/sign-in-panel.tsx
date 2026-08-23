import darkArtwork from "@/features/auth/assets/sign-in-panel-dark.webp";
import lightArtwork from "@/features/auth/assets/sign-in-panel-light.webp";

/**
 * Props of {@link SignInPanel}.
 */
export interface SignInPanelProps {
  /** Utility classes controlling where the panel appears and at which breakpoints. */
  readonly className?: string;
}

/**
 * Renders the illustrated half of the sign-in screen.
 *
 * @remarks
 * Both variants are in the markup at once and CSS decides which one shows,
 * because the theme is a class the visitor can override rather than an operating
 * system preference. A `<picture>` keyed on `prefers-color-scheme` would ignore
 * that override, and the server cannot know the resolved theme, so it cannot pick
 * one either. The `dark` class is on the root element before the first paint, so
 * the correct artwork is the one that appears rather than one that replaces
 * something else a frame later.
 *
 * The artwork is a background image rather than `next/image`, which is the only
 * way to keep that arrangement from wasting bandwidth. A `display: none` element
 * never fetches its background, whereas a hidden `<img loading="lazy">` is still
 * requested: measured over the network, the `next/image` version pulled both
 * variants on every load, including on a phone where this whole panel is
 * `display: none` and neither is ever seen. Now a phone fetches nothing, a
 * desktop fetches only the active theme, and the other arrives the first time
 * somebody switches, with `bg-sidebar` standing in until it lands.
 *
 * The URL comes from a static import rather than `public/` so it keeps the
 * content hash and the immutable caching that go with it, and the inline style
 * exists because a Tailwind class cannot carry that generated path.
 *
 * The scrim exists so the headline stays readable over either variant: the light
 * artwork is pale where the type sits and the dark one is not, and one gradient
 * covering both beats maintaining two sets of text colours.
 *
 * @returns The illustrated panel tree.
 */
export function SignInPanel({ className }: SignInPanelProps) {
  return (
    <aside className={className}>
      <div className="relative h-full overflow-hidden bg-sidebar">
        <div
          aria-hidden="true"
          className="absolute inset-0 bg-cover bg-center dark:hidden"
          style={{ backgroundImage: `url(${lightArtwork.src})` }}
        />

        <div
          aria-hidden="true"
          className="absolute inset-0 hidden bg-cover bg-center dark:block"
          style={{ backgroundImage: `url(${darkArtwork.src})` }}
        />

        <div
          aria-hidden="true"
          className="absolute inset-x-0 bottom-0 h-2/5 bg-gradient-to-t from-sidebar via-sidebar/70 to-transparent"
        />

        <div className="relative flex h-full flex-col justify-end gap-6 p-10 xl:p-14">
          <span aria-hidden="true" className="h-px w-24 bg-primary" />

          <p className="font-display text-4xl leading-[0.92] font-bold tracking-tight text-balance uppercase xl:text-6xl">
            Read the evidence before the whistle
          </p>
        </div>
      </div>
    </aside>
  );
}
