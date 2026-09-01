/**
 * Administration, over HTTP — the eleven writes that had no browser caller.
 *
 * 🔴 THE LONGEST-STANDING GAP IN THE PRODUCT, AND THE PLAN NAMED IT FIRST.
 *
 * `IMPLEMENTATION_PLAN.md` §H has a section headed *"Administration is a thread
 * through the build, not a slice"*, written because both earlier plan versions
 * said role→permission mapping was "editable in Administration", that test
 * methods were "editable in Administration", that pipeline stages were
 * "configuration rows" — and **no slice ever built the screen**. Its own words:
 *
 *   *ask of every role, which production path WRITES it? Seeding a Keycloak
 *   realm is not a write path. An administrator who can be read but never
 *   granted does not exist.*
 *
 * The API answered that in Slice 1. The browser did not: measured 2026-08-27,
 * eleven `admin.*` write endpoints existed, were permission-gated and tested,
 * and **not one had a client function**. So the plan's own most-repeated lesson
 * had been committed against the section that exists to record it.
 *
 * 🔴 SHAPES MEASURED AGAINST THE RUNNING API, NOT READ OFF THE SQL. Every
 * schema below was probed with a real `admin.demo` token before it was written.
 * That has caught a wrong client type three times in two days — `has_root_cause`
 * returning a count, `must_differ_from_group` returning a group number, and the
 * requirement matrix being reshaped past recognition.
 *
 * ⚠️ THIS APPLICATION CANNOT CREATE CREDENTIALS AND MUST NOT LOOK AS IF IT CAN.
 * `MemberInvite`'s own docstring: *"Keycloak owns identity. This binds an
 * existing subject to an organization."* So the form asks for a `keycloak_sub`
 * that already exists — it is a MEMBERSHIP form, not a sign-up form, and the
 * screen says so in as many words.
 */

import { z } from "zod";

import { apiRequest, type ApiCredentials } from "./client";

/* -------------------------------------------------------------------------- */
/* Members, roles, permissions                                                 */
/* -------------------------------------------------------------------------- */

export const adminMemberSchema = z.object({
  member_id: z.string(),
  user_id: z.string(),
  email: z.string(),
  display_name: z.string(),
  status: z.string(),
  roles: z.array(z.string()),
});
export type AdminMember = z.infer<typeof adminMemberSchema>;

export function fetchAdminMembers(
  credentials: ApiCredentials,
  signal?: AbortSignal,
): Promise<AdminMember[]> {
  return apiRequest({ path: "/api/admin/members", credentials, signal }, (payload) =>
    z.array(adminMemberSchema).parse(payload),
  );
}

export const roleSchema = z.object({
  code: z.string(),
  name: z.string(),
  /**
   * A seeded role is one of the ten the realm ships with.
   *
   * Shown because it is the difference between a role somebody here defined and
   * one the product depends on — and §6 fixes the ten by name, so a screen that
   * presented them all as equally editable would be inviting a change that
   * breaks the permission model.
   */
  is_seeded: z.boolean(),
  description: z.string().nullable(),
  permissions: z.array(z.string()),
});
export type Role = z.infer<typeof roleSchema>;

export function fetchRoles(credentials: ApiCredentials, signal?: AbortSignal): Promise<Role[]> {
  return apiRequest({ path: "/api/admin/roles", credentials, signal }, (payload) =>
    z.array(roleSchema).parse(payload),
  );
}

export const permissionSchema = z.object({
  code: z.string(),
  domain: z.string(),
  // 🔴 NOT NULLABLE. Raised by Codex: `PermissionRead.description` is a
  // mandatory `str`, while `RoleRead.description` a few lines above it in the
  // same file is `str | None`. Copying the role's nullability onto the
  // permission made this client MORE permissive than the response model — so a
  // server-side regression that started emitting null would have parsed
  // cleanly here and rendered as an empty cell. A schema looser than the
  // contract hides exactly the change it exists to catch.
  description: z.string(),
});
export type Permission = z.infer<typeof permissionSchema>;

export function fetchPermissions(
  credentials: ApiCredentials,
  signal?: AbortSignal,
): Promise<Permission[]> {
  return apiRequest({ path: "/api/admin/permissions", credentials, signal }, (payload) =>
    z.array(permissionSchema).parse(payload),
  );
}

export interface MemberInviteRequest {
  readonly keycloak_sub: string;
  readonly email: string;
  readonly display_name: string;
  readonly roles: readonly string[];
}

/** Bind an existing Keycloak subject to this organization. `admin.users`. */
export function inviteMember(
  credentials: ApiCredentials,
  request: MemberInviteRequest,
): Promise<unknown> {
  return apiRequest(
    { path: "/api/admin/members", method: "POST", body: request, credentials },
    (payload) => payload,
  );
}

/** Grant a role. `admin.roles`, with a reason. */
export function grantRole(
  credentials: ApiCredentials,
  memberId: string,
  roleCode: string,
  reason: string,
): Promise<unknown> {
  return apiRequest(
    {
      path: `/api/admin/members/${memberId}/roles`,
      method: "POST",
      body: { role_code: roleCode, reason },
      credentials,
    },
    (payload) => payload,
  );
}

/**
 * Revoke a role. `admin.roles`, with a reason.
 *
 * 🔴 THE LAST HOLDER OF `admin.roles` CANNOT BE REVOKED, AND THE SERVER SAYS SO.
 * An organization that can no longer grant any role needs direct database
 * access to recover — the same dead end as a role with no write path. The
 * refusal is surfaced verbatim rather than translated, because it names the
 * thing that would have broken.
 *
 * ⚠️ A DELETE WITH A BODY. Unusual, and deliberate: the reason is part of the
 * decision record, and a query string is not where an audited justification
 * belongs.
 */
export function revokeRole(
  credentials: ApiCredentials,
  memberId: string,
  roleCode: string,
  reason: string,
): Promise<unknown> {
  return apiRequest(
    {
      path: `/api/admin/members/${memberId}/roles/${roleCode}`,
      method: "DELETE",
      body: { role_code: roleCode, reason },
      credentials,
    },
    (payload) => payload,
  );
}

/**
 * Activate or deactivate a membership. `admin.users`, with a reason.
 *
 * ⚠️ DEACTIVATED, NEVER DELETED. Removing the row would orphan every audit
 * event and approval that names it — R&D history is retired by status, not
 * destroyed (§5).
 */
export function setMemberStatus(
  credentials: ApiCredentials,
  memberId: string,
  status: "active" | "inactive",
  reason: string,
): Promise<unknown> {
  return apiRequest(
    {
      path: `/api/admin/members/${memberId}/status`,
      method: "PATCH",
      body: { status, reason },
      credentials,
    },
    (payload) => payload,
  );
}

/* -------------------------------------------------------------------------- */
/* Stage gates                                                                 */
/* -------------------------------------------------------------------------- */

export const stageDefinitionSchema = z.object({
  id: z.string(),
  stage_code: z.string(),
  name: z.string(),
  sequence: z.number(),
  entry_criteria: z.string().nullable(),
  required_deliverables: z.string().nullable(),
  exit_criteria: z.string().nullable(),
  responsible_role: z.string().nullable(),
  requires_approval: z.boolean(),
  approval_role: z.string().nullable(),
  is_active: z.boolean(),
  /**
   * How many projects have ever been in this stage.
   *
   * 🔴 THIS IS WHAT MAKES RETIRING A STAGE A DECISION RATHER THAN A CLICK. A
   * stage no project has visited can be turned off freely; one with history
   * behind it is a configuration change that alters what those projects' stage
   * records refer to. Shown on the row so the number is in front of whoever is
   * deciding.
   */
  projects_visited: z.number(),
});
export type StageDefinition = z.infer<typeof stageDefinitionSchema>;

export function fetchStageDefinitions(
  credentials: ApiCredentials,
  signal?: AbortSignal,
): Promise<StageDefinition[]> {
  return apiRequest({ path: "/api/admin/stage-gates", credentials, signal }, (payload) =>
    z.array(stageDefinitionSchema).parse(payload),
  );
}

export interface StageWriteRequest {
  readonly stage_code: string;
  readonly name: string;
  readonly sequence: number;
  readonly entry_criteria?: string;
  readonly required_deliverables?: string;
  readonly exit_criteria?: string;
  readonly responsible_role?: string;
  readonly requires_approval: boolean;
  readonly approval_role?: string;
}

/** Define a stage. `admin.stage_gates`. */
export function createStage(
  credentials: ApiCredentials,
  request: StageWriteRequest,
): Promise<unknown> {
  return apiRequest(
    { path: "/api/admin/stage-gates", method: "POST", body: request, credentials },
    (payload) => payload,
  );
}

/** Replace a stage definition. `admin.stage_gates`. */
export function updateStage(
  credentials: ApiCredentials,
  stageId: string,
  request: StageWriteRequest,
): Promise<unknown> {
  return apiRequest(
    { path: `/api/admin/stage-gates/${stageId}`, method: "PUT", body: request, credentials },
    (payload) => payload,
  );
}

/** Retire or restore a stage. `admin.stage_gates`, with a reason. */
export function setStageActive(
  credentials: ApiCredentials,
  stageId: string,
  isActive: boolean,
  reason: string,
): Promise<unknown> {
  return apiRequest(
    {
      path: `/api/admin/stage-gates/${stageId}/activation`,
      method: "PATCH",
      body: { is_active: isActive, reason },
      credentials,
    },
    (payload) => payload,
  );
}

/**
 * Reorder the pipeline.
 *
 * ⚠️ IT TAKES THE WHOLE ORDER, NOT A MOVE. `ordered_stage_ids` is every stage
 * in its new sequence — so the server sets the order it was given rather than
 * inferring one from a delta, and two administrators reordering at once cannot
 * interleave into a sequence neither of them chose.
 */
export function reorderStages(
  credentials: ApiCredentials,
  orderedStageIds: readonly string[],
): Promise<unknown> {
  return apiRequest(
    {
      path: "/api/admin/stage-gates/reorder",
      method: "POST",
      body: { ordered_stage_ids: orderedStageIds },
      credentials,
    },
    (payload) => payload,
  );
}

/* -------------------------------------------------------------------------- */
/* Reference data                                                              */
/* -------------------------------------------------------------------------- */

export const unitSchema = z.object({
  id: z.string(),
  code: z.string(),
  name: z.string(),
  /**
   * What kind of quantity this unit measures — density, stress, time.
   *
   * Required on the server, and the comment there says why: *"a unit with no
   * quantity kind cannot be offered as a choice for a requirement — the form
   * has to know that MPa is a stress and minutes are a time, or it lists every
   * unit in the system for every measurement."*
   */
  quantity_kind: z.string(),
  is_active: z.boolean(),
  display_order: z.number(),
});
export type Unit = z.infer<typeof unitSchema>;

export const productFamilySchema = z.object({
  id: z.string(),
  code: z.string(),
  name: z.string(),
  description: z.string().nullable(),
  is_active: z.boolean(),
  display_order: z.number(),
});
export type ProductFamily = z.infer<typeof productFamilySchema>;

/**
 * 🔴 `include_inactive=true`, AND WITHOUT IT "RESTORE" WAS UNREACHABLE.
 *
 * Raised by Codex. Both endpoints default `include_inactive` to FALSE, so
 * retiring a row and then refetching made it vanish — taking its Restore
 * control with it. The screen's own comment said *"a retired row still appears.
 * It has to"*, which was a description of intent rather than of the request
 * being sent: a comment asserting a behaviour the code did not have.
 *
 * This is an ADMINISTRATION surface, so it wants everything: an administrator
 * needs to see the retired row before wondering why its code cannot be reused,
 * and needs it on screen to bring it back. Read paths for ordinary callers —
 * the unit picker on a requirement form — should keep the default and get only
 * what is offerable.
 */
export function fetchUnits(credentials: ApiCredentials, signal?: AbortSignal): Promise<Unit[]> {
  return apiRequest(
    { path: "/api/admin/units?include_inactive=true", credentials, signal },
    (payload) => z.array(unitSchema).parse(payload),
  );
}

export function fetchProductFamilies(
  credentials: ApiCredentials,
  signal?: AbortSignal,
): Promise<ProductFamily[]> {
  return apiRequest(
    { path: "/api/admin/product-families?include_inactive=true", credentials, signal },
    (payload) => z.array(productFamilySchema).parse(payload),
  );
}

/** Add a unit. `admin.reference_data`. */
export function createUnit(
  credentials: ApiCredentials,
  request: {
    readonly code: string;
    readonly name: string;
    readonly quantity_kind: string;
    readonly display_order?: number;
  },
): Promise<unknown> {
  return apiRequest(
    { path: "/api/admin/units", method: "POST", body: request, credentials },
    (payload) => payload,
  );
}

/** Add a product family. `admin.reference_data`. */
export function createProductFamily(
  credentials: ApiCredentials,
  request: {
    readonly code: string;
    readonly name: string;
    readonly description?: string;
    readonly display_order?: number;
  },
): Promise<unknown> {
  return apiRequest(
    { path: "/api/admin/product-families", method: "POST", body: request, credentials },
    (payload) => payload,
  );
}

/**
 * Retire or restore one reference-data row.
 *
 * ⚠️ `collection` IS A PATH SEGMENT AND THE SERVER TREATS IT AS A KEY, NOT A
 * TABLE NAME. `_RETIRE_SQL` is a dictionary of two complete statements and an
 * unknown key is a 404 — there is no template and no interpolation, which is
 * why a path segment can safely select one. The two literal values are spelled
 * out in the union below rather than passed through as a string, so a third
 * collection has to be added deliberately in both places.
 */
export function setReferenceItemActive(
  credentials: ApiCredentials,
  collection: "units" | "product-families",
  itemId: string,
  isActive: boolean,
): Promise<unknown> {
  return apiRequest(
    {
      path: `/api/admin/${collection}/${itemId}`,
      method: "PATCH",
      body: { is_active: isActive },
      credentials,
    },
    (payload) => payload,
  );
}

/* -------------------------------------------------------------------------- */
/* Access requests — the landing page's Sign Up, reviewed                      */
/* -------------------------------------------------------------------------- */
//
// 🔴 THE TABLE HAD A WRITER AND NO READER (L1).
//
// `POST /api/public/access-requests` has recorded interest since migration
// 059, and until 2026-09-01 nothing anywhere read it back — so an anonymous
// visitor's request went into a queue no screen could open. That is the same
// defect as a route with no caller, seen from the other side.

export const accessRequestSchema = z.object({
  id: z.string(),
  full_name: z.string(),
  work_email: z.string(),
  company: z.string(),
  reason: z.string().nullable(),
  status: z.string(),
  created_at: z.string(),
  decided_at: z.string().nullable(),
  decided_by: z.string().nullable(),
});
export type AccessRequest = z.infer<typeof accessRequestSchema>;

/** Read the queue. `admin.users`. Defaults to the undecided requests. */
export function fetchAccessRequests(
  credentials: ApiCredentials,
  signal?: AbortSignal,
  status: "new" | "approved" | "rejected" | "all" = "new",
): Promise<AccessRequest[]> {
  return apiRequest(
    { path: `/api/admin/access-requests?status=${status}`, credentials, signal },
    (payload) => z.array(accessRequestSchema).parse(payload),
  );
}

export interface AccessRequestDecisionRequest {
  readonly decision: "approved" | "rejected";
  readonly reason: string;
  /** Required on an approval — the identity already in Keycloak. */
  readonly keycloak_sub?: string;
  readonly display_name?: string;
  readonly roles?: readonly string[];
}

/**
 * Decide one request. `admin.users`.
 *
 * ⚠️ APPROVING IS A BIND, NOT A REGISTRATION. This application cannot create
 * credentials — Keycloak owns identity and self-registration stays off. An
 * approval carries the `keycloak_sub` of an identity that already exists and
 * goes through the same bind as `POST /api/admin/members`.
 *
 * ⚠️ THE ADDRESS IS NOT SENT. The server binds the address that was
 * SUBMITTED, read from the request row, so an approval cannot be quietly
 * redirected to a different person than the one that was reviewed.
 */
export function decideAccessRequest(
  credentials: ApiCredentials,
  requestId: string,
  request: AccessRequestDecisionRequest,
): Promise<unknown> {
  return apiRequest(
    {
      path: `/api/admin/access-requests/${requestId}/decision`,
      method: "POST",
      body: request,
      credentials,
    },
    (payload) => payload,
  );
}
