import { z } from "zod";

import { authenticatedUserPayloadSchema } from "@/features/auth/schemas/authenticated-user";

/**
 * Wire contract of `POST /api/v1/auth/login` exposed by the Tactiqo backend.
 *
 * @remarks
 * `token` is opaque to this application: it is forwarded as a bearer credential
 * and never parsed. `expires_at` is an ISO 8601 UTC timestamp and is what gives
 * the session cookie the same lifetime the backend recorded, so the browser and
 * the database cannot disagree about when the session ends.
 */
export const signInPayloadSchema = z.object({
  token: z.string().min(1),
  expires_at: z.iso.datetime(),
  user: authenticatedUserPayloadSchema,
});
