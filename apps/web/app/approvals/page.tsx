"use client";

/**
 * Approvals — the queue, and the ladder behind each item.
 *
 * 🔴 §9's ENGINE IS SHARED INFRASTRUCTURE AND HAD NO SCREEN.
 *
 * *"One shared approval engine. Never re-implement approval inside Formula,
 * Test, Validation, Pilot, Qualification or Release."* The engine exists, with
 * route snapshotting, parallel groups, seven decision types and
 * segregation-of-duties — and until this screen there was no way to see a
 * pending signature, let alone give one. `Approvals` sat inert in the sidebar
 * while `workflow.approval_route_steps` filled up.
 *
 * 🔴 THE QUEUE IS THE SERVER'S ANSWER TO "WHOSE TURN", AND IT IS NOT FILTERED
 * HERE.
 *
 * `pending_steps_for` returns steps this caller could decide **right now** —
 * open route, undecided step, a permission they hold, and no earlier mandatory
 * group still outstanding. Codex found that last clause reading `decision IS
 * NULL` alone, which treated a step *returned for correction* as satisfied and
 * exposed every later rung; it now tests for an ADVANCING decision. None of
 * that reasoning belongs in a browser, so this screen renders what it is given.
 *
 * ⚠️ SEVEN DECISION TYPES, NOT TWO. §9: Approve · Approve with Condition ·
 * Return for Correction · Request Retest · Reject · Escalate · Request
 * Additional Test. A screen offering approve/reject would quietly delete five
 * of them from the product, and `approve_with_condition` is the one that
 * yields YELLOW with a stated limitation that travels with the result.
 *
 * ⚠️ A 403 HERE MEANS TWO DIFFERENT THINGS AND THE SERVER SAYS WHICH: the
 * caller lacks the rung's permission, or holds it and is barred on THIS route
 * by their own earlier involvement (ADR-019). Only the first is knowable in the
 * browser — and the queue has already applied it — so the message is surfaced
 * verbatim rather than translated.
 */

import { useState } from "react";

import { DataSourceError, LiveOnlyPage } from "@/components/ui/data-source-banner";
import { serverMessage } from "@/lib/api/client";
import { useApprovalDecision, useApprovalQueue } from "@/lib/api/hooks";
import type { ApprovalQueueItem, StepDecisionRequest } from "@/lib/api/failures";

const INPUT =
  "mt-1 w-full rounded border border-slate-300 px-2 py-1.5 text-sm text-slate-900 " +
  "focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500";
const LABEL = "block text-xs font-medium text-slate-700";
const BUTTON =
  "rounded bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-700 " +
  "disabled:cursor-not-allowed disabled:bg-slate-300";

/**
 * §9's seven decisions, with the label a person reads.
 *
 * Exported so a test can assert there are seven of them. A control that
 * quietly offered two would not fail to compile, would not fail any rendering
 * test, and would remove five capabilities from a regulated approval chain.
 */
export const DECISIONS: ReadonlyArray<readonly [StepDecisionRequest["decision"], string]> = [
  ["approve", "Approve"],
  ["approve_with_condition", "Approve with condition"],
  ["return_for_correction", "Return for correction"],
  ["request_retest", "Request retest"],
  ["reject", "Reject"],
  ["escalate", "Escalate"],
  ["request_additional_test", "Request an additional test"],
];

function words(value: string): string {
  return value.replace(/_/g, " ");
}

function QueueRow({
  item,
  pending,
  onDecide,
}: {
  item: ApprovalQueueItem;
  pending: boolean;
  onDecide: (routeId: string, stepId: string, request: StepDecisionRequest) => void;
}) {
  const [decision, setDecision] = useState<StepDecisionRequest["decision"]>("approve");
  const [condition, setCondition] = useState("");
  const [rationale, setRationale] = useState("");

  // 🔴 A CONDITION IS MANDATORY FOR A CONDITIONAL APPROVAL, AND ONLY THEN.
  // §9: a conditional approval yields YELLOW and the stated limitation is
  // preserved — "valid for development comparison only", say. One with no
  // condition is a YELLOW that cannot explain itself, which §10 calls a defect
  // in as many words.
  const needsCondition = decision === "approve_with_condition";

  return (
    <li className="rounded border border-slate-200 bg-white p-4">
      <div className="flex flex-wrap items-baseline gap-2">
        <span className="text-xs font-medium tabular-nums text-slate-500">
          step {item.step_number}
        </span>
        <h2 className="flex-1 text-sm font-semibold text-slate-900">{item.step_label}</h2>
        <span className="rounded border border-slate-300 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-slate-600">
          {words(item.entity_type)}
        </span>
        <span className="rounded border border-slate-300 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-slate-600">
          {item.template_code}
        </span>
      </div>

      <dl className="mt-2 grid gap-x-6 gap-y-1 text-xs text-slate-600 sm:grid-cols-2">
        <div className="flex gap-1.5">
          <dt className="font-medium text-slate-500">Opened</dt>
          <dd className="tabular-nums">{item.opened_at.slice(0, 10)}</dd>
        </div>
        <div className="flex gap-1.5">
          <dt className="font-medium text-slate-500">Requires</dt>
          {/* The rung names its own permission. Shown because a reader refused
              on segregation-of-duties grounds needs to see that they DO hold
              the permission — otherwise the refusal reads as a mistake. */}
          <dd>{item.permission_required ?? "unspecified"}</dd>
        </div>
      </dl>

      <div className="mt-3 grid gap-2 sm:max-w-2xl">
        <div className="flex flex-wrap gap-2">
          <div className="min-w-[14rem] flex-1">
            <label className={LABEL} htmlFor={`decision-${item.step_id}`}>
              Decision — seven types, not two
            </label>
            <select
              id={`decision-${item.step_id}`}
              className={INPUT}
              value={decision}
              onChange={(e) => setDecision(e.target.value as StepDecisionRequest["decision"])}
            >
              {DECISIONS.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </div>
        </div>

        {needsCondition && (
          <div>
            <label className={LABEL} htmlFor={`condition-${item.step_id}`}>
              Condition — travels with the result
            </label>
            <input
              id={`condition-${item.step_id}`}
              className={INPUT}
              value={condition}
              onChange={(e) => setCondition(e.target.value)}
              placeholder="e.g. valid for development comparison only"
            />
          </div>
        )}

        <div>
          <label className={LABEL} htmlFor={`rationale-${item.step_id}`}>
            Rationale
          </label>
          <input
            id={`rationale-${item.step_id}`}
            className={INPUT}
            value={rationale}
            onChange={(e) => setRationale(e.target.value)}
          />
        </div>

        <div>
          <button
            type="button"
            className={BUTTON}
            disabled={pending || (needsCondition && condition.trim() === "")}
            onClick={() =>
              onDecide(item.route_id, item.step_id, {
                decision,
                ...(condition.trim() === "" ? {} : { condition_text: condition.trim() }),
                ...(rationale.trim() === "" ? {} : { rationale: rationale.trim() }),
              })
            }
          >
            Record decision
          </button>
        </div>
      </div>
    </li>
  );
}

export default function ApprovalsPage() {
  const { data, isLoading, error, unavailable } = useApprovalQueue((live) => live);
  const decision = useApprovalDecision();
  const rows: ApprovalQueueItem[] = data ?? [];

  return (
    <LiveOnlyPage
      title="Approvals"
      lede="Steps waiting on you, and only those: the engine excludes rungs whose
            turn has not come. Every decision is a permanent record, and a
            conditional approval keeps the limitation that made it conditional."
      unavailable={unavailable}
      notInvented="approval routes"
    >
      {error !== null ? (
        <DataSourceError error={error} />
      ) : unavailable !== null ? (
        <p className="text-sm text-slate-600">
          No approvals can be shown until this build is pointed at an API.
        </p>
      ) : (
        <>
          {rows.length === 0 ? (
            <p className="text-sm text-slate-600">
              {isLoading
                ? "Loading the queue…"
                : // 🔴 AN EMPTY QUEUE IS NOT "NO APPROVALS EXIST". It is "none
                  // are waiting on you", and the difference matters to a
                  // director who would otherwise conclude the ladder is clear.
                  "Nothing is waiting on you. Other approvals may be open elsewhere in this organization — this queue shows only steps you could decide right now."}
            </p>
          ) : (
            <ul className="grid gap-3">
              {rows.map((item) => (
                <QueueRow
                  key={item.step_id}
                  item={item}
                  pending={decision.isPending}
                  onDecide={decision.decide}
                />
              ))}
            </ul>
          )}

          {decision.error !== null && (
            <p
              role="alert"
              className="mt-3 rounded border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-900"
            >
              {serverMessage(decision.error)}
            </p>
          )}
          {decision.error === null && decision.lastAction !== null && (
            <p role="status" className="mt-3 text-sm text-slate-700">
              Recorded: {words(decision.lastAction)}. The queue above is re-read from
              the server, so a step that settled its route has already gone.
            </p>
          )}
        </>
      )}
    </LiveOnlyPage>
  );
}
