/**
 * Formulas, over HTTP.
 *
 * `GET /api/formulations` returns each formula WITH its latest version
 * (`list_formulas`, a LEFT JOIN LATERAL). That matters for the shape: the
 * latest-version fields are nullable not because the API is sloppy but
 * because a formula can exist with no version yet, and the list must be
 * able to say so rather than omit the formula.
 *
 * 🔴 `version_count` IS A COUNT AND `latest_version_number` IS A VERSION.
 *
 * They are both integers and they are not interchangeable. A formula with
 * versions 1, 2 and 4 (3 having been deleted — which this schema forbids,
 * but the reasoning is the point) has a count of 3 and a latest number of
 * 4. Rendering one under the other's heading is the kind of error nobody
 * notices because both are small plausible numbers.
 *
 * ---------------------------------------------------------------------------
 * THE VERSION HALF — added when the twelve orphaned routes got a caller
 * ---------------------------------------------------------------------------
 *
 * Until this file grew its second half, `GET /api/formulations` was the ONLY
 * formulation route a browser could reach. Twelve others existed and no
 * production path called any of them, so the formula workspace a user opened
 * rendered `lib/demo/dataset.ts` — a BUILD-TIME fixture — and could not show
 * a tenant's own records at all.
 *
 * 🔴 AND THE LIST COULD NOT HAVE REACHED THEM EVEN IF SOMEBODY HAD TRIED (I86).
 * Twelve of the thirteen routes are keyed by `version_id`, and `list_formulas`
 * returned the latest version's code, number and status — but not its id. A
 * `version_code` is a label, unique per formula rather than per organization,
 * so it is not a key. `latest_version_id` was added server-side; it is what
 * makes the link below possible, and it is why this was never merely a
 * missing screen.
 *
 * 🔴 EVERY MEASUREMENT ON THESE ROUTES WAS A FLOAT (I84). Measured against the
 * running service before the fix:
 *
 *     percentage                 2.5                  float
 *     theoretical_density_g_cm3  1.0906918323011936   float
 *
 * `CLAUDE.md` §5 — *"NUMERIC, never float, for percentages, masses, densities
 * and measured values"* — was satisfied in the database, in the engine, and
 * nowhere in between. It survived because nothing ever parsed these numbers.
 * Fixed server-side; typing them `z.string()` here is the client half of that
 * contract, and a regression to float now fails to parse loudly instead of
 * rounding a controlled percentage in silence.
 *
 * **Do not `Number()` any of them, and do not subtract two of them.** §4 and
 * rule 2 keep derivation on the server — that is why `delta` and
 * `percent_delta` arrive from the API rather than being computed here.
 */

import { z } from "zod";

import { apiRequest, type ApiCredentials } from "./client";

export const formulaSchema = z.object({
  id: z.string(),
  formula_code: z.string(),
  name: z.string(),
  product_family: z.string().nullable(),
  status: z.string(),
  project_id: z.string(),
  project_code: z.string(),
  // Both are NOT NULL in `formulations.formulas` (migration 015:352,357).
  // Typing them nullable would let a real contract regression through
  // while the UI silently rendered a gap. Codex found it.
  owner_user_id: z.string(),
  updated_at: z.string(),
  // Null when the formula has no version yet. Not an error, and not zero.
  // `latest_version_id` is the KEY the workspace opens with (I86); the code
  // beside it is a label and cannot be used for that.
  latest_version_id: z.string().nullable(),
  latest_version_code: z.string().nullable(),
  latest_version_number: z.number().nullable(),
  latest_version_status: z.string().nullable(),
  version_count: z.number(),
});

/**
 * 🔴 THE LATEST-VERSION FIELDS TRAVEL TOGETHER OR NOT AT ALL.
 *
 * Typed independently, a row with a version code and a null status parsed
 * cleanly — and `VersionBadge` then announced "no version has been created
 * for this formula yet" for a formula that plainly has one. The LEFT JOIN
 * LATERAL either matches a version or it does not; there is no state in
 * which it half-matches. Codex found it.
 *
 * `latest_version_id` joins that group rather than being checked separately:
 * it comes from the same LATERAL row, so a present id beside a null code is
 * the same impossible half-match — and it is the field the workspace link
 * depends on, so a silent null here would produce a dead link rather than a
 * visible error.
 */
export const formulaWithCoherentVersion = formulaSchema.refine(
  (f) =>
    (f.latest_version_id === null &&
      f.latest_version_code === null &&
      f.latest_version_number === null &&
      f.latest_version_status === null) ||
    (f.latest_version_id !== null &&
      f.latest_version_code !== null &&
      f.latest_version_number !== null &&
      f.latest_version_status !== null),
  {
    message:
      "latest_version_id, _code, _number and _status must all be present or all be null — " +
      "a half-populated latest version is not a state this endpoint can produce",
  },
);

export type Formula = z.infer<typeof formulaSchema>;

const formulaList = z.array(formulaWithCoherentVersion);

export function fetchFormulas(
  credentials: ApiCredentials,
  signal?: AbortSignal,
): Promise<Formula[]> {
  return apiRequest({ path: "/api/formulations", credentials, signal }, (payload) =>
    formulaList.parse(payload),
  );
}

// ---------------------------------------------------------------------------
// The version — composition, and every derived property
// ---------------------------------------------------------------------------

/**
 * One line of the composition.
 *
 * ⚠️ `cost_per_kg` IS ABSENT, NOT NULL, WITHOUT `formula.view_cost`. The
 * server removes the key deliberately: *"a null says 'this material has no
 * cost on file', which is a different and false claim."* `.optional()` and
 * `.nullable()` therefore mean different things here and both are needed —
 * absent (not permitted to see) and null (permitted, none recorded) are
 * distinct states and the screen renders them differently.
 *
 * `material_status` is carried because a restricted or obsolete material is
 * a submission block, and the chemist needs to see WHICH line caused it.
 */
export const formulaComponentSchema = z
  .object({
    id: z.string(),
    material_id: z.string(),
    material_code: z.string(),
    material_name: z.string(),
    material_status: z.string(),
    category: z.string().nullable(),
    effective_role: z.string().nullable(),
    role_override: z.string().nullable(),
    display_order: z.number(),
    // Strings — see this file's header. A recipe share is a controlled figure.
    percentage: z.string(),
    density_g_cm3: z.string().nullable(),
    solids_fraction: z.string().nullable(),
    voc_fraction: z.string().nullable(),
    cost_per_kg: z.string().nullable().optional(),
    requires_sds: z.boolean(),
    sds_count: z.number(),
    notes: z.string().nullable(),
  })
  .passthrough();

export type FormulaComponent = z.infer<typeof formulaComponentSchema>;

/** The version's own record — lifecycle, lineage and the change narrative. */
export const formulaVersionSchema = z
  .object({
    id: z.string(),
    formula_id: z.string(),
    project_id: z.string(),
    version_number: z.number(),
    version_code: z.string(),
    // Null on a first version. The whole difference engine hangs off this.
    parent_version_id: z.string().nullable(),
    parent_version_code: z.string().nullable(),
    status: z.string(),
    // §H Slice 3's narrative columns. `observed_effect` is null until the
    // laboratory has actually reported back — that is the honest state, and
    // it is what distinguishes a hypothesis from a result.
    change_reason: z.string().nullable(),
    technical_hypothesis: z.string().nullable(),
    expected_effect: z.string().nullable(),
    observed_effect: z.string().nullable(),
    total_tolerance_pct: z.string(),
    submitted_by: z.string().nullable(),
    submitted_at: z.string().nullable(),
    approved_by: z.string().nullable(),
    approved_at: z.string().nullable(),
    approval_note: z.string().nullable(),
    created_at: z.string(),
    updated_at: z.string(),
    formula_code: z.string(),
    formula_name: z.string(),
    product_family: z.string().nullable(),
  })
  .passthrough();

export type FormulaVersion = z.infer<typeof formulaVersionSchema>;

export const formulaVersionDetailSchema = formulaVersionSchema.extend({
  components: z.array(formulaComponentSchema),
});

export type FormulaVersionDetail = z.infer<typeof formulaVersionDetailSchema>;

export function fetchVersion(
  credentials: ApiCredentials,
  versionId: string,
  signal?: AbortSignal,
): Promise<FormulaVersionDetail> {
  return apiRequest(
    { path: `/api/formulations/versions/${versionId}`, credentials, signal },
    (payload) => formulaVersionDetailSchema.parse(payload),
  );
}

/**
 * One derived property: a value, OR a stated reason it could not be computed.
 *
 * 🔴 NEVER A BARE NULL AND NEVER A ZERO. The engine raises
 * *"density unknown for: RM-FIL-07"* and the service carries that sentence
 * through as `unavailable_reason`, *"so the caller can never mistake a
 * missing property for a computed zero"*. A screen that rendered an empty
 * cell here would leave a chemist believing the property had been calculated
 * and had come out blank. Render the reason.
 */
export const derivedPropertySchema = z.object({
  value: z.string().nullable(),
  unavailable_reason: z.string().nullable(),
});

export type DerivedProperty = z.infer<typeof derivedPropertySchema>;

/**
 * A reason this version may not be submitted.
 *
 * Server-decided, and the screen never invents one: the submit control is
 * offered and the server refuses, exactly as the laboratory review does.
 */
export const submissionBlockSchema = z.object({
  code: z.string(),
  message: z.string(),
});

/**
 * ⚠️ `properties` IS A MAP AND ITS KEYS DEPEND ON PERMISSION.
 *
 * `raw_material_cost_per_kg` is present only for a caller holding
 * `formula.view_cost`, and `properties` is `{}` entirely when the version has
 * no components yet. `z.record` rather than a fixed object, so a legitimate
 * response is never rejected for lacking a key the caller was not allowed to
 * receive.
 */
export const versionEvaluationSchema = z.object({
  version: formulaVersionSchema,
  component_count: z.number(),
  properties: z.record(z.string(), derivedPropertySchema),
  submission_blocks: z.array(submissionBlockSchema),
  submittable: z.boolean(),
});

export type VersionEvaluation = z.infer<typeof versionEvaluationSchema>;

export function fetchVersionEvaluation(
  credentials: ApiCredentials,
  versionId: string,
  signal?: AbortSignal,
): Promise<VersionEvaluation> {
  return apiRequest(
    {
      path: `/api/formulations/versions/${versionId}/evaluation`,
      credentials,
      signal,
    },
    (payload) => versionEvaluationSchema.parse(payload),
  );
}

// ---------------------------------------------------------------------------
// The weigh-up sheet
// ---------------------------------------------------------------------------

export const weighUpLineSchema = z.object({
  material_code: z.string(),
  material_name: z.string(),
  percentage: z.string(),
  mass_kg: z.string(),
});

/**
 * The sheet a technician weighs against.
 *
 * 🔴 THE MASSES SUM EXACTLY TO THE BATCH MASS, AND THE SCREEN MUST NOT
 * RE-ADD THEM. The engine guarantees it by putting the rounding remainder on
 * the LARGEST line — chosen by percentage, not by position, *"so the residue
 * lands where it is proportionally smallest"*. Summing these in JavaScript to
 * "check" would reintroduce float error and report a discrepancy that does
 * not exist.
 *
 * ⚠️ THE SERVER REFUSES A FORMULA THAT DOES NOT TOTAL 100%, and that refusal
 * is a feature: *"scaling it silently would produce masses that contradict
 * the stated percentages."* Measured on real demo data — a 98.5% version
 * returns 422 with that sentence. The screen shows it rather than an empty
 * sheet.
 */
export const weighUpSchema = z.object({
  version: formulaVersionSchema,
  batch_mass_kg: z.string(),
  lines: z.array(weighUpLineSchema),
});

export type WeighUp = z.infer<typeof weighUpSchema>;

export function fetchWeighUp(
  credentials: ApiCredentials,
  versionId: string,
  batchMassKg: string,
): Promise<WeighUp> {
  return apiRequest(
    {
      path: `/api/formulations/versions/${versionId}/weigh-up`,
      method: "POST",
      // A string, never a number — the batch mass is a controlled quantity
      // and the server parses it as `Decimal`.
      body: { batch_mass_kg: batchMassKg },
      credentials,
    },
    (payload) => weighUpSchema.parse(payload),
  );
}

// ---------------------------------------------------------------------------
// The difference engine
// ---------------------------------------------------------------------------

/**
 * One row of old / new / Δ / %Δ.
 *
 * 🔴 `delta` AND `percent_delta` ARE COMPUTED BY THE PYTHON ENGINE AND MUST
 * NEVER BE COMPUTED HERE (I84). `compare_versions` refused to subtract the
 * two percentages itself and named the engine as *"the one place that may"* —
 * and then no such engine function existed, so the difference engine shipped
 * without two of the columns the plan names. `component_delta` closes that,
 * and the reason for the discipline is concrete: in JavaScript
 * `0.3 - 0.1` is `0.19999999999999998`, and a component share is a controlled
 * figure on a master formulation.
 *
 * Both are `null` for an ADDED or REMOVED component. Not zero, and not the
 * component's own percentage: a component that did not exist has no delta,
 * and reporting one would say "it increased by 2.5 points" about something
 * that was not there to increase. `change` says which case it is.
 *
 * `percent_delta` is additionally null when the previous share was zero —
 * a division by zero, not an infinite increase.
 */
export const comparisonRowSchema = z.object({
  material_code: z.string(),
  material_name: z.string(),
  previous_percentage: z.string().nullable(),
  new_percentage: z.string().nullable(),
  delta: z.string().nullable(),
  percent_delta: z.string().nullable(),
  change: z.string(),
});

export type ComparisonRow = z.infer<typeof comparisonRowSchema>;

/**
 * The full difference: composition, properties, and the narrative.
 *
 * §H Slice 3 specifies exactly these columns — *"old/new/Δ/%Δ/reason/
 * expected/observed"*. The last three are the scientific record: what was
 * changed, what was predicted, and what actually happened. `observed_effect`
 * is null until the laboratory reports, and rendering that gap honestly is
 * the difference between a hypothesis and a result.
 */
export const versionComparisonSchema = z.object({
  previous: formulaVersionSchema,
  new: formulaVersionSchema,
  change_reason: z.string().nullable(),
  technical_hypothesis: z.string().nullable(),
  expected_effect: z.string().nullable(),
  observed_effect: z.string().nullable(),
  components: z.array(comparisonRowSchema),
  previous_properties: z.record(z.string(), derivedPropertySchema),
  new_properties: z.record(z.string(), derivedPropertySchema),
});

export type VersionComparison = z.infer<typeof versionComparisonSchema>;

export function fetchVersionComparison(
  credentials: ApiCredentials,
  versionId: string,
  againstVersionId: string,
  signal?: AbortSignal,
): Promise<VersionComparison> {
  return apiRequest(
    {
      path: `/api/formulations/versions/${versionId}/comparison?against=${againstVersionId}`,
      credentials,
      signal,
    },
    (payload) => versionComparisonSchema.parse(payload),
  );
}

// ---------------------------------------------------------------------------
// Lifecycle — the only ways a formula changes
// ---------------------------------------------------------------------------

export interface ComponentInput {
  readonly material_id: string;
  /** A string. See the header: never a JavaScript number. */
  readonly percentage: string;
  readonly role_override?: string;
  readonly display_order?: number;
  readonly notes?: string;
}

/**
 * Replace the composition of a DRAFT version.
 *
 * ⚠️ A PUT, AND WHOLE-SET: the server replaces the composition rather than
 * patching a line, so a caller that sends one row deletes the rest. The
 * workspace therefore sends the full edited table.
 *
 * The server refuses this on a frozen (submitted or approved) version — that
 * is `VersionFrozenError`, and it is a 409, because a controlled formula does
 * not change in place. The route to change one is `createRevision` below.
 */
export function putComponents(
  credentials: ApiCredentials,
  versionId: string,
  components: readonly ComponentInput[],
): Promise<unknown> {
  return apiRequest(
    {
      path: `/api/formulations/versions/${versionId}/components`,
      method: "PUT",
      body: { components },
      credentials,
    },
    (payload) => payload,
  );
}

/**
 * Submit a draft for approval. The server re-runs every submission block.
 *
 * 🔴 THERE IS NO NOTE PARAMETER, BECAUSE THE ROUTE HAS NOWHERE TO PUT ONE.
 * `post_submission` declares no request body at all, so FastAPI ignored
 * anything sent — a caller passing a submission note got a 200 and no note
 * recorded. A parameter with no destination is a promise the API does not
 * keep, and the honest fix is to stop offering it rather than to keep posting
 * a field nothing reads. Found by the Supervisor.
 *
 * A blocked submission answers 422 listing EVERY block; `serverMessage`
 * renders them all.
 */
export function submitVersion(
  credentials: ApiCredentials,
  versionId: string,
): Promise<unknown> {
  return apiRequest(
    {
      path: `/api/formulations/versions/${versionId}/submission`,
      method: "POST",
      body: {},
      credentials,
    },
    (payload) => payload,
  );
}

export interface VersionDecisionRequest {
  readonly decision: "approve" | "reject";
  readonly note?: string;
}

/**
 * Approve or reject a submitted version.
 *
 * ⚠️ THE TWO OUTCOMES NEED DIFFERENT PERMISSIONS AND THE SERVER IS
 * AUTHORITATIVE. The screen offers both and lets it refuse — a frontend
 * permission check is cosmetic, and hiding the control would also need
 * `/api/me` to report permissions, which it does not (I79).
 */
export function decideVersion(
  credentials: ApiCredentials,
  versionId: string,
  request: VersionDecisionRequest,
): Promise<unknown> {
  return apiRequest(
    {
      path: `/api/formulations/versions/${versionId}/decision`,
      method: "POST",
      body: request,
      credentials,
    },
    (payload) => payload,
  );
}

/**
 * 🔴 THREE FIELDS ARE REQUIRED, NOT ONE, AND THE TYPE NOW SAYS SO.
 *
 * `RevisionCreate` on the server requires `change_reason`,
 * `technical_hypothesis` AND `driver_type`, none with a default. This
 * interface declared the first as required, the second as optional and the
 * third not at all — so the type system could not catch it, and the only UI
 * path that creates a revision returned 422 "Field required" every single
 * time, on the operation the workspace itself calls "the only way a formula
 * changes". Found by the Supervisor.
 *
 * `driver_type` has no default deliberately, and the server's comment says
 * why: §2 requires a revision to show *"exactly which failure or improvement
 * objective caused it"*, `change_reason` is prose, and this is the link that
 * makes "why was F008 created?" answerable by query. *"A default would answer
 * the question on the chemist's behalf."*
 */
export type RevisionDriver =
  | "failure"
  | "requirement"
  | "optimization"
  | "cost"
  | "regulatory"
  | "customer_request"
  | "other";

export interface RevisionRequest {
  readonly change_reason: string;
  readonly technical_hypothesis: string;
  readonly driver_type: RevisionDriver;
  readonly driver_failure_id?: string;
  readonly driver_requirement_id?: string;
  readonly expected_effect?: string;
  readonly version_code?: string;
}

/**
 * Clone a version into a new draft — **the only way a formula changes.**
 *
 * The route's own words. An approved formulation is never edited in place;
 * it is superseded by a revision that records why. `change_reason` is
 * mandatory server-side for that reason: a revision with no stated reason
 * breaks the development history the difference engine reads.
 */
export function createRevision(
  credentials: ApiCredentials,
  versionId: string,
  request: RevisionRequest,
): Promise<{ id: string }> {
  return apiRequest(
    {
      path: `/api/formulations/versions/${versionId}/revision`,
      method: "POST",
      body: request,
      credentials,
    },
    (payload) => z.object({ id: z.string() }).passthrough().parse(payload),
  );
}

/**
 * Record what actually happened.
 *
 * 🔴 THIS IS THE FIELD THAT CLOSES THE SCIENTIFIC LOOP. `expected_effect` is
 * a prediction made before the work; `observed_effect` is the outcome, and it
 * is deliberately a separate column so that a hypothesis can never be
 * quietly rewritten into a result once the answer is known.
 */
export function recordObservedEffect(
  credentials: ApiCredentials,
  versionId: string,
  observedEffect: string,
): Promise<unknown> {
  return apiRequest(
    {
      path: `/api/formulations/versions/${versionId}/observed-effect`,
      method: "POST",
      body: { observed_effect: observedEffect },
      credentials,
    },
    (payload) => payload,
  );
}

/**
 * The classification ladder, in RANK order.
 *
 * 🔴 THE ORDER IS THE MEANING, so it is preserved rather than re-sorted. The
 * export ceiling is expressed as a rank comparison — not a list of level
 * names — precisely so that inserting a level between two others does not
 * silently widen it. A screen that sorted these alphabetically would put
 * `CONFIDENTIAL` above `DIRECTOR_CONTROLLED` and teach the reader the ladder
 * backwards.
 *
 * Without this list, reclassifying a formula could only have been a free-text
 * field — and a mistyped level is a confidentiality decision made by a typo.
 */
export const classificationSchema = z.object({
  code: z.string(),
  rank: z.number(),
});

export type Classification = z.infer<typeof classificationSchema>;

export function fetchClassifications(
  credentials: ApiCredentials,
  signal?: AbortSignal,
): Promise<Classification[]> {
  return apiRequest(
    { path: "/api/formulations/classifications", credentials, signal },
    (payload) => z.array(classificationSchema).parse(payload),
  );
}

export interface ClassificationRequest {
  readonly classification: string;
  readonly reason: string;
}

/** Reclassify a formula. `reason` is mandatory and audited. */
export function classifyFormula(
  credentials: ApiCredentials,
  formulaId: string,
  request: ClassificationRequest,
): Promise<unknown> {
  return apiRequest(
    {
      path: `/api/formulations/${formulaId}/classification`,
      method: "POST",
      body: request,
      credentials,
    },
    (payload) => payload,
  );
}

export interface FormulaCreateRequest {
  readonly formula_code: string;
  readonly name: string;
  readonly project_id: string;
  readonly product_family?: string;
}

export function createFormula(
  credentials: ApiCredentials,
  request: FormulaCreateRequest,
): Promise<{ id: string }> {
  return apiRequest(
    { path: "/api/formulations", method: "POST", body: request, credentials },
    (payload) => z.object({ id: z.string() }).passthrough().parse(payload),
  );
}

/**
 * One line of a composition, on its way to the server.
 *
 * 🔴 `percentage` IS A STRING AND MUST STAY ONE.
 *
 * `NUMERIC(9,4)` in PostgreSQL, `Decimal` in Pydantic. The API's own comment
 * says declaring it `float` "would undo the whole Decimal discipline at the one
 * point where a number enters the system" — and this is that point. A
 * `Number()` here would round 33.3333 before the server ever saw it, on a
 * controlled formulation percentage, which `CLAUDE.md` §5 calls a defect in as
 * many words.
 */
export interface ComponentLineRequest {
  readonly material_id: string;
  readonly percentage: string;
  readonly role_override?: string;
  readonly display_order?: number;
  readonly notes?: string;
}

/**
 * Replace a draft version's composition.
 *
 * 🔴 THE WHOLE COMPOSITION, NOT A PATCH — and the server says why: a formula is
 * a set of lines that must total 100%, so every intermediate state of a partial
 * update is invalid. Sending all of it makes the write atomic and idempotent.
 * A client that sent one changed line would be asking the server to hold an
 * invalid formula between two requests.
 */
export function setComposition(
  credentials: ApiCredentials,
  versionId: string,
  components: readonly ComponentLineRequest[],
): Promise<{ total_percentage: string }> {
  return apiRequest(
    {
      path: `/api/formulations/versions/${versionId}/components`,
      method: "PUT",
      credentials,
      body: { components },
    },
    (payload) =>
      z.object({ total_percentage: z.string() }).passthrough().parse(payload),
  );
}
