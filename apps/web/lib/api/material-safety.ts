/**
 * Material Safety Data, over HTTP.
 *
 * 🔴 THE SCHEMAS MIRROR THE RESPONSE, NOT THE SQL.
 *
 * This project shipped three wrong client types in two days by reading the
 * query instead of the value the service returns. `current_safety_position`
 * returns `{current, hazards, components, storage_rules, incompatibilities}` —
 * a shape assembled in Python from five separate queries, which no single
 * SELECT describes.
 *
 * 🔴 `current` IS NULLABLE AND THAT IS A REAL ANSWER.
 *
 * It is null when the material has no interpreted SDS that
 * `materials.usable_documents` still returns — no sheet on file, or the one on
 * file expired, was superseded, or never passed the scanner. The screen must
 * SAY that rather than render an empty panel: "no current safety data on file"
 * is the actionable fact, and it is exactly what `agents/tools/safety.py`
 * reports rather than hides.
 *
 * ⚠️ CONCENTRATIONS ARE STRINGS. They are `NUMERIC(7,4)` in PostgreSQL and
 * arrive as strings over JSON. Parsing them to `number` here would reintroduce
 * the float this project forbids on a controlled record (CLAUDE.md §5), and
 * "10.0000" is also how the range was disclosed — rendering it as `10` quietly
 * changes what the manufacturer said.
 */

import { z } from "zod";

import { apiRequest, type ApiCredentials } from "./client";

export const hazardSchema = z.object({
  hazard_class: z.string(),
  hazard_category: z.string().nullable(),
  hazard_code: z.string().nullable(),
  signal_word: z.string().nullable(),
  statement: z.string().nullable(),
});

export const componentSchema = z.object({
  component_name: z.string(),
  cas_number: z.string().nullable(),
  ec_number: z.string().nullable(),
  // Strings. See the header.
  concentration_low: z.string().nullable(),
  concentration_high: z.string().nullable(),
});

export const storageRuleSchema = z.object({
  id: z.string(),
  min_temperature_c: z.string().nullable(),
  max_temperature_c: z.string().nullable(),
  segregation_class: z.string().nullable(),
  shelf_life_months: z.number().nullable(),
  requirement: z.string(),
});

export const incompatibilitySchema = z.object({
  id: z.string(),
  severity: z.enum(["prohibited", "segregate", "caution"]),
  consequence: z.string(),
  incompatible_hazard_class: z.string().nullable(),
  incompatible_material_code: z.string().nullable(),
  incompatible_material_name: z.string().nullable(),
});

export const currentSdsSchema = z.object({
  id: z.string(),
  document_id: z.string(),
  supplier_revision: z.string().nullable(),
  manufacturer: z.string().nullable(),
  effective_date: z.string().nullable(),
  review_state: z.enum(["pending_review", "confirmed", "rejected"]),
  reviewed_at: z.string().nullable(),
  created_at: z.string(),
  document_title: z.string(),
  issued_on: z.string().nullable(),
  expires_on: z.string().nullable(),
});

export const safetyPositionSchema = z.object({
  // 🔴 NULLABLE, DELIBERATELY. See the header.
  current: currentSdsSchema.nullable(),
  hazards: z.array(hazardSchema),
  components: z.array(componentSchema),
  storage_rules: z.array(storageRuleSchema),
  incompatibilities: z.array(incompatibilitySchema),
});

export const pendingInterpretationSchema = z.object({
  id: z.string(),
  material_id: z.string(),
  supplier_revision: z.string().nullable(),
  manufacturer: z.string().nullable(),
  effective_date: z.string().nullable(),
  created_at: z.string(),
  material_code: z.string(),
  material_name: z.string(),
});

export const safetyAlertSchema = z.object({
  id: z.string(),
  severity: z.enum(["critical", "high", "informational"]),
  change_summary: z.string(),
  created_at: z.string(),
  acknowledged_at: z.string().nullable(),
  project_id: z.string(),
  material_id: z.string().nullable(),
  // The interpretation this alert is about. A safety review is opened against
  // the REVISION, not against the alert — an earlier version of the control
  // sent the alert's own id and would have failed the foreign key every time.
  sds_version_id: z.string(),
  formula_version_id: z.string().nullable(),
  batch_id: z.string().nullable(),
  project_code: z.string(),
  project_name: z.string(),
  material_code: z.string().nullable(),
  material_name: z.string().nullable(),
});

export type Hazard = z.infer<typeof hazardSchema>;
export type Component = z.infer<typeof componentSchema>;
export type StorageRule = z.infer<typeof storageRuleSchema>;
export type Incompatibility = z.infer<typeof incompatibilitySchema>;
export type SafetyPosition = z.infer<typeof safetyPositionSchema>;
export type PendingInterpretation = z.infer<typeof pendingInterpretationSchema>;
export type SafetyAlert = z.infer<typeof safetyAlertSchema>;

const alertList = z.array(safetyAlertSchema);
const pendingList = z.array(pendingInterpretationSchema);

export function fetchSafetyPosition(
  credentials: ApiCredentials,
  materialId: string,
  signal?: AbortSignal,
): Promise<SafetyPosition> {
  return apiRequest(
    { path: `/api/material-safety/materials/${materialId}`, credentials, signal },
    (payload) => safetyPositionSchema.parse(payload),
  );
}

export function fetchSafetyAlerts(
  credentials: ApiCredentials,
  signal?: AbortSignal,
): Promise<SafetyAlert[]> {
  return apiRequest(
    { path: "/api/material-safety/alerts", credentials, signal },
    (payload) => alertList.parse(payload),
  );
}

export function fetchPendingInterpretations(
  credentials: ApiCredentials,
  signal?: AbortSignal,
): Promise<PendingInterpretation[]> {
  return apiRequest(
    { path: "/api/material-safety/interpretations/pending", credentials, signal },
    (payload) => pendingList.parse(payload),
  );
}

export function acknowledgeAlert(
  credentials: ApiCredentials,
  alertId: string,
): Promise<{ id: string }> {
  return apiRequest(
    {
      path: `/api/material-safety/alerts/${alertId}/acknowledge`,
      method: "POST",
      credentials,
      body: {},
    },
    (payload) => z.object({ id: z.string() }).parse(payload),
  );
}

export function reviewInterpretation(
  credentials: ApiCredentials,
  sdsVersionId: string,
  accept: boolean,
): Promise<{ id: string; review_state: string }> {
  return apiRequest(
    {
      path: `/api/material-safety/interpretations/${sdsVersionId}/confirm`,
      method: "POST",
      credentials,
      body: { accept },
    },
    (payload) => z.object({ id: z.string(), review_state: z.string() }).parse(payload),
  );
}

// ---------------------------------------------------------------------------
// The three writes that had no browser caller, and the reads that make them
// pressable.
//
// 🔴 A ROUTE WITH NO CALLER IS THE SAME DEFECT AS A TABLE WITH NO WRITER.
// The first version of this module shipped `POST /interpretations`,
// `POST .../alerts` and `POST .../safety-reviews` with nothing in the browser
// able to reach them — the precise failure this project counted 23 instances
// of on 2026-08-24, reintroduced by the slice whose own plan forbade it in red
// letters. Codex found it.
// ---------------------------------------------------------------------------

export const interpretableDocumentSchema = z.object({
  document_id: z.string(),
  material_id: z.string(),
  title: z.string(),
  issued_on: z.string().nullable(),
  expires_on: z.string().nullable(),
  material_code: z.string(),
  material_name: z.string(),
});

export const materialInterpretationSchema = z.object({
  id: z.string(),
  supplier_revision: z.string().nullable(),
  manufacturer: z.string().nullable(),
  effective_date: z.string().nullable(),
  review_state: z.enum(["pending_review", "confirmed", "rejected"]),
  created_at: z.string(),
  // Whether `materials.usable_documents` still returns its document. A reading
  // whose document has been superseded is HISTORY — still readable, and the
  // only reason revision comparison is possible at all.
  is_current: z.boolean(),
});

export const raisedAlertSchema = z.object({
  id: z.string(),
  project_id: z.string(),
  severity: z.string(),
});

export type InterpretableDocument = z.infer<typeof interpretableDocumentSchema>;
export type MaterialInterpretation = z.infer<typeof materialInterpretationSchema>;

export interface HazardInput {
  readonly hazard_class: string;
  readonly hazard_code?: string;
  readonly signal_word?: string;
  readonly statement?: string;
}

export interface ComponentInput {
  readonly component_name: string;
  readonly cas_number?: string;
  // Strings, never numbers. NUMERIC(7,4) in PostgreSQL, and a float here would
  // round a disclosed concentration before the database ever saw it.
  readonly concentration_low?: string;
  readonly concentration_high?: string;
}

export interface InterpretationRequest {
  readonly document_id: string;
  readonly material_id: string;
  readonly supplier_revision?: string;
  readonly manufacturer?: string;
  readonly effective_date?: string;
  readonly hazards?: readonly HazardInput[];
  readonly components?: readonly ComponentInput[];
}

export function fetchInterpretableDocuments(
  credentials: ApiCredentials,
  signal?: AbortSignal,
): Promise<InterpretableDocument[]> {
  return apiRequest(
    { path: "/api/material-safety/interpretations/candidates", credentials, signal },
    (payload) => z.array(interpretableDocumentSchema).parse(payload),
  );
}

export function fetchMaterialInterpretations(
  credentials: ApiCredentials,
  materialId: string,
  signal?: AbortSignal,
): Promise<MaterialInterpretation[]> {
  return apiRequest(
    {
      path: `/api/material-safety/materials/${materialId}/interpretations`,
      credentials,
      signal,
    },
    (payload) => z.array(materialInterpretationSchema).parse(payload),
  );
}

export function createInterpretation(
  credentials: ApiCredentials,
  request: InterpretationRequest,
): Promise<{ id: string; review_state: string }> {
  return apiRequest(
    {
      path: "/api/material-safety/interpretations",
      method: "POST",
      credentials,
      body: request,
    },
    (payload) => z.object({ id: z.string(), review_state: z.string() }).parse(payload),
  );
}

export function raiseAlerts(
  credentials: ApiCredentials,
  sdsVersionId: string,
  previousVersionId: string,
): Promise<{ id: string; project_id: string; severity: string }[]> {
  return apiRequest(
    {
      path: `/api/material-safety/interpretations/${sdsVersionId}/alerts`,
      method: "POST",
      credentials,
      body: { previous_version_id: previousVersionId },
    },
    // An EMPTY array is a real, meaningful answer: nothing substantive
    // changed between the two revisions, so nothing was raised.
    (payload) => z.array(raisedAlertSchema).parse(payload),
  );
}

export function openSafetyReview(
  credentials: ApiCredentials,
  sdsVersionId: string,
  projectId: string,
  reason: string,
): Promise<{ id: string }> {
  return apiRequest(
    {
      path: `/api/material-safety/interpretations/${sdsVersionId}/safety-reviews`,
      method: "POST",
      credentials,
      body: { project_id: projectId, reason },
    },
    (payload) => z.object({ id: z.string() }).parse(payload),
  );
}

export const comparableRevisionSchema = z.object({
  current_id: z.string(),
  current_revision: z.string().nullable(),
  current_review_state: z.enum(["pending_review", "confirmed", "rejected"]),
  previous_id: z.string(),
  previous_revision: z.string().nullable(),
  material_id: z.string(),
  material_code: z.string(),
  material_name: z.string(),
});

export type ComparableRevision = z.infer<typeof comparableRevisionSchema>;

export function fetchComparableRevisions(
  credentials: ApiCredentials,
  signal?: AbortSignal,
): Promise<ComparableRevision[]> {
  return apiRequest(
    { path: "/api/material-safety/interpretations/comparable", credentials, signal },
    (payload) => z.array(comparableRevisionSchema).parse(payload),
  );
}
