import { z } from "zod";

import {
  PREDICTION_MARKETS,
  PREDICTION_RELIABILITIES,
  PREDICTION_SELECTIONS,
} from "@/features/fixtures/domain/prediction-markets";

/**
 * Wire contract of one selection's probability.
 *
 * @remarks
 * The bounds are validated rather than assumed, because every consumer of this
 * number treats it as a percentage of a bar's width. A value the backend should
 * never send is cheaper to refuse here than to find later as a bar overflowing
 * its own row.
 */
export const predictionSelectionPayloadSchema = z.object({
  selection: z.enum(PREDICTION_SELECTIONS),
  probability: z.number().min(0).max(100),
});

/**
 * Wire contract of one market inside `GET /api/v1/fixtures/{id}/predictions`.
 *
 * @remarks
 * The grade and the hit ratio are independently nullable here even though the
 * backend writes them together, because a schema states what the transport may
 * carry and the two are genuinely absent for the markets the provider does not
 * grade at all.
 *
 * The hit ratio is a fraction of one where the probability is a percentage of a
 * hundred. That asymmetry is the provider's, kept rather than normalized away:
 * the two numbers answer different questions, and rescaling one would invite
 * reading a model's record as another probability.
 */
export const predictionMarketPayloadSchema = z.object({
  market: z.enum(PREDICTION_MARKETS),
  reliability: z.enum(PREDICTION_RELIABILITIES).nullable(),
  hit_ratio: z.number().min(0).max(1).nullable(),
  selections: z.array(predictionSelectionPayloadSchema),
});

/**
 * Wire contract of the `GET /api/v1/fixtures/{id}/predictions` response body.
 *
 * @remarks
 * `synchronized_at` is validated as an ISO-8601 instant with an offset rather
 * than as a plain string, for the same reason the fixtures schema validates the
 * kick-off that way: the field names an absolute moment, and a value with no
 * offset would be read differently by the server and the browser. Here the
 * mismatch would surface as predictions claiming to be an hour staler or
 * fresher than they are.
 *
 * It is nullable, and null is the ordinary answer. A fixture the model has not
 * reached carries no stamp and no markets, which is a fixture with nothing to
 * show rather than a fixture the platform failed to read.
 */
export const fixturePredictionsPayloadSchema = z.object({
  fixture_id: z.number().int().positive(),
  synchronized_at: z.iso.datetime({ offset: true }).nullable(),
  markets: z.array(predictionMarketPayloadSchema),
});

/**
 * Decoded shape of one selection's probability as the transport carries it.
 */
export type PredictionSelectionPayload = z.infer<
  typeof predictionSelectionPayloadSchema
>;

/**
 * Decoded shape of one market as the transport carries it.
 */
export type PredictionMarketPayload = z.infer<
  typeof predictionMarketPayloadSchema
>;

/**
 * Decoded shape of one fixture's predictions as the transport carries them.
 */
export type FixturePredictionsPayload = z.infer<
  typeof fixturePredictionsPayloadSchema
>;
