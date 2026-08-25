import type { FixtureStatus } from "@/features/fixtures/domain/fixture-status";
import type { League } from "@/features/fixtures/types/league";

/**
 * One of the two sides of a fixture, in product terms.
 */
export interface FixtureTeam {
  /** Internal team identifier. */
  readonly id: number;

  /** Full club name, such as `Nottingham Forest`. */
  readonly name: string;

  /** Three-letter abbreviation, empty when the club has none. */
  readonly shortCode: string;

  /** Absolute URL of the club crest, empty when none is published. */
  readonly crestUrl: string;
}

/**
 * Goals both sides scored.
 *
 * @remarks
 * A pair rather than two nullable numbers on the fixture, so a half-written
 * score cannot be represented at all. The API carries the two counts
 * separately and the mapper is what turns them into this.
 */
export interface FixtureScore {
  /** Goals the home side scored. */
  readonly home: number;

  /** Goals the away side scored. */
  readonly away: number;
}

/**
 * A match, in product terms.
 */
export interface Fixture {
  /** Internal fixture identifier. */
  readonly id: number;

  /** Instant the match kicks off, always an absolute point in time. */
  readonly kickoffAt: Date;

  /** State the match is in. */
  readonly status: FixtureStatus;

  /** Goals scored, `null` while the platform has no score for the match. */
  readonly score: FixtureScore | null;

  /** Competition the match belongs to. */
  readonly league: League;

  /** Side playing at home. */
  readonly homeTeam: FixtureTeam;

  /** Side playing away. */
  readonly awayTeam: FixtureTeam;

  /** Whether the platform holds prediction probabilities for the match. */
  readonly hasPredictions: boolean;
}

/**
 * Outcome of asking the backend for the fixtures of one day.
 *
 * @remarks
 * The empty and the unavailable answers are different products: the first says
 * there is no football, the second says the platform cannot tell. Collapsing
 * them into an empty array would show "no fixtures today" during an outage, so
 * the branch is carried in the type and the list component has to handle both.
 */
export type FixturesResult =
  | {
      readonly loaded: true;
      readonly fixtures: readonly Fixture[];
    }
  | {
      readonly loaded: false;
      readonly reason: string;
    };
