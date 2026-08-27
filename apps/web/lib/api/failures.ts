/**
 * Failure investigations and the approval queue, over HTTP.
 *
 * 🔴 SLICE 6 SHIPPED ITS BACKEND AND NOT ITS BROWSER, AND THIS IS THE HALF
 * THAT WAS MISSING.
 *
 * Measured 2026-08-27: `app/api/failures.py` declares **eleven write
 * endpoints** and not one of them had a client function, so a person could
 * not open an investigation, propose a hypothesis, record evidence, accept a
 * root cause, raise a corrective action or close anything. The approval queue
 * was in the same state — the only way to reach it was to construct an HTTP
 * request by hand.
 *
 * ⚠️ ONE MODULE, TWO ROUTERS, TWO PREFIXES. `app/api/failures.py` mounts
 * `router` at `/api/quality/failures` AND `approvals_router` at
 * `/api/approvals`. The first draft of this file put the approval paths under
 * the failures prefix because they live in the same source file, which is a
 * fact about the file and not about the API. Every path below was read off
 * `app/main.py`'s `include_router` calls instead.
 *
 * *A route with no caller is the same defect as a table with no writer*, and
 * this project found twenty-three of them on 2026-08-24 across four other
 * modules. These are the next eleven.
 *
 * ---------------------------------------------------------------------------
 * TWO RULES THIS FILE EXISTS TO KEEP
 * ---------------------------------------------------------------------------
 *
 * 🔴 **AN AI HYPOTHESIS IS NOT AN ACCEPTED ROOT CAUSE** (§7). Every hypothesis
 * carries `origin` (`human` | `msd`) and `status`
 * (`proposed` | `under_review` | `accepted` | `rejected`), and **only a human
 * moves anything to `accepted`** — through `POST /root-cause`, which requires
 * `failure.accept_root_cause` and a mandatory rationale. Both fields are
 * modelled here rather than dropped, because a screen that showed a
 * confidently-worded MSD hypothesis without saying where it came from is the
 * single worst thing this module can render.
 *
 * 🔴 **EVIDENCE BEARS ON A HYPOTHESIS IN THREE WAYS, NOT ONE.** The link
 * carries `supports` | `contradicts` | `inconclusive`, and `get_failure`'s own
 * docstring says why it must be shown: *"a screen showing only supporting
 * evidence would make every hypothesis look well-founded."* So `relationship`
 * is required in the schema, not optional.
 */

import { z } from "zod";

import { apiRequest, type ApiCredentials } from "./client";

// ---------------------------------------------------------------------------
// Failure investigations
// ---------------------------------------------------------------------------

/**
 * A row in the investigation queue.
 *
 * `hypothesis_count`, `has_root_cause` and `open_actions` come back on every
 * row because they are what makes the queue actionable — §11 requires counts
 * to represent items needing action, not total rows. An investigation with
 * three hypotheses and no accepted root cause is a different piece of work
 * from one with none at all, and the list is where that has to be visible.
 */
export const failureSummarySchema = z.object({
  id: z.string(),
  failure_code: z.string(),
  title: z.string(),
  severity: z.string(),
  status: z.string(),
  project_id: z.string(),
  test_id: z.string().nullable(),
  formula_version_id: z.string().nullable(),
  opened_at: z.string(),
  closed_at: z.string().nullable(),
  hypothesis_count: z.number(),
  // 🔴 A BOOLEAN, AND IT WAS A COUNT UNTIL THIS CLIENT WAS WRITTEN.
  //
  // `list_failures` returned `(SELECT count(*) …) AS has_root_cause` — a
  // column whose NAME asks a yes/no question and whose VALUE was a number.
  // Every consumer reading it loosely would have been right by accident (0 is
  // falsy, 2 is truthy) and this schema, which validates, would have rejected
  // every response. *Ask what a returned value answers, not what the column is
  // called.* Fixed in the service on 2026-08-27 with `> 0`, and pinned by
  // `test_has_root_cause_answers_the_question_its_name_asks`, so it cannot
  // quietly go back to a count.
  has_root_cause: z.boolean(),
  open_actions: z.number(),
});
export type FailureSummary = z.infer<typeof failureSummarySchema>;

const failureList = z.array(failureSummarySchema);

export function fetchFailures(
  credentials: ApiCredentials,
  signal?: AbortSignal,
): Promise<FailureSummary[]> {
  return apiRequest({ path: "/api/quality/failures", credentials, signal }, (payload) =>
    failureList.parse(payload),
  );
}

/** How a piece of evidence bears on one hypothesis. */
export const hypothesisEvidenceSchema = z.object({
  hypothesis_id: z.string(),
  evidence_id: z.string(),
  // Required, never defaulted. See the header: only rendering `supports`
  // makes every hypothesis look well-founded.
  relationship: z.enum(["supports", "contradicts", "inconclusive"]),
  note: z.string().nullable(),
  evidence_type: z.string(),
  summary: z.string(),
  origin: z.enum(["human", "msd"]),
});
export type HypothesisEvidence = z.infer<typeof hypothesisEvidenceSchema>;

export const hypothesisSchema = z.object({
  id: z.string(),
  possible_cause: z.string(),
  mechanism: z.string().nullable(),
  confidence: z.enum(["low", "medium", "high"]),
  source: z.string().nullable(),
  // §7 rests on this distinction and the screen renders it differently.
  origin: z.enum(["human", "msd"]),
  status: z.enum(["proposed", "under_review", "accepted", "rejected"]),
  accepted_by: z.string().nullable(),
  accepted_at: z.string().nullable(),
  rejection_reason: z.string().nullable(),
  proposed_by: z.string().nullable(),
  created_at: z.string(),
  evidence: z.array(hypothesisEvidenceSchema),
});
export type Hypothesis = z.infer<typeof hypothesisSchema>;

export const evidenceSchema = z.object({
  id: z.string(),
  evidence_type: z.string(),
  summary: z.string(),
  detail: z.string().nullable(),
  referenced_entity_type: z.string().nullable(),
  referenced_entity_id: z.string().nullable(),
  source_reference: z.string().nullable(),
  origin: z.enum(["human", "msd"]),
  recorded_at: z.string(),
});
export type Evidence = z.infer<typeof evidenceSchema>;

export const actionSchema = z.object({
  id: z.string(),
  action_type: z.string(),
  description: z.string(),
  status: z.string(),
  assigned_to: z.string().nullable(),
  due_date: z.string().nullable(),
  completed_at: z.string().nullable(),
  outcome: z.string().nullable(),
});
export type FailureAction = z.infer<typeof actionSchema>;

export const failureDetailSchema = z.object({
  id: z.string(),
  organization_id: z.string(),
  project_id: z.string(),
  failure_code: z.string(),
  title: z.string(),
  description: z.string().nullable(),
  severity: z.string(),
  status: z.string(),
  test_id: z.string().nullable(),
  formula_version_id: z.string().nullable(),
  batch_id: z.string().nullable(),
  opened_by: z.string().nullable(),
  opened_at: z.string(),
  closed_by: z.string().nullable(),
  closed_at: z.string().nullable(),
  closure_summary: z.string().nullable(),
  hypotheses: z.array(hypothesisSchema),
  // 🔴 THE SERVER DECIDES THIS, NOT THE SCREEN. `get_failure` computes it as
  // the hypothesis whose status is `accepted`. Re-deriving it in the browser
  // would be a second implementation of "what is the root cause", free to
  // disagree with the one the database answered — the two-literals defect
  // applied to the most consequential field in the module.
  accepted_root_cause: hypothesisSchema.nullable(),
  evidence: z.array(evidenceSchema),
  actions: z.array(actionSchema),
});
export type FailureDetail = z.infer<typeof failureDetailSchema>;

export function fetchFailure(
  credentials: ApiCredentials,
  failureId: string,
  signal?: AbortSignal,
): Promise<FailureDetail> {
  return apiRequest(
    { path: `/api/quality/failures/${failureId}`, credentials, signal },
    (payload) => failureDetailSchema.parse(payload),
  );
}

// ---------------------------------------------------------------------------
// The writes. Eleven endpoints, none of which had a caller.
// ---------------------------------------------------------------------------

export interface HypothesisRequest {
  readonly possible_cause: string;
  readonly mechanism?: string;
  readonly confidence: "low" | "medium" | "high";
  readonly source?: string;
}

/**
 * Propose a hypothesis.
 *
 * ⚠️ `origin` IS NOT IN THIS REQUEST, AND THAT IS THE POINT. The server
 * defaults it to `human` and the field exists so an MSD-proposed hypothesis
 * must SAY it is one. A browser form that could send `origin: "msd"` would let
 * a person file a machine's opinion under the machine's name, or — worse — let
 * a future MSD path file its own under a human's. The label can only be wrong
 * by a caller asserting it, so this caller cannot assert it.
 */
export function proposeHypothesis(
  credentials: ApiCredentials,
  failureId: string,
  request: HypothesisRequest,
): Promise<unknown> {
  return apiRequest(
    {
      path: `/api/quality/failures/${failureId}/hypotheses`,
      method: "POST",
      body: request,
      credentials,
    },
    (payload) => payload,
  );
}

export interface EvidenceRequest {
  readonly evidence_type: string;
  readonly summary: string;
  readonly detail?: string;
  readonly source_reference?: string;
}

/** Record evidence against the investigation. `origin` is the server's, as above. */
export function recordEvidence(
  credentials: ApiCredentials,
  failureId: string,
  request: EvidenceRequest,
): Promise<unknown> {
  return apiRequest(
    {
      path: `/api/quality/failures/${failureId}/evidence`,
      method: "POST",
      body: request,
      credentials,
    },
    (payload) => payload,
  );
}

export interface EvidenceLinkRequest {
  readonly evidence_id: string;
  readonly relationship: "supports" | "contradicts" | "inconclusive";
  readonly note?: string;
}

/** Link a piece of evidence to a hypothesis, stating HOW it bears on it. */
export function linkEvidence(
  credentials: ApiCredentials,
  failureId: string,
  hypothesisId: string,
  request: EvidenceLinkRequest,
): Promise<unknown> {
  return apiRequest(
    {
      path: `/api/quality/failures/${failureId}/hypotheses/${hypothesisId}/evidence`,
      method: "POST",
      body: request,
      credentials,
    },
    (payload) => payload,
  );
}

/**
 * Accept a hypothesis as the root cause. **A human act, and only a human act.**
 *
 * `rationale` is mandatory server-side and mandatory in this signature:
 * accepting a root cause is a technical decision and an unexplained one cannot
 * be reviewed later. Requires `failure.accept_root_cause`, held by the Lead and
 * the Director — not by the investigator who proposed it.
 */
export function acceptRootCause(
  credentials: ApiCredentials,
  failureId: string,
  request: { readonly hypothesis_id: string; readonly rationale: string },
): Promise<unknown> {
  return apiRequest(
    {
      path: `/api/quality/failures/${failureId}/root-cause`,
      method: "POST",
      body: request,
      credentials,
    },
    (payload) => payload,
  );
}

/** Reject a hypothesis, with a reason that stays on the record. */
export function rejectHypothesis(
  credentials: ApiCredentials,
  failureId: string,
  hypothesisId: string,
  reason: string,
): Promise<unknown> {
  return apiRequest(
    {
      path: `/api/quality/failures/${failureId}/hypotheses/${hypothesisId}/rejection`,
      method: "POST",
      body: { reason },
      credentials,
    },
    (payload) => payload,
  );
}

export interface ActionRequest {
  readonly action_type: string;
  readonly description: string;
  readonly due_date?: string;
}

/** Raise a corrective action. */
export function raiseAction(
  credentials: ApiCredentials,
  failureId: string,
  request: ActionRequest,
): Promise<unknown> {
  return apiRequest(
    {
      path: `/api/quality/failures/${failureId}/actions`,
      method: "POST",
      body: request,
      credentials,
    },
    (payload) => payload,
  );
}

/** Close the investigation. Requires `failure.close`. */
export function closeFailure(
  credentials: ApiCredentials,
  failureId: string,
  summary: string,
): Promise<unknown> {
  return apiRequest(
    {
      path: `/api/quality/failures/${failureId}/closure`,
      method: "POST",
      body: { summary },
      credentials,
    },
    (payload) => payload,
  );
}

// ---------------------------------------------------------------------------
// The approval queue
// ---------------------------------------------------------------------------

/**
 * One step this caller could decide **right now**.
 *
 * "Right now" is load-bearing and the server owns it: `pending_steps_for`
 * excludes steps whose turn has not come, because §11 requires a queue to
 * represent items needing action BY THE HOLDER. The screen must not filter
 * this further and must not widen it — both would be a second implementation
 * of whose turn it is.
 */
export const approvalQueueItemSchema = z.object({
  step_id: z.string(),
  step_number: z.number(),
  step_label: z.string(),
  permission_required: z.string().nullable(),
  route_id: z.string(),
  entity_type: z.string(),
  entity_id: z.string(),
  template_code: z.string(),
  project_id: z.string(),
  opened_at: z.string(),
});
export type ApprovalQueueItem = z.infer<typeof approvalQueueItemSchema>;

const approvalQueue = z.array(approvalQueueItemSchema);

export function fetchApprovalQueue(
  credentials: ApiCredentials,
  signal?: AbortSignal,
): Promise<ApprovalQueueItem[]> {
  return apiRequest({ path: "/api/approvals/queue", credentials, signal }, (payload) =>
    approvalQueue.parse(payload),
  );
}

export const routeStepSchema = z.object({
  id: z.string(),
  step_number: z.number(),
  parallel_group: z.number(),
  permission_required: z.string().nullable(),
  step_label: z.string(),
  is_mandatory: z.boolean(),
  must_differ_from_group: z.boolean(),
  decision: z.string().nullable(),
  condition_text: z.string().nullable(),
  rationale: z.string().nullable(),
  decided_by: z.string().nullable(),
  decided_at: z.string().nullable(),
});
export type RouteStep = z.infer<typeof routeStepSchema>;

export const approvalRouteSchema = z.object({
  id: z.string(),
  entity_type: z.string(),
  entity_id: z.string(),
  template_code: z.string(),
  status: z.string(),
  project_id: z.string(),
  opened_at: z.string(),
  closed_at: z.string().nullable(),
  steps: z.array(routeStepSchema),
  // 🔴 COMPUTED BY THE ENGINE, NOT BY THE SCREEN. `get_route`'s docstring is
  // explicit that a stored "current step" would go stale the moment a parallel
  // step was decided out of order, so it is derived per read. A browser that
  // worked out whose turn it is would be the stale copy the server refused to
  // keep.
  current_group: z.number().nullable(),
  next_steps: z.array(routeStepSchema),
  awaiting: z.array(z.string()),
});
export type ApprovalRoute = z.infer<typeof approvalRouteSchema>;

export function fetchApprovalRoute(
  credentials: ApiCredentials,
  routeId: string,
  signal?: AbortSignal,
): Promise<ApprovalRoute> {
  return apiRequest(
    { path: `/api/approvals/${routeId}`, credentials, signal },
    (payload) => approvalRouteSchema.parse(payload),
  );
}

export interface StepDecisionRequest {
  readonly decision:
    | "approve"
    | "approve_with_condition"
    | "return_for_correction"
    | "request_retest"
    | "reject"
    | "escalate"
    | "request_additional_test";
  readonly condition_text?: string;
  readonly rationale?: string;
}

/**
 * Record a decision on one rung.
 *
 * ⚠️ `require_permission("test.view")` ON THE ROUTE IS ONLY A FLOOR, and the
 * engine re-checks the STEP's own `permission_required` plus the
 * segregation-of-duties rule. So a 403 here means one of two different things
 * — you lack the rung's permission, or you hold it and are barred by your own
 * earlier involvement — and the server says which. The message is surfaced
 * verbatim rather than translated.
 */
export function decideStep(
  credentials: ApiCredentials,
  routeId: string,
  stepId: string,
  request: StepDecisionRequest,
): Promise<unknown> {
  return apiRequest(
    {
      path: `/api/approvals/${routeId}/steps/${stepId}/decision`,
      method: "POST",
      body: request,
      credentials,
    },
    (payload) => payload,
  );
}
