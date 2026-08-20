/**
 * The test queue, over HTTP.
 *
 * 🔴 THIS ENDPOINT DELIBERATELY DOES NOT RETURN A TRAFFIC LIGHT, AND THE
 * SCREEN MUST NOT INVENT ONE.
 *
 * `list_tests` says so in its own docstring: deriving a disposition per
 * row would mean a statistics query per test, and *"a list view that
 * silently costs N round trips is how a queue becomes unusable at fifty
 * rows"*. So it returns the **five stored axes** and leaves the derived
 * `display_color` / `final_status` to the detail view, where they can be
 * computed from real replicates rather than guessed from a subset.
 *
 * That is a trap for a list screen, and it is the same shape as the S2
 * gaps recorded as I14–I17. `CLAUDE.md` §10 is emphatic that status is
 * **derived and server-owned** — *"never a field a user picks"* — and the
 * ordered first-match-wins algorithm needs `replicates_valid`,
 * `cv > method.cv_limit`, `margin < warning_threshold` and `trend_alert`,
 * three of which this endpoint does not return.
 *
 * A browser that coloured these rows would therefore be doing the one
 * thing the rule forbids: deciding a traffic light on the client, from an
 * incomplete input. **So this screen renders the axes as facts and shows
 * no colour at all**, and says why on the page.
 *
 * The axes, per §10:
 *   execution_status  not_started · in_progress · complete · abandoned
 *   validity_status   valid · minor_deviation · invalid
 *   calculated_result pass · fail · inconclusive · improved ·
 *                     no_significant_change · worsened   (NULL until run)
 *   review_state      awaiting_review · under_review · returned_for_correction ·
 *                     retest_requested · escalated · reviewed
 *   approval_state    not_required · pending · conditionally_approved ·
 *                     approved · rejected
 */

import { z } from "zod";

import { apiRequest, type ApiCredentials } from "./client";

export const testSchema = z.object({
  id: z.string(),
  test_number: z.string(),
  project_id: z.string(),
  // The five stored axes. Four are NOT NULL with defaults in the schema;
  // `calculated_result` is the only nullable one — it has no value until
  // the test has actually been evaluated, and NULL there means
  // "not yet", never "inconclusive".
  execution_status: z.string(),
  validity_status: z.string(),
  calculated_result: z.string().nullable(),
  review_state: z.string(),
  approval_state: z.string(),
  // Orthogonal to each other and to the axes above (§10): a green
  // SCREENING test is never qualification evidence.
  test_purpose: z.string(),
  authority_level: z.string(),
  final_confirmed: z.boolean(),
  // DATE, nullable — a test that has not been scheduled has none.
  planned_for: z.string().nullable(),
  executed_at: z.string().nullable(),
  updated_at: z.string(),
  // From the join to `test_methods`, all NOT NULL there.
  method_code: z.string(),
  method_name: z.string(),
  canonical_unit: z.string(),
  replicates_required: z.number(),
  // From the join to `laboratory.samples` — the physical specimen the
  // result is traceable to. §5's referential traceability rule: no test
  // result without traceability to the physical sample.
  sample_number: z.string(),
  // A COUNT of non-excluded replicates, not a measurement.
  replicates_valid: z.number(),
});

export type Test = z.infer<typeof testSchema>;

const testList = z.array(testSchema);

export function fetchTests(
  credentials: ApiCredentials,
  signal?: AbortSignal,
): Promise<Test[]> {
  return apiRequest(
    { path: "/api/testing/tests", credentials, signal },
    (payload) => testList.parse(payload),
  );
}
