/**
 * Competitor intelligence, over HTTP.
 *
 * 🔴 THE MATRIX IS NOT A RECIPE, AND THIS MODULE MUST NOT LET IT LOOK LIKE ONE.
 *
 * The specification forbids presenting an inferred competitor composition as a
 * known or verified formula. So `compositionMatrixSchema` carries a
 * `disclaimer` the SERVER supplies and the screen renders — not a sentence the
 * screen remembers to add, because a screen that forgets it would be doing the
 * one thing the specification rules out.
 *
 * ⚠️ CONCENTRATIONS ARE STRINGS. `NUMERIC(7,4)` in PostgreSQL, and the server
 * stringifies them at the boundary. Parsing to `number` here would reintroduce
 * the float CLAUDE.md §5 forbids on a controlled record, and would render
 * "10.0000" — a range disclosed to four decimal places — as "10".
 */

import { z } from "zod";

import { apiRequest, type ApiCredentials } from "./client";
import { API_BASE_URL } from "./config";

export const competitorProductSchema = z.object({
  id: z.string(),
  manufacturer: z.string(),
  product_name: z.string(),
  product_code: z.string().nullable(),
  market_segment: z.string().nullable(),
  project_id: z.string().nullable(),
  created_at: z.string(),
  document_count: z.number(),
  evidence_count: z.number(),
});

/**
 * How a claim is known. SEPARATE from the document's type: a person reading a
 * tin is making an observation, not an inference, and the two must not collapse
 * into one field.
 */
export const EVIDENCE_SOURCES = [
  { id: "document", label: "A document on file", needsDocument: true },
  { id: "manual_observation", label: "Read from the product myself", needsDocument: false },
  { id: "laboratory", label: "Our own laboratory result", needsDocument: false },
  { id: "literature", label: "Published literature", needsDocument: false },
  { id: "patent", label: "A patent", needsDocument: false },
  { id: "inference", label: "Inferred from the above", needsDocument: false },
  { id: "model", label: "Model hypothesis", needsDocument: false },
] as const;

/** The A–X ranking from the research source document. */
export const EVIDENCE_GRADES = [
  { id: "A", label: "A — validated internal evidence, a standard, or manufacturer documentation" },
  { id: "B", label: "B — peer-reviewed literature, a patent, or a recognised institution" },
  { id: "C", label: "C — supplier literature or a conference paper" },
  { id: "D", label: "D — a general web source" },
  { id: "X", label: "X — unverified or unreliable" },
] as const;

export const evidenceRowSchema = z.object({
  id: z.string(),
  component_name: z.string(),
  cas_number: z.string().nullable(),
  component_function: z.string().nullable(),
  // Strings. See the header.
  concentration_low: z.string().nullable(),
  concentration_high: z.string().nullable(),
  is_balance: z.boolean(),
  evidence_source: z.string(),
  evidence_grade: z.string(),
  confidence: z.enum(["verified", "supported", "probable", "possible", "unknown"]),
  source_locator: z.string().nullable(),
  rationale: z.string().nullable(),
  verified_at: z.string().nullable(),
  source_document_id: z.string().nullable(),
  sample_id: z.string().nullable(),
  test_id: z.string().nullable(),
  source_document_title: z.string().nullable(),
  source_document_type: z.string().nullable(),
});

export const compositionMatrixSchema = z.object({
  rows: z.array(evidenceRowSchema),
  summary: z.record(z.string(), z.number()),
  // 🔴 SUPPLIED BY THE SERVER AND RENDERED VERBATIM.
  disclaimer: z.string(),
});

export const competitorDocumentSchema = z.object({
  id: z.string(),
  document_type: z.string(),
  title: z.string(),
  content_type: z.string().nullable(),
  byte_size: z.number().nullable(),
  issued_on: z.string().nullable(),
  expires_on: z.string().nullable(),
  created_at: z.string(),
});

export const competitorSampleSchema = z.object({
  id: z.string(),
  sample_reference: z.string(),
  acquired_on: z.string().nullable(),
  batch_marking: z.string().nullable(),
  observations: z.string().nullable(),
  registered_by: z.string(),
  created_at: z.string(),
  // A count, and it is named as one. `has_root_cause` was a column whose name
  // asked a yes/no question and whose value was a number (2026-08-27); a field
  // called `evidence_count` can only be read as the number it is.
  evidence_count: z.number(),
});

export const competitorBenchmarkSchema = z.object({
  id: z.string(),
  attribute: z.string(),
  competitor_value: z.string().nullable(),
  our_value: z.string().nullable(),
  gap_summary: z.string(),
  project_id: z.string(),
  project_name: z.string().nullable(),
  project_code: z.string().nullable(),
  formula_version_id: z.string().nullable(),
  test_id: z.string().nullable(),
  recorded_by: z.string(),
  created_at: z.string(),
  // 🔴 NO DISPOSITION FIELD, DELIBERATELY. Testing owns GREEN/YELLOW/RED and
  // the server does not send one; a colour invented here would be a second
  // answer to a question Testing already answers.
});

export type CompetitorProduct = z.infer<typeof competitorProductSchema>;
export type EvidenceRow = z.infer<typeof evidenceRowSchema>;
export type CompositionMatrix = z.infer<typeof compositionMatrixSchema>;
export type CompetitorDocument = z.infer<typeof competitorDocumentSchema>;
export type CompetitorSample = z.infer<typeof competitorSampleSchema>;
export type CompetitorBenchmark = z.infer<typeof competitorBenchmarkSchema>;

export interface ProductRequest {
  readonly manufacturer: string;
  readonly product_name: string;
  readonly product_code?: string;
  readonly market_segment?: string;
  readonly notes?: string;
}

export interface EvidenceRequest {
  readonly component_name: string;
  readonly evidence_source: string;
  readonly evidence_grade: string;
  readonly cas_number?: string;
  readonly component_function?: string;
  readonly concentration_low?: string;
  readonly concentration_high?: string;
  readonly is_balance?: boolean;
  readonly source_document_id?: string;
  // 🔴 THE SERVER HAS ALWAYS ACCEPTED THIS AND NOTHING EVER SENT IT.
  // `manual_observation` means somebody read a physical tin; without naming
  // WHICH tin, the claim cannot be re-checked and the grade is unearned.
  readonly sample_id?: string;
  readonly source_locator?: string;
  readonly rationale?: string;
}

export interface SampleRequest {
  readonly sample_reference: string;
  readonly acquired_on?: string;
  readonly batch_marking?: string;
  readonly observations?: string;
}

export interface BenchmarkRequest {
  readonly project_id: string;
  readonly attribute: string;
  readonly gap_summary: string;
  readonly competitor_value?: string;
  readonly our_value?: string;
  readonly formula_version_id?: string;
  readonly test_id?: string;
}

export function fetchCompetitorProducts(
  credentials: ApiCredentials,
  signal?: AbortSignal,
): Promise<CompetitorProduct[]> {
  return apiRequest({ path: "/api/competitors", credentials, signal }, (payload) =>
    z.array(competitorProductSchema).parse(payload),
  );
}

export function fetchCompositionMatrix(
  credentials: ApiCredentials,
  productId: string,
  signal?: AbortSignal,
): Promise<CompositionMatrix> {
  return apiRequest(
    { path: `/api/competitors/${productId}/composition`, credentials, signal },
    (payload) => compositionMatrixSchema.parse(payload),
  );
}

export function fetchCompetitorDocuments(
  credentials: ApiCredentials,
  productId: string,
  signal?: AbortSignal,
): Promise<CompetitorDocument[]> {
  return apiRequest(
    { path: `/api/competitors/${productId}/documents`, credentials, signal },
    (payload) => z.array(competitorDocumentSchema).parse(payload),
  );
}

export function registerCompetitorProduct(
  credentials: ApiCredentials,
  request: ProductRequest,
): Promise<{ id: string }> {
  return apiRequest(
    { path: "/api/competitors", method: "POST", credentials, body: request },
    (payload) => z.object({ id: z.string() }).parse(payload),
  );
}

export function recordCompetitorEvidence(
  credentials: ApiCredentials,
  productId: string,
  request: EvidenceRequest,
): Promise<{ id: string; confidence: string }> {
  return apiRequest(
    {
      path: `/api/competitors/${productId}/evidence`,
      method: "POST",
      credentials,
      body: request,
    },
    (payload) => z.object({ id: z.string(), confidence: z.string() }).parse(payload),
  );
}

export function gradeCompetitorEvidence(
  credentials: ApiCredentials,
  evidenceId: string,
  confidence: string,
): Promise<{ id: string; confidence: string }> {
  return apiRequest(
    {
      path: `/api/competitors/evidence/${evidenceId}/grade`,
      method: "POST",
      credentials,
      body: { confidence },
    },
    (payload) => z.object({ id: z.string(), confidence: z.string() }).parse(payload),
  );
}

/**
 * Upload a label or a product photograph.
 *
 * 🔴 MULTIPART, AND IT DOES NOT GO THROUGH `apiRequest`.
 *
 * `apiRequest` JSON-encodes its body and sets `Content-Type: application/json`.
 * A file needs `FormData` and the browser's own boundary — setting the header
 * by hand omits the boundary and the server cannot parse the parts. So this is
 * a deliberate exception, and it still carries the same credentials and
 * organization header every other call does.
 */
export async function uploadCompetitorDocument(
  credentials: ApiCredentials,
  productId: string,
  file: File,
  documentType: string,
  title: string,
): Promise<{ id: string }> {
  const body = new FormData();
  body.append("file", file);
  body.append("document_type", documentType);
  body.append("title", title);

  if (API_BASE_URL === null) {
    // The same absence `apiRequest` distinguishes: this build has nothing to
    // call, which is not a failure and must not read as one.
    throw new Error("this build is not pointed at an API, so nothing can be uploaded");
  }
  const response = await fetch(`${API_BASE_URL}/api/competitors/${productId}/documents`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${credentials.token}`,
      "X-Organization-Id": credentials.organizationId,
      // NO Content-Type: the browser sets it, WITH the multipart boundary.
    },
    body,
  });

  if (!response.ok) {
    let detail = `the upload failed (${response.status})`;
    try {
      const parsed = (await response.json()) as { detail?: unknown };
      if (typeof parsed.detail === "string") detail = parsed.detail;
    } catch {
      // A non-JSON error body. The status alone is what we have.
    }
    throw new Error(detail);
  }
  return z.object({ id: z.string() }).parse(await response.json());
}


export function fetchCompetitorSamples(
  credentials: ApiCredentials,
  productId: string,
  signal?: AbortSignal,
): Promise<CompetitorSample[]> {
  return apiRequest(
    { path: `/api/competitors/${productId}/samples`, credentials, signal },
    (payload) => z.array(competitorSampleSchema).parse(payload),
  );
}

export function fetchCompetitorBenchmarks(
  credentials: ApiCredentials,
  productId: string,
  signal?: AbortSignal,
): Promise<CompetitorBenchmark[]> {
  return apiRequest(
    { path: `/api/competitors/${productId}/benchmarks`, credentials, signal },
    (payload) => z.array(competitorBenchmarkSchema).parse(payload),
  );
}

export function registerCompetitorSample(
  credentials: ApiCredentials,
  productId: string,
  request: SampleRequest,
): Promise<{ id: string }> {
  return apiRequest(
    {
      path: `/api/competitors/${productId}/samples`,
      method: "POST",
      credentials,
      body: request,
    },
    (payload) => z.object({ id: z.string() }).parse(payload),
  );
}

export function recordCompetitorBenchmark(
  credentials: ApiCredentials,
  productId: string,
  request: BenchmarkRequest,
): Promise<{ id: string }> {
  return apiRequest(
    {
      path: `/api/competitors/${productId}/benchmarks`,
      method: "POST",
      credentials,
      body: request,
    },
    (payload) => z.object({ id: z.string() }).parse(payload),
  );
}
