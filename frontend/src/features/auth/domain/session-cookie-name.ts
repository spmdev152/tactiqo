/**
 * Name of the single cookie that carries the Tactiqo session token.
 *
 * @remarks
 * It sits in `domain/` rather than beside the cookie reader and writer because
 * `src/proxy.ts` needs it and runs outside the React Server environment, where
 * importing a `server-only` module throws. Every module in `server/` is either
 * marked `server-only` or is a `"use server"` action boundary, so the name has
 * to live where every runtime can reach it.
 */
export const SESSION_COOKIE_NAME = "tactiqo_session";
