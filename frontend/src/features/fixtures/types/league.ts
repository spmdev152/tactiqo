/**
 * A competition the platform covers, in product terms.
 *
 * @remarks
 * `id` is the internal primary key, never the provider's identifier: it is the
 * value the `league` search parameter carries and the one the backend accepts,
 * so a change of provider cannot invalidate a bookmarked URL.
 */
export interface League {
  /** Internal league identifier. */
  readonly id: number;

  /** Full competition name, such as `Premier League`. */
  readonly name: string;

  /** Abbreviated name, empty when the competition has none. */
  readonly shortCode: string;

  /** Absolute URL of the competition logo, empty when none is published. */
  readonly logoUrl: string;

  /** Country the competition is played in. */
  readonly countryName: string;

  /** Absolute URL of the country flag, empty when none is published. */
  readonly countryFlagUrl: string;
}

/**
 * Outcome of asking the backend for the covered competitions.
 *
 * @remarks
 * A discriminated union rather than a thrown error or an empty array. The
 * fixtures route renders three surfaces from one request, and an empty list is
 * a legitimate answer that must not be confused with an unreachable API, so the
 * distinction has to survive as far as the component that shows it.
 */
export type LeaguesResult =
  | {
      readonly loaded: true;
      readonly leagues: readonly League[];
    }
  | {
      readonly loaded: false;
      readonly reason: string;
    };
