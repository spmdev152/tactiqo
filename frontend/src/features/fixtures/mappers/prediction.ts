import {
  fixturePredictionsPayloadSchema,
  type PredictionMarketPayload,
} from "@/features/fixtures/schemas/predictions";
import type {
  FixturePredictionsResult,
  PredictionMarketProbabilities,
} from "@/features/fixtures/types/prediction";

const CONTRACT_MISMATCH_REASON =
  "The API returned a payload that does not match the predictions contract.";

/**
 * Normalizes one decoded market payload into the product contract.
 *
 * @param payload - Market as the transport carries it.
 * @returns The normalized market.
 */
function toMarketProbabilities(
  payload: PredictionMarketPayload,
): PredictionMarketProbabilities {
  return {
    market: payload.market,
    reliability: payload.reliability,
    hitRatio: payload.hit_ratio,
    selections: payload.selections.map((selection) => ({
      selection: selection.selection,
      probability: selection.probability,
    })),
  };
}

/**
 * Normalizes a raw predictions response body into the product result.
 *
 * @remarks
 * The synchronization stamp is turned into a `Date` here and stays one from
 * this point on, so no component parses a timestamp of its own and none can
 * mistake the transport format for the value. It stays `null` when the backend
 * sent none, which is the fixture the model has not reached yet rather than a
 * fixture read at the epoch.
 *
 * The backend orders the markets and each market's selections, and that order
 * is preserved rather than re-derived. Both orders are product decisions — the
 * markets a visitor recognizes first come first, and a market's outcomes read in
 * their natural sequence — and re-sorting here would be a second definition of
 * them, free to diverge silently from the one the API publishes.
 *
 * A payload that does not decode is reported as a contract mismatch rather than
 * as an empty set of predictions. An empty set is a real, common answer, so
 * collapsing the two would turn a schema change into a fixture that quietly
 * claims the model has not run.
 *
 * Decoding is deliberately asymmetric about what "does not decode" means, and
 * the schema is where the two halves are drawn. An *additive* change degrades
 * to rendering what the platform understands: a market or a selection the
 * frontend has no name for is dropped, because `api` and `web` ship separately
 * and refusing the payload would take ten decoded markets down with the
 * eleventh. A *structural* change still fails loudly here, because a payload
 * whose shape has moved cannot be partially believed, and a market list emptied
 * without a word would render as the fixture the model has not reached.
 *
 * @param payload - Decoded JSON body returned by
 * `GET /api/v1/fixtures/{id}/predictions`.
 * @returns The normalized predictions, or the reason they are unavailable.
 */
export function toFixturePredictions(
  payload: unknown,
): FixturePredictionsResult {
  const decoded = fixturePredictionsPayloadSchema.safeParse(payload);

  if (!decoded.success) {
    return { loaded: false, reason: CONTRACT_MISMATCH_REASON };
  }

  const stamp = decoded.data.synchronized_at;

  return {
    loaded: true,
    predictions: {
      fixtureId: decoded.data.fixture_id,
      synchronizedAt: stamp === null ? null : new Date(stamp),
      markets: decoded.data.markets.map(toMarketProbabilities),
    },
  };
}
