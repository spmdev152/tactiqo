import {
  fixtureFormPayloadSchema,
  type TeamFormPayload,
} from "@/features/fixtures/schemas/form";
import type {
  FixtureFormResult,
  TeamForm,
} from "@/features/fixtures/types/form";

const CONTRACT_MISMATCH_REASON =
  "The API returned a payload that does not match the form contract.";

/**
 * Normalizes one decoded side of the fixture into the product contract.
 *
 * @param payload - One team's form as the transport carries it.
 * @returns The normalized team form.
 */
function toTeamForm(payload: TeamFormPayload): TeamForm {
  return {
    teamId: payload.team_id,
    samples: payload.samples.map((sample) => ({
      range: sample.range,
      scope: sample.scope,
      matchesCounted: sample.matches_counted,
      metrics: sample.metrics.map((metric) => ({
        metric: metric.metric,
        value: metric.value,
        opposedValue: metric.opposed_value,
      })),
    })),
  };
}

/**
 * Normalizes a raw form response body into the product result.
 *
 * @remarks
 * The synchronization stamp is turned into a `Date` here and stays one from
 * this point on, so no component parses a timestamp of its own and none can
 * mistake the transport format for the value. It stays `null` when the backend
 * sent none, which is a fixture with no completed match behind either side
 * rather than a fixture read at the epoch.
 *
 * The backend orders the samples, each sample's metrics, and the families, and
 * every one of those orders is preserved rather than re-derived. All three are
 * product decisions — windows widen, a family's metrics read in a chosen
 * sequence, families run from result to discipline — and re-sorting here would
 * be a second definition of them, free to diverge silently from the one the API
 * publishes.
 *
 * A payload that does not decode is reported as a contract mismatch rather than
 * as an absence of form. An absence is a real, common answer in August, so
 * collapsing the two would turn a schema change into a fixture that quietly
 * claims neither side has played.
 *
 * Decoding is deliberately asymmetric about what "does not decode" means, and
 * the schema is where the two halves are drawn. An *additive* change degrades to
 * rendering what the platform understands: a metric, a window, or a family the
 * frontend has no name for is dropped, because `api` and `web` ship separately
 * and refusing the payload would take twenty-four decoded figures down with the
 * twenty-fifth. A *structural* change still fails loudly here, because a payload
 * whose shape has moved cannot be partially believed.
 *
 * @param payload - Decoded JSON body returned by
 * `GET /api/v1/fixtures/{id}/form`.
 * @returns The normalized form, or the reason it is unavailable.
 */
export function toFixtureForm(payload: unknown): FixtureFormResult {
  const decoded = fixtureFormPayloadSchema.safeParse(payload);

  if (!decoded.success) {
    return { loaded: false, reason: CONTRACT_MISMATCH_REASON };
  }

  const stamp = decoded.data.synchronized_at;

  return {
    loaded: true,
    form: {
      fixtureId: decoded.data.fixture_id,
      synchronizedAt: stamp === null ? null : new Date(stamp),
      home: toTeamForm(decoded.data.home),
      away: toTeamForm(decoded.data.away),
      families: decoded.data.families.map((family) => ({
        family: family.family,
        metrics: family.metrics,
      })),
    },
  };
}
