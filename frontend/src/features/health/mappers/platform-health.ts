import { platformHealthPayloadSchema } from "@/features/health/schemas/platform-health";
import type {
  DependencyState,
  PlatformHealth,
} from "@/features/health/types/platform-health";

const DEPENDENCY_STATES: Record<"ok" | "unavailable", DependencyState> = {
  ok: "operational",
  unavailable: "unavailable",
};

/**
 * Normalizes a raw backend health payload into the product health contract.
 *
 * @remarks
 * An unrecognized payload is not coerced into a healthy state: it maps to the
 * unreported branch so the interface can surface the mismatch instead of
 * displaying invented data.
 *
 * @param payload - Decoded JSON body returned by `GET /api/v1/health`.
 * @returns The normalized platform health.
 *
 * @example
 * ```ts
 * toPlatformHealth({
 *   status: "degraded",
 *   version: "1.0.0",
 *   database: "ok",
 *   cache: "unavailable",
 * });
 * ```
 */
export function toPlatformHealth(payload: unknown): PlatformHealth {
  const result = platformHealthPayloadSchema.safeParse(payload);

  if (!result.success) {
    return {
      reported: false,
      reason:
        "The API returned a payload that does not match the health contract.",
    };
  }

  const { status, version, database, cache } = result.data;

  return {
    reported: true,
    status: status === "ok" ? "operational" : "degraded",
    version,
    database: DEPENDENCY_STATES[database],
    cache: DEPENDENCY_STATES[cache],
  };
}
