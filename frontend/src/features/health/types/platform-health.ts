/**
 * Availability of a single backend dependency, expressed in product terms.
 */
export type DependencyState = "operational" | "unavailable";

/**
 * Overall backend availability when the platform answered a health probe.
 *
 * @remarks
 * `degraded` means the backend is serving traffic while at least one of its
 * dependencies is down.
 */
export type PlatformStatus = "operational" | "degraded";

/**
 * Health of the backend platform as reported by a successful health probe.
 */
export interface ReportedPlatformHealth {
  readonly reported: true;
  readonly status: PlatformStatus;
  readonly version: string;
  readonly database: DependencyState;
  readonly cache: DependencyState;
}

/**
 * Health of the backend platform when no trustworthy report could be obtained.
 *
 * @remarks
 * Covers an unreachable API, an error response, and a payload that does not
 * match the published health contract. The product never guesses a status in
 * this case.
 */
export interface UnreportedPlatformHealth {
  readonly reported: false;
  readonly reason: string;
}

/**
 * Normalized product contract for backend platform health.
 *
 * @remarks
 * Consumers must handle the unreported branch explicitly; the discriminated
 * union makes an omitted unavailable state a type error.
 */
export type PlatformHealth = ReportedPlatformHealth | UnreportedPlatformHealth;
