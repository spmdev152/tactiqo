import type {
  PredictionMarket,
  PredictionReliability,
  PredictionSelection,
} from "@/features/fixtures/domain/prediction-markets";

/**
 * The probability the provider's model gives one selection.
 */
export interface PredictionSelectionProbability {
  /** Outcome the probability belongs to. */
  readonly selection: PredictionSelection;

  /** Probability as a percentage between `0` and `100`. */
  readonly probability: number;
}

/**
 * One market's probabilities, together with how far the model can be trusted
 * on that market in this competition.
 *
 * @remarks
 * The grade is carried beside the probabilities rather than shown separately,
 * because a probability with no sense of the model's record on that market is
 * the number most likely to be over-read. It is nullable and often null: the
 * provider grades nine markets and publishes nothing at all for double chance
 * or over/under 4.5, so an absent grade is the ordinary state rather than a
 * failure, and the panel has to say "not graded" instead of implying a poor one.
 */
export interface PredictionMarketProbabilities {
  /** Market the probabilities belong to. */
  readonly market: PredictionMarket;

  /** Historical grade of the model on this market, `null` when ungraded. */
  readonly reliability: PredictionReliability | null;

  /** Historical hit ratio between `0` and `1`, `null` when ungraded. */
  readonly hitRatio: number | null;

  /** Probabilities of the market's outcomes, in the order the API sent them. */
  readonly selections: readonly PredictionSelectionProbability[];
}

/**
 * Every prediction the platform holds for one fixture.
 *
 * @remarks
 * An available-but-empty state is representable on purpose, as `synchronizedAt`
 * of `null` with no markets. Sportmonks publishes nothing for a fixture more
 * than roughly a fortnight out, and that is the common case rather than an
 * edge: the panel has to say the model has not run yet, which is different from
 * saying the platform could not ask.
 */
export interface FixturePredictions {
  /** Internal fixture identifier the predictions belong to. */
  readonly fixtureId: number;

  /** Instant the platform last read these predictions, `null` when unread. */
  readonly synchronizedAt: Date | null;

  /** Markets with published probabilities, in the order the API sent them. */
  readonly markets: readonly PredictionMarketProbabilities[];
}

/**
 * Outcome of asking the backend for one fixture's predictions.
 *
 * @remarks
 * Three answers rather than two, and the third is why this is a union. The
 * platform can have predictions, can have none yet, or can be unable to tell —
 * and only the last is a failure. The first two are both the `loaded` branch,
 * separated inside {@link FixturePredictions}, so an outage can never render as
 * "no predictions yet" and a fixture the model has not reached can never render
 * as an error the visitor is invited to retry.
 */
export type FixturePredictionsResult =
  | {
      readonly loaded: true;
      readonly predictions: FixturePredictions;
    }
  | {
      readonly loaded: false;
      readonly reason: string;
    };
