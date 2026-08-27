"use client";

/**
 * A live project — the workspace where Slice 2's writes finally have controls.
 *
 * 🔴 THE PROJECT MODULE COULD BE READ AND NOT WORKED.
 *
 * Measured 2026-08-27: eleven write endpoints on `app/api/projects.py`, and
 * exactly one — `POST /api/projects` — reachable from a browser. Advancing a
 * stage, approving a requirement, managing a milestone, tracking a risk and
 * putting somebody on a project were all API-only. Those are precisely the acts
 * that make the Lead and the Director roles mean anything: `lead.demo` holds
 * `project.advance_stage`, `requirement.approve`, `milestone.manage` and
 * `project.assign_member`, and had a control for none of them.
 *
 * 🔴 WHY THIS IS `?id=` AND NOT `/projects/[code]`.
 *
 * `/projects/[code]` is a STATIC EXPORT of the bundled demonstration fixture —
 * `generateStaticParams` prerenders the three fixture codes and there is no
 * server to resolve a fourth. A live project has a UUID and no prerendered
 * page, so a query parameter is the only shape that works, exactly as
 * `/testing/test?id=`, `/laboratory/batch?id=`, `/formulations/formula?version=`
 * and `/failures/investigation?id=` already do. The demonstration route is left
 * alone; this is the live one.
 *
 * 🔴 TWO GATES PER WRITE, AND ONLY ONE IS A PERMISSION.
 *
 * Every route here carries `require_permission(...)` AND
 * `require_project_member()`. The second is not in any permission set — and
 * does not need to be, because `GET /api/projects/{id}` is member-gated too:
 * **if this workspace loaded at all, the caller is a member.** Fetching the
 * member list to decide what to show would be a second implementation of a gate
 * the server already applied, and that read is itself member-gated, so it could
 * never answer for somebody outside.
 *
 * ⚠️ FOUR OF THE TEN REQUIRE A `reason`, AND THAT IS §9 RATHER THAN FORM
 * VALIDATION. Advancing a stage, changing a milestone's status, updating a risk
 * and removing a member are decisions somebody has to reconstruct later. The
 * button stays disabled until there is one, so the round trip is not spent
 * being told.
 */

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { DataSourceError, LiveOnlyPage } from "@/components/ui/data-source-banner";
import { Absent } from "@/components/ui/record-link";
import { serverMessage } from "@/lib/api/client";
import {
  useMilestones,
  usePipeline,
  useProject,
  useProjectActions,
  useProjectMembers,
  useRequirementMatrix,
  useRisks,
} from "@/lib/api/hooks";
import type {
  Milestone,
  PipelineStage,
  Project,
  ProjectMember,
  RequirementMatrix,
  Risk,
} from "@/lib/api/projects";
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

/* -------------------------------------------------------------------------- */
/* Pipeline                                                                    */
/* -------------------------------------------------------------------------- */

function PipelineSection({
  projectId,
  mayAdvance,
  pending,
  onAdvance,
}: {
  projectId: string;
  mayAdvance: boolean;
  pending: boolean;
  onAdvance: (
    request: { to_stage_code: string; reason: string; force?: boolean },
    after: () => void,
  ) => void;
}) {
  const { data, error } = usePipeline(projectId);
  const [target, setTarget] = useState("");
  const [reason, setReason] = useState("");

  const stages: PipelineStage[] = data ?? [];

  return (
    <section>
      <h2 className="text-sm font-semibold text-slate-900">Pipeline</h2>
      <p className="mt-1 text-xs text-slate-600">
        Stage history is preserved, never overwritten — §5. A stage that was
        reworked says so.
      </p>

      {error !== null ? (
        <DataSourceError error={error} />
      ) : stages.length === 0 ? (
        <p className="mt-2 text-sm text-slate-600">No stages defined.</p>
      ) : (
        <ol className="mt-2 space-y-1">
          {stages.map((s) => (
            <li key={s.stage_code} className="flex flex-wrap items-baseline gap-2 text-xs">
              <span className="tabular-nums text-slate-500">{s.sequence}</span>
              <span className="font-medium text-slate-900">{s.name}</span>
              {/* 🔴 A STAGE WITH NO ROW IS "NOT REACHED", NOT "not_started".
                  `project_pipeline` LEFT JOINs the project's stage rows onto
                  the definitions, so `status` is null for a stage the project
                  has never been in — a different fact from a stage it has
                  reached and not begun. */}
              <span className={TAG}>{s.status === null ? "not reached" : words(s.status)}</span>
              {s.requires_approval && <span className={TAG}>needs approval</span>}
              {s.is_rework && <span className={TAG}>rework</span>}
              {s.blocked_reason !== null && (
                <span className="text-amber-900">blocked: {s.blocked_reason}</span>
              )}
            </li>
          ))}
        </ol>
      )}

      {mayAdvance && (
        <div className="mt-3 flex max-w-3xl flex-wrap items-end gap-2">
          <div className="w-56">
            <label className={LABEL} htmlFor="advance-stage">
              Advance to
            </label>
            <select
              id="advance-stage"
              className={INPUT}
              value={target}
              onChange={(e) => setTarget(e.target.value)}
            >
              <option value="">Choose a stage</option>
              {/* From the pipeline the server returned, never a hardcoded list:
                  stages are configuration rows and a second copy here would go
                  stale the first time Administration edited one. */}
              {stages.map((s) => (
                <option key={s.stage_code} value={s.stage_code}>
                  {s.sequence}. {s.name}
                </option>
              ))}
            </select>
          </div>
          <div className="min-w-[16rem] flex-1">
            <label className={LABEL} htmlFor="advance-reason">
              Why — recorded on the transition
            </label>
            <input
              id="advance-reason"
              className={INPUT}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          </div>
          <button
            type="button"
            className={BUTTON}
            disabled={pending || target === "" || reason.trim().length < 3}
            onClick={() =>
              onAdvance({ to_stage_code: target, reason: reason.trim() }, () => {
                setTarget("");
                setReason("");
              })
            }
          >
            Advance
          </button>
        </div>
      )}
    </section>
  );
}

/* -------------------------------------------------------------------------- */
/* Requirements                                                                */
/* -------------------------------------------------------------------------- */

function RequirementsSection({ projectId }: { projectId: string }) {
  const { data, error } = useRequirementMatrix(projectId);

  if (error !== null) {
    return (
      <section>
        <h2 className="text-sm font-semibold text-slate-900">Requirements</h2>
        <DataSourceError error={error} />
      </section>
    );
  }

  const matrix: RequirementMatrix | undefined = data;

  return (
    <section>
      <h2 className="text-sm font-semibold text-slate-900">Requirements</h2>
      {matrix === undefined ? (
        <p className="mt-1 text-sm text-slate-600">Loading the verification matrix…</p>
      ) : (
        <>
          <p className="mt-1 text-xs text-slate-600">
            {matrix.summary.verified} of {matrix.summary.total} verified ·{" "}
            {matrix.summary.blocking_validation} blocking validation
          </p>
          {/* 🔴 THE SERVER'S NOTE, RENDERED. It says WHY everything reads
              `not_verified` — "because no test evidence exists yet, not because
              testing has failed". That sentence is the difference between a
              project that is early and one that is failing, and dropping it
              would let a director draw the second conclusion from the first
              situation. */}
          {matrix.note !== null && (
            <p
              role="note"
              className="mt-2 rounded border border-slate-300 bg-slate-50 px-3 py-2 text-xs text-slate-800"
            >
              {matrix.note}
            </p>
          )}
          {matrix.requirements.length === 0 ? (
            <p className="mt-2 text-sm text-slate-600">No requirements recorded.</p>
          ) : (
            <ul className="mt-2 space-y-2">
              {matrix.requirements.map((r) => (
                <li key={r.requirement_id} className="rounded border border-slate-200 bg-white p-3">
                  <div className="flex flex-wrap items-baseline gap-2">
                    <span className="text-xs tabular-nums text-slate-500">
                      {r.requirement_code}
                    </span>
                    <span className="flex-1 text-sm font-medium text-slate-900">{r.name}</span>
                    <span className={TAG}>{words(r.criticality)}</span>
                    <span className={TAG}>{words(r.requirement_status)}</span>
                    <span className={TAG}>{words(r.verification_status)}</span>
                    {r.blocking_validation && <span className={TAG}>blocks validation</span>}
                  </div>
                  <dl className="mt-1 flex flex-wrap gap-x-6 text-xs text-slate-600">
                    <div className="flex gap-1.5">
                      <dt className="font-medium text-slate-500">Acceptance</dt>
                      {/* Pre-formatted by the server from NUMERIC columns.
                          Rendered as given — parsing it back into numbers would
                          reconstruct the database from a display string. */}
                      <dd>{r.acceptance ?? <Absent what="not stated" />}</dd>
                    </div>
                    <div className="flex gap-1.5">
                      <dt className="font-medium text-slate-500">Verified by</dt>
                      <dd>{words(r.verification_method)}</dd>
                    </div>
                    <div className="flex gap-1.5">
                      <dt className="font-medium text-slate-500">Revision</dt>
                      <dd className="tabular-nums">{r.revision}</dd>
                    </div>
                  </dl>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </section>
  );
}

/* -------------------------------------------------------------------------- */
/* Milestones                                                                  */
/* -------------------------------------------------------------------------- */

const MILESTONE_STATUSES = ["planned", "in_progress", "met", "missed", "cancelled"] as const;

function MilestonesSection({
  projectId,
  mayManage,
  pending,
  onAdd,
  onSetStatus,
}: {
  projectId: string;
  mayManage: boolean;
  pending: boolean;
  onAdd: (request: { name: string; planned_date: string }, after: () => void) => void;
  onSetStatus: (
    milestoneId: string,
    request: { status: string; reason: string },
    after: () => void,
  ) => void;
}) {
  const { data, error } = useMilestones(projectId);
  const [name, setName] = useState("");
  const [plannedDate, setPlannedDate] = useState("");
  const [openFor, setOpenFor] = useState<string | null>(null);
  const [status, setStatus] = useState<string>("in_progress");
  const [reason, setReason] = useState("");

  const milestones: Milestone[] = data ?? [];

  return (
    <section>
      <h2 className="text-sm font-semibold text-slate-900">Milestones</h2>

      {error !== null ? (
        <DataSourceError error={error} />
      ) : milestones.length === 0 ? (
        <p className="mt-1 text-sm text-slate-600">None planned.</p>
      ) : (
        <ul className="mt-2 space-y-2">
          {milestones.map((m) => (
            <li key={m.id} className="rounded border border-slate-200 bg-white p-3">
              <div className="flex flex-wrap items-baseline gap-2">
                <span className="flex-1 text-sm font-medium text-slate-900">{m.name}</span>
                <span className={TAG}>{words(m.status)}</span>
                {/* Computed by the server. A browser deriving "overdue" from a
                    date string would be a second definition of it, and would
                    get the timezone wrong. */}
                {m.is_overdue && <span className={TAG}>overdue</span>}
                <span className="text-xs tabular-nums text-slate-600">
                  planned {m.planned_date}
                </span>
                {m.actual_date !== null && (
                  <span className="text-xs tabular-nums text-slate-600">
                    actual {m.actual_date}
                  </span>
                )}
                {mayManage && openFor !== m.id && (
                  <button
                    type="button"
                    className="text-xs text-slate-700 underline underline-offset-2"
                    onClick={() => setOpenFor(m.id)}
                  >
                    Change status
                  </button>
                )}
              </div>

              {mayManage && openFor === m.id && (
                <div className="mt-2 flex flex-wrap items-end gap-2">
                  <div className="w-40">
                    <label className={LABEL} htmlFor={`ms-status-${m.id}`}>
                      Status
                    </label>
                    <select
                      id={`ms-status-${m.id}`}
                      className={INPUT}
                      value={status}
                      onChange={(e) => setStatus(e.target.value)}
                    >
                      {MILESTONE_STATUSES.map((s) => (
                        <option key={s} value={s}>
                          {words(s)}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="min-w-[14rem] flex-1">
                    <label className={LABEL} htmlFor={`ms-reason-${m.id}`}>
                      Why
                    </label>
                    <input
                      id={`ms-reason-${m.id}`}
                      className={INPUT}
                      value={reason}
                      onChange={(e) => setReason(e.target.value)}
                    />
                  </div>
                  <button
                    type="button"
                    className={BUTTON_QUIET}
                    disabled={pending || reason.trim().length < 3}
                    onClick={() =>
                      onSetStatus(m.id, { status, reason: reason.trim() }, () => {
                        setReason("");
                        setOpenFor(null);
                      })
                    }
                  >
                    Record
                  </button>
                  <button
                    type="button"
                    className={BUTTON_QUIET}
                    onClick={() => {
                      setReason("");
                      setOpenFor(null);
                    }}
                  >
                    Cancel
                  </button>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}

      {mayManage && (
        <div className="mt-3 flex max-w-3xl flex-wrap items-end gap-2">
          <div className="min-w-[16rem] flex-1">
            <label className={LABEL} htmlFor="milestone-name">
              New milestone
            </label>
            <input
              id="milestone-name"
              className={INPUT}
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>
          <div className="w-44">
            <label className={LABEL} htmlFor="milestone-date">
              Planned date
            </label>
            <input
              id="milestone-date"
              type="date"
              className={INPUT}
              value={plannedDate}
              onChange={(e) => setPlannedDate(e.target.value)}
            />
          </div>
          <button
            type="button"
            className={BUTTON_QUIET}
            disabled={pending || name.trim() === "" || plannedDate === ""}
            onClick={() =>
              onAdd({ name: name.trim(), planned_date: plannedDate }, () => {
                setName("");
                setPlannedDate("");
              })
            }
          >
            Add milestone
          </button>
        </div>
      )}
    </section>
  );
}

/* -------------------------------------------------------------------------- */
/* Risks                                                                       */
/* -------------------------------------------------------------------------- */

const RISK_CATEGORIES = [
  "technical",
  "material",
  "process",
  "schedule",
  "commercial",
  "regulatory",
  "supply",
] as const;
const RISK_STATUSES = ["open", "mitigating", "closed", "accepted", "realised"] as const;
const LEVELS = ["low", "medium", "high"] as const;

function RisksSection({
  projectId,
  mayCreate,
  mayManage,
  pending,
  onAdd,
  onChange,
}: {
  projectId: string;
  mayCreate: boolean;
  mayManage: boolean;
  pending: boolean;
  onAdd: (
    request: {
      risk_code: string;
      title: string;
      probability: "low" | "medium" | "high";
      impact: "low" | "medium" | "high";
      category: string;
    },
    after: () => void,
  ) => void;
  onChange: (
    riskId: string,
    request: { reason: string; status?: string; mitigation?: string },
    after: () => void,
  ) => void;
}) {
  const { data, error } = useRisks(projectId);
  const [code, setCode] = useState("");
  const [title, setTitle] = useState("");
  const [probability, setProbability] = useState<"low" | "medium" | "high">("medium");
  const [impact, setImpact] = useState<"low" | "medium" | "high">("medium");
  const [category, setCategory] = useState<string>("technical");
  const [openFor, setOpenFor] = useState<string | null>(null);
  const [status, setStatus] = useState<string>("mitigating");
  const [mitigation, setMitigation] = useState("");
  const [reason, setReason] = useState("");

  const risks: Risk[] = data ?? [];

  return (
    <section>
      <h2 className="text-sm font-semibold text-slate-900">Risks</h2>

      {error !== null ? (
        <DataSourceError error={error} />
      ) : risks.length === 0 ? (
        <p className="mt-1 text-sm text-slate-600">None recorded.</p>
      ) : (
        <ul className="mt-2 space-y-2">
          {risks.map((r) => (
            <li key={r.id} className="rounded border border-slate-200 bg-white p-3">
              <div className="flex flex-wrap items-baseline gap-2">
                <span className="text-xs tabular-nums text-slate-500">{r.risk_code}</span>
                <span className="flex-1 text-sm font-medium text-slate-900">{r.title}</span>
                <span className={TAG}>{words(r.category)}</span>
                {/* Probability and impact in words, both of them, always. A
                    single "risk score" would be a judgement this endpoint has
                    not made — and §11 forbids colour-only status, which a
                    heat-map cell is. */}
                <span className={TAG}>probability {r.probability}</span>
                <span className={TAG}>impact {r.impact}</span>
                <span className={TAG}>{words(r.status)}</span>
                {mayManage && openFor !== r.id && (
                  <button
                    type="button"
                    className="text-xs text-slate-700 underline underline-offset-2"
                    onClick={() => setOpenFor(r.id)}
                  >
                    Update
                  </button>
                )}
              </div>
              {r.mitigation !== null && (
                <p className="mt-1 text-xs text-slate-700">
                  <span className="font-medium">Mitigation: </span>
                  {r.mitigation}
                </p>
              )}

              {mayManage && openFor === r.id && (
                <div className="mt-2 flex flex-wrap items-end gap-2">
                  <div className="w-40">
                    <label className={LABEL} htmlFor={`risk-status-${r.id}`}>
                      Status
                    </label>
                    <select
                      id={`risk-status-${r.id}`}
                      className={INPUT}
                      value={status}
                      onChange={(e) => setStatus(e.target.value)}
                    >
                      {RISK_STATUSES.map((s) => (
                        <option key={s} value={s}>
                          {words(s)}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="min-w-[14rem] flex-1">
                    <label className={LABEL} htmlFor={`risk-mitigation-${r.id}`}>
                      Mitigation
                    </label>
                    <input
                      id={`risk-mitigation-${r.id}`}
                      className={INPUT}
                      value={mitigation}
                      onChange={(e) => setMitigation(e.target.value)}
                    />
                  </div>
                  <div className="min-w-[12rem] flex-1">
                    <label className={LABEL} htmlFor={`risk-reason-${r.id}`}>
                      Why
                    </label>
                    <input
                      id={`risk-reason-${r.id}`}
                      className={INPUT}
                      value={reason}
                      onChange={(e) => setReason(e.target.value)}
                    />
                  </div>
                  <button
                    type="button"
                    className={BUTTON_QUIET}
                    disabled={pending || reason.trim().length < 3}
                    onClick={() =>
                      onChange(
                        r.id,
                        {
                          reason: reason.trim(),
                          status,
                          // 🔴 OMITTED WHEN EMPTY, NEVER SENT AS "". `RiskUpdate`
                          // treats null as "leave unchanged", and its own
                          // docstring says why: a PATCH that blanked the
                          // mitigation because the client did not resend it is
                          // how a risk stops being tracked without anyone
                          // deciding that.
                          ...(mitigation.trim() === "" ? {} : { mitigation: mitigation.trim() }),
                        },
                        () => {
                          setReason("");
                          setMitigation("");
                          setOpenFor(null);
                        },
                      )
                    }
                  >
                    Record
                  </button>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}

      {mayCreate && (
        <div className="mt-3 grid max-w-3xl gap-2">
          <div className="flex flex-wrap items-end gap-2">
            <div className="w-36">
              <label className={LABEL} htmlFor="risk-code">
                Risk code
              </label>
              <input
                id="risk-code"
                className={INPUT}
                value={code}
                onChange={(e) => setCode(e.target.value)}
                placeholder="RSK-01"
              />
            </div>
            <div className="min-w-[16rem] flex-1">
              <label className={LABEL} htmlFor="risk-title">
                What could go wrong
              </label>
              <input
                id="risk-title"
                className={INPUT}
                value={title}
                onChange={(e) => setTitle(e.target.value)}
              />
            </div>
          </div>
          <div className="flex flex-wrap items-end gap-2">
            <div className="w-36">
              <label className={LABEL} htmlFor="risk-probability">
                Probability
              </label>
              <select
                id="risk-probability"
                className={INPUT}
                value={probability}
                onChange={(e) => setProbability(e.target.value as "low" | "medium" | "high")}
              >
                {LEVELS.map((l) => (
                  <option key={l} value={l}>
                    {l}
                  </option>
                ))}
              </select>
            </div>
            <div className="w-36">
              <label className={LABEL} htmlFor="risk-impact">
                Impact
              </label>
              <select
                id="risk-impact"
                className={INPUT}
                value={impact}
                onChange={(e) => setImpact(e.target.value as "low" | "medium" | "high")}
              >
                {LEVELS.map((l) => (
                  <option key={l} value={l}>
                    {l}
                  </option>
                ))}
              </select>
            </div>
            <div className="w-44">
              <label className={LABEL} htmlFor="risk-category">
                Category
              </label>
              <select
                id="risk-category"
                className={INPUT}
                value={category}
                onChange={(e) => setCategory(e.target.value)}
              >
                {RISK_CATEGORIES.map((c) => (
                  <option key={c} value={c}>
                    {words(c)}
                  </option>
                ))}
              </select>
            </div>
            <button
              type="button"
              className={BUTTON_QUIET}
              disabled={pending || code.trim().length < 2 || title.trim() === ""}
              onClick={() =>
                onAdd(
                  {
                    risk_code: code.trim(),
                    title: title.trim(),
                    probability,
                    impact,
                    category,
                  },
                  () => {
                    setCode("");
                    setTitle("");
                  },
                )
              }
            >
              Raise risk
            </button>
          </div>
        </div>
      )}
    </section>
  );
}

/* -------------------------------------------------------------------------- */
/* Members                                                                     */
/* -------------------------------------------------------------------------- */

const PROJECT_ROLES = [
  "lead",
  "chemist",
  "engineer",
  "technician",
  "qa",
  "director",
  "observer",
] as const;

function MembersSection({
  projectId,
  mayAssign,
  pending,
  onAdd,
  onRemove,
}: {
  projectId: string;
  mayAssign: boolean;
  pending: boolean;
  onAdd: (request: { user_id: string; project_role: string }, after: () => void) => void;
  onRemove: (userId: string, reason: string, after: () => void) => void;
}) {
  const { data, error } = useProjectMembers(projectId);
  const [userId, setUserId] = useState("");
  const [role, setRole] = useState<string>("chemist");
  const [openFor, setOpenFor] = useState<string | null>(null);
  const [reason, setReason] = useState("");

  const members: ProjectMember[] = data ?? [];

  return (
    <section>
      <h2 className="text-sm font-semibold text-slate-900">Members</h2>
      <p className="mt-1 text-xs text-slate-600">
        Inactive members are shown, not hidden. <em>Who has ever had access to
        this project</em> is the question asked after an incident, and a list
        that dropped them could not answer it.
      </p>

      {error !== null ? (
        <DataSourceError error={error} />
      ) : members.length === 0 ? (
        <p className="mt-1 text-sm text-slate-600">Nobody is on this project.</p>
      ) : (
        <ul className="mt-2 space-y-1">
          {members.map((m) => (
            <li key={m.id} className="flex flex-wrap items-baseline gap-2 text-sm">
              <span className="font-medium text-slate-900">{m.display_name}</span>
              <span className="text-xs text-slate-600">{m.email}</span>
              <span className={TAG}>{words(m.project_role)}</span>
              {m.is_project_lead && <span className={TAG}>project lead</span>}
              {m.status !== "active" && <span className={TAG}>{words(m.status)}</span>}
              {mayAssign && m.status === "active" && openFor !== m.user_id && (
                <button
                  type="button"
                  className="text-xs text-slate-700 underline underline-offset-2"
                  onClick={() => setOpenFor(m.user_id)}
                >
                  Remove
                </button>
              )}
              {mayAssign && openFor === m.user_id && (
                <span className="flex flex-wrap items-end gap-2">
                  <input
                    aria-label={`Reason for removing ${m.display_name}`}
                    className={INPUT + " w-64"}
                    value={reason}
                    onChange={(e) => setReason(e.target.value)}
                    placeholder="why they are coming off the project"
                  />
                  <button
                    type="button"
                    className={BUTTON_QUIET}
                    disabled={pending || reason.trim().length < 3}
                    onClick={() =>
                      onRemove(m.user_id, reason.trim(), () => {
                        setReason("");
                        setOpenFor(null);
                      })
                    }
                  >
                    Remove
                  </button>
                  <button
                    type="button"
                    className={BUTTON_QUIET}
                    onClick={() => {
                      setReason("");
                      setOpenFor(null);
                    }}
                  >
                    Cancel
                  </button>
                </span>
              )}
            </li>
          ))}
        </ul>
      )}

      {mayAssign && (
        <div className="mt-3 flex max-w-3xl flex-wrap items-end gap-2">
          <div className="min-w-[20rem] flex-1">
            <label className={LABEL} htmlFor="member-user">
              Person — their user id
            </label>
            {/* ⚠️ A UUID FIELD, AND THAT IS A KNOWN GAP RATHER THAN A CHOICE.
                There is no endpoint that lists the organization's members for
                somebody to pick from: `GET /api/admin/members` needs
                `admin.users`, which the Lead does not hold, and the project's
                own member list only shows who is already on it. Asking for a
                UUID is honest about that; inventing a directory read the API
                does not offer would not be. Filed rather than papered over. */}
            <input
              id="member-user"
              className={INPUT}
              value={userId}
              onChange={(e) => setUserId(e.target.value)}
              placeholder="00000000-0000-0000-0000-000000000000"
            />
          </div>
          <div className="w-44">
            <label className={LABEL} htmlFor="member-role">
              Project role
            </label>
            <select
              id="member-role"
              className={INPUT}
              value={role}
              onChange={(e) => setRole(e.target.value)}
            >
              {PROJECT_ROLES.map((r) => (
                <option key={r} value={r}>
                  {words(r)}
                </option>
              ))}
            </select>
          </div>
          <button
            type="button"
            className={BUTTON_QUIET}
            disabled={pending || userId.trim() === ""}
            onClick={() =>
              onAdd({ user_id: userId.trim(), project_role: role }, () => setUserId(""))
            }
          >
            Add member
          </button>
        </div>
      )}
    </section>
  );
}

/* -------------------------------------------------------------------------- */

function ProjectWorkspace({ project }: { project: Project }) {
  const actions = useProjectActions(project.id);
  const permissions = usePermissions();

  // Each name is the permission THAT endpoint declares, read off
  // `app/api/projects.py` rather than inferred from the control's label.
  const mayAdvance = permits(permissions, "project.advance_stage");
  const mayManageMilestones = permits(permissions, "milestone.manage");
  const mayCreateRisk = permits(permissions, "risk.create");
  const mayManageRisk = permits(permissions, "risk.manage");
  const mayAssign = permits(permissions, "project.assign_member");

  return (
    <div className="space-y-6">
      <section>
        <div className="flex flex-wrap items-baseline gap-2">
          <span className="text-xs font-medium tabular-nums text-slate-500">
            {project.project_code}
          </span>
          <h1 className="flex-1 text-lg font-semibold text-slate-900">{project.name}</h1>
          <span className={TAG}>{words(project.status)}</span>
          <span className={TAG}>{words(project.priority)}</span>
          {project.confidentiality === "restricted" && <span className={TAG}>restricted</span>}
        </div>
        <dl className="mt-2 flex flex-wrap gap-x-6 gap-y-1 text-xs text-slate-600">
          <div className="flex gap-1.5">
            <dt className="font-medium text-slate-500">Stage</dt>
            <dd>{project.current_stage ?? <Absent what="not started" />}</dd>
          </div>
          <div className="flex gap-1.5">
            <dt className="font-medium text-slate-500">Family</dt>
            <dd>{project.product_family ?? <Absent what="not set" />}</dd>
          </div>
          <div className="flex gap-1.5">
            <dt className="font-medium text-slate-500">Target release</dt>
            <dd className="tabular-nums">
              {project.target_release_date ?? <Absent what="not set" />}
            </dd>
          </div>
        </dl>
      </section>

      <PipelineSection
        projectId={project.id}
        mayAdvance={mayAdvance}
        pending={actions.isPending}
        onAdvance={actions.advance}
      />
      <RequirementsSection projectId={project.id} />
      <MilestonesSection
        projectId={project.id}
        mayManage={mayManageMilestones}
        pending={actions.isPending}
        onAdd={actions.addMilestone}
        onSetStatus={actions.setMilestone}
      />
      <RisksSection
        projectId={project.id}
        mayCreate={mayCreateRisk}
        mayManage={mayManageRisk}
        pending={actions.isPending}
        onAdd={actions.addRisk}
        onChange={actions.changeRisk}
      />
      <MembersSection
        projectId={project.id}
        mayAssign={mayAssign}
        pending={actions.isPending}
        onAdd={actions.addMember}
        onRemove={actions.removeMember}
      />

      {/* 🔴 A READER WITH NONE OF THE FIVE IS TOLD SO. Loading this page proves
          project membership — `GET /api/projects/{id}` is member-gated — so the
          only thing withheld here is a permission, and naming them gives
          "why can I not do anything?" an answer somebody can act on. */}
      {!mayAdvance && !mayManageMilestones && !mayCreateRisk && !mayManageRisk && !mayAssign && (
        <p className="text-sm text-slate-600">
          You are a member of this project and hold none of{" "}
          <code className="text-xs">project.advance_stage</code>,{" "}
          <code className="text-xs">milestone.manage</code>,{" "}
          <code className="text-xs">risk.create</code>,{" "}
          <code className="text-xs">risk.manage</code> or{" "}
          <code className="text-xs">project.assign_member</code>, so it is read-only
          from here. The record above is complete; only the controls are withheld.
        </p>
      )}

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

function ProjectScreen() {
  const params = useSearchParams();
  const projectId = params.get("id") ?? "";
  const { data, isLoading, error, unavailable } = useProject(projectId);

  return (
    <LiveOnlyPage
      title="Project"
      lede="The pipeline, requirements, milestones, risks and members of one live
            project — and the controls to move them, for whoever holds the
            permission each one requires."
      unavailable={unavailable}
      notInvented="live projects"
    >
      {projectId === "" ? (
        <p className="text-sm text-slate-600">
          No project chosen.{" "}
          <Link href="/projects" className="underline underline-offset-2">
            Open one from the list.
          </Link>
        </p>
      ) : error !== null ? (
        <DataSourceError error={error} />
      ) : unavailable !== null ? (
        <p className="text-sm text-slate-600">
          This project cannot be shown until this build is pointed at an API.
        </p>
      ) : data === undefined ? (
        <p className="text-sm text-slate-600">
          {isLoading ? "Loading the project…" : "Not found, or you are not a member of it."}
        </p>
      ) : (
        <ProjectWorkspace project={data} />
      )}
    </LiveOnlyPage>
  );
}

export default function ProjectWorkspacePage() {
  return (
    <Suspense fallback={<p className="p-6 text-sm text-slate-600">Loading…</p>}>
      <ProjectScreen />
    </Suspense>
  );
}
