import type { AuthenticatedUserPayload } from "@/features/auth/schemas/authenticated-user";
import type { AuthenticatedUser } from "@/features/auth/types/authenticated-user";

/**
 * Normalizes a validated backend user payload into the product contract.
 *
 * @remarks
 * Total by construction: it accepts a payload that already satisfied
 * `authenticatedUserPayloadSchema`, so validation stays at the transport
 * boundary and this function has no failure branch to invent. The only work it
 * does is renaming `full_name` to the frontend casing, and an empty name is
 * carried through untouched rather than replaced by a placeholder.
 *
 * @param payload - Decoded user object returned by the authentication API.
 * @returns The normalized authenticated user.
 *
 * @example
 * ```ts
 * toAuthenticatedUser({ id: 1, email: "ada@example.com", full_name: "Ada" });
 * // -> { id: 1, email: "ada@example.com", fullName: "Ada" }
 * ```
 */
export function toAuthenticatedUser(
  payload: AuthenticatedUserPayload,
): AuthenticatedUser {
  return {
    id: payload.id,
    email: payload.email,
    fullName: payload.full_name,
  };
}
