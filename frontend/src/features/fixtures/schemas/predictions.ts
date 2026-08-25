import { z } from "zod";

import {
  PREDICTION_MARKETS,
  PREDICTION_RELIABILITIES,
  PREDICTION_SELECTIONS,
} from "@/features/fixtures/domain/prediction-markets";

const KNOWN_MARKETS: readonly string[] = PREDICTION_MARKETS;

const KNOWN_SELECTIONS: readonly string[] = PREDICTION_SELECTIONS;

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

const unrecognizedSelectionPayloadSchema = z
  .object({
    selection: z.string().refine((name) => !KNOWN_SELECTIONS.includes(name)),
  })
  .transform(() => null);

/**
 * Wire contract of one market's selections, tolerant of an unknown outcome.
 *
 * @remarks
 * A selection the platform has no name for is dropped rather than fatal. The
 * alternative loses the market it was published in, and with it every outcome
 * that decoded perfectly, over one row nothing could have labelled.
 *
 * Tolerance stops at the vocabulary. The second branch matches only an object
 * whose `selection` is a string outside the published list, so an outcome that
 * is recognized but malformed — a probability of `120`, a missing field — fails
 * both branches and takes the payload down with it, which is what a structural
 * change to the contract has to do.
 */
const predictionSelectionsPayloadSchema = z
  .array(
    z.union([
      predictionSelectionPayloadSchema,
      unrecognizedSelectionPayloadSchema,
    ]),
  )
  .transform((entries) => entries.filter((entry) => entry !== null));

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
  selections: predictionSelectionsPayloadSchema,
});

const unrecognizedMarketPayloadSchema = z
  .object({
    market: z.string().refine((name) => !KNOWN_MARKETS.includes(name)),
  })
  .transform(() => null);

/**
 * Wire contract of a fixture's markets, tolerant of an unknown market.
 *
 * @remarks
 * `api` and `web` are separate images released by separate jobs, so a backend
 * that starts publishing a twelfth market is a state this contract has to
 * survive rather than one to rule out. Refusing the array would leave every
 * panel in the product reading "unavailable" until the frontend shipped, over
 * one market out of eleven that decoded.
 *
 * The same limit as the selections above applies, and for the same reason: only
 * a market named outside the published vocabulary is dropped. A renamed field
 * or a retyped one is a structural break and still fails loudly, because a
 * silently emptied list of markets is indistinguishable from a fixture the
 * provider's model has not reached.
 */
const predictionMarketsPayloadSchema = z
  .array(
    z.union([predictionMarketPayloadSchema, unrecognizedMarketPayloadSchema]),
  )
  .transform((entries) => entries.filter((entry) => entry !== null));

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
  markets: predictionMarketsPayloadSchema,
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
