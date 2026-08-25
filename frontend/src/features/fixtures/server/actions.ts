"use server";

import { z } from "zod";

import { getFixturePredictions } from "@/features/fixtures/server/get-fixture-predictions";
import type { FixturePredictionsResult } from "@/features/fixtures/types/prediction";

const MALFORMED_REASON = "The predictions request could not be read.";

const fixtureIdSchema = z.number().int().positive();

/**
 * Reads one fixture's prediction probabilities on behalf of the browser.
 *
 * @remarks
 * The panel is opened by a click, and the probabilities are worth fetching only
 * once somebody asks for them: a day's list is dozens of rows, and reading every
 * row's predictions to render a collapsed toggle would be dozens of
 * authenticated round trips for data nobody looked at. An action is what lets
 * the read stay on the server while the decision to make it stays in the
 * browser.
 *
 * This module is deliberately *not* marked `server-only`. A client component
 * imports it, which is the entire mechanism: the marker would throw at build
 * time and the boundary is already enforced by `"use server"`, which compiles
 * the body away from the bundle and leaves a reference behind.
 *
 * The argument is typed `unknown` because a Server Action is a public endpoint.
 * Next.js exposes it at a stable identifier and anybody may post to it with any
 * body, so the fixture identifier is validated on arrival rather than trusted
 * from the component that was supposed to have sent it. A malformed payload
 * returns the unavailable branch rather than throwing, because the failure a
 * visitor can see must read the same whether the cause was a bad request or an
 * unreachable API.
 *
 * @param payload - Fixture identifier sent by the caller, validated here.
 * @returns The fixture's predictions, or the reason they are unavailable.
 */
export async function loadFixturePredictionsAction(
  payload: unknown,
): Promise<FixturePredictionsResult> {
  const requested = fixtureIdSchema.safeParse(payload);

  if (!requested.success) {
    return { loaded: false, reason: MALFORMED_REASON };
  }

  return getFixturePredictions(requested.data);
}
