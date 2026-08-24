import "server-only";

/**
 * Resolves the server-side base URL of the Tactiqo backend API.
 *
 * @remarks
 * The base URL is intentionally server-only: browser code must never talk to
 * the backend API or the upstream provider directly. The value is read at
 * request time so container orchestration can inject it without a rebuild.
 *
 * @returns The configured base URL without trailing slashes, or `null` when
 * `BACKEND_API_BASE_URL` is unset or blank.
 */
export function getBackendApiBaseUrl(): string | null {
  const configuredBaseUrl = process.env.BACKEND_API_BASE_URL?.trim();

  if (!configuredBaseUrl) {
    return null;
  }

  return configuredBaseUrl.replace(/\/+$/, "");
}

/**
 * Reports whether the session cookie must be issued without `Secure`.
 *
 * @remarks
 * The opt-out is explicit rather than derived from `NODE_ENV`, because `Secure`
 * is a transport control and must not depend on which command built the bundle.
 * `frontend/Dockerfile` pins `NODE_ENV=development`, so a derivation from the
 * build mode would ship a session cookie with no `Secure` attribute to the
 * first deployed image and say nothing about it. Only the exact string `"true"`
 * opts out, so a typo, a blank value, or an unset variable all keep the cookie
 * secure.
 *
 * @returns `true` when `SESSION_COOKIE_INSECURE` is exactly `"true"`, which is
 * the only configuration that drops `Secure`.
 */
export function isSessionCookieInsecure(): boolean {
  return process.env.SESSION_COOKIE_INSECURE === "true";
}
