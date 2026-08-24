/**
 * Cookie the sidebar primitive writes its expanded or collapsed state to.
 *
 * @remarks
 * The name is declared privately inside `src/components/ui/sidebar.tsx` and is
 * not exported, so it is mirrored here rather than imported. Reading it on the
 * server is the only way the first paint can match the state the visitor left
 * the sidebar in; without it the shell renders expanded and snaps shut after
 * hydration.
 *
 * Keep the two in step. A rename in the generated primitive degrades silently
 * to "always expanded on first paint" rather than failing.
 */
export const SIDEBAR_STATE_COOKIE_NAME = "sidebar_state";

/**
 * The only cookie value that means the visitor collapsed the sidebar.
 */
export const SIDEBAR_COLLAPSED_STATE = "false";
