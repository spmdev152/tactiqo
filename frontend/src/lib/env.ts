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
