import { SiteHeader } from "@/components/site-header";

/**
 * Props of {@link PublicLayout}.
 */
interface PublicLayoutProps {
  /** Public route subtree rendered below the header. */
  readonly children: React.ReactNode;
}

/**
 * Wraps every public route in the plain header.
 *
 * @remarks
 * The counterpart of the authenticated group: the same wordmark and theme
 * switch, with no navigation, because a visitor without a session has nowhere
 * inside the application to go.
 *
 * @returns The public shell tree.
 */
export default function PublicLayout({ children }: PublicLayoutProps) {
  return (
    <>
      <SiteHeader />

      {children}
    </>
  );
}
