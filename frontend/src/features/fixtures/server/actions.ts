"use server";

import { z } from "zod";

import { getFixtureForm } from "@/features/fixtures/server/get-fixture-form";
import { getFixturePredictions } from "@/features/fixtures/server/get-fixture-predictions";
import type { FixtureFormResult } from "@/features/fixtures/types/form";
import type { FixturePredictionsResult } from "@/features/fixtures/types/prediction";

const MALFORMED_PREDICTIONS_REASON =
  "The predictions request could not be read.";

const MALFORMED_FORM_REASON = "The form request could not be read.";

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
    return { loaded: false, reason: MALFORMED_PREDICTIONS_REASON };
  }

  return getFixturePredictions(requested.data);
}

/**
 * Reads one fixture's pre-match form on behalf of the browser.
 *
 * @remarks
 * A second action rather than one that reads both, because the panel's two tabs
 * are opened independently and most visitors open one of them. Answering with
 * both would make the cheaper tab pay for the larger payload, and a fixture
 * whose form read failed would take its probabilities down with it.
 *
 * Everything the predictions action documents applies here unchanged: the
 * module is deliberately not marked `server-only` because a client component
 * imports it, the argument is typed `unknown` because a Server Action is a
 * public endpoint anybody may post to, and a malformed payload returns the
 * unavailable branch rather than throwing.
 *
 * @param payload - Fixture identifier sent by the caller, validated here.
 * @returns The fixture's form, or the reason it is unavailable.
 */
export async function loadFixtureFormAction(
  payload: unknown,
): Promise<FixtureFormResult> {
  const requested = fixtureIdSchema.safeParse(payload);

  if (!requested.success) {
    return { loaded: false, reason: MALFORMED_FORM_REASON };
  }

  return getFixtureForm(requested.data);
}
