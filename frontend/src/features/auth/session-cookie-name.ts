/**
 * Name of the single cookie that carries the Tactiqo session token.
 *
 * @remarks
 * It lives in its own module rather than beside the cookie reader and writer
 * because `src/proxy.ts` needs it and runs outside the React Server
 * environment, where importing a `server-only` module throws.
 */
export const SESSION_COOKIE_NAME = "tactiqo_session";
