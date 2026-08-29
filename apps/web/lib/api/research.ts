/**
 * The Research Center, over HTTP.
 *
 * 🔴 EVERY SCHEMA HERE MIRRORS THE RESPONSE, NOT THE SQL.
 *
 * Three wrong client types shipped in two days by reading the query instead of
 * the return value — the most recent because a service stringified a `NUMERIC`
 * at the boundary and the schema said `z.number()`. So each field below was
 * checked against what `app/api/research.py` actually returns, which is what
 * `app/domains/research/service.py` actually selects.
 *
 * 🔴 `approval_status` IS THE ROUTE'S, AND IT IS NULLABLE FOR A REASON.
 *
 * A finding's approval is not a column on the finding: it is the status of its
 * route in the one approval engine. `null` means the finding has never been
 * submitted — an ordinary state, not a fault — and the screen must render that
 * as "Draft", never as a failed approval.
 *
 * ⚠️ TWO CONFIDENCE SCALES EXIST IN THIS PRODUCT AND THEY ARE NOT THE SAME.
 * A research FINDING is high / moderate / low / unknown (§29 — how strong is
 * this conclusion?). A competitor composition CLAIM is verified / supported /
 * probable / possible / unknown (how well do we know somebody else's recipe?).
 * Do not import one into the other.
 */

import { z } from "zod";

import { apiRequest, type ApiCredentials } from "./client";

/**
 * §6's A-X source ranking, the same vocabulary `competitors.ts` carries — the
 * server stores the identical values, because two spellings of one enum is the
 * "two literals in two files" defect this project keeps finding.
 */
export const RESEARCH_GRADES = [
  { id: "A", label: "A — validated internal evidence, a standard, or manufacturer documentation" },
  { id: "B", label: "B — peer-reviewed literature, a patent, or a recognised institution" },
  { id: "C", label: "C — supplier literature or a conference paper" },
  { id: "D", label: "D — a general web source" },
  { id: "X", label: "X — unverified or unreliable" },
] as const;

export const RESEARCH_SOURCE_KINDS = [
  { id: "document", label: "A document on file", needsDocument: true },
  { id: "manual_observation", label: "Something observed directly", needsDocument: false },
  { id: "laboratory", label: "Our own laboratory result", needsDocument: false },
  { id: "literature", label: "Published literature", needsDocument: false },
  { id: "patent", label: "A patent", needsDocument: false },
  { id: "inference", label: "Inferred from the above", needsDocument: false },
  { id: "model", label: "Model hypothesis", needsDocument: false },
] as const;

/**
 * §29's scale, and its own warning: *"Never use green PASS for an AI
 * recommendation. Green should remain reserved for validated/approved
 * technical results."* So none of these carries a green tone — a finding is a
 * conclusion, not a passed test, and the screen keeps that distinction.
 */
export const FINDING_CONFIDENCES = [
  { id: "high", label: "High — multiple consistent validated internal results" },
  { id: "moderate", label: "Moderate — some experimental plus credible external evidence" },
  { id: "low", label: "Low — limited evidence or significant extrapolation" },
  { id: "unknown", label: "Unknown — insufficient evidence" },
] as const;

/** §28's card marks: ✓ supports, ○ related — plus the honest third case. */
export const EVIDENCE_STANCES = [
  { id: "supports", label: "Supports", mark: "✓" },
  { id: "related", label: "Related", mark: "○" },
  { id: "contradicts", label: "Contradicts", mark: "✕" },
] as const;

export const investigationSchema = z.object({
  id: z.string(),
  investigation_code: z.string(),
  title: z.string(),
  research_question: z.string(),
  status: z.enum(["active", "on_hold", "closed"]),
  project_id: z.string().nullable(),
  project_code: z.string().nullable(),
  owner_user_id: z.string(),
  created_at: z.string(),
  question_count: z.number(),
  evidence_count: z.number(),
  finding_count: z.number(),
  proposal_count: z.number(),
});

export const researchQuestionSchema = z.object({
  id: z.string(),
  sequence_number: z.number(),
  question: z.string(),
  status: z.enum(["open", "answered", "unanswerable"]),
  created_at: z.string(),
  evidence_count: z.number(),
});

export const researchSourceSchema = z.object({
  id: z.string(),
  source_kind: z.string(),
  evidence_grade: z.string(),
  title: z.string(),
  source_locator: z.string().nullable(),
  document_id: z.string().nullable(),
  created_at: z.string(),
});

export const evidenceCardSchema = z.object({
  id: z.string(),
  question_id: z.string().nullable(),
  source_id: z.string().nullable(),
  formula_version_id: z.string().nullable(),
  test_id: z.string().nullable(),
  failure_id: z.string().nullable(),
  stance: z.enum(["supports", "related", "contradicts"]),
  summary: z.string(),
  created_at: z.string(),
  source_title: z.string().nullable(),
  evidence_grade: z.string().nullable(),
  source_kind: z.string().nullable(),
  question_number: z.number().nullable(),
  version_code: z.string().nullable(),
  test_number: z.string().nullable(),
  failure_code: z.string().nullable(),
});

export const findingSchema = z.object({
  id: z.string(),
  finding_code: z.string(),
  subject: z.string(),
  statement: z.string(),
  applicability: z.string(),
  limitations: z.string().nullable(),
  confidence: z.enum(["high", "moderate", "low", "unknown"]),
  status: z.enum(["draft", "submitted", "withdrawn"]),
  author_id: z.string(),
  promoted_document_id: z.string().nullable(),
  promoted_at: z.string().nullable(),
  created_at: z.string(),
  investigation_id: z.string(),
  investigation_code: z.string(),
  project_id: z.string().nullable(),
  // The ROUTE's status. `null` = never submitted.
  approval_status: z.string().nullable(),
});

export const hypothesisSchema = z.object({
  id: z.string(),
  statement: z.string(),
  rationale: z.string().nullable(),
  status: z.enum(["open", "supported", "refuted", "withdrawn"]),
  finding_id: z.string().nullable(),
  finding_code: z.string().nullable(),
  created_at: z.string(),
  proposal_count: z.number(),
});

export const knowledgeGapSchema = z.object({
  id: z.string(),
  description: z.string(),
  impact: z.enum(["high", "moderate", "low"]),
  status: z.enum(["open", "closed"]),
  question_id: z.string().nullable(),
  question_number: z.number().nullable(),
  created_at: z.string(),
});

export const proposalSchema = z.object({
  id: z.string(),
  proposal_code: z.string(),
  objective: z.string(),
  basis: z.string(),
  variables: z.string(),
  controlled_variables: z.string().nullable(),
  expected_direction: z.string(),
  required_tests: z.string(),
  risks: z.string().nullable(),
  confidence: z.enum(["high", "moderate", "low", "unknown"]),
  status: z.enum(["proposed", "accepted", "rejected", "withdrawn"]),
  hypothesis_id: z.string().nullable(),
  resulting_formula_version_id: z.string().nullable(),
  resulting_version_code: z.string().nullable(),
  decided_by: z.string().nullable(),
  decided_at: z.string().nullable(),
  decision_note: z.string().nullable(),
  created_at: z.string(),
  investigation_id: z.string(),
  investigation_code: z.string(),
});

export type Investigation = z.infer<typeof investigationSchema>;
export type ResearchQuestion = z.infer<typeof researchQuestionSchema>;
export type ResearchSource = z.infer<typeof researchSourceSchema>;
export type EvidenceCard = z.infer<typeof evidenceCardSchema>;
export type Finding = z.infer<typeof findingSchema>;
export type Hypothesis = z.infer<typeof hypothesisSchema>;
export type KnowledgeGap = z.infer<typeof knowledgeGapSchema>;
export type ExperimentProposal = z.infer<typeof proposalSchema>;

export interface InvestigationRequest {
  readonly title: string;
  readonly research_question: string;
  readonly project_id?: string;
  readonly search_strategy?: string;
}

export interface SourceRequest {
  readonly source_kind: string;
  readonly evidence_grade: string;
  readonly title: string;
  readonly source_locator?: string;
  readonly document_id?: string;
}

export interface EvidenceRequest {
  readonly summary: string;
  readonly stance: string;
  readonly question_id?: string;
  readonly source_id?: string;
  readonly formula_version_id?: string;
  readonly test_id?: string;
  readonly failure_id?: string;
}

export interface FindingRequest {
  readonly subject: string;
  readonly statement: string;
  readonly applicability: string;
  readonly confidence: string;
  readonly limitations?: string;
}

export interface GapRequest {
  readonly description: string;
  readonly impact: string;
  readonly question_id?: string;
}

export interface ProposalRequest {
  readonly objective: string;
  readonly basis: string;
  readonly variables: string;
  readonly expected_direction: string;
  readonly required_tests: string;
  readonly confidence: string;
  readonly controlled_variables?: string;
  readonly risks?: string;
  readonly hypothesis_id?: string;
}

export interface AcceptProposalRequest {
  readonly version_id: string;
  readonly change_reason: string;
  readonly technical_hypothesis: string;
  readonly decision_note?: string;
}

const idResult = z.object({ id: z.string() });

export function fetchInvestigations(
  credentials: ApiCredentials,
  signal?: AbortSignal,
): Promise<Investigation[]> {
  return apiRequest({ path: "/api/research", credentials, signal }, (payload) =>
    z.array(investigationSchema).parse(payload),
  );
}

export function fetchResearchQuestions(
  credentials: ApiCredentials,
  investigationId: string,
  signal?: AbortSignal,
): Promise<ResearchQuestion[]> {
  return apiRequest(
    { path: `/api/research/${investigationId}/questions`, credentials, signal },
    (payload) => z.array(researchQuestionSchema).parse(payload),
  );
}

export function fetchResearchSources(
  credentials: ApiCredentials,
  investigationId: string,
  signal?: AbortSignal,
): Promise<ResearchSource[]> {
  return apiRequest(
    { path: `/api/research/${investigationId}/sources`, credentials, signal },
    (payload) => z.array(researchSourceSchema).parse(payload),
  );
}

export function fetchEvidenceCards(
  credentials: ApiCredentials,
  investigationId: string,
  signal?: AbortSignal,
): Promise<EvidenceCard[]> {
  return apiRequest(
    { path: `/api/research/${investigationId}/evidence`, credentials, signal },
    (payload) => z.array(evidenceCardSchema).parse(payload),
  );
}

export function fetchHypotheses(
  credentials: ApiCredentials,
  investigationId: string,
  signal?: AbortSignal,
): Promise<Hypothesis[]> {
  return apiRequest(
    { path: `/api/research/${investigationId}/hypotheses`, credentials, signal },
    (payload) => z.array(hypothesisSchema).parse(payload),
  );
}

export function fetchKnowledgeGaps(
  credentials: ApiCredentials,
  investigationId: string,
  signal?: AbortSignal,
): Promise<KnowledgeGap[]> {
  return apiRequest(
    { path: `/api/research/${investigationId}/gaps`, credentials, signal },
    (payload) => z.array(knowledgeGapSchema).parse(payload),
  );
}

export function fetchFindings(
  credentials: ApiCredentials,
  signal?: AbortSignal,
): Promise<Finding[]> {
  return apiRequest({ path: "/api/research/findings", credentials, signal }, (payload) =>
    z.array(findingSchema).parse(payload),
  );
}

export function fetchProposals(
  credentials: ApiCredentials,
  signal?: AbortSignal,
): Promise<ExperimentProposal[]> {
  return apiRequest({ path: "/api/research/proposals", credentials, signal }, (payload) =>
    z.array(proposalSchema).parse(payload),
  );
}

export function openInvestigation(
  credentials: ApiCredentials,
  request: InvestigationRequest,
): Promise<{ id: string; investigation_code: string }> {
  return apiRequest(
    { path: "/api/research", method: "POST", credentials, body: request },
    (payload) => z.object({ id: z.string(), investigation_code: z.string() }).parse(payload),
  );
}

export function closeInvestigation(
  credentials: ApiCredentials,
  investigationId: string,
): Promise<{ id: string; status: string }> {
  return apiRequest(
    { path: `/api/research/${investigationId}/close`, method: "POST", credentials },
    (payload) => z.object({ id: z.string(), status: z.string() }).parse(payload),
  );
}

export function recordResearchQuestion(
  credentials: ApiCredentials,
  investigationId: string,
  question: string,
): Promise<{ id: string; sequence_number: number }> {
  return apiRequest(
    {
      path: `/api/research/${investigationId}/questions`,
      method: "POST",
      credentials,
      body: { question },
    },
    (payload) => z.object({ id: z.string(), sequence_number: z.number() }).parse(payload),
  );
}

export function settleResearchQuestion(
  credentials: ApiCredentials,
  questionId: string,
  status: string,
): Promise<{ id: string; status: string }> {
  return apiRequest(
    {
      path: `/api/research/questions/${questionId}/settle`,
      method: "POST",
      credentials,
      body: { status },
    },
    (payload) => z.object({ id: z.string(), status: z.string() }).parse(payload),
  );
}

export function recordResearchSource(
  credentials: ApiCredentials,
  investigationId: string,
  request: SourceRequest,
): Promise<{ id: string }> {
  return apiRequest(
    {
      path: `/api/research/${investigationId}/sources`,
      method: "POST",
      credentials,
      body: request,
    },
    (payload) => idResult.parse(payload),
  );
}

export function recordEvidenceCard(
  credentials: ApiCredentials,
  investigationId: string,
  request: EvidenceRequest,
): Promise<{ id: string }> {
  return apiRequest(
    {
      path: `/api/research/${investigationId}/evidence`,
      method: "POST",
      credentials,
      body: request,
    },
    (payload) => idResult.parse(payload),
  );
}

export interface HypothesisRequest {
  readonly statement: string;
  readonly rationale?: string;
  readonly finding_id?: string;
}

export function recordHypothesis(
  credentials: ApiCredentials,
  investigationId: string,
  request: HypothesisRequest,
): Promise<{ id: string }> {
  return apiRequest(
    {
      path: `/api/research/${investigationId}/hypotheses`,
      method: "POST",
      credentials,
      body: request,
    },
    (payload) => idResult.parse(payload),
  );
}

export function decideHypothesis(
  credentials: ApiCredentials,
  hypothesisId: string,
  status: string,
): Promise<{ id: string; status: string }> {
  return apiRequest(
    {
      path: `/api/research/hypotheses/${hypothesisId}/decide`,
      method: "POST",
      credentials,
      body: { status },
    },
    (payload) => z.object({ id: z.string(), status: z.string() }).parse(payload),
  );
}

export function recordKnowledgeGap(
  credentials: ApiCredentials,
  investigationId: string,
  request: GapRequest,
): Promise<{ id: string }> {
  return apiRequest(
    { path: `/api/research/${investigationId}/gaps`, method: "POST", credentials, body: request },
    (payload) => idResult.parse(payload),
  );
}

export function resolveKnowledgeGap(
  credentials: ApiCredentials,
  gapId: string,
): Promise<{ id: string; status: string }> {
  return apiRequest(
    { path: `/api/research/gaps/${gapId}/resolve`, method: "POST", credentials },
    (payload) => z.object({ id: z.string(), status: z.string() }).parse(payload),
  );
}

export function recordFinding(
  credentials: ApiCredentials,
  investigationId: string,
  request: FindingRequest,
): Promise<{ id: string; finding_code: string; status: string }> {
  return apiRequest(
    {
      path: `/api/research/${investigationId}/findings`,
      method: "POST",
      credentials,
      body: request,
    },
    (payload) =>
      z
        .object({ id: z.string(), finding_code: z.string(), status: z.string() })
        .parse(payload),
  );
}

export function submitFinding(
  credentials: ApiCredentials,
  findingId: string,
): Promise<{ id: string; status: string }> {
  return apiRequest(
    { path: `/api/research/findings/${findingId}/submit`, method: "POST", credentials },
    // 🔴 `.passthrough()` ON THE ROUTE, DELIBERATELY. The server returns the
    // approval engine's own route object beside the two fields this screen
    // reads. Restating the engine's shape here would be a second definition of
    // it, drifting the moment `/approvals` changes.
    (payload) =>
      z.object({ id: z.string(), status: z.string() }).passthrough().parse(payload),
  );
}

export function promoteFinding(
  credentials: ApiCredentials,
  findingId: string,
): Promise<{ id: string; document_id: string }> {
  return apiRequest(
    { path: `/api/research/findings/${findingId}/promote`, method: "POST", credentials },
    (payload) => z.object({ id: z.string(), document_id: z.string() }).parse(payload),
  );
}

export function proposeExperiment(
  credentials: ApiCredentials,
  investigationId: string,
  request: ProposalRequest,
): Promise<{ id: string; proposal_code: string; status: string }> {
  return apiRequest(
    {
      path: `/api/research/${investigationId}/proposals`,
      method: "POST",
      credentials,
      body: request,
    },
    (payload) =>
      z
        .object({ id: z.string(), proposal_code: z.string(), status: z.string() })
        .parse(payload),
  );
}

export function acceptProposal(
  credentials: ApiCredentials,
  proposalId: string,
  request: AcceptProposalRequest,
): Promise<{ id: string; status: string; version_code: string }> {
  return apiRequest(
    {
      path: `/api/research/proposals/${proposalId}/accept`,
      method: "POST",
      credentials,
      body: request,
    },
    (payload) =>
      z
        .object({
          id: z.string(),
          status: z.string(),
          formula_version_id: z.string(),
          version_code: z.string(),
        })
        .parse(payload),
  );
}

export function rejectProposal(
  credentials: ApiCredentials,
  proposalId: string,
  decisionNote: string,
): Promise<{ id: string; status: string }> {
  return apiRequest(
    {
      path: `/api/research/proposals/${proposalId}/reject`,
      method: "POST",
      credentials,
      body: { decision_note: decisionNote },
    },
    (payload) => z.object({ id: z.string(), status: z.string() }).parse(payload),
  );
}
