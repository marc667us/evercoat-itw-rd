"use client";

/**
 * Users and memberships — the write path §H said was missing for four slices.
 *
 * 🔴 THE SCREEN THAT EXISTED TO PROVE A LESSON, AND DEMONSTRATED IT INSTEAD.
 *
 * `IMPLEMENTATION_PLAN.md` §H carries a section headed *"Administration is a
 * thread through the build, not a slice"*, written because two earlier plan
 * versions promised things were "editable in Administration" while no slice
 * ever built the screen. Its conclusion: *"ask of every role, which production
 * path WRITES it? An administrator who can be read but never granted does not
 * exist."*
 *
 * Slice 1 built the API and this page, and the page said, honestly, *"Not yet
 * connected. The API is live at /api/admin/members; this table is wired in
 * Slice 2, once authentication supplies a verified principal."* Authentication
 * arrived on 2026-08-19. The table did not. Measured 2026-08-27: four member
 * write endpoints, permission-gated and tested, with no client function.
 *
 * 🔴 TWO PERMISSIONS, NOT ONE, AND THEY ARE DELIBERATELY DIFFERENT.
 * `admin.users` binds and unbinds a person; `admin.roles` decides what they may
 * do. Both are held only by the administrator on the seeded realm, but the
 * endpoints separate them and so does this screen — collapsing them would make
 * "can add a colleague" and "can grant them every permission in the product"
 * the same decision.
 *
 * ⚠️ THIS APPLICATION CANNOT CREATE CREDENTIALS. `MemberInvite` binds an
 * EXISTING Keycloak subject: Keycloak owns identity. The form says so, because
 * a field labelled "email" on a page called Administration looks exactly like a
 * sign-up form, and it is not one.
 */

import { useState } from "react";

import { serverMessage } from "@/lib/api/client";
import { useAdminActions, useAdminMembers, useRoles } from "@/lib/api/hooks";
import type { AdminMember, Role } from "@/lib/api/admin";
import { permits, usePermissions } from "@/lib/permissions";

const INPUT =
  "mt-1 w-full rounded border border-slate-300 px-2 py-1.5 text-sm text-slate-900 " +
  "focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500";
const LABEL = "block text-xs font-medium text-slate-700";
const BUTTON =
  "rounded bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-700 " +
  "disabled:cursor-not-allowed disabled:bg-slate-300";
const BUTTON_QUIET =
  "rounded border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-800 " +
  "hover:bg-slate-50 disabled:cursor-not-allowed disabled:text-slate-400";
const TAG =
  "rounded border border-slate-300 px-1.5 py-0.5 text-[10px] font-medium uppercase " +
  "tracking-wide text-slate-600";

function words(value: string): string {
  return value.replace(/_/g, " ");
}

/**
 * One membership, holding its own drafts.
 *
 * State lives on the ROW, for the reason the project workspace learned it the
 * hard way: a shared reason field means a justification typed against one
 * colleague can be submitted against another, and this is the record that
 * answers *"who was given what, and why"*.
 */
function MemberRow({
  member,
  roles,
  mayManageUsers,
  mayManageRoles,
  pending,
  onGrant,
  onRevoke,
  onSetStatus,
}: {
  member: AdminMember;
  roles: readonly Role[];
  mayManageUsers: boolean;
  mayManageRoles: boolean;
  pending: boolean;
  onGrant: (memberId: string, roleCode: string, reason: string, after: () => void) => void;
  onRevoke: (memberId: string, roleCode: string, reason: string, after: () => void) => void;
  onSetStatus: (
    memberId: string,
    status: "active" | "inactive",
    reason: string,
    after: () => void,
  ) => void;
}) {
  const [granting, setGranting] = useState(false);
  const [roleCode, setRoleCode] = useState("");
  const [grantReason, setGrantReason] = useState("");
  const [revoking, setRevoking] = useState<string | null>(null);
  const [revokeReason, setRevokeReason] = useState("");
  const [changingStatus, setChangingStatus] = useState(false);
  const [statusReason, setStatusReason] = useState("");

  const held = new Set(member.roles);
  const grantable = roles.filter((r) => !held.has(r.code));
  const nextStatus = member.status === "active" ? "inactive" : "active";

  return (
    <li className="rounded border border-slate-200 bg-white p-3">
      <div className="flex flex-wrap items-baseline gap-2">
        <span className="text-sm font-medium text-slate-900">{member.display_name}</span>
        <span className="text-xs text-slate-600">{member.email}</span>
        <span className={TAG}>{words(member.status)}</span>
        {member.roles.length === 0 ? (
          // 🔴 A MEMBER WITH NO ROLES IS A REAL AND MEANINGFUL STATE, not an
          // empty cell. They hold no permissions at all, which is exactly what
          // `effectiveNavPermissions` renders as an empty sidebar — and an
          // administrator looking at this list needs to see it.
          <span className={TAG}>no roles — holds no permissions</span>
        ) : (
          member.roles.map((code) => (
            <span key={code} className={TAG}>
              {words(code)}
            </span>
          ))
        )}
      </div>

      <div className="mt-2 flex flex-wrap gap-2">
        {mayManageRoles && !granting && grantable.length > 0 && (
          <button
            type="button"
            className="text-xs text-slate-700 underline underline-offset-2"
            onClick={() => setGranting(true)}
          >
            Grant a role
          </button>
        )}
        {mayManageRoles &&
          member.roles.map((code) => (
            <button
              key={`revoke-${code}`}
              type="button"
              className="text-xs text-slate-700 underline underline-offset-2"
              onClick={() => setRevoking(code)}
            >
              Revoke {words(code)}
            </button>
          ))}
        {mayManageUsers && !changingStatus && (
          <button
            type="button"
            className="text-xs text-slate-700 underline underline-offset-2"
            onClick={() => setChangingStatus(true)}
          >
            {member.status === "active" ? "Deactivate" : "Reactivate"}
          </button>
        )}
      </div>

      {mayManageRoles && granting && (
        <div className="mt-2 flex flex-wrap items-end gap-2">
          <div className="w-56">
            <label className={LABEL} htmlFor={`grant-${member.member_id}`}>
              Role
            </label>
            <select
              id={`grant-${member.member_id}`}
              className={INPUT}
              value={roleCode}
              onChange={(e) => setRoleCode(e.target.value)}
            >
              <option value="">Choose a role</option>
              {/* From `GET /api/admin/roles`, never a hardcoded list. §6 fixes
                  ten role codes by name and a second copy here would drift the
                  first time one was added. */}
              {grantable.map((r) => (
                <option key={r.code} value={r.code}>
                  {r.name}
                </option>
              ))}
            </select>
          </div>
          <div className="min-w-[14rem] flex-1">
            <label className={LABEL} htmlFor={`grant-reason-${member.member_id}`}>
              Why
            </label>
            <input
              id={`grant-reason-${member.member_id}`}
              className={INPUT}
              maxLength={500}
              value={grantReason}
              onChange={(e) => setGrantReason(e.target.value)}
            />
          </div>
          <button
            type="button"
            className={BUTTON_QUIET}
            disabled={pending || roleCode === "" || grantReason.trim().length < 3}
            onClick={() =>
              onGrant(member.member_id, roleCode, grantReason.trim(), () => {
                setRoleCode("");
                setGrantReason("");
                setGranting(false);
              })
            }
          >
            Grant
          </button>
          <button
            type="button"
            className={BUTTON_QUIET}
            onClick={() => {
              setRoleCode("");
              setGrantReason("");
              setGranting(false);
            }}
          >
            Cancel
          </button>
        </div>
      )}

      {mayManageRoles && revoking !== null && (
        <div className="mt-2 flex flex-wrap items-end gap-2">
          <div className="min-w-[16rem] flex-1">
            <label className={LABEL} htmlFor={`revoke-reason-${member.member_id}`}>
              Why {words(revoking)} is being revoked
            </label>
            <input
              id={`revoke-reason-${member.member_id}`}
              className={INPUT}
              maxLength={500}
              value={revokeReason}
              onChange={(e) => setRevokeReason(e.target.value)}
            />
          </div>
          <button
            type="button"
            className={BUTTON_QUIET}
            disabled={pending || revokeReason.trim().length < 3}
            onClick={() =>
              onRevoke(member.member_id, revoking, revokeReason.trim(), () => {
                setRevokeReason("");
                setRevoking(null);
              })
            }
          >
            Revoke
          </button>
          <button
            type="button"
            className={BUTTON_QUIET}
            onClick={() => {
              setRevokeReason("");
              setRevoking(null);
            }}
          >
            Cancel
          </button>
          {/* 🔴 THE ONE REFUSAL WORTH WARNING ABOUT IN ADVANCE. Revoking the
              last role that holds `admin.roles` is refused, because an
              organization that can no longer grant any role needs direct
              database access to recover. The server decides; this says why a
              refusal here is not a bug. */}
          <p className="w-full text-xs text-slate-600">
            The last role holding <code>admin.roles</code> cannot be revoked — an
            organization that can grant nothing needs database access to recover.
          </p>
        </div>
      )}

      {mayManageUsers && changingStatus && (
        <div className="mt-2 flex flex-wrap items-end gap-2">
          <div className="min-w-[16rem] flex-1">
            <label className={LABEL} htmlFor={`status-reason-${member.member_id}`}>
              Why this membership is being set to {nextStatus}
            </label>
            <input
              id={`status-reason-${member.member_id}`}
              className={INPUT}
              maxLength={500}
              value={statusReason}
              onChange={(e) => setStatusReason(e.target.value)}
            />
          </div>
          <button
            type="button"
            className={BUTTON_QUIET}
            disabled={pending || statusReason.trim().length < 3}
            onClick={() =>
              onSetStatus(
                member.member_id,
                nextStatus as "active" | "inactive",
                statusReason.trim(),
                () => {
                  setStatusReason("");
                  setChangingStatus(false);
                },
              )
            }
          >
            Set {nextStatus}
          </button>
          <button
            type="button"
            className={BUTTON_QUIET}
            onClick={() => {
              setStatusReason("");
              setChangingStatus(false);
            }}
          >
            Cancel
          </button>
          <p className="w-full text-xs text-slate-600">
            Members are deactivated, never deleted — removing the row would
            orphan every audit event and approval that names it.
          </p>
        </div>
      )}
    </li>
  );
}

export function MembersAdministration() {
  const permissions = usePermissions();
  const mayManageUsers = permits(permissions, "admin.users");
  const mayManageRoles = permits(permissions, "admin.roles");

  const members = useAdminMembers();
  const roles = useRoles();
  const actions = useAdminActions();

  const [sub, setSub] = useState("");
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");

  // 🔴 THE ROLE CATALOGUE IS ITS OWN PERMISSION. `GET /api/admin/roles` needs
  // `admin.roles`, so a caller holding only `admin.users` sees the member list
  // and no roles — and the grant control is hidden for them anyway. Rendering
  // `roles.error` as a failure of the whole page would be wrong: it is a
  // legitimate refusal for that caller.
  const roleList: Role[] = roles.data ?? [];

  if (!mayManageUsers) {
    return (
      <p className="text-sm text-slate-600">
        Managing memberships needs <code className="text-xs">admin.users</code>,
        which this account does not hold.
      </p>
    );
  }

  return (
    <div className="space-y-4">
      <section>
        <h2 className="text-sm font-semibold text-slate-900">Users and memberships</h2>
        <p className="mt-1 max-w-3xl text-sm leading-relaxed text-slate-600">
          Membership binds an existing Keycloak subject to this organization and
          carries its roles. <strong>The application deliberately cannot create
          credentials</strong> — Keycloak owns identity.
        </p>

        {members.error !== null ? (
          <p role="alert" className="mt-2 text-sm text-red-700">
            The member list could not be loaded: {serverMessage(members.error)}
          </p>
        ) : members.data === undefined ? (
          <p className="mt-2 text-sm text-slate-600">Loading memberships…</p>
        ) : members.data.length === 0 ? (
          <p className="mt-2 text-sm text-slate-600">
            No memberships in this organization.
          </p>
        ) : (
          <ul className="mt-3 space-y-2">
            {members.data.map((m) => (
              <MemberRow
                key={m.member_id}
                member={m}
                roles={roleList}
                mayManageUsers={mayManageUsers}
                mayManageRoles={mayManageRoles}
                pending={actions.isPending}
                onGrant={actions.grant}
                onRevoke={actions.revoke}
                onSetStatus={actions.setStatus}
              />
            ))}
          </ul>
        )}
      </section>

      <section>
        <h3 className="text-sm font-semibold text-slate-900">Bind an existing subject</h3>
        {/* ⚠️ NOT A SIGN-UP FORM, AND IT HAS TO SAY SO. A page called
            Administration with an email field looks exactly like one. */}
        <p className="mt-1 max-w-3xl text-xs text-slate-600">
          This does <strong>not</strong> create an account. The person must already
          exist in Keycloak; their subject identifier is what binds them here.
        </p>
        <div className="mt-2 flex max-w-3xl flex-wrap items-end gap-2">
          <div className="min-w-[16rem] flex-1">
            <label className={LABEL} htmlFor="invite-sub">
              Keycloak subject
            </label>
            <input
              id="invite-sub"
              className={INPUT}
              maxLength={255}
              value={sub}
              onChange={(e) => setSub(e.target.value)}
            />
          </div>
          <div className="min-w-[14rem] flex-1">
            <label className={LABEL} htmlFor="invite-email">
              Email
            </label>
            <input
              id="invite-email"
              type="email"
              className={INPUT}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          <div className="min-w-[12rem] flex-1">
            <label className={LABEL} htmlFor="invite-name">
              Display name
            </label>
            <input
              id="invite-name"
              className={INPUT}
              maxLength={200}
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
            />
          </div>
          <button
            type="button"
            className={BUTTON}
            disabled={
              actions.isPending ||
              sub.trim() === "" ||
              // The server's field is `EmailStr`; requiring an "@" here is the
              // cheapest thing that stops a round trip, not a validation model.
              !email.includes("@") ||
              displayName.trim() === ""
            }
            onClick={() =>
              actions.invite(
                {
                  keycloak_sub: sub.trim(),
                  email: email.trim(),
                  display_name: displayName.trim(),
                  // No roles at binding time. Granting is a separate permission
                  // and a separate decision, each with its own recorded reason.
                  roles: [],
                },
                () => {
                  setSub("");
                  setEmail("");
                  setDisplayName("");
                },
              )
            }
          >
            Bind membership
          </button>
        </div>
      </section>

      {actions.error !== null && (
        <p
          role="alert"
          className="rounded border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-900"
        >
          {serverMessage(actions.error)}
        </p>
      )}
      {actions.error === null && actions.lastAction !== null && (
        <p role="status" className="text-sm text-slate-700">
          Recorded: {actions.lastAction}.
        </p>
      )}
    </div>
  );
}
