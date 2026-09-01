"use client";

/**
 * Access requests — the landing page's "Sign Up", and the reader it never had.
 *
 * 🔴 THE TABLE HAD A WRITER AND NO READER (L1).
 *
 * `POST /api/public/access-requests` has recorded interest since migration 059
 * and the landing page has offered the form since the marketplace shipped. Until
 * 2026-09-01 nothing in `apps/api/app` or `apps/web` ever read the table back,
 * so every request an anonymous visitor submitted went into a queue no screen
 * could open. `MEMORY.md` states the rule this breaks: *"a route with no caller,
 * a permission with no enforcement point and a table with no writer are one
 * defect."* A table with no READER is the same defect seen from the other side —
 * and the more misleading one, because the visitor got a cheerful "your request
 * has been queued for review" and nobody could review it.
 *
 * The schema had been ready the whole time: `status` already CHECKs
 * `new|approved|rejected`, `decided_by` already references `core.users`,
 * `decided_at` already exists, and there was already an index on
 * `(status, created_at DESC)`. So closing this needed no migration. It needed
 * the reader and the decision.
 *
 * 🔴 APPROVING IS A BIND, NOT A REGISTRATION, AND THIS FORM SAYS SO.
 *
 * This application cannot create credentials — Keycloak owns identity, and
 * self-registration into a tenanted R&D system stays off (ADR-025). Approving
 * therefore carries the `keycloak_sub` of an identity that already exists, and
 * goes through the *same* bind as `POST /api/admin/members`. The field is
 * labelled for what it is rather than hidden behind the word "approve", because
 * an administrator who thinks this creates an account will approve somebody and
 * then wonder why they cannot sign in.
 *
 * ⚠️ THE ADDRESS IS NOT AN INPUT. The server binds the address that was
 * SUBMITTED, read from the request row, so an approval cannot be quietly
 * redirected to a different person than the one that was reviewed. Only the
 * display name may be corrected, and only because it is presentation.
 *
 * ⚠️ AND THE ROLE IS REQUIRED. A membership with no role holds no permission,
 * so approving into one produces an account that signs in and reaches nothing —
 * a "yes" that behaves like a "no". The server refuses it at 422; this form
 * refuses to submit it, so the refusal is not the first thing the administrator
 * learns.
 */

import { useState } from "react";

import { serverMessage } from "@/lib/api/client";
import { useAccessRequests, useAdminActions, useRoles } from "@/lib/api/hooks";
import type { AccessRequest, Role } from "@/lib/api/admin";
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

type Queue = "new" | "approved" | "rejected" | "all";

const QUEUES: readonly { readonly key: Queue; readonly label: string }[] = [
  { key: "new", label: "Awaiting decision" },
  { key: "approved", label: "Approved" },
  { key: "rejected", label: "Rejected" },
  { key: "all", label: "All" },
];

/**
 * A decided request states its outcome in text as well as by which queue it is
 * in — colour and position alone are not a status (`CLAUDE.md` §11: no
 * colour-only status, and every state carries icon + text).
 */
function statusLabel(status: string): string {
  if (status === "new") return "● Awaiting decision";
  if (status === "approved") return "✓ Approved";
  if (status === "rejected") return "✕ Rejected";
  return status;
}

function whenever(value: string | null): string {
  if (!value) return "—";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString();
}

function RequestRow({
  request,
  roles,
  mayDecide,
  pending,
  onDecide,
}: {
  request: AccessRequest;
  roles: readonly Role[];
  mayDecide: boolean;
  pending: boolean;
  onDecide: (
    requestId: string,
    body: {
      decision: "approved" | "rejected";
      reason: string;
      keycloak_sub?: string;
      display_name?: string;
      roles?: readonly string[];
    },
    after: () => void,
  ) => void;
}) {
  const [approving, setApproving] = useState(false);
  const [rejecting, setRejecting] = useState(false);
  const [subject, setSubject] = useState("");
  const [displayName, setDisplayName] = useState(request.full_name);
  const [roleCode, setRoleCode] = useState("");
  const [reason, setReason] = useState("");

  const decided = request.status !== "new";
  const canSubmitApproval =
    subject.trim().length > 0 && roleCode.length > 0 && reason.trim().length >= 3;

  const reset = () => {
    setApproving(false);
    setRejecting(false);
    setSubject("");
    setRoleCode("");
    setReason("");
  };

  return (
    <li className="rounded border border-slate-200 bg-white p-3">
      <div className="flex flex-wrap items-baseline gap-2">
        <span className="text-sm font-medium text-slate-900">{request.full_name}</span>
        <span className="text-xs text-slate-600">{request.work_email}</span>
        <span className={TAG}>{request.company}</span>
        <span className="text-xs text-slate-600">{statusLabel(request.status)}</span>
      </div>

      <dl className="mt-2 grid grid-cols-1 gap-x-6 gap-y-1 text-xs text-slate-600 sm:grid-cols-2">
        <div className="flex gap-2">
          <dt className="font-medium text-slate-700">Requested</dt>
          <dd>{whenever(request.created_at)}</dd>
        </div>
        <div className="flex gap-2">
          <dt className="font-medium text-slate-700">Decided</dt>
          <dd>{whenever(request.decided_at)}</dd>
        </div>
      </dl>

      {request.reason ? (
        <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-slate-700">
          {request.reason}
        </p>
      ) : (
        <p className="mt-2 text-xs italic text-slate-500">
          No reason was given. The form does not require one.
        </p>
      )}

      {decided || !mayDecide ? null : (
        <div className="mt-3 flex flex-wrap gap-2">
          <button
            type="button"
            className={BUTTON_QUIET}
            disabled={pending}
            onClick={() => {
              setApproving((open) => !open);
              setRejecting(false);
            }}
          >
            {approving ? "Cancel" : "Approve…"}
          </button>
          <button
            type="button"
            className={BUTTON_QUIET}
            disabled={pending}
            onClick={() => {
              setRejecting((open) => !open);
              setApproving(false);
            }}
          >
            {rejecting ? "Cancel" : "Reject…"}
          </button>
        </div>
      )}

      {approving ? (
        <form
          className="mt-3 space-y-3 rounded border border-slate-200 bg-slate-50 p-3"
          onSubmit={(event) => {
            event.preventDefault();
            onDecide(
              request.id,
              {
                decision: "approved",
                reason: reason.trim(),
                keycloak_sub: subject.trim(),
                display_name: displayName.trim() || undefined,
                roles: [roleCode],
              },
              reset,
            );
          }}
        >
          <p className="text-xs leading-relaxed text-slate-600">
            <strong className="font-medium text-slate-900">
              This binds an identity that already exists in Keycloak.
            </strong>{" "}
            It does not create one. Create the account in Keycloak first, then
            paste its subject id here. The address bound is the one that was
            submitted — <code className="rounded bg-white px-1">{request.work_email}</code> —
            and is not editable here.
          </p>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <label className={LABEL}>
              Keycloak subject id
              <input
                className={INPUT}
                value={subject}
                onChange={(event) => setSubject(event.target.value)}
                required
              />
            </label>
            <label className={LABEL}>
              Display name
              <input
                className={INPUT}
                value={displayName}
                onChange={(event) => setDisplayName(event.target.value)}
              />
            </label>
            <label className={LABEL}>
              Role
              <select
                className={INPUT}
                value={roleCode}
                onChange={(event) => setRoleCode(event.target.value)}
                required
              >
                <option value="">Choose a role…</option>
                {roles.map((role) => (
                  <option key={role.code} value={role.code}>
                    {role.name}
                  </option>
                ))}
              </select>
            </label>
            <label className={LABEL}>
              Reason (recorded in the audit trail)
              <input
                className={INPUT}
                value={reason}
                onChange={(event) => setReason(event.target.value)}
                minLength={3}
                required
              />
            </label>
          </div>
          <button type="submit" className={BUTTON} disabled={pending || !canSubmitApproval}>
            Approve and bind
          </button>
        </form>
      ) : null}

      {rejecting ? (
        <form
          className="mt-3 space-y-3 rounded border border-slate-200 bg-slate-50 p-3"
          onSubmit={(event) => {
            event.preventDefault();
            onDecide(request.id, { decision: "rejected", reason: reason.trim() }, reset);
          }}
        >
          <label className={LABEL}>
            Reason (recorded in the audit trail)
            <input
              className={INPUT}
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              minLength={3}
              required
            />
          </label>
          <button
            type="submit"
            className={BUTTON}
            disabled={pending || reason.trim().length < 3}
          >
            Reject
          </button>
        </form>
      ) : null}
    </li>
  );
}

export function AccessRequestsAdministration() {
  const [queue, setQueue] = useState<Queue>("new");
  const requests = useAccessRequests(queue);
  const roles = useRoles();
  const actions = useAdminActions();
  const permissions = usePermissions();
  const mayDecide = permits(permissions, "admin.users");

  return (
    <section className="mt-10">
      <h2 className="text-base font-semibold text-slate-900">Access requests</h2>
      <p className="mt-1 max-w-3xl text-sm leading-relaxed text-slate-600">
        Sign Up on the public landing page records a request here. It creates no
        identity and no membership: access to the R&amp;D environment is granted
        by an administrator, not automatically.
      </p>
      <p className="mt-2 max-w-3xl text-xs leading-relaxed text-slate-500">
        This queue is platform-wide rather than per-organization — an access
        request names no tenant, because the person submitting it does not know
        which one they would be joining. In a multi-organization deployment that
        means an administrator sees applicants who did not mean to apply here.
        Recorded as <span className="font-medium">I113</span> rather than left
        unsaid.
      </p>

      <div className="mt-3 flex flex-wrap gap-2">
        {QUEUES.map((option) => (
          <button
            key={option.key}
            type="button"
            className={
              option.key === queue
                ? "rounded bg-slate-900 px-3 py-1 text-xs font-medium text-white"
                : "rounded border border-slate-300 bg-white px-3 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50"
            }
            aria-pressed={option.key === queue}
            onClick={() => setQueue(option.key)}
          >
            {option.label}
          </button>
        ))}
      </div>

      {actions.error ? (
        <p role="alert" className="mt-3 text-sm text-rose-700">
          {serverMessage(actions.error)}
        </p>
      ) : null}

      {requests.unavailable ? (
        <p className="mt-3 text-sm text-slate-600">{requests.unavailable}</p>
      ) : requests.isLoading ? (
        <p className="mt-3 text-sm text-slate-600">Loading…</p>
      ) : requests.error ? (
        <p role="alert" className="mt-3 text-sm text-rose-700">
          {serverMessage(requests.error)}
        </p>
      ) : (requests.data ?? []).length === 0 ? (
        // 🔴 AN EMPTY QUEUE IS AN ANSWER, AND IT SAYS WHICH QUEUE IS EMPTY.
        // "No requests" beside a filter the reader may not have noticed is the
        // shape that makes somebody conclude the feature is broken.
        <p className="mt-3 text-sm text-slate-600">
          No requests in “{QUEUES.find((option) => option.key === queue)?.label}”.
        </p>
      ) : (
        <ul className="mt-3 space-y-2">
          {(requests.data ?? []).map((request) => (
            <RequestRow
              key={request.id}
              request={request}
              roles={roles.data ?? []}
              mayDecide={mayDecide}
              pending={actions.isPending}
              onDecide={actions.decide}
            />
          ))}
        </ul>
      )}
    </section>
  );
}
