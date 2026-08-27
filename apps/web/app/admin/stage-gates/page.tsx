"use client";

/**
 * Stage gates — the configuration the pipeline reads and nobody could write.
 *
 * 🔴 "PIPELINE STAGES ARE CONFIGURATION ROWS" WAS TRUE AND UNREACHABLE.
 *
 * `IMPLEMENTATION_PLAN.md` §H schedules this section for Slice 2, *"because
 * stages are config rows from Slice 2"*, under the rule that **a configuration
 * value referenced anywhere in the plan must have an Administration screen in
 * the same slice or earlier**. Slice 2 shipped the eight seeded stages and the
 * four endpoints that maintain them; the screen was never built. Measured
 * 2026-08-27: zero client functions.
 *
 * The project workspace makes it concrete — its "Advance to" list is built from
 * these rows, so until now the set of stages a project could ever reach was
 * fixed at seed time with no way to change it through the product.
 *
 * 🔴 `projects_visited` IS ON EVERY ROW BECAUSE RETIRING IS NOT A CLICK.
 * A stage no project has entered can be turned off freely. One with history
 * behind it is a configuration change that alters what those projects' stage
 * records point at — so the number is put in front of whoever is deciding,
 * rather than left in an endpoint they would have to go and ask for.
 *
 * ⚠️ REORDERING SENDS THE WHOLE ORDER, NOT A MOVE. `ordered_stage_ids` is every
 * stage in its new sequence, so the server sets what it was given rather than
 * inferring from a delta — and two administrators reordering at once cannot
 * interleave into a sequence neither of them chose.
 */

import Link from "next/link";
import { useState } from "react";

import { LiveOnlyPage } from "@/components/ui/data-source-banner";
import { ContextSubmenu } from "@/components/ui/context-submenu";
import { EntityHeader } from "@/components/ui/entity-header";
import { serverMessage } from "@/lib/api/client";
import { useAdminActions, useStageDefinitions } from "@/lib/api/hooks";
import type { StageDefinition, StageWriteRequest } from "@/lib/api/admin";
import { permits, usePermissions } from "@/lib/permissions";

import { ADMIN_SECTIONS } from "../sections";

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

/** `^[A-Z0-9_]+$`, exactly as `StageDefinitionWrite` declares it. */
const STAGE_CODE = /^[A-Z0-9_]+$/;

function StageForm({
  initial,
  submitLabel,
  pending,
  onSubmit,
  onCancel,
}: {
  initial?: StageDefinition;
  submitLabel: string;
  pending: boolean;
  onSubmit: (request: StageWriteRequest, after: () => void) => void;
  onCancel?: () => void;
}) {
  const [code, setCode] = useState(initial?.stage_code ?? "");
  const [name, setName] = useState(initial?.name ?? "");
  const [sequence, setSequence] = useState(String(initial?.sequence ?? ""));
  const [entry, setEntry] = useState(initial?.entry_criteria ?? "");
  const [deliverables, setDeliverables] = useState(initial?.required_deliverables ?? "");
  const [exit, setExit] = useState(initial?.exit_criteria ?? "");
  const [responsible, setResponsible] = useState(initial?.responsible_role ?? "");
  const [requiresApproval, setRequiresApproval] = useState(initial?.requires_approval ?? false);
  const [approvalRole, setApprovalRole] = useState(initial?.approval_role ?? "");

  const sequenceNumber = Number(sequence);
  const sequenceValid =
    sequence.trim() !== "" &&
    Number.isInteger(sequenceNumber) &&
    sequenceNumber >= 1 &&
    sequenceNumber <= 999;
  const codeValid = STAGE_CODE.test(code);
  // 🔴 THE SERVER'S OWN VALIDATOR, MIRRORED. Raised by Codex.
  // `_approval_needs_an_approver` refuses `requires_approval` with no
  // `approval_role` — *"a gate that requires approval from nobody never opens"*
  // — and it mirrors a CHECK constraint, so it is refused twice. The form
  // enabled submission anyway and the omission produced a guaranteed 422.
  const approverMissing = requiresApproval && approvalRole.trim() === "";

  return (
    <div className="mt-3 grid max-w-3xl gap-2 rounded border border-slate-200 p-3">
      <div className="flex flex-wrap items-end gap-2">
        <div className="w-56">
          <label className={LABEL} htmlFor={`stage-code-${submitLabel}`}>
            Stage code
          </label>
          <input
            id={`stage-code-${submitLabel}`}
            className={INPUT}
            maxLength={50}
            value={code}
            onChange={(e) => setCode(e.target.value.toUpperCase())}
            placeholder="FEASIBILITY"
          />
          {code !== "" && !codeValid && (
            // The server's own pattern, mirrored so the refusal is not a round
            // trip. Upper case, digits and underscores — a code is an
            // identifier, not a label.
            <p className="mt-1 text-xs text-slate-600">
              Capital letters, digits and underscores only.
            </p>
          )}
        </div>
        <div className="min-w-[14rem] flex-1">
          <label className={LABEL} htmlFor={`stage-name-${submitLabel}`}>
            Name
          </label>
          <input
            id={`stage-name-${submitLabel}`}
            className={INPUT}
            maxLength={100}
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </div>
        <div className="w-28">
          <label className={LABEL} htmlFor={`stage-seq-${submitLabel}`}>
            Sequence
          </label>
          <input
            id={`stage-seq-${submitLabel}`}
            className={INPUT + " tabular-nums"}
            inputMode="numeric"
            value={sequence}
            onChange={(e) => setSequence(e.target.value)}
          />
        </div>
      </div>

      <div className="grid gap-2 sm:grid-cols-3">
        <div>
          <label className={LABEL} htmlFor={`stage-entry-${submitLabel}`}>
            Entry criteria
          </label>
          <input
            id={`stage-entry-${submitLabel}`}
            className={INPUT}
            value={entry}
            onChange={(e) => setEntry(e.target.value)}
          />
        </div>
        <div>
          <label className={LABEL} htmlFor={`stage-deliv-${submitLabel}`}>
            Required deliverables
          </label>
          <input
            id={`stage-deliv-${submitLabel}`}
            className={INPUT}
            value={deliverables}
            onChange={(e) => setDeliverables(e.target.value)}
          />
        </div>
        <div>
          <label className={LABEL} htmlFor={`stage-exit-${submitLabel}`}>
            Exit criteria
          </label>
          <input
            id={`stage-exit-${submitLabel}`}
            className={INPUT}
            value={exit}
            onChange={(e) => setExit(e.target.value)}
          />
        </div>
      </div>

      <div className="flex flex-wrap items-end gap-2">
        <div className="w-56">
          <label className={LABEL} htmlFor={`stage-resp-${submitLabel}`}>
            Responsible role
          </label>
          <input
            id={`stage-resp-${submitLabel}`}
            className={INPUT}
            value={responsible}
            onChange={(e) => setResponsible(e.target.value)}
            placeholder="product_development_lead"
          />
        </div>
        <label className="flex items-center gap-2 pb-1.5 text-sm text-slate-800">
          <input
            type="checkbox"
            checked={requiresApproval}
            onChange={(e) => setRequiresApproval(e.target.checked)}
          />
          Requires approval to leave
        </label>
        {requiresApproval && (
          <div className="w-56">
            <label className={LABEL} htmlFor={`stage-approver-${submitLabel}`}>
              Approving role
            </label>
            <input
              id={`stage-approver-${submitLabel}`}
              className={INPUT}
              value={approvalRole}
              onChange={(e) => setApprovalRole(e.target.value)}
            />
          </div>
        )}
      </div>

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          className={BUTTON}
          disabled={pending || !codeValid || name.trim() === "" || !sequenceValid || approverMissing}
          onClick={() =>
            onSubmit(
              {
                stage_code: code.trim(),
                name: name.trim(),
                sequence: sequenceNumber,
                requires_approval: requiresApproval,
                // Omitted when blank rather than sent as "": these are
                // `str | None` on the server, and an empty string is a value
                // that says "the criteria are the empty string" rather than
                // "there are none".
                ...(entry.trim() === "" ? {} : { entry_criteria: entry.trim() }),
                ...(deliverables.trim() === ""
                  ? {}
                  : { required_deliverables: deliverables.trim() }),
                ...(exit.trim() === "" ? {} : { exit_criteria: exit.trim() }),
                ...(responsible.trim() === "" ? {} : { responsible_role: responsible.trim() }),
                ...(requiresApproval && approvalRole.trim() !== ""
                  ? { approval_role: approvalRole.trim() }
                  : {}),
              },
              () => {
                if (initial === undefined) {
                  setCode("");
                  setName("");
                  setSequence("");
                  setEntry("");
                  setDeliverables("");
                  setExit("");
                  setResponsible("");
                  setRequiresApproval(false);
                  setApprovalRole("");
                }
              },
            )
          }
        >
          {submitLabel}
        </button>
        {onCancel !== undefined && (
          <button type="button" className={BUTTON_QUIET} onClick={onCancel}>
            Cancel
          </button>
        )}
        {approverMissing && (
          <p className="w-full text-xs text-slate-600">
            A stage that requires approval has to name the role that gives it — a
            gate requiring approval from nobody never opens.
          </p>
        )}
      </div>
    </div>
  );
}

function StageRow({
  stage,
  pending,
  canMoveUp,
  canMoveDown,
  onEdit,
  onSetActive,
  onMove,
}: {
  stage: StageDefinition;
  pending: boolean;
  canMoveUp: boolean;
  canMoveDown: boolean;
  onEdit: (stageId: string, request: StageWriteRequest, after: () => void) => void;
  onSetActive: (stageId: string, isActive: boolean, reason: string, after: () => void) => void;
  onMove: (stageId: string, direction: -1 | 1) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [retiring, setRetiring] = useState(false);
  const [reason, setReason] = useState("");

  return (
    <li className="rounded border border-slate-200 bg-white p-3">
      <div className="flex flex-wrap items-baseline gap-2">
        <span className="text-xs tabular-nums text-slate-500">{stage.sequence}</span>
        <span className="text-sm font-medium text-slate-900">{stage.name}</span>
        <span className="text-xs text-slate-600">{stage.stage_code}</span>
        {stage.requires_approval && <span className={TAG}>needs approval</span>}
        {!stage.is_active && <span className={TAG}>retired</span>}
        {/* 🔴 THE NUMBER THAT MAKES RETIRING A DECISION. */}
        <span className={TAG}>
          {stage.projects_visited} project{stage.projects_visited === 1 ? "" : "s"} visited
        </span>
        {!editing && (
          <button
            type="button"
            className="text-xs text-slate-700 underline underline-offset-2"
            onClick={() => setEditing(true)}
          >
            Edit
          </button>
        )}
        {!retiring && (
          <button
            type="button"
            className="text-xs text-slate-700 underline underline-offset-2"
            onClick={() => setRetiring(true)}
          >
            {stage.is_active ? "Retire" : "Restore"}
          </button>
        )}
        {/* 🔴 MOVE, NOT DRAG. `POST /stage-gates/reorder` takes
            `ordered_stage_ids` — the WHOLE order — and the page computes that
            list from what it is already showing, so there is no way to submit a
            partial one. A drag-and-drop surface would be nicer and would put
            the burden of producing a complete, correct order on a mouse
            gesture; two buttons cannot get it wrong. */}
        <button
          type="button"
          className="text-xs text-slate-700 underline underline-offset-2 disabled:cursor-not-allowed disabled:text-slate-400 disabled:no-underline"
          disabled={pending || !canMoveUp}
          aria-label={`Move ${stage.name} earlier`}
          onClick={() => onMove(stage.id, -1)}
        >
          ↑ earlier
        </button>
        <button
          type="button"
          className="text-xs text-slate-700 underline underline-offset-2 disabled:cursor-not-allowed disabled:text-slate-400 disabled:no-underline"
          disabled={pending || !canMoveDown}
          aria-label={`Move ${stage.name} later`}
          onClick={() => onMove(stage.id, 1)}
        >
          ↓ later
        </button>
      </div>

      {stage.entry_criteria !== null && (
        <p className="mt-1 text-xs text-slate-600">Entry: {stage.entry_criteria}</p>
      )}

      {editing && (
        <StageForm
          initial={stage}
          submitLabel="Save"
          pending={pending}
          onSubmit={(request) => onEdit(stage.id, request, () => setEditing(false))}
          onCancel={() => setEditing(false)}
        />
      )}

      {retiring && (
        <div className="mt-2 flex flex-wrap items-end gap-2">
          <div className="min-w-[16rem] flex-1">
            <label className={LABEL} htmlFor={`stage-reason-${stage.id}`}>
              Why
            </label>
            <input
              id={`stage-reason-${stage.id}`}
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
              onSetActive(stage.id, !stage.is_active, reason.trim(), () => {
                setReason("");
                setRetiring(false);
              })
            }
          >
            {stage.is_active ? "Retire" : "Restore"}
          </button>
          <button
            type="button"
            className={BUTTON_QUIET}
            onClick={() => {
              setReason("");
              setRetiring(false);
            }}
          >
            Cancel
          </button>
          {stage.is_active && stage.projects_visited > 0 && (
            <p className="w-full text-xs text-amber-900">
              {stage.projects_visited} project
              {stage.projects_visited === 1 ? " has" : "s have"} been in this
              stage. Retiring it does not remove that history; it stops new
              projects entering.
            </p>
          )}
        </div>
      )}
    </li>
  );
}

export default function StageGatesPage() {
  const permissions = usePermissions();
  const mayManage = permits(permissions, "admin.stage_gates");
  const { data, error, isLoading, unavailable } = useStageDefinitions();
  const actions = useAdminActions();
  const [adding, setAdding] = useState(false);

  const stages: StageDefinition[] = data ?? [];

  /**
   * Move one stage one place, and send the WHOLE resulting order.
   *
   * 🔴 THE SERVER TAKES `ordered_stage_ids`, NOT A MOVE — deliberately, so it
   * sets the order it was given rather than inferring one from a delta. This
   * builds that complete list from the rows already on screen, so a partial or
   * interleaved order is not expressible.
   *
   * ⚠️ IT SENDS THE ORDER THIS PAGE IS SHOWING. If somebody else reordered
   * since the last read, this submits what THIS reader saw — which is the
   * honest behaviour for a whole-order endpoint, and the reason the server
   * takes the whole order rather than a move.
   */
  const move = (stageId: string, direction: -1 | 1) => {
    const index = stages.findIndex((s) => s.id === stageId);
    const target = index + direction;
    if (index < 0 || target < 0 || target >= stages.length) {
      return;
    }
    const ordered = stages.map((s) => s.id);
    const [moved] = ordered.splice(index, 1);
    if (moved === undefined) {
      return;
    }
    ordered.splice(target, 0, moved);
    actions.reorder(ordered);
  };

  return (
    <div>
      <EntityHeader
        eyebrow="Governance"
        title="Stage gates"
        crumbs={[
          { label: "Dashboard", href: "/dashboard" },
          { label: "Administration", href: "/admin" },
        ]}
        fields={[{ label: "Stages", value: String(stages.length) }]}
      />
      <ContextSubmenu items={ADMIN_SECTIONS} activeHref="/admin/stage-gates" />

      <div className="p-6">
        <LiveOnlyPage
          title="Pipeline stages"
          lede="The stages a project can be in, in order. The project workspace's
                'Advance to' list is built from these rows, so this is where the
                shape of the pipeline is decided."
          // 🔴 THE HOOK'S ANSWER, NOT A HARD-CODED `null`. Raised by Codex: a
          // build with no API compiled in returns `unavailable`, and claiming
          // the source was live turned that into a permission message — which
          // sends a reader to an administrator for a problem no grant can fix.
          unavailable={unavailable}
          notInvented="stage definitions"
        >
          {unavailable !== null ? (
            <p className="text-sm text-slate-600">
              Stage gates cannot be shown until this build is pointed at an API.
            </p>
          ) : !mayManage ? (
            <p className="text-sm text-slate-600">
              Configuring stage gates needs{" "}
              <code className="text-xs">admin.stage_gates</code>, which this account
              does not hold.
            </p>
          ) : error !== null ? (
            <p role="alert" className="text-sm text-red-700">
              The stage definitions could not be loaded: {serverMessage(error)}
            </p>
          ) : (
            <>
              {/* 🔴 "LOADING" AND "NONE" ARE DIFFERENT ANSWERS. Raised by
                  Codex: collapsing `data === undefined` to an empty list made
                  a first load render "No stages defined" and enable the create
                  form before any existing code or sequence was known — an
                  invitation to collide with a stage already there. */}
              {isLoading ? (
                <p className="text-sm text-slate-600">Loading stage definitions…</p>
              ) : stages.length === 0 ? (
                <p className="text-sm text-slate-600">No stages defined.</p>
              ) : (
                <ol className="space-y-2">
                  {stages.map((s, index) => (
                    <StageRow
                      key={s.id}
                      stage={s}
                      pending={actions.isPending}
                      canMoveUp={index > 0}
                      canMoveDown={index < stages.length - 1}
                      onEdit={actions.editStage}
                      onSetActive={actions.setStageActive}
                      onMove={move}
                    />
                  ))}
                </ol>
              )}

              {isLoading ? null : !adding ? (
                <button
                  type="button"
                  className={BUTTON_QUIET + " mt-4"}
                  onClick={() => setAdding(true)}
                >
                  Define a stage
                </button>
              ) : (
                <StageForm
                  submitLabel="Define"
                  pending={actions.isPending}
                  onSubmit={(request, after) =>
                    actions.addStage(request, () => {
                      after();
                      setAdding(false);
                    })
                  }
                  onCancel={() => setAdding(false)}
                />
              )}

              {actions.error !== null && (
                <p
                  role="alert"
                  className="mt-3 rounded border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-900"
                >
                  {serverMessage(actions.error)}
                </p>
              )}
              {actions.error === null && actions.lastAction !== null && (
                <p role="status" className="mt-3 text-sm text-slate-700">
                  Recorded: {actions.lastAction}.
                </p>
              )}

              <p className="mt-6 text-xs text-slate-600">
                <Link href="/admin" className="underline underline-offset-2">
                  Back to Administration
                </Link>
              </p>
            </>
          )}
        </LiveOnlyPage>
      </div>
    </div>
  );
}
