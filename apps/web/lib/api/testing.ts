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
 *
 * ---------------------------------------------------------------------------
 * THE DETAIL HALF — added when the eight orphaned routes got a caller
 * ---------------------------------------------------------------------------
 *
 * Until this file grew its second half, `GET /api/testing/tests` was the
 * ONLY test route a browser could reach. The other eight — detail, start,
 * replicate, exclusion, completion, decision, confirmation and create —
 * existed, were tested, and no production path called any of them. A route
 * with no caller is the same defect as a table with no writer.
 *
 * 🔴 AND THE ORPHAN WAS HIDING A LIVE CORRECTNESS BUG (I84). `statistics.mean`,
 * `standard_deviation`, `cv_percent` and `automatic_evaluation.margin_percent`
 * were leaving the API as **floats**, because FastAPI's `jsonable_encoder`
 * maps `Decimal` to float and those four never passed through
 * `_decimal_strings`. Measured: `Decimal("12.500000") -> 12.5`. The same
 * defect was found and fixed for batch masses long ago; it survived here
 * only because nothing ever parsed these numbers. Fixed server-side in
 * `app/domains/testing/service.py::get_test`; typing them as `z.string()`
 * below is the client half of that contract, and a regression to float
 * now fails to parse loudly instead of rounding a measurement in silence.
 *
 * **Do not `Number()` any of them.** §4 keeps derivation on the server.
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
  // When this record was created. ⚠️ ZOD STRIPS WHAT IT DOES NOT DECLARE,
  // so the API returning the column is not enough — without this line the
  // field is silently removed before any view can render it.
  created_at: z.string(),
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

/**
 * A test method, for the planning form.
 *
 * 🔴 THIS LIST IS WHAT MAKES PLANNING A TEST POSSIBLE AT ALL. `POST /tests`
 * requires a `method_id` and nothing returned one, so a create form could
 * only have offered a bare UUID field — which is why the create route stayed
 * orphaned and the Test Module could be driven only from records a seeding
 * script had planned.
 *
 * `cv_limit` is a string (NUMERIC) and is shown because rule 6 of the traffic
 * light compares a measured CV against it: a planner choosing between two
 * methods is entitled to see which is stricter. It is displayed, never
 * compared here.
 */
export const testMethodSchema = z.object({
  id: z.string(),
  method_code: z.string(),
  name: z.string(),
  canonical_unit: z.string(),
  replicates_required: z.number(),
  cv_limit: z.string().nullable(),
  calibration_breach_policy: z.string().nullable(),
});

export type TestMethod = z.infer<typeof testMethodSchema>;

export function fetchTestMethods(
  credentials: ApiCredentials,
  signal?: AbortSignal,
): Promise<TestMethod[]> {
  return apiRequest(
    { path: "/api/testing/methods", credentials, signal },
    (payload) => z.array(testMethodSchema).parse(payload),
  );
}

// ---------------------------------------------------------------------------
// The test detail — raw replicates, statistics, and the two status fields
// ---------------------------------------------------------------------------

/**
 * One raw measurement, exactly as recorded.
 *
 * 🔴 AN EXCLUDED REPLICATE IS STILL HERE, AND THAT IS THE POINT. The route
 * refuses to delete one and says why: *"raw measurements are evidence: an
 * excluded replicate stays on the record, visibly excluded, so that 'why
 * does this test have four measurements when the method requires five'
 * remains answerable."* A screen that filtered them out would undo that.
 *
 * `measured_value` is a string — see this file's header.
 */
export const replicateSchema = z.object({
  id: z.string(),
  replicate_number: z.number(),
  measured_value: z.string(),
  unit: z.string(),
  is_excluded: z.boolean(),
  exclusion_reason: z.string().nullable(),
  observed_at: z.string().nullable(),
  notes: z.string().nullable(),
});

export type Replicate = z.infer<typeof replicateSchema>;

/**
 * Mean, sample SD and CV over the NON-excluded replicates.
 *
 * 🔴 `null` IS NOT ZERO, IN THREE SEPARATE PLACES. A single replicate has a
 * mean and **no** standard deviation — the engine returns `None` rather
 * than `0`, because zero claims "perfectly repeatable", which one
 * measurement cannot support. `cv_percent` is `null` when the mean is
 * zero, a legitimate case for a measurement centred on zero. Rendering
 * either as `0` would invent a claim, and rule 6 of the traffic light
 * compares CV against a limit — a spurious `0.0` would silently pass every
 * single-replicate test.
 *
 * `count` and `valid_count` are cardinalities, so numbers. The three
 * measurements are strings. Both halves matter.
 */
export const testStatisticsSchema = z.object({
  count: z.number(),
  valid_count: z.number(),
  mean: z.string().nullable(),
  standard_deviation: z.string().nullable(),
  cv_percent: z.string().nullable(),
});

/**
 * What the engine concluded from the numbers ALONE.
 *
 * Never displayed as the test's status. §3.3 and F31 require this shown
 * beside `final_disposition`, separately and always: *"a low-margin pass
 * awaiting approval is both a pass and not final, and one field cannot
 * say that."* A client that renders only one of them is rendering half
 * the truth.
 */
export const automaticEvaluationSchema = z.object({
  calculated_result: z.string().nullable(),
  detail: z.string(),
  margin_percent: z.string().nullable(),
});

/**
 * The traffic light, derived by the server and explained by it.
 *
 * `rule` is the number of the rule that fired, out of the fourteen ordered
 * rules in `derive_disposition`. It is returned deliberately — *"a traffic
 * light nobody can explain is a traffic light nobody trusts"* — and the
 * workspace shows it, so a disputed colour can be traced to the predicate
 * that produced it rather than argued about.
 *
 * `next_action` is non-empty for every YELLOW (§3.3: *"a yellow with no
 * explanation is a defect"*). It is nullable here because GREEN and RED
 * legitimately have none, not because a YELLOW may omit it.
 */
export const dispositionSchema = z
  .object({
    colour: z.string(),
    label: z.string(),
    reason: z.string(),
    next_action: z.string().nullable(),
    rule: z.number(),
  })
  // 🔴 THE YELLOW INVARIANT, ENFORCED RATHER THAN ASSERTED.
  //
  // `next_action` is `nullable` because GREEN and RED legitimately have none.
  // On YELLOW it is mandatory: §3.3 says *"every YELLOW states why AND what
  // the next required action is. A yellow with no explanation is a defect."*
  //
  // Codex found this stated in a comment and enforced nowhere — the schema
  // accepted the exact prohibited state, and the renderer displayed it. That
  // is this codebase's most-repeated defect (a comment asserting a rule the
  // code does not have), and the zod boundary exists precisely to catch a
  // response-contract regression. So it is a refinement now: if the engine
  // ever emits a bare amber, this fails loudly instead of rendering one.
  .refine(
    (d) => d.colour !== "yellow" || (d.next_action !== null && d.next_action.trim() !== ""),
    {
      message:
        "a YELLOW disposition must carry a next_action — a yellow with no stated " +
        "next step is a defect (DATA_MODEL.md §3.3), not a response to render",
    },
  );

export type Disposition = z.infer<typeof dispositionSchema>;

/** A recorded review decision. Append-only, and never edited in place. */
export const testDecisionSchema = z.object({
  id: z.string(),
  decision: z.string(),
  decision_stage: z.string(),
  authority_level: z.string().nullable(),
  condition_text: z.string().nullable(),
  rationale: z.string().nullable(),
  decided_by: z.string().nullable(),
  decided_at: z.string().nullable(),
});

/**
 * One rung of the snapshotted approval ladder.
 *
 * 🔴 EVERY STEP IS RETURNED, DECIDED OR NOT — and an undecided step is the
 * answer to "what requires action?" (§11), so the screen must render the
 * undecided ones rather than only the signatures collected so far.
 *
 * This is the route's IMMUTABLE SNAPSHOT (F28), not the template as it
 * stands today: editing a template can never retroactively change what a
 * live test required.
 */
export const approvalStepSchema = z.object({
  step_number: z.number(),
  parallel_group: z.number().nullable(),
  step_label: z.string(),
  permission_required: z.string().nullable(),
  is_mandatory: z.boolean(),
  must_differ_from_group: z.boolean().nullable(),
  decision: z.string().nullable(),
  condition_text: z.string().nullable(),
  rationale: z.string().nullable(),
  decided_by: z.string().nullable(),
  decided_at: z.string().nullable(),
  template_code: z.string(),
  route_status: z.string(),
});

export type ApprovalStep = z.infer<typeof approvalStepSchema>;

/**
 * The full test record.
 *
 * ⚠️ NOT A SUPERSET OF THE LIST ROW, and the two schemas are separate for
 * that reason — the same lesson `laboratory.ts` records. `get_test` returns
 * the test's own columns plus replicates, statistics, both status fields,
 * decisions and the approval route; it does **not** carry `method_code`,
 * `method_name`, `canonical_unit`, `replicates_required` or `sample_number`,
 * because those come from joins only `list_tests` performs. One shared
 * schema would be wrong in one direction or the other.
 *
 * `.passthrough()` is deliberate: the row carries columns this screen does
 * not render (`equipment_id`, `confirmed_by`, `next_approver_role` …), and
 * a strict schema would reject a response that is entirely correct.
 */
export const testDetailSchema = z
  .object({
    id: z.string(),
    test_number: z.string(),
    project_id: z.string(),
    sample_id: z.string(),
    method_id: z.string(),
    requirement_id: z.string().nullable(),
    execution_status: z.string(),
    validity_status: z.string(),
    calculated_result: z.string().nullable(),
    review_state: z.string(),
    approval_state: z.string(),
    test_purpose: z.string(),
    authority_level: z.string(),
    final_confirmed: z.boolean(),
    approval_condition: z.string().nullable(),
    next_approver_role: z.string().nullable(),
    trend_alert: z.boolean().nullable(),
    planned_for: z.string().nullable(),
    executed_at: z.string().nullable(),
    notes: z.string().nullable(),
    updated_at: z.string(),
    replicates: z.array(replicateSchema),
    statistics: testStatisticsSchema,
    automatic_evaluation: automaticEvaluationSchema,
    final_disposition: dispositionSchema,
    decisions: z.array(testDecisionSchema),
    approval_route: z.array(approvalStepSchema),
  })
  .passthrough();

export type TestDetail = z.infer<typeof testDetailSchema>;

export function fetchTest(
  credentials: ApiCredentials,
  testId: string,
  signal?: AbortSignal,
): Promise<TestDetail> {
  return apiRequest(
    { path: `/api/testing/tests/${testId}`, credentials, signal },
    (payload) => testDetailSchema.parse(payload),
  );
}

// ---------------------------------------------------------------------------
// The lifecycle — plan, execute, review, approve, confirm
// ---------------------------------------------------------------------------

export interface TestCreateRequest {
  readonly test_number: string;
  readonly sample_id: string;
  readonly method_id: string;
  readonly test_purpose?: string;
  readonly authority_level?: string;
  readonly requirement_id?: string;
  readonly planned_for?: string;
  readonly notes?: string;
}

/**
 * Plan a test against a physical sample.
 *
 * `sample_id` is required by the API and there is no route that invents one:
 * §5's traceability rule means a result exists only against a specimen that
 * was actually taken. The queue therefore offers this only against a sample
 * that exists.
 *
 * 🔴 THE 201 IS NOT A TEST, IT IS THREE COLUMNS. `create_test`'s
 * `INSERT ... RETURNING` names exactly `id, test_number, project_id`, so
 * parsing the response with `testDetailSchema` threw a validation error
 * AFTER the row had been written — a success reported as a failure, which is
 * the worst possible shape for a retry: the caller retries and creates a
 * second test. Found by Codex, latent only because nothing called this yet.
 *
 * The caller navigates to the workspace with the returned `id`, which then
 * fetches the full record.
 */
export const testCreatedSchema = z
  .object({
    id: z.string(),
    test_number: z.string(),
    project_id: z.string(),
  })
  .passthrough();

export type TestCreated = z.infer<typeof testCreatedSchema>;

export function createTest(
  credentials: ApiCredentials,
  request: TestCreateRequest,
): Promise<TestCreated> {
  return apiRequest(
    { path: "/api/testing/tests", method: "POST", body: request, credentials },
    (payload) => testCreatedSchema.parse(payload),
  );
}

/** Begin execution. */
export function startTest(
  credentials: ApiCredentials,
  testId: string,
): Promise<unknown> {
  return apiRequest(
    {
      path: `/api/testing/tests/${testId}/start`,
      method: "POST",
      body: {},
      credentials,
    },
    (payload) => payload,
  );
}

export interface ReplicateRequest {
  readonly replicate_number: number;
  /**
   * A string, and the server parses it as `Decimal`.
   *
   * 🔴 NEVER SEND A JavaScript NUMBER HERE. The API declares this
   * `Decimal` and *"the engine refuses a float at its boundary"* — a
   * measured value is a controlled quantity, and JSON has only floats.
   * Sending `12.5` where the bench read `12.500` would destroy the scale
   * at the one point a number enters the system.
   */
  readonly measured_value: string;
  /** Checked against the method's canonical unit by the server. */
  readonly unit: string;
  readonly notes?: string;
}

/**
 * Record one raw measurement.
 *
 * Per replicate, always — never an aggregate. The route says why: rules 5
 * and 6 of the traffic light cannot be recomputed from a mean, so a
 * system that accepted only an average would leave two of fourteen rules
 * permanently unevaluable and silent about it.
 */
export function recordReplicate(
  credentials: ApiCredentials,
  testId: string,
  request: ReplicateRequest,
): Promise<{ id: string }> {
  return apiRequest(
    {
      path: `/api/testing/tests/${testId}/replicates`,
      method: "POST",
      body: request,
      credentials,
    },
    (payload) => z.object({ id: z.string() }).parse(payload),
  );
}

/**
 * Set a replicate aside, with a reason.
 *
 * There is deliberately no delete, and the database refuses one anyway.
 * The reason is mandatory server-side (min 3 characters) because an
 * exclusion without one is indistinguishable from discarding an
 * inconvenient measurement.
 */
export function excludeReplicate(
  credentials: ApiCredentials,
  testId: string,
  replicateId: string,
  reason: string,
): Promise<unknown> {
  return apiRequest(
    {
      path: `/api/testing/tests/${testId}/replicates/${replicateId}/exclusion`,
      method: "POST",
      body: { reason },
      credentials,
    },
    (payload) => payload,
  );
}

/**
 * Close execution. **The result is COMPUTED, not supplied.**
 *
 * 🔴 THIS SENDS AN EMPTY BODY ON PURPOSE, AND NOTHING MAY BE ADDED TO IT.
 * The route's own words: *"This endpoint takes no body on purpose. There
 * is nowhere to put a result, because the caller does not get to state
 * one."* Rule 2 of the seven non-negotiables gives the arithmetic to
 * Python, and `calculated_result` is a SYS-only transition. A future
 * field here would be a way for a browser to assert a test outcome.
 *
 * The response carries `failure_investigation` — `null` means "no
 * investigation was warranted", never "not checked".
 */
export function completeTest(
  credentials: ApiCredentials,
  testId: string,
): Promise<unknown> {
  return apiRequest(
    {
      path: `/api/testing/tests/${testId}/completion`,
      method: "POST",
      body: {},
      credentials,
    },
    (payload) => payload,
  );
}

/**
 * A review or approval decision — SEVEN types, not two.
 *
 * §9: *"Decisions are richer than approve/reject"* — returning for
 * correction and rejecting have different consequences, and collapsing
 * them loses the difference. The workspace offers all seven.
 *
 * 🔴 `authority_level` MUST BE OMITTED ON AN APPROVAL AND THE SERVER
 * REFUSES IT (I5). The route was opened at the test's authority when
 * review completed, and each rung names the permission it requires — so
 * a caller naming an authority would believe it had chosen the authority
 * its signature carries, which the code does not honour. The API returns
 * 422 rather than ignoring it, and this client does not send it.
 */
export interface DecisionRequest {
  readonly decision:
    | "approve"
    | "approve_with_condition"
    | "return_for_correction"
    | "request_retest"
    | "reject"
    | "escalate"
    | "request_additional_test";
  readonly stage: "review" | "approval";
  readonly condition_text?: string;
  readonly rationale?: string;
}

/**
 * ⚠️ A 403 HERE MEANS TWO DIFFERENT THINGS AND THE SERVER SAYS WHICH: the
 * caller lacks the permission, or the caller holds it and is barred on
 * THIS test by their own earlier involvement (ADR-019, segregation of
 * duties). The screen must surface the server's message rather than
 * substitute a generic "not allowed" — the second case is a finding, not
 * a misconfiguration.
 */
export function recordTestDecision(
  credentials: ApiCredentials,
  testId: string,
  request: DecisionRequest,
): Promise<unknown> {
  return apiRequest(
    {
      path: `/api/testing/tests/${testId}/decisions`,
      method: "POST",
      body: request,
      credentials,
    },
    (payload) => payload,
  );
}

/**
 * Mark a result final.
 *
 * `test.confirm` is held by the Lead, QA and the Director — and the
 * administrator is deliberately excluded, with a test asserting it:
 * administering the system is not the authority to make a technical
 * decision.
 *
 * Only from `approved`. A conditional approval carries a limitation, and
 * confirming one would silently discard it.
 */
export function confirmTest(
  credentials: ApiCredentials,
  testId: string,
): Promise<unknown> {
  return apiRequest(
    {
      path: `/api/testing/tests/${testId}/confirmation`,
      method: "POST",
      body: {},
      credentials,
    },
    (payload) => payload,
  );
}
