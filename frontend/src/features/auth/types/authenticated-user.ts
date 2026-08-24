/**
 * Person the current session belongs to, in product terms.
 *
 * @remarks
 * `fullName` may legitimately be an empty string: the backend stores a display
 * name that an account is not required to fill in, so the interface falls back
 * to the e-mail address instead of treating the empty value as missing data.
 */
export interface AuthenticatedUser {
  readonly id: number;
  readonly email: string;
  readonly fullName: string;
}
