/**
 * Laboratory batches, over HTTP.
 *
 * Parsed rather than cast, for the reason set out in `materials.ts`: a
 * server that renamed a field would hand back rows whose value is
 * `undefined`, and the grid would render blanks that look exactly like a
 * database with nothing recorded.
 *
 * 🔴 THE MASSES ARE STRINGS, AND THAT IS A CORRECTNESS REQUIREMENT.
 *
 * `planned_quantity_kg` is `NUMERIC(14,4)` and `tolerance_percent` is
 * `NUMERIC(6,4)`. FastAPI's `jsonable_encoder` maps `Decimal` to
 * **float** — measured, `Decimal("12.5000") -> 12.5` — so until this was
 * wired the API was shipping a controlled batch mass with its stored
 * scale destroyed. `CLAUDE.md` §5: *"NUMERIC, never float, for
 * percentages, masses, densities and measured values."*
 *
 * That was fixed server-side (`_decimal_strings` in
 * `app/domains/laboratory/service.py`, and
 * `tests/test_laboratory_testing_serialisation.py` pins it). Typing them
 * as `z.string()` here is the client half of the same contract: if the
 * server ever regresses to a float, these rows fail to parse and the
 * screen says so, rather than silently displaying a rounded mass.
 *
 * **Do not `Number()` these.** No arithmetic happens in the browser —
 * §4 keeps derivation on the server, and `0.1 + 0.2` is why.
 *
 * 🔴 WHAT THE LIST ENDPOINT DOES **NOT** RETURN
 *
 * No components, no weighings, no process parameters, no deviations
 * beyond a COUNT. `list_batches` returns the batch's own columns plus
 * four sub-counts, deliberately — a queue of forty batches must not run
 * forty sub-queries. The weigh-up sheet belongs to the batch detail
 * screen, which `fetchBatch` below now serves.
 *
 * ⚠️ AND THE DETAIL RESPONSE IS NOT A SUPERSET OF THE LIST ROW. Measured
 * against the running service rather than inferred: `get_batch` returns the
 * batch's own columns plus `components`, `process_parameters`, `deviations`
 * and `samples`, and it does **not** carry `formula_code`, `formula_name` or
 * `version_code` — those come from joins only `list_batches` performs. One
 * shared schema would therefore be wrong in one direction or the other,
 * which is why there are two.
 */

import { z } from "zod";

import { apiRequest, type ApiCredentials } from "./client";

export const batchSchema = z.object({
  id: z.string(),
  batch_number: z.string(),
  status: z.string(),
  // NOT NULL in the schema, so required here. Strings — see the header.
  planned_quantity_kg: z.string(),
  tolerance_percent: z.string(),
  project_id: z.string(),
  formula_version_id: z.string(),
  // From the joins to `formula_versions` and `formulas`. Both are inner
  // joins on NOT NULL foreign keys, so these are always present.
  version_code: z.string(),
  formula_code: z.string(),
  formula_name: z.string(),
  // A batch that has not started has no `started_at`. Nullable, but the
  // key is always sent, so `.nullable()` and never `.optional()` — the
  // distinction Codex flagged on `target_release_date`.
  started_at: z.string().nullable(),
  completed_at: z.string().nullable(),
  updated_at: z.string(),
  // Sub-counts. Integers, so numbers rather than strings: they are
  // cardinalities, not measurements, and no scale can be lost.
  component_count: z.number(),
  unweighed_count: z.number(),
  deviation_count: z.number(),
  sample_count: z.number(),
});

export type Batch = z.infer<typeof batchSchema>;

const batchList = z.array(batchSchema);

export function fetchBatches(
  credentials: ApiCredentials,
  signal?: AbortSignal,
): Promise<Batch[]> {
  return apiRequest(
    { path: "/api/laboratory/batches", credentials, signal },
    (payload) => batchList.parse(payload),
  );
}

// ---------------------------------------------------------------------------
// The batch detail — the weigh-up sheet and everything recorded against it
// ---------------------------------------------------------------------------

/**
 * One line of the weigh-up sheet.
 *
 * 🔴 `deviation` IS `null` WHEN THE LINE IS UNWEIGHED, AND THAT IS NOT ZERO.
 * The server is explicit about it — *"NOT a zero deviation. An unweighed line
 * is unweighed, and reporting it as 0.00% within tolerance would make an
 * incomplete batch look finished."* The screen must render the two
 * differently or it re-creates that defect one layer up.
 *
 * Masses are strings, per this file's header. Do not `Number()` them: the
 * server computes the deviation and sends it already decided.
 */
export const batchComponentSchema = z.object({
  id: z.string(),
  material_id: z.string(),
  material_code: z.string(),
  material_name: z.string(),
  role: z.string().nullable(),
  display_order: z.number(),
  planned_mass_kg: z.string(),
  actual_mass_kg: z.string().nullable(),
  weighed_at: z.string().nullable(),
  notes: z.string().nullable(),
  material_lot_id: z.string().nullable(),
  lot_number: z.string().nullable(),
  lot_status: z.string().nullable(),
  deviation: z
    .object({
      delta_kg: z.string(),
      delta_percent: z.string(),
      within_tolerance: z.boolean(),
    })
    .nullable(),
});

export type BatchComponent = z.infer<typeof batchComponentSchema>;

export const processParameterSchema = z.object({
  id: z.string(),
  parameter_code: z.string(),
  value: z.string(),
  unit: z.string(),
  stage: z.string().nullable(),
  recorded_at: z.string(),
  notes: z.string().nullable(),
});

export type ProcessParameter = z.infer<typeof processParameterSchema>;

export const batchDeviationSchema = z.object({
  id: z.string(),
  description: z.string(),
  severity: z.string(),
  raised_at: z.string(),
  resolution: z.string().nullable(),
  resolved_at: z.string().nullable(),
  batch_component_id: z.string().nullable(),
});

export type BatchDeviation = z.infer<typeof batchDeviationSchema>;

export const batchSampleSchema = z.object({
  id: z.string(),
  sample_number: z.string(),
  quantity_g: z.string().nullable(),
  purpose: z.string().nullable(),
  status: z.string(),
  storage_location: z.string().nullable(),
  taken_at: z.string(),
  expires_on: z.string().nullable(),
});

export type BatchSample = z.infer<typeof batchSampleSchema>;

export const batchDetailSchema = z.object({
  id: z.string(),
  organization_id: z.string(),
  project_id: z.string(),
  formula_version_id: z.string(),
  batch_number: z.string(),
  status: z.string(),
  planned_quantity_kg: z.string(),
  tolerance_percent: z.string(),
  purpose: z.string().nullable(),
  mixing_procedure: z.string().nullable(),
  notes: z.string().nullable(),
  created_by: z.string(),
  created_at: z.string(),
  authorized_by: z.string().nullable(),
  authorized_at: z.string().nullable(),
  executed_by: z.string().nullable(),
  started_at: z.string().nullable(),
  completed_at: z.string().nullable(),
  reviewed_by: z.string().nullable(),
  reviewed_at: z.string().nullable(),
  review_note: z.string().nullable(),
  updated_at: z.string(),
  components: z.array(batchComponentSchema),
  process_parameters: z.array(processParameterSchema),
  deviations: z.array(batchDeviationSchema),
  samples: z.array(batchSampleSchema),
});

export type BatchDetail = z.infer<typeof batchDetailSchema>;

export function fetchBatch(
  credentials: ApiCredentials,
  batchId: string,
  signal?: AbortSignal,
): Promise<BatchDetail> {
  return apiRequest(
    { path: `/api/laboratory/batches/${batchId}`, credentials, signal },
    (payload) => batchDetailSchema.parse(payload),
  );
}

// ---------------------------------------------------------------------------
// The lifecycle — each of these is a step somebody performs at the bench
// ---------------------------------------------------------------------------
//
// 🔴 NONE OF THESE PARSE THE RESPONSE INTO A BATCH, AND THAT IS DELIBERATE.
// The routes return varying shapes (a batch row, a deviation result, a bare
// `{id}`), and the screen refetches the batch after every one of them rather
// than patching local state from a reply. §10's `status`, `display_color` and
// `final_status` are DERIVED and server-owned; a client that set any of them
// optimistically would be inventing a safety-critical field. Refetch is
// slower and it is the only version that cannot be wrong.

/** Issue the weigh-up sheet. Planned quantities freeze here. */
export function authorizeBatch(
  credentials: ApiCredentials,
  batchId: string,
): Promise<unknown> {
  return apiRequest(
    {
      path: `/api/laboratory/batches/${batchId}/authorization`,
      method: "POST",
      body: {},
      credentials,
    },
    (payload) => payload,
  );
}

/** Begin execution. */
export function startBatch(
  credentials: ApiCredentials,
  batchId: string,
): Promise<unknown> {
  return apiRequest(
    {
      path: `/api/laboratory/batches/${batchId}/start`,
      method: "POST",
      body: {},
      credentials,
    },
    (payload) => payload,
  );
}

export interface WeighingRequest {
  readonly actual_mass_kg: string;
  /** Omitted, never sent as "", when the bench recorded no lot. */
  readonly material_lot_id?: string;
}

/**
 * Record what was actually weighed.
 *
 * The route returns the deviation immediately, and its docstring says why:
 * *"a technician needs to know at the bench, while the material is still in
 * front of them, not at review a day later."* The screen surfaces it and then
 * refetches, so the sheet and the answer come from the same read.
 */
export function recordWeighing(
  credentials: ApiCredentials,
  batchId: string,
  componentId: string,
  request: WeighingRequest,
): Promise<unknown> {
  return apiRequest(
    {
      path: `/api/laboratory/batches/${batchId}/components/${componentId}/weighing`,
      method: "POST",
      body: request,
      credentials,
    },
    (payload) => payload,
  );
}

export interface ProcessParameterRequest {
  readonly parameter_code: string;
  readonly value: string;
  readonly unit: string;
  readonly stage?: string;
  readonly notes?: string;
}

/** Mixing RPM, mixing time, temperature, vacuum — value + unit, never a string. */
export function recordProcessParameter(
  credentials: ApiCredentials,
  batchId: string,
  request: ProcessParameterRequest,
): Promise<{ id: string }> {
  return apiRequest(
    {
      path: `/api/laboratory/batches/${batchId}/process-parameters`,
      method: "POST",
      body: request,
      credentials,
    },
    (payload) => z.object({ id: z.string() }).parse(payload),
  );
}

export interface DeviationRequest {
  readonly description: string;
  readonly severity: string;
  readonly batch_component_id?: string;
}

export function raiseDeviation(
  credentials: ApiCredentials,
  batchId: string,
  request: DeviationRequest,
): Promise<{ id: string }> {
  return apiRequest(
    {
      path: `/api/laboratory/batches/${batchId}/deviations`,
      method: "POST",
      body: request,
      credentials,
    },
    (payload) => z.object({ id: z.string() }).parse(payload),
  );
}

export interface SampleRequest {
  readonly sample_number: string;
  readonly quantity_g?: string;
  readonly purpose?: string;
  readonly storage_location?: string;
  readonly notes?: string;
}

/** Take a sample. This is the record every future test result cites. */
export function createSample(
  credentials: ApiCredentials,
  batchId: string,
  request: SampleRequest,
): Promise<{ id: string }> {
  return apiRequest(
    {
      path: `/api/laboratory/batches/${batchId}/samples`,
      method: "POST",
      body: request,
      credentials,
    },
    (payload) => z.object({ id: z.string() }).parse(payload),
  );
}

/** Close execution. The server refuses while any line is unweighed. */
export function completeBatch(
  credentials: ApiCredentials,
  batchId: string,
): Promise<unknown> {
  return apiRequest(
    {
      path: `/api/laboratory/batches/${batchId}/completion`,
      method: "POST",
      body: {},
      credentials,
    },
    (payload) => payload,
  );
}

/**
 * Chemist Review — accept for testing, or reject for process deviation.
 *
 * ⚠️ THE TWO DECISIONS REQUIRE DIFFERENT PERMISSIONS SERVER-SIDE. Only the
 * Engineer holds `batch.reject` (`REVIEW_PERMISSION` in the route). The screen
 * offers both and lets the server refuse, per §6: a frontend permission check
 * is cosmetic and the server is authoritative. Hiding the button here would
 * also need `/api/me` to report permissions, which it does not — I79.
 */
export interface ReviewRequest {
  readonly decision: "accept" | "reject";
  readonly note?: string;
}

export function reviewBatch(
  credentials: ApiCredentials,
  batchId: string,
  request: ReviewRequest,
): Promise<unknown> {
  return apiRequest(
    {
      path: `/api/laboratory/batches/${batchId}/review`,
      method: "POST",
      body: request,
      credentials,
    },
    (payload) => payload,
  );
}
