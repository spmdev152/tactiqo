import { z } from "zod";

/**
 * Wire contract of the user object returned by the Tactiqo authentication API.
 *
 * @remarks
 * This schema mirrors the transport payload only, down to its snake_case
 * naming. Product code consumes the normalized `AuthenticatedUser` contract
 * instead, so a backend field rename never leaks into components.
 *
 * `full_name` is intentionally not constrained to a non-empty string: the
 * backend publishes an empty display name as a valid value.
 */
export const authenticatedUserPayloadSchema = z.object({
  id: z.int().positive(),
  email: z.email(),
  full_name: z.string(),
});

/**
 * Decoded shape of a user object that satisfied the wire contract.
 */
export type AuthenticatedUserPayload = z.infer<
  typeof authenticatedUserPayloadSchema
>;
