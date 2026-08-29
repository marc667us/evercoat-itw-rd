/**
 * Projects, over HTTP.
 *
 * Parsed rather than cast, for the reason set out at length in
 * `materials.ts`: a server that renamed a field would hand back rows whose
 * value is `undefined`, and the grid would render a column of blanks that
 * looks exactly like a database with nothing recorded. Parsing turns that
 * into a named error on the screen that consumes it.
 *
 * 🔴 WHAT THE LIST ENDPOINT DOES **NOT** RETURN
 *
 * `ProjectSummary` (apps/api/app/api/projects.py:80) carries the project's
 * own columns and nothing else. It has no gate progress, no requirement
 * counts and no team lead — each of those needs a separate query, and the
 * API exposes them on separate routes (`/dashboard`,
 * `/requirements/matrix`, `/members`) precisely so a list of forty
 * projects does not run forty sub-queries.
 *
 * The demonstration dataset DOES carry them, because it is a bundled
 * fixture with no cost to joining. That difference is the trap: a grid
 * built to the fixture's shape would show three rich columns on
 * demonstration data and three empty ones on live data, and the obvious
 * "fix" is to invent something to put in them.
 *
 * So those columns are not on the list at all. They belong to the project
 * detail screen, where the routes that answer them are already called.
 * Same judgement as `materials.ts` making the supplier column a COUNT
 * rather than inventing names it had not fetched.
 */

import { z } from "zod";

import { apiRequest, type ApiCredentials } from "./client";

export const projectSchema = z.object({
  id: z.string(),
  project_code: z.string(),
  name: z.string(),
  product_family: z.string().nullable(),
  status: z.string(),
  priority: z.string(),
  current_stage: z.string().nullable(),
  confidentiality: z.string(),
  // 🔴 REQUIRED, THOUGH NULLABLE. IT WAS `.optional()` AND THAT WAS WRONG.
  //
  // `ProjectSummary` declares a DEFAULT for this field, and Pydantic
  // serialises defaulted fields, so the key is ALWAYS present — either a
  // date or null. Accepting its absence meant a server that dropped or
  // renamed the column would parse cleanly and the grid would state "no
  // target release date set", which is a claim about the project rather
  // than about the response. Absence presenting as a fact. Codex found it.
  target_release_date: z.string().nullable(),
});

export type Project = z.infer<typeof projectSchema>;

const projectList = z.array(projectSchema);

export function fetchProjects(
  credentials: ApiCredentials,
  signal?: AbortSignal,
): Promise<Project[]> {
  return apiRequest({ path: "/api/projects", credentials, signal }, (payload) =>
    projectList.parse(payload),
  );
}

// ---------------------------------------------------------------------------
// Slice 2's write half — ten endpoints, one of which had a browser caller
// ---------------------------------------------------------------------------
//
// 🔴 THE PROJECT MODULE COULD BE READ AND NOT WORKED.
//
// Measured 2026-08-27: `app/api/projects.py` declares eleven write endpoints
// and exactly one — `POST /api/projects` — could be reached from a browser.
// Advancing a stage, approving a requirement, managing a milestone, tracking a
// risk and putting somebody on a project were all API-only. Those are the acts
// that make the Lead and the Director roles mean anything: measured on the
// seeded realm, `lead.demo` holds `project.advance_stage`, `requirement.approve`,
// `milestone.manage` and `project.assign_member`, and had a control for none of
// them.
//
// 🔴 EVERY WRITE HERE NEEDS TWO GATES, AND ONLY ONE IS A PERMISSION.
//
// Each route carries `require_permission(...)` AND `require_project_member()`.
// The second is not visible in a permission set — but it does not have to be:
// `GET /api/projects/{id}` is member-gated too, so a caller who can load the
// workspace at all has already passed it. That is worth stating because the
// obvious alternative — fetching the member list to decide what to show — would
// be a second implementation of a gate the server already applied, and the
// membership read is itself member-gated, so it could never answer for someone
// outside.
//
// ⚠️ A `reason` IS MANDATORY ON FOUR OF THESE, and that is §9's shape rather
// than a form-validation detail: advancing a stage, changing a milestone's
// status, updating a risk and removing a member are all decisions somebody has
// to be able to reconstruct later. The server requires 3 characters minimum;
// the screens require the same so the round trip is not spent being told.

export const projectMemberSchema = z.object({
  id: z.string(),
  user_id: z.string(),
  project_role: z.string(),
  status: z.string(),
  created_at: z.string(),
  // 🔴 THE ORGANIZATION'S VIEW OF THE PERSON, NOT THE GLOBAL IDENTITY'S.
  // `list_members` joins `core.organization_members`, because migration 052
  // moved a tenant's `display_name` and `email` onto the membership and revoked
  // the global columns from the runtime roles (I106). So these are this
  // organization's name for this colleague, which is the only name it is
  // entitled to.
  display_name: z.string(),
  email: z.string(),
  // 🔴 NULLABLE. Raised by Codex and confirmed against migration 003:
  // `lead_user_id` is a nullable UUID, and `(p.lead_user_id = pm.user_id)`
  // yields NULL — not false — when there is no lead. A project without one is
  // rare (everything created through `POST /api/projects` sets it) and the
  // database permits it, so `z.boolean()` would have failed the WHOLE members
  // response for exactly the projects most likely to be imported rather than
  // created here. Null means "not the lead", which is what a reader needs.
  is_project_lead: z.boolean().nullable(),
});
export type ProjectMember = z.infer<typeof projectMemberSchema>;

const membersEnvelope = z.object({
  project_id: z.string(),
  members: z.array(projectMemberSchema),
});

export function fetchProjectMembers(
  credentials: ApiCredentials,
  projectId: string,
  signal?: AbortSignal,
): Promise<ProjectMember[]> {
  return apiRequest(
    { path: `/api/projects/${projectId}/members`, credentials, signal },
    (payload) => membersEnvelope.parse(payload).members,
  );
}

export const milestoneSchema = z.object({
  id: z.string(),
  name: z.string(),
  description: z.string().nullable(),
  planned_date: z.string(),
  actual_date: z.string().nullable(),
  status: z.string(),
  // Computed by the server as `status IN ('planned','in_progress') AND
  // planned_date < CURRENT_DATE`. A browser deriving this from a date string
  // would be a second definition of "overdue" — and would get it wrong the
  // moment a timezone was involved.
  is_overdue: z.boolean(),
});
export type Milestone = z.infer<typeof milestoneSchema>;

const milestonesEnvelope = z.object({
  project_id: z.string(),
  milestones: z.array(milestoneSchema),
});

export function fetchMilestones(
  credentials: ApiCredentials,
  projectId: string,
  signal?: AbortSignal,
): Promise<Milestone[]> {
  return apiRequest(
    { path: `/api/projects/${projectId}/milestones`, credentials, signal },
    (payload) => milestonesEnvelope.parse(payload).milestones,
  );
}

export const riskSchema = z.object({
  id: z.string(),
  risk_code: z.string(),
  title: z.string(),
  description: z.string().nullable(),
  category: z.string(),
  probability: z.string(),
  impact: z.string(),
  status: z.string(),
  mitigation: z.string().nullable(),
  owner_user_id: z.string().nullable(),
  updated_at: z.string(),
});
export type Risk = z.infer<typeof riskSchema>;

const risksEnvelope = z.object({
  project_id: z.string(),
  risks: z.array(riskSchema),
});

export function fetchRisks(
  credentials: ApiCredentials,
  projectId: string,
  signal?: AbortSignal,
): Promise<Risk[]> {
  return apiRequest(
    { path: `/api/projects/${projectId}/risks`, credentials, signal },
    (payload) => risksEnvelope.parse(payload).risks,
  );
}

/**
 * One stage of the pipeline.
 *
 * 🔴 `status` IS NOT NULLABLE, AND THE FIRST VERSION OF THIS COMMENT WAS WRONG.
 *
 * It read: *"`status` IS NULLABLE BECAUSE THE JOIN IS… a stage the project has
 * not reached has no row and every `ps.*` column comes back null."* The join
 * is indeed a LEFT JOIN — and `project_pipeline` RESHAPES the result before
 * returning it: `"status": r["status"] or "not_started"`. So the API never
 * emits null here, the screen's "not reached" branch was unreachable code, and
 * the comment asserted a distinction the response does not make.
 *
 * Raised by Codex. It is the same mistake as the requirement matrix twenty
 * lines of this file away — reading the SQL and believing it — caught twice in
 * one commit, once by measuring and once by review. *The SQL is not the
 * contract; the response is.*
 */
export const pipelineStageSchema = z.object({
  stage_code: z.string(),
  name: z.string(),
  sequence: z.number(),
  requires_approval: z.boolean(),
  status: z.string(),
  started_at: z.string().nullable(),
  completed_at: z.string().nullable(),
  blocked_reason: z.string().nullable(),
  // `ps.rework_of_stage_id IS NOT NULL` — an `IS NOT NULL` test never yields
  // NULL in PostgreSQL, even when the LEFT JOIN produced no row, so this is a
  // real boolean. Measured `false` on a stage the project has not reached.
  is_rework: z.boolean(),
});
export type PipelineStage = z.infer<typeof pipelineStageSchema>;

const pipelineEnvelope = z.object({
  project_id: z.string(),
  stages: z.array(pipelineStageSchema),
});

export function fetchPipeline(
  credentials: ApiCredentials,
  projectId: string,
  signal?: AbortSignal,
): Promise<PipelineStage[]> {
  return apiRequest(
    { path: `/api/projects/${projectId}/pipeline`, credentials, signal },
    (payload) => pipelineEnvelope.parse(payload).stages,
  );
}

/**
 * One row of the verification matrix.
 *
 * 🔴 THIS SHAPE WAS MEASURED AGAINST THE RUNNING API, NOT INFERRED FROM THE SQL.
 *
 * The first draft of this schema was written from `verification_matrix`'s
 * SELECT list — `id`, `target_value`, `minimum_value`, `maximum_value`,
 * `canonical_unit`, `status` — and every field of it was wrong. The service
 * RESHAPES that query before returning it: the id is `requirement_id`, the four
 * numeric columns are collapsed into one human-readable `acceptance` string
 * ("≥ 6 MPa", "1.2–1.3 g/cm3"), `status` is `requirement_status`, and three
 * fields that appear in no SELECT at all — `verification_status`,
 * `latest_result`, `blocking_validation` — are computed on top.
 *
 * A schema built from the query would have thrown on every response, which is
 * the third time in two days that reading a SELECT and believing it produced a
 * wrong client type (`has_root_cause`, `must_differ_from_group`). *The SQL is
 * not the contract; the response is.* Probed with a real token before this line
 * was written.
 *
 * ⚠️ `acceptance` IS PRE-FORMATTED AND MUST NOT BE PARSED. §5 stores targets as
 * NUMERIC precisely so scale survives; the server has already turned them into
 * the sentence a person reads. A screen that split "1.2–1.3 g/cm3" back into
 * numbers would be reconstructing what the database holds from a string built
 * for display — and would get the en-dash wrong on the first try.
 */
export const requirementSchema = z.object({
  requirement_id: z.string(),
  requirement_code: z.string(),
  name: z.string(),
  category: z.string(),
  criticality: z.string(),
  /** The acceptance criterion as a sentence, built by the server. */
  acceptance: z.string().nullable(),
  verification_method: z.string(),
  test_method_code: z.string().nullable(),
  requirement_status: z.string(),
  revision: z.number(),
  verification_status: z.string(),
  latest_result: z.string().nullable(),
  blocking_validation: z.boolean(),
});
export type Requirement = z.infer<typeof requirementSchema>;

/**
 * The matrix, with the two things a bare array cannot carry.
 *
 * `summary` counts what is verified and what is blocking; `note` explains WHY
 * everything currently reads `not_verified` — *"because no test evidence exists
 * yet, not because testing has failed"*. That sentence is the difference
 * between a project that is early and a project that is failing, and dropping
 * it would let a director draw the second conclusion from the first situation.
 */
export const requirementMatrixSchema = z.object({
  project_id: z.string(),
  requirements: z.array(requirementSchema),
  summary: z.object({
    total: z.number(),
    verified: z.number(),
    not_verified: z.number(),
    blocking_validation: z.number(),
  }),
  tests_available: z.boolean(),
  note: z.string().nullable(),
});
export type RequirementMatrix = z.infer<typeof requirementMatrixSchema>;

export function fetchRequirementMatrix(
  credentials: ApiCredentials,
  projectId: string,
  signal?: AbortSignal,
): Promise<RequirementMatrix> {
  return apiRequest(
    { path: `/api/projects/${projectId}/requirements/matrix`, credentials, signal },
    (payload) => requirementMatrixSchema.parse(payload),
  );
}

export function fetchProject(
  credentials: ApiCredentials,
  projectId: string,
  signal?: AbortSignal,
): Promise<Project> {
  return apiRequest({ path: `/api/projects/${projectId}`, credentials, signal }, (payload) =>
    projectSchema.parse(payload),
  );
}

// ---------------------------------------------------------------------------
// The writes
// ---------------------------------------------------------------------------

/** Advance the project to another stage. `project.advance_stage`. */
export function advanceStage(
  credentials: ApiCredentials,
  projectId: string,
  request: { readonly to_stage_code: string; readonly reason: string; readonly force?: boolean },
): Promise<unknown> {
  return apiRequest(
    {
      path: `/api/projects/${projectId}/pipeline/advance`,
      method: "POST",
      body: request,
      credentials,
    },
    (payload) => payload,
  );
}

export interface MilestoneRequest {
  readonly name: string;
  readonly planned_date: string;
  readonly description?: string;
}

/** Add a milestone. `milestone.manage`. */
export function createMilestone(
  credentials: ApiCredentials,
  projectId: string,
  request: MilestoneRequest,
): Promise<unknown> {
  return apiRequest(
    {
      path: `/api/projects/${projectId}/milestones`,
      method: "POST",
      body: request,
      credentials,
    },
    (payload) => payload,
  );
}

/** Move a milestone's status. `milestone.manage`, and a `reason` is mandatory. */
export function setMilestoneStatus(
  credentials: ApiCredentials,
  projectId: string,
  milestoneId: string,
  request: {
    readonly status: string;
    readonly actual_date?: string;
    readonly reason: string;
  },
): Promise<unknown> {
  return apiRequest(
    {
      path: `/api/projects/${projectId}/milestones/${milestoneId}/status`,
      method: "PATCH",
      body: request,
      credentials,
    },
    (payload) => payload,
  );
}

export interface RiskRequest {
  readonly risk_code: string;
  readonly title: string;
  readonly probability: "low" | "medium" | "high";
  readonly impact: "low" | "medium" | "high";
  readonly category: string;
  readonly description?: string;
  readonly mitigation?: string;
}

/** Raise a risk. `risk.create`. */
export function createRisk(
  credentials: ApiCredentials,
  projectId: string,
  request: RiskRequest,
): Promise<unknown> {
  return apiRequest(
    { path: `/api/projects/${projectId}/risks`, method: "POST", body: request, credentials },
    (payload) => payload,
  );
}

/**
 * Update a risk. `risk.manage`, and a `reason` is mandatory.
 *
 * ⚠️ EVERY OTHER FIELD IS OPTIONAL AND OMITTING ONE MEANS "LEAVE UNCHANGED".
 * `RiskUpdate`'s own docstring says why: *"a PATCH that silently blanked the
 * mitigation because the client did not resend it is how a risk stops being
 * tracked without anyone deciding that."* So this signature must never grow a
 * convenience that sends the whole object.
 */
export function updateRisk(
  credentials: ApiCredentials,
  projectId: string,
  riskId: string,
  request: {
    readonly reason: string;
    readonly status?: string;
    readonly mitigation?: string;
    readonly probability?: "low" | "medium" | "high";
    readonly impact?: "low" | "medium" | "high";
  },
): Promise<unknown> {
  return apiRequest(
    {
      path: `/api/projects/${projectId}/risks/${riskId}`,
      method: "PATCH",
      body: request,
      credentials,
    },
    (payload) => payload,
  );
}

/** Put somebody on the project. `project.assign_member`. */
export function addProjectMember(
  credentials: ApiCredentials,
  projectId: string,
  request: { readonly user_id: string; readonly project_role: string },
): Promise<unknown> {
  return apiRequest(
    { path: `/api/projects/${projectId}/members`, method: "POST", body: request, credentials },
    (payload) => payload,
  );
}

/**
 * Take somebody off the project. `project.assign_member`, with a reason.
 *
 * ⚠️ IT IS A POST TO `/remove`, NOT A DELETE, AND THE MEMBER IS DEACTIVATED
 * RATHER THAN DELETED. `list_members` returns inactive members deliberately:
 * *"who has ever had access to this project"* is the question asked after an
 * incident, and a list that silently drops them cannot answer it.
 */
export function removeProjectMember(
  credentials: ApiCredentials,
  projectId: string,
  userId: string,
  reason: string,
): Promise<unknown> {
  return apiRequest(
    {
      path: `/api/projects/${projectId}/members/${userId}/remove`,
      method: "POST",
      body: { reason },
      credentials,
    },
    (payload) => payload,
  );
}

/**
 * A requirement, as `RequirementCreate` expects it.
 *
 * 🔴 THE NUMERIC FIELDS ARE STRINGS ON THE WIRE AND MUST STAY STRINGS. §5:
 * NUMERIC, never float. Pydantic parses `Decimal` from a JSON string exactly,
 * and from a JSON *number* through a float — so sending `1.15` as a number is
 * how a specification acquires a rounding error nobody typed. The form keeps
 * what the user entered, character for character.
 */
export interface RequirementRequest {
  readonly requirement_code: string;
  readonly name: string;
  readonly category?: string;
  readonly description?: string;
  readonly target_value?: string;
  readonly minimum_value?: string;
  readonly maximum_value?: string;
  readonly canonical_unit?: string;
  readonly criticality: "critical" | "major" | "minor" | "informational";
  readonly verification_method?: string;
}

/** Add a requirement. `requirement.create`. */
export function createRequirement(
  credentials: ApiCredentials,
  projectId: string,
  request: RequirementRequest,
): Promise<unknown> {
  return apiRequest(
    {
      path: `/api/projects/${projectId}/requirements`,
      method: "POST",
      body: request,
      credentials,
    },
    (payload) => payload,
  );
}

/**
 * Approve a requirement. `requirement.approve` — the Lead's permission.
 *
 * ⚠️ NO BODY, AND 204 BACK. There is nowhere to put an opinion: approving a
 * requirement freezes it, and `RequirementImmutableError` turns a second
 * attempt into a 409 rather than a silent no-op.
 */
export function approveRequirement(
  credentials: ApiCredentials,
  projectId: string,
  requirementId: string,
): Promise<unknown> {
  return apiRequest(
    {
      path: `/api/projects/${projectId}/requirements/${requirementId}/approve`,
      method: "POST",
      body: {},
      credentials,
    },
    (payload) => payload,
  );
}

/**
 * Revise an approved requirement. `requirement.create`, plus a mandatory reason.
 *
 * 🔴 A REVISION IS A NEW REVISION, NOT AN EDIT. `RequirementRevise` extends
 * `RequirementCreate`, so the whole requirement is restated and the server
 * bumps `revision` — an approved requirement is never changed in place, which
 * is §8's rule for formulas applied to the thing formulas are tested against.
 */
export function reviseRequirement(
  credentials: ApiCredentials,
  projectId: string,
  requirementId: string,
  request: RequirementRequest & { readonly reason: string },
): Promise<unknown> {
  return apiRequest(
    {
      path: `/api/projects/${projectId}/requirements/${requirementId}/revise`,
      method: "POST",
      body: request,
      credentials,
    },
    (payload) => payload,
  );
}

export interface ProjectCreateRequest {
  readonly project_code: string;
  readonly name: string;
  readonly product_family?: string;
  readonly description?: string;
  readonly technical_objective?: string;
  readonly commercial_objective?: string;
  readonly priority?: string;
  readonly confidentiality?: string;
}

/**
 * 🔴 `confidentiality` IS OFFERED, AND IT IS NOT COSMETIC.
 *
 * `restricted` is what makes RLS scope the project to its MEMBERS rather than
 * to the whole organization — the second of the three layers this platform's
 * tenancy rests on. Defaulting it silently would mean every project created
 * through this form was readable company-wide, which is the opposite of what
 * somebody creating a confidential project intends. So it is a visible choice
 * with `normal` preselected, matching the server.
 */
export const PROJECT_CONFIDENTIALITY = ["normal", "restricted"] as const;
export const PROJECT_PRIORITIES = ["low", "medium", "high", "critical"] as const;

export function createProject(
  credentials: ApiCredentials,
  request: ProjectCreateRequest,
): Promise<{ id: string; project_code: string }> {
  return apiRequest(
    { path: "/api/projects", method: "POST", credentials, body: request },
    (payload) =>
      z.object({ id: z.string(), project_code: z.string() }).passthrough().parse(payload),
  );
}
