import { z } from "zod";

/**
 * Credentials the sign-in form collects.
 *
 * @remarks
 * One schema serves the browser and the Server Action. React Hook Form uses it
 * for immediate feedback while typing, and the action parses the same shape
 * again on arrival, because a Server Action argument is attacker-controlled and
 * browser validation is a courtesy rather than a boundary.
 *
 * The address is trimmed before it is checked so a copy-pasted value with a
 * trailing space is accepted rather than rejected as malformed.
 */
export const credentialsSchema = z.object({
  email: z
    .string()
    .trim()
    .min(1, "Enter your e-mail address.")
    .pipe(z.email("Enter a valid e-mail address.")),
  password: z.string().min(1, "Enter your password."),
});

/**
 * Credentials accepted by the sign-in Server Action.
 */
export type Credentials = z.infer<typeof credentialsSchema>;
