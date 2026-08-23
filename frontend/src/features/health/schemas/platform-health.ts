import { z } from "zod";

/**
 * Wire contract of `GET /api/v1/health` exposed by the Tactiqo backend.
 *
 * @remarks
 * This schema mirrors the transport payload only. Product code consumes the
 * normalized `PlatformHealth` contract instead, so a backend field rename never
 * leaks into components.
 */
export const platformHealthPayloadSchema = z.object({
  status: z.enum(["ok", "degraded"]),
  version: z.string().min(1),
  database: z.enum(["ok", "unavailable"]),
  cache: z.enum(["ok", "unavailable"]),
});
