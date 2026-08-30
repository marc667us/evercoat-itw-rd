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
import { formatDay, formatInstant } from "@/lib/format/date";
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
  RequirementRequest,
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
  // `_ENTERABLE` in `app/domains/pipeline/service.py`. Named here so the two
  // are findable together; a filter with four inline strings would not be.
  const ENTERABLE = ["not_started", "rework_required", "blocked", "on_hold"];
  const enterable = stages.filter((stage) => ENTERABLE.includes(stage.status));

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
              {/* ✅ CORRECTED. This branched on `s.status === null` to render
                  "not reached", under a comment claiming the LEFT JOIN left it
                  null for a stage the project had never been in. It does — and
                  `project_pipeline` then reshapes it: `r["status"] or
                  "not_started"`. The branch was unreachable and the comment
                  described a distinction the response does not make. Raised by
                  Codex. */}
              <span className={TAG}>{words(s.status)}</span>
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
              {/* 🔴 ONLY STAGES THE ENGINE WILL ACCEPT. Raised by Codex.
                  `advance_stage` re-enters a stage only when its previous
                  status is one of `not_started`, `rework_required`, `blocked`
                  or `on_hold` (`_ENTERABLE`); anything else is refused with a
                  409. The browser already HAS each status, so offering the
                  current stage and every completed one was offering work the
                  server had already decided against — the same shape as the
                  approvals queue listing test-owned routes.

                  ⚠️ THE LIST IS READ OFF THE SERVER'S OWN STATUSES, not from a
                  copy of `_ENTERABLE` invented here. If the engine widens the
                  rule this list widens with it only when the constant below is
                  updated too — which is why it is named and commented rather
                  than inlined as four strings in a filter. */}
              {enterable.map((stage) => (
                <option key={stage.stage_code} value={stage.stage_code}>
                  {stage.sequence}. {stage.name} ({words(stage.status)})
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
              maxLength={500}
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
          {enterable.length === 0 && (
            <p className="w-full text-xs text-slate-600">
              No stage can be entered from here. A stage already in progress or
              completed has to be marked <code>rework_required</code> before it
              can be re-entered.
            </p>
          )}
        </div>
      )}
    </section>
  );
}

/* -------------------------------------------------------------------------- */
/* Requirements                                                                */
/* -------------------------------------------------------------------------- */

const CRITICALITIES = ["critical", "major", "minor", "informational"] as const;

/**
 * The three requirement writes — and my own commit message said they were done.
 *
 * 🔴 CODEX CORRECTED A CLAIM I MADE. The commit that added this workspace said
 * *"ten of eleven endpoints now do"*. It was seven: `POST /requirements`,
 * `/approve` and `/revise` had client functions in neither the API module nor
 * the hook, and no control anywhere. A Lead still could not approve a
 * requirement — which is one of the four permissions the commit itself named as
 * the reason the Lead role was not real.
 *
 * Counting the endpoints I had wired, rather than the ones I meant to, would
 * have caught it. *Measure the claim, including your own.*
 *
 * 🔴 APPROVING FREEZES IT, AND REVISING MAKES A NEW REVISION.
 * `approve_requirement` is a 204 with no body — there is nowhere to put an
 * opinion — and a second attempt is a 409 rather than a silent no-op.
 * `RequirementRevise` extends `RequirementCreate`, so a revision RESTATES the
 * whole requirement and the server bumps `revision`: an approved requirement is
 * never edited in place, which is §8's rule for formulas applied to the thing
 * formulas are tested against.
 *
 * ⚠️ THE NUMERIC FIELDS ARE TEXT INPUTS AND STAY STRINGS ON THE WIRE. §5:
 * NUMERIC, never float. Pydantic parses a `Decimal` from a JSON string exactly
 * and from a JSON number through a float, so `type="number"` here is how a
 * specification quietly acquires a rounding error nobody typed.
 */
function RequirementForm({
  heading,
  submitLabel,
  requireReason,
  pending,
  onSubmit,
}: {
  heading: string;
  submitLabel: string;
  requireReason: boolean;
  pending: boolean;
  onSubmit: (
    request: RequirementRequest & { reason?: string },
    after: () => void,
  ) => void;
}) {
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [criticality, setCriticality] =
    useState<(typeof CRITICALITIES)[number]>("major");
  const [target, setTarget] = useState("");
  const [minimum, setMinimum] = useState("");
  const [maximum, setMaximum] = useState("");
  const [unit, setUnit] = useState("");
  const [reason, setReason] = useState("");

  const ready =
    code.trim().length >= 3 &&
    name.trim() !== "" &&
    (!requireReason || reason.trim().length >= 3);

  return (
    <div className="mt-3 grid max-w-3xl gap-2 rounded border border-slate-200 p-3">
      <p className="text-xs font-medium text-slate-700">{heading}</p>
      <div className="flex flex-wrap items-end gap-2">
        <div className="w-40">
          <label className={LABEL} htmlFor={`req-code-${heading}`}>
            Requirement code
          </label>
          <input
            id={`req-code-${heading}`}
            className={INPUT}
            maxLength={50}
            value={code}
            onChange={(e) => setCode(e.target.value)}
            placeholder="REQ-ADH-001"
          />
        </div>
        <div className="min-w-[14rem] flex-1">
          <label className={LABEL} htmlFor={`req-name-${heading}`}>
            What is required
          </label>
          <input
            id={`req-name-${heading}`}
            className={INPUT}
            maxLength={200}
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </div>
        <div className="w-40">
          <label className={LABEL} htmlFor={`req-crit-${heading}`}>
            Criticality
          </label>
          <select
            id={`req-crit-${heading}`}
            className={INPUT}
            value={criticality}
            onChange={(e) =>
              setCriticality(e.target.value as (typeof CRITICALITIES)[number])
            }
          >
            {CRITICALITIES.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="flex flex-wrap items-end gap-2">
        {/* Text inputs, not `type="number"` — see the header. A browser that
            normalises "6.00" to "6" has changed a specification. */}
        <div className="w-28">
          <label className={LABEL} htmlFor={`req-target-${heading}`}>
            Target
          </label>
          <input
            id={`req-target-${heading}`}
            className={INPUT + " tabular-nums"}
            inputMode="decimal"
            value={target}
            onChange={(e) => setTarget(e.target.value)}
          />
        </div>
        <div className="w-28">
          <label className={LABEL} htmlFor={`req-min-${heading}`}>
            Minimum
          </label>
          <input
            id={`req-min-${heading}`}
            className={INPUT + " tabular-nums"}
            inputMode="decimal"
            value={minimum}
            onChange={(e) => setMinimum(e.target.value)}
          />
        </div>
        <div className="w-28">
          <label className={LABEL} htmlFor={`req-max-${heading}`}>
            Maximum
          </label>
          <input
            id={`req-max-${heading}`}
            className={INPUT + " tabular-nums"}
            inputMode="decimal"
            value={maximum}
            onChange={(e) => setMaximum(e.target.value)}
          />
        </div>
        <div className="w-32">
          <label className={LABEL} htmlFor={`req-unit-${heading}`}>
            Unit
          </label>
          <input
            id={`req-unit-${heading}`}
            className={INPUT}
            value={unit}
            onChange={(e) => setUnit(e.target.value)}
            placeholder="MPa"
          />
        </div>
      </div>

      {requireReason && (
        <div>
          <label className={LABEL} htmlFor={`req-reason-${heading}`}>
            Why it is being revised
          </label>
          <input
            id={`req-reason-${heading}`}
            className={INPUT}
            maxLength={500}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
        </div>
      )}

      <div>
        <button
          type="button"
          className={BUTTON}
          disabled={pending || !ready}
          onClick={() =>
            onSubmit(
              {
                requirement_code: code.trim(),
                name: name.trim(),
                criticality,
                // Omitted when blank, never sent as "". A Decimal field given
                // an empty string is a 422; given nothing, it is absent.
                ...(target.trim() === "" ? {} : { target_value: target.trim() }),
                ...(minimum.trim() === "" ? {} : { minimum_value: minimum.trim() }),
                ...(maximum.trim() === "" ? {} : { maximum_value: maximum.trim() }),
                ...(unit.trim() === "" ? {} : { canonical_unit: unit.trim() }),
                ...(requireReason ? { reason: reason.trim() } : {}),
              },
              () => {
                setCode("");
                setName("");
                setTarget("");
                setMinimum("");
                setMaximum("");
                setUnit("");
                setReason("");
              },
            )
          }
        >
          {submitLabel}
        </button>
      </div>
    </div>
  );
}

function RequirementsSection({
  projectId,
  mayCreate,
  mayApprove,
  pending,
  onCreate,
  onApprove,
  onRevise,
}: {
  projectId: string;
  mayCreate: boolean;
  mayApprove: boolean;
  pending: boolean;
  onCreate: (request: RequirementRequest, after: () => void) => void;
  onApprove: (requirementId: string, after: () => void) => void;
  onRevise: (
    requirementId: string,
    request: RequirementRequest & { reason: string },
    after: () => void,
  ) => void;
}) {
  const { data, error } = useRequirementMatrix(projectId);
  const [revising, setRevising] = useState<string | null>(null);

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
                    {/* 🔴 APPROVE ONLY WHAT IS NOT APPROVED. `approve_requirement`
                        raises `RequirementImmutableError` on an approved one and
                        the route answers 409, so offering it again would be a
                        button that cannot work. */}
                    {mayApprove && r.requirement_status !== "approved" && (
                      <button
                        type="button"
                        className="text-xs text-slate-700 underline underline-offset-2"
                        disabled={pending}
                        onClick={() => onApprove(r.requirement_id, () => undefined)}
                      >
                        Approve
                      </button>
                    )}
                    {mayCreate && revising !== r.requirement_id && (
                      <button
                        type="button"
                        className="text-xs text-slate-700 underline underline-offset-2"
                        onClick={() => setRevising(r.requirement_id)}
                      >
                        Revise
                      </button>
                    )}
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
                    {/* WHEN THE REQUIREMENT WAS DEFINED — the owner named this
                        one explicitly. Note that a REVISION creates a new row
                        (§8's clone-never-edit discipline applied to
                        requirements), so this is the date THIS revision was
                        written, not the date the requirement first existed. */}
                    <div className="flex gap-1.5">
                      <dt className="font-medium text-slate-500">Defined</dt>
                      <dd title={formatInstant(r.created_at)}>{formatDay(r.created_at)}</dd>
                    </div>
                  </dl>

                  {mayCreate && revising === r.requirement_id && (
                    <RequirementForm
                      heading={`Revise ${r.requirement_code} — this creates revision ${r.revision + 1}`}
                      submitLabel="Revise"
                      requireReason
                      pending={pending}
                      onSubmit={(request, after) =>
                        onRevise(
                          r.requirement_id,
                          request as RequirementRequest & { reason: string },
                          () => {
                            after();
                            setRevising(null);
                          },
                        )
                      }
                    />
                  )}
                </li>
              ))}
            </ul>
          )}

          {mayCreate && (
            <RequirementForm
              heading="Add a requirement"
              submitLabel="Add"
              requireReason={false}
              pending={pending}
              onSubmit={(request, after) => onCreate(request, after)}
            />
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

/**
 * One milestone, holding its OWN draft.
 *
 * 🔴 THE SECTION USED TO HOLD ONE `status`/`reason` PAIR FOR EVERY ROW.
 *
 * Raised by Codex. Opening a second row only moved `openFor`; it did not clear
 * or re-initialise the fields — so a reason typed for milestone A appeared in
 * milestone B's box and could be submitted against it. On a screen whose whole
 * purpose is that a reason is recorded and reconstructable later, attaching the
 * wrong one to the wrong record is worse than having no control.
 *
 * State lives on the ROW. There is no shared draft to leak, and `status`
 * initialises from the milestone's own current value rather than from a
 * constant, so "change status" opens on what it actually is.
 */
function MilestoneRow({
  milestone,
  mayManage,
  pending,
  onSetStatus,
}: {
  milestone: Milestone;
  mayManage: boolean;
  pending: boolean;
  onSetStatus: (
    milestoneId: string,
    request: { status: string; reason: string },
    after: () => void,
  ) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [status, setStatus] = useState(milestone.status);
  const [reason, setReason] = useState("");

  return (
    <li className="rounded border border-slate-200 bg-white p-3">
      <div className="flex flex-wrap items-baseline gap-2">
        <span className="flex-1 text-sm font-medium text-slate-900">{milestone.name}</span>
        <span className={TAG}>{words(milestone.status)}</span>
        {/* Computed by the server. A browser deriving "overdue" from a date
            string would be a second definition of it, in a timezone of its
            own choosing. */}
        {milestone.is_overdue && <span className={TAG}>overdue</span>}
        <span className="text-xs tabular-nums text-slate-600">
          planned {milestone.planned_date}
        </span>
        {milestone.actual_date !== null && (
          <span className="text-xs tabular-nums text-slate-600">
            actual {milestone.actual_date}
          </span>
        )}
        {mayManage && !editing && (
          <button
            type="button"
            className="text-xs text-slate-700 underline underline-offset-2"
            onClick={() => setEditing(true)}
          >
            Change status
          </button>
        )}
      </div>

      {mayManage && editing && (
        <div className="mt-2 flex flex-wrap items-end gap-2">
          <div className="w-40">
            <label className={LABEL} htmlFor={`ms-status-${milestone.id}`}>
              Status
            </label>
            <select
              id={`ms-status-${milestone.id}`}
              className={INPUT}
              value={status}
              onChange={(e) => setStatus(e.target.value)}
            >
              {MILESTONE_STATUSES.map((value) => (
                <option key={value} value={value}>
                  {words(value)}
                </option>
              ))}
            </select>
          </div>
          <div className="min-w-[14rem] flex-1">
            <label className={LABEL} htmlFor={`ms-reason-${milestone.id}`}>
              Why
            </label>
            <input
              id={`ms-reason-${milestone.id}`}
              className={INPUT}
              maxLength={500}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          </div>
          <button
            type="button"
            className={BUTTON_QUIET}
            disabled={pending || reason.trim().length < 3}
            onClick={() =>
              onSetStatus(milestone.id, { status, reason: reason.trim() }, () => {
                setReason("");
                setEditing(false);
              })
            }
          >
            Record
          </button>
          <button
            type="button"
            className={BUTTON_QUIET}
            onClick={() => {
              setStatus(milestone.status);
              setReason("");
              setEditing(false);
            }}
          >
            Cancel
          </button>
        </div>
      )}
    </li>
  );
}

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
            <MilestoneRow
              key={m.id}
              milestone={m}
              mayManage={mayManage}
              pending={pending}
              onSetStatus={onSetStatus}
            />
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
              maxLength={200}
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

/**
 * One risk, holding its OWN draft.
 *
 * 🔴 TWO DEFECTS AT ONCE, BOTH RAISED BY CODEX.
 *
 * The section held one `status`/`mitigation`/`reason` set for every row, so a
 * mitigation typed against risk A could be submitted against risk B — and the
 * status opened on the constant `"mitigating"` rather than on the row's own
 * value, so a reader who only wanted to add a mitigation silently also changed
 * the status.
 *
 * 🔴 AND THAT DEFAULT MADE A GUARANTEED 422 THE EASIEST THING TO PRESS.
 * `risks_mitigating_states_the_mitigation` (migration 012) refuses
 * `status = 'mitigating'` with a blank mitigation. A risk whose stored
 * mitigation is null, opened with the status defaulted to `mitigating` and the
 * mitigation box empty, produced a request the DATABASE must reject — from a
 * form that looked complete once a reason was typed.
 *
 * Both are the same root cause: the draft did not come from the record. It does
 * now, and the button knows the constraint.
 */
function RiskRow({
  risk,
  mayManage,
  pending,
  onChange,
}: {
  risk: Risk;
  mayManage: boolean;
  pending: boolean;
  onChange: (
    riskId: string,
    request: { reason: string; status?: string; mitigation?: string },
    after: () => void,
  ) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [status, setStatus] = useState(risk.status);
  const [mitigation, setMitigation] = useState(risk.mitigation ?? "");
  const [reason, setReason] = useState("");

  // 🔴 THE DATABASE'S RULE, MIRRORED SO THE BUTTON CAN BE HONEST.
  // `risks_mitigating_states_the_mitigation`: a risk that is being mitigated
  // must say how. The server enforces it either way; this stops the form
  // offering a submission that cannot succeed.
  const mitigatingNeedsText = status === "mitigating" && mitigation.trim() === "";

  return (
    <li className="rounded border border-slate-200 bg-white p-3">
      <div className="flex flex-wrap items-baseline gap-2">
        <span className="text-xs tabular-nums text-slate-500">{risk.risk_code}</span>
        <span className="flex-1 text-sm font-medium text-slate-900">{risk.title}</span>
        <span className={TAG}>{words(risk.category)}</span>
        {/* Probability and impact in words, both of them, always. A single
            "risk score" would be a judgement this endpoint has not made, and
            §11 forbids colour-only status — which a heat-map cell is. */}
        <span className={TAG}>probability {risk.probability}</span>
        <span className={TAG}>impact {risk.impact}</span>
        <span className={TAG}>{words(risk.status)}</span>
        {mayManage && !editing && (
          <button
            type="button"
            className="text-xs text-slate-700 underline underline-offset-2"
            onClick={() => setEditing(true)}
          >
            Update
          </button>
        )}
      </div>
      {risk.mitigation !== null && (
        <p className="mt-1 text-xs text-slate-700">
          <span className="font-medium">Mitigation: </span>
          {risk.mitigation}
        </p>
      )}

      {mayManage && editing && (
        <div className="mt-2 flex flex-wrap items-end gap-2">
          <div className="w-40">
            <label className={LABEL} htmlFor={`risk-status-${risk.id}`}>
              Status
            </label>
            <select
              id={`risk-status-${risk.id}`}
              className={INPUT}
              value={status}
              onChange={(e) => setStatus(e.target.value)}
            >
              {RISK_STATUSES.map((value) => (
                <option key={value} value={value}>
                  {words(value)}
                </option>
              ))}
            </select>
          </div>
          <div className="min-w-[14rem] flex-1">
            <label className={LABEL} htmlFor={`risk-mitigation-${risk.id}`}>
              Mitigation
            </label>
            <input
              id={`risk-mitigation-${risk.id}`}
              className={INPUT}
              value={mitigation}
              onChange={(e) => setMitigation(e.target.value)}
            />
          </div>
          <div className="min-w-[12rem] flex-1">
            <label className={LABEL} htmlFor={`risk-reason-${risk.id}`}>
              Why
            </label>
            <input
              id={`risk-reason-${risk.id}`}
              className={INPUT}
              maxLength={500}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          </div>
          <button
            type="button"
            className={BUTTON_QUIET}
            disabled={pending || reason.trim().length < 3 || mitigatingNeedsText}
            onClick={() =>
              onChange(
                risk.id,
                {
                  reason: reason.trim(),
                  status,
                  // 🔴 OMITTED WHEN BLANK, NEVER SENT AS "". `RiskUpdate` treats
                  // absence as "leave unchanged", and its own docstring says
                  // why: a PATCH that blanked the mitigation because the client
                  // did not resend it is how a risk stops being tracked without
                  // anyone deciding that.
                  ...(mitigation.trim() === "" ? {} : { mitigation: mitigation.trim() }),
                },
                () => {
                  setReason("");
                  setEditing(false);
                },
              )
            }
          >
            Record
          </button>
          <button
            type="button"
            className={BUTTON_QUIET}
            onClick={() => {
              setStatus(risk.status);
              setMitigation(risk.mitigation ?? "");
              setReason("");
              setEditing(false);
            }}
          >
            Cancel
          </button>
          {mitigatingNeedsText && (
            <p className="w-full text-xs text-slate-600">
              A risk being <strong>mitigated</strong> has to say how — the
              database refuses a blank mitigation on that status.
            </p>
          )}
        </div>
      )}
    </li>
  );
}

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
            <RiskRow
              key={r.id}
              risk={r}
              mayManage={mayManage}
              pending={pending}
              onChange={onChange}
            />
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
                maxLength={50}
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
                maxLength={200}
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

/**
 * A UUID, as PostgreSQL and Pydantic accept one.
 *
 * 🔴 THE MEMBER FORM ENABLED ITS BUTTON FOR ANY NON-EMPTY TEXT. Raised by
 * Codex: `MemberAdd.user_id` is a `uuid.UUID`, so anything else is a 422 the
 * browser could have seen coming. This is not validation for its own sake —
 * the field asks for an id a person has to paste from somewhere, which is
 * exactly the input most likely to arrive with a stray space or half a value.
 */
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/**
 * One member, holding its own removal reason.
 *
 * 🔴 THE SECTION HELD ONE `reason` FOR EVERY ROW. Raised by Codex, and the
 * same defect as the milestone and risk lists: a reason typed against one
 * colleague could be submitted against another. On the record that answers
 * *"who was taken off this project, and why"* after an incident, attaching the
 * wrong reason to the wrong person is the worst version of it.
 */
function MemberRow({
  member,
  mayAssign,
  pending,
  onRemove,
}: {
  member: ProjectMember;
  mayAssign: boolean;
  pending: boolean;
  onRemove: (userId: string, reason: string, after: () => void) => void;
}) {
  const [removing, setRemoving] = useState(false);
  const [reason, setReason] = useState("");

  // 🔴 NOT THE PROJECT LEAD. `remove_member` refuses the lead outright and the
  // route answers 409, so offering the control was offering a button that
  // cannot work. `is_project_lead` is NULLABLE — null means "not the lead" —
  // so this tests for `true` rather than for truthiness.
  const removable = mayAssign && member.status === "active" && member.is_project_lead !== true;

  return (
    <li className="flex flex-wrap items-baseline gap-2 text-sm">
      <span className="font-medium text-slate-900">{member.display_name}</span>
      <span className="text-xs text-slate-600">{member.email}</span>
      <span className={TAG}>{words(member.project_role)}</span>
      {member.is_project_lead === true && <span className={TAG}>project lead</span>}
      {member.status !== "active" && <span className={TAG}>{words(member.status)}</span>}

      {removable && !removing && (
        <button
          type="button"
          className="text-xs text-slate-700 underline underline-offset-2"
          onClick={() => setRemoving(true)}
        >
          Remove
        </button>
      )}
      {removable && removing && (
        <span className="flex flex-wrap items-end gap-2">
          <input
            aria-label={`Reason for removing ${member.display_name}`}
            className={INPUT + " w-64"}
            maxLength={500}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="why they are coming off the project"
          />
          <button
            type="button"
            className={BUTTON_QUIET}
            disabled={pending || reason.trim().length < 3}
            onClick={() =>
              onRemove(member.user_id, reason.trim(), () => {
                setReason("");
                setRemoving(false);
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
              setRemoving(false);
            }}
          >
            Cancel
          </button>
        </span>
      )}
    </li>
  );
}

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

  const members: ProjectMember[] = data ?? [];
  const idLooksRight = UUID.test(userId.trim());

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
            <MemberRow
              key={m.id}
              member={m}
              mayAssign={mayAssign}
              pending={pending}
              onRemove={onRemove}
            />
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
                No endpoint lists the organization's people for a Lead to pick
                from: `GET /api/admin/members` needs `admin.users`, which the
                Lead does not hold, and the project's own member list only shows
                who is already on it. Asking for a UUID is honest about that;
                inventing a directory read the API does not offer would not be.
                Filed rather than papered over. */}
            <input
              id="member-user"
              className={INPUT}
              value={userId}
              onChange={(e) => setUserId(e.target.value)}
              placeholder="00000000-0000-0000-0000-000000000000"
              aria-describedby="member-user-hint"
            />
            {userId.trim() !== "" && !idLooksRight && (
              <p id="member-user-hint" className="mt-1 text-xs text-slate-600">
                That is not a user id. It should look like the placeholder —
                thirty-two hexadecimal characters in five dash-separated groups.
              </p>
            )}
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
            disabled={pending || !idLooksRight}
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
  // `requirement.create` covers BOTH creating and revising — `post_requirement`
  // and `post_requirement_revision` declare the same permission, because a
  // revision is a new statement of the requirement rather than an edit of it.
  const mayCreateRequirement = permits(permissions, "requirement.create");
  const mayApproveRequirement = permits(permissions, "requirement.approve");

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
      <RequirementsSection
        projectId={project.id}
        mayCreate={mayCreateRequirement}
        mayApprove={mayApproveRequirement}
        pending={actions.isPending}
        onCreate={actions.addRequirement}
        onApprove={actions.approve}
        onRevise={actions.revise}
      />
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
      {!mayAdvance &&
        !mayManageMilestones &&
        !mayCreateRisk &&
        !mayManageRisk &&
        !mayAssign &&
        !mayCreateRequirement &&
        !mayApproveRequirement && (
        <p className="text-sm text-slate-600">
          You are a member of this project and hold none of{" "}
          <code className="text-xs">project.advance_stage</code>,{" "}
          <code className="text-xs">milestone.manage</code>,{" "}
          <code className="text-xs">risk.create</code>,{" "}
          <code className="text-xs">risk.manage</code>,{" "}
          <code className="text-xs">project.assign_member</code>,{" "}
          <code className="text-xs">requirement.create</code> or{" "}
          <code className="text-xs">requirement.approve</code>, so it is read-only
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
