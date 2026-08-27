"use client";

/**
 * Testing — one test, from planning to confirmation.
 *
 * This is the screen the test queue could not be. The queue shows five stored
 * axes and deliberately no colour, because `list_tests` withholds the inputs
 * the traffic light needs. **This is where the traffic light lives**, and it
 * arrives already decided by the server.
 *
 * 🔴 WHY THIS IS `/testing/test?id=…` AND NOT `/testing/[id]`.
 *
 * Same reason as the batch bench, and it is worth repeating because the
 * temptation to use a dynamic segment is constant. ADR-025 ships the web tier
 * as a STATIC EXPORT, so a `[id]` route must enumerate its params at build
 * time. A test id is a live UUID created minutes ago by an engineer;
 * pre-rendering "every test" would pre-render the seeded ones and 404 every
 * real one — a deep link that works in the demo and breaks in use.
 *
 * 🔴 NOTHING ON THIS SCREEN DERIVES A STATUS, AND THAT IS THE WHOLE POINT.
 *
 * `CLAUDE.md` §10 makes `display_color` and `final_status` derived and
 * server-owned by an ORDERED, first-match-wins algorithm of fourteen rules.
 * `get_test` runs it on every read and returns the answer with the number of
 * the rule that fired. This file renders that answer. It does not re-derive
 * it, does not shortcut it for the "obvious" cases, and does not colour
 * anything from `calculated_result` — because a technically PASSING test
 * stays YELLOW while mandatory approvals are incomplete, and that is rule 12,
 * not an edge case.
 *
 * 🔴 TWO FIELDS, ALWAYS DISPLAYED SEPARATELY (F31 / §3.3).
 *
 * `Automatic evaluation: PASS` and `Final disposition: YELLOW — Awaiting Lead
 * approval` are different statements and one field cannot make both. A
 * low-margin pass awaiting approval is genuinely a pass AND genuinely not
 * final. Collapsing them is how a screening result gets mistaken for release
 * evidence, so they sit side by side and are labelled.
 *
 * 🔴 EVERY MEASUREMENT IS A STRING AND STAYS ONE. `measured_value`, `mean`,
 * `standard_deviation`, `cv_percent` and `margin_percent` arrive as strings so
 * the recorded scale survives (I84 — they were floats until this screen was
 * written and something finally parsed them). No `Number()`, no `toFixed`.
 * The replicate entry field is a text input whose value is passed through
 * untouched, so the browser never rounds a measurement.
 *
 * 🔴 A `null` STATISTIC IS NOT ZERO. One replicate has a mean and NO standard
 * deviation; a CV over a mean of zero is undefined. The server sends `null`
 * for both rather than `0`, because zero would claim "perfectly repeatable" —
 * a claim one measurement cannot support, and one that would make rule 6 pass
 * silently. This screen renders the absence, never a zero.
 *
 * ✅ CORRECTED 2026-08-27 — AN ACTION THE CALLER CANNOT PERFORM IS NO LONGER
 * OFFERED, AND THE SERVER STILL DECIDES.
 *
 * This paragraph used to end: *"Hiding controls properly needs `/api/me` to
 * report permissions, which it does not — that is I79."* I79 CLOSED on
 * 2026-08-25 and `/api/me` has reported permissions ever since (measured
 * 2026-08-27: `tech.demo` 11, `chem.demo` 33, `lead.demo` 38). The sentence
 * outlived the constraint it described and kept this screen offering
 * `test.confirm` to a technician who has never held it.
 *
 * 🔴 SO THE HIDING IS ONLY ABOUT PERMISSIONS, AND THAT IS THE WHOLE POINT.
 * A 403 here means two different things and the server says which: the caller
 * lacks the permission, or the caller HOLDS it and is barred on THIS test by
 * their own earlier involvement (ADR-019). Only the first is knowable in the
 * browser. So a control whose permission the caller does not hold is hidden,
 * every control that survives is still offered to the server for the second
 * decision, and the refusal is surfaced verbatim exactly as before. Hiding the
 * first case does not hide the second, and pretending otherwise would be the
 * more dangerous change.
 */

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { DataSourceError, LiveOnlyPage } from "@/components/ui/data-source-banner";
import { serverMessage } from "@/lib/api/client";
import { usePermissions } from "@/lib/permissions";
import { Absent } from "@/components/ui/record-link";
import {
  StatusBadge,
  type AuthorityLevel,
  type StatusBadgeInput,
} from "@/components/ui/status-badge";
import { useTest, useTestActions } from "@/lib/api/hooks";
import type {
  ApprovalStep,
  Disposition,
  Replicate,
  TestDetail,
} from "@/lib/api/testing";

const CARD = "rounded border border-slate-200 bg-white p-4";
const LABEL = "block text-xs font-medium text-slate-600";
const INPUT =
  "mt-1 w-full rounded border border-slate-300 px-2 py-1.5 text-sm text-slate-900 " +
  "focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500";
const BUTTON =
  "rounded bg-slate-900 px-3 py-1.5 text-sm font-medium text-white " +
  "hover:bg-slate-700 disabled:cursor-not-allowed disabled:bg-slate-400";
const BUTTON_QUIET =
  "rounded border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium " +
  "text-slate-800 hover:bg-slate-50 disabled:cursor-not-allowed disabled:text-slate-400";

/**
 * The authority levels the badge knows, as a runtime check.
 *
 * The API pins these with a regex on `TestCreate.authority_level`, so the two
 * lists are a cross-language copy — the defect this project records as *"two
 * literals in two files cannot be type-checked into agreement"*. Pinned by a
 * drift test rather than by hope; see `lib/api/schemas.test.ts` for the
 * pattern this follows.
 */
const AUTHORITY_LEVELS: ReadonlySet<string> = new Set<AuthorityLevel>([
  "preliminary",
  "development",
  "controlled",
  "validation",
  "qualification",
  "release",
]);

function isAuthorityLevel(value: string): value is AuthorityLevel {
  return AUTHORITY_LEVELS.has(value);
}

/** A stored axis as a readable word, without implying a judgement. */
function axis(value: string): string {
  return value.replace(/_/g, " ");
}

/**
 * The server's disposition, rendered as the badge — never recomputed.
 *
 * 🔴 NOTHING IS DECIDED HERE. The engine emits exactly `green` / `yellow` /
 * `red`, which is the badge's own vocabulary minus `neutral`, and this
 * function only maps one to the other. An unrecognised colour is a contract
 * break rather than a value to be coerced, so it falls through to `neutral`
 * with the raw label showing — visible, rather than silently painted a colour
 * the server did not choose.
 *
 * A YELLOW always carries its reason, because the badge's own type demands
 * one: `StatusBadgeInput` makes `reason` REQUIRED on yellow. That is §3.3
 * enforced by the type system — *"a yellow with no explanation is a defect"* —
 * and it is why this function cannot accidentally emit a bare amber.
 */
function dispositionBadge(d: Disposition, authorityLevel: string): StatusBadgeInput {
  if (d.colour === "yellow") {
    return {
      status: "yellow",
      label: d.label,
      // `reason` is required on yellow, and `next_action` is non-empty for
      // every yellow the engine produces. Both are shown: why it is amber,
      // and what makes it stop being amber.
      reason: d.next_action ? `${d.reason} — next: ${d.next_action}` : d.reason,
    };
  }
  if (d.colour === "green" || d.colour === "red") {
    return {
      status: d.colour,
      label: d.label,
      // GREEN IS AUTHORITY-QUALIFIED (X12/F30). The badge appends the
      // authority for the preliminary levels, so a screening pass can never
      // be read at a glance as confirmation evidence.
      //
      // Narrowed against the real set rather than cast: `authority_level` is
      // a string on the wire, and a cast would hand the badge a value it does
      // not know, which silently drops the qualifier — the one thing that
      // stops a preliminary green being read as confirmation.
      authority: isAuthorityLevel(authorityLevel) ? authorityLevel : undefined,
    };
  }
  return { status: "neutral", label: d.label };
}

/** One raw measurement, with the exclusion control. */
function ReplicateRow({
  replicate,
  mayExclude,
  onExclude,
  pending,
}: {
  replicate: Replicate;
  /**
   * Whether this caller may set a measurement aside.
   *
   * `POST /{test_id}/replicates/{replicate_id}/exclusion` accepts
   * `test.execute` OR `test.review` — the only endpoint on this screen that
   * takes two, because an excluded replicate is both an execution correction
   * and a review judgement. Passed in rather than read from a hook here so
   * the row stays a presentational component with no session of its own.
   */
  mayExclude: boolean;
  onExclude: (replicateId: string, reason: string) => void;
  pending: boolean;
}) {
  const [reason, setReason] = useState("");
  const [open, setOpen] = useState(false);

  return (
    <tr className="border-b border-slate-100 align-top">
      <td className="py-2 pr-4 tabular-nums text-slate-900">{replicate.replicate_number}</td>

      {/* Verbatim. The string IS the value — see the file header. */}
      <td className="py-2 pr-4 tabular-nums text-slate-900">
        <span className={replicate.is_excluded ? "line-through text-slate-500" : ""}>
          {replicate.measured_value}
        </span>{" "}
        <span className="text-xs text-slate-600">{replicate.unit}</span>
      </td>

      <td className="py-2 pr-4">
        {replicate.is_excluded ? (
          <>
            <StatusBadge status="neutral" label="EXCLUDED" size="sm" />
            {/*
              The reason is shown, not hidden behind a tooltip. An exclusion
              with no visible justification is indistinguishable from
              discarding an inconvenient measurement, which is the thing the
              server's mandatory `reason` exists to prevent.
            */}
            <span className="mt-1 block text-xs text-slate-600">
              {replicate.exclusion_reason ?? <Absent what="no reason recorded" />}
            </span>
          </>
        ) : (
          <span className="text-xs text-slate-600">in the mean</span>
        )}
      </td>

      <td className="py-2">
        {replicate.is_excluded || !mayExclude ? null : open ? (
          <div className="flex flex-wrap items-start gap-2">
            <label className="sr-only" htmlFor={`reason-${replicate.id}`}>
              Reason for excluding replicate {replicate.replicate_number}
            </label>
            <input
              id={`reason-${replicate.id}`}
              className={INPUT + " w-64"}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="why this measurement is set aside"
            />
            <button
              type="button"
              className={BUTTON_QUIET}
              // The server requires at least 3 characters. Matching that here
              // is a courtesy, not the enforcement — the server refuses either
              // way, and this only avoids a round trip to be told so.
              disabled={pending || reason.trim().length < 3}
              onClick={() => onExclude(replicate.id, reason.trim())}
            >
              Exclude
            </button>
            <button type="button" className={BUTTON_QUIET} onClick={() => setOpen(false)}>
              Cancel
            </button>
          </div>
        ) : (
          <button type="button" className={BUTTON_QUIET} onClick={() => setOpen(true)}>
            Exclude…
          </button>
        )}
      </td>
    </tr>
  );
}

/** The seven decision types, as the server names them. */
const DECISIONS = [
  ["approve", "Approve"],
  ["approve_with_condition", "Approve with condition"],
  ["return_for_correction", "Return for correction"],
  ["request_retest", "Request retest"],
  ["request_additional_test", "Request additional test"],
  ["escalate", "Escalate"],
  ["reject", "Reject"],
] as const;

function ApprovalLadder({ steps }: { steps: readonly ApprovalStep[] }) {
  // Destructured rather than indexed. Every step of one route carries the same
  // `template_code` and `route_status` — `get_test` returns ONE route, never
  // the cancelled ones beside it — so the first step is a fair source for the
  // heading, but `steps[0]` is only safe once the empty case has returned.
  const [first] = steps;
  if (first === undefined) {
    return (
      <p className="text-sm text-slate-600">
        No approval route is open. A route is opened at the test&rsquo;s own authority
        when technical review completes.
      </p>
    );
  }

  return (
    <>
      <p className="mb-2 text-xs text-slate-600">
        Route <span className="font-medium">{first.template_code}</span> ·{" "}
        {axis(first.route_status)} — the immutable snapshot taken when the route
        opened, not the template as it stands today.
      </p>
      <ol className="grid gap-2">
        {steps.map((s) => (
          <li
            key={`${s.parallel_group ?? 0}-${s.step_number}`}
            className="rounded border border-slate-200 px-3 py-2"
          >
            <div className="flex flex-wrap items-baseline gap-2">
              <span className="text-xs font-medium tabular-nums text-slate-500">
                {s.step_number}
              </span>
              <span className="flex-1 text-sm font-medium text-slate-900">
                {s.step_label}
              </span>
              {/*
                🔴 AN UNDECIDED STEP IS THE ANSWER TO "WHAT REQUIRES ACTION?"
                (§11), so it is rendered as a state rather than omitted. A
                ladder showing only collected signatures answers the wrong
                question.
              */}
              {s.decision === null ? (
                <StatusBadge
                  status="yellow"
                  label="AWAITING"
                  reason={
                    s.is_mandatory
                      ? "mandatory — this test cannot be approved without it"
                      : "optional step, not yet decided"
                  }
                  size="sm"
                />
              ) : (
                <StatusBadge
                  status={s.decision === "approve" ? "green" : "neutral"}
                  label={axis(s.decision).toUpperCase()}
                  size="sm"
                />
              )}
            </div>
            <dl className="mt-1 grid gap-x-6 gap-y-0.5 text-xs text-slate-600 sm:grid-cols-2">
              <div className="flex gap-1.5">
                <dt className="font-medium text-slate-500">Requires</dt>
                <dd>{s.permission_required ?? <Absent what="unspecified" />}</dd>
              </div>
              <div className="flex gap-1.5">
                <dt className="font-medium text-slate-500">Decided</dt>
                <dd>{s.decided_at ? s.decided_at.slice(0, 10) : <Absent what="—" />}</dd>
              </div>
              {s.condition_text !== null && (
                <div className="flex gap-1.5 sm:col-span-2">
                  <dt className="font-medium text-slate-500">Condition</dt>
                  <dd>{s.condition_text}</dd>
                </div>
              )}
              {s.rationale !== null && (
                <div className="flex gap-1.5 sm:col-span-2">
                  <dt className="font-medium text-slate-500">Rationale</dt>
                  <dd>{s.rationale}</dd>
                </div>
              )}
            </dl>
          </li>
        ))}
      </ol>
    </>
  );
}

function TestWorkspace({ test }: { test: TestDetail }) {
  const actions = useTestActions(test.id);
  // Each name below is the permission THAT endpoint declares, read off
  // `app/api/testing.py` rather than inferred from the label on the button:
  // start / replicate / completion require `test.execute`, exclusion accepts
  // `test.execute` OR `test.review`, confirmation requires `test.confirm`, and
  // a decision requires `test.review` at the review stage or the rung's own
  // permission at the approval stage.
  const permissions = usePermissions();
  const mayExecute = permissions.has("test.execute");
  const mayReview = permissions.has("test.review");
  const mayConfirm = permissions.has("test.confirm");
  // 🔴 THE LADDER NAMES ITS OWN PERMISSIONS, SO ASK IT RATHER THAN GUESS.
  // `authority_level` selects nothing any more — the route opens at the test's
  // authority and each rung carries `permission_required`. A hard-coded list
  // here would be a second copy of the ladder, disagreeing with the first the
  // day a template changes.
  const mayApproveARung = test.approval_route.some(
    (step) => step.permission_required !== null && permissions.has(step.permission_required),
  );
  const mayDecide = mayReview || mayApproveARung;

  const [value, setValue] = useState("");
  const [unit, setUnit] = useState("");
  const [decision, setDecision] = useState<(typeof DECISIONS)[number][0]>("approve");
  const [stage, setStage] = useState<"review" | "approval">("review");
  const [condition, setCondition] = useState("");
  const [rationale, setRationale] = useState("");
  // 🔴 RAISED BY CODEX AND MEASURED: THE STAGE SELECT OFFERED BOTH MODES TO
  // BOTH KINDS OF CALLER, WITH `review` AS THE DEFAULT.
  //
  // `mayDecide` decides whether the FORM appears. It does not decide which
  // STAGE the caller may use, and those are different questions:
  // `POST /{test_id}/decisions` requires `test.review` for a review decision
  // and the CURRENT RUNG's own permission for an approval one. So a lead
  // holding an approval rung and not `test.review` saw a form defaulted to the
  // one stage they cannot use — and the first thing they would have pressed
  // was a 403.
  //
  // ⚠️ THE DEFAULT MOVES WITH THE OPTIONS. Offering only `approval` while
  // leaving `stage` initialised to `review` would send the refused value
  // anyway, which is the same defect with the evidence removed.
  const stages = [
    ...(mayReview ? (["review"] as const) : []),
    ...(mayApproveARung ? (["approval"] as const) : []),
  ];
  const effectiveStage = stages.includes(stage) ? stage : (stages[0] ?? "review");

  const stats = test.statistics;
  const auto = test.automatic_evaluation;

  /**
   * 🔴 DERIVED FROM THE CACHE, SO ENTRY IS BLOCKED UNTIL THE CACHE IS FRESH.
   *
   * `replicate_number` is computed from `test.replicates`, which is a
   * react-query cache. After a successful `recordReplicate` the invalidation
   * refetches ASYNCHRONOUSLY — so a technician typing the next value before
   * that lands would resubmit the same number and hit the database's
   * uniqueness constraint. The bench is precisely where measurements are
   * typed in quick succession, so this is not a theoretical race.
   * Found by the Supervisor.
   *
   * The honest fix inside this screen is to refuse entry while a write is in
   * flight rather than to guess a number: the server owns the sequence, and
   * a client that incremented optimistically would be inventing an identifier
   * for a controlled record. The button is disabled on `isPending`, and the
   * field says why.
   */
  const nextReplicate = test.replicates.length + 1;

  return (
    <>
      <div className="mb-4 flex flex-wrap items-baseline gap-3">
        <h1 className="text-lg font-semibold text-slate-900">{test.test_number}</h1>
        <span className="rounded border border-slate-300 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-slate-600">
          {axis(test.test_purpose)} · {axis(test.authority_level)}
        </span>
        <Link href="/testing" className="text-sm text-slate-600 underline">
          ← the test queue
        </Link>
      </div>

      {/*
        🔴 THE TWO FIELDS, SIDE BY SIDE AND LABELLED. F31 requires them
        displayed separately and always. The left one is what the numbers say;
        the right one is what the organisation says. They routinely disagree,
        and that disagreement is information.
      */}
      <section className="grid gap-3 sm:grid-cols-2">
        <div className={CARD}>
          <h2 className={LABEL}>Automatic evaluation</h2>
          <p className="mt-1 text-sm font-semibold text-slate-900">
            {auto.calculated_result === null ? (
              <Absent what="not yet evaluated" />
            ) : (
              axis(auto.calculated_result).toUpperCase()
            )}
          </p>
          <p className="mt-1 text-xs text-slate-600">{auto.detail}</p>
          {auto.margin_percent !== null && (
            <p className="mt-1 text-xs text-slate-600">
              Pass margin <span className="tabular-nums">{auto.margin_percent}</span>%
            </p>
          )}
        </div>

        <div className={CARD}>
          <h2 className={LABEL}>Final disposition</h2>
          <div className="mt-1">
            <StatusBadge {...dispositionBadge(test.final_disposition, test.authority_level)} />
          </div>
          {/*
            The rule number is shown because the server returns it, and because
            "a traffic light nobody can explain is a traffic light nobody
            trusts". It makes a disputed colour traceable to the predicate that
            produced it rather than a matter of opinion.
          */}
          <p className="mt-2 text-xs text-slate-500">
            Rule {test.final_disposition.rule} of 14 fired, first match wins.
          </p>
        </div>
      </section>

      {/* ---------------------------------------------------------------- */}
      <section className="mt-6">
        <h2 className="text-sm font-semibold text-slate-900">The five stored axes</h2>
        <dl className="mt-2 grid gap-x-6 gap-y-1 text-xs text-slate-600 sm:grid-cols-3">
          {(
            [
              ["Execution", test.execution_status],
              ["Validity", test.validity_status],
              ["Result", test.calculated_result],
              ["Review", test.review_state],
              ["Approval", test.approval_state],
            ] as const
          ).map(([name, v]) => (
            <div key={name} className="flex gap-1.5">
              <dt className="font-medium text-slate-500">{name}</dt>
              <dd>{v === null ? <Absent what="not yet evaluated" /> : axis(v)}</dd>
            </div>
          ))}
          <div className="flex gap-1.5">
            <dt className="font-medium text-slate-500">Confirmed</dt>
            <dd>{test.final_confirmed ? "yes" : "no"}</dd>
          </div>
        </dl>
        {test.approval_condition !== null && (
          <p className="mt-2 rounded border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-slate-800">
            <strong>Condition attached:</strong> {test.approval_condition}
          </p>
        )}
      </section>

      {/* ---------------------------------------------------------------- */}
      <section className="mt-6">
        <h2 className="text-sm font-semibold text-slate-900">
          Replicates — the raw measurements
        </h2>
        <p className="mt-1 text-xs text-slate-600">
          Every measurement is recorded individually and none is ever deleted. An
          excluded replicate stays on the record, visibly excluded, so &ldquo;why does
          this test have four measurements when the method requires five&rdquo; stays
          answerable.
        </p>

        <div className="mt-3 overflow-x-auto">
          <table className="w-full min-w-[36rem] text-left text-sm">
            <thead>
              <tr className="border-b border-slate-300 text-xs uppercase tracking-wide text-slate-600">
                <th className="py-2 pr-4 font-medium">#</th>
                <th className="py-2 pr-4 font-medium">Measured</th>
                <th className="py-2 pr-4 font-medium">In the statistics</th>
                <th className="py-2 font-medium">
                  <span className="sr-only">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {test.replicates.length === 0 ? (
                <tr>
                  <td colSpan={4} className="py-3 text-sm text-slate-600">
                    No measurements recorded yet.
                  </td>
                </tr>
              ) : (
                test.replicates.map((r) => (
                  <ReplicateRow
                    key={r.id}
                    replicate={r}
                    mayExclude={mayExecute || mayReview}
                    onExclude={actions.excludeOne}
                    pending={actions.isPending}
                  />
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Entry. Offered to a caller holding `test.execute`, which is what
            `POST /{test_id}/replicates` requires. Beyond that the server still
            decides: it refuses outside `in_progress` with a 409, and the
            message is shown. Permission is knowable here; execution state is
            the server's answer. */}
        {mayExecute && (
        <div className="mt-3 flex flex-wrap items-end gap-2">
          <div>
            <label className={LABEL} htmlFor="measured">
              {actions.isPending
                ? "Saving the last measurement…"
                : `Replicate ${nextReplicate} — measured value`}
            </label>
            {/*
              A TEXT input, not `type="number"`. A number input would let the
              browser normalise "12.500" to "12.5" and the recorded scale would
              be lost before the request was even made. `inputMode` still gives
              a numeric keypad on a phone.
            */}
            <input
              id="measured"
              className={INPUT + " w-40"}
              inputMode="decimal"
              value={value}
              onChange={(e) => setValue(e.target.value)}
              placeholder="e.g. 12.500"
              // Blocked while a write is in flight: the number above is read
              // from a cache that has not refetched yet.
              disabled={actions.isPending}
            />
          </div>
          <div>
            <label className={LABEL} htmlFor="unit">
              Unit
            </label>
            <input
              id="unit"
              className={INPUT + " w-28"}
              value={unit}
              onChange={(e) => setUnit(e.target.value)}
              placeholder="MPa"
            />
          </div>
          <button
            type="button"
            className={BUTTON}
            disabled={actions.isPending || value.trim() === "" || unit.trim() === ""}
            onClick={() => {
              actions.addReplicate({
                replicate_number: nextReplicate,
                // Passed through untouched. No parse, no round.
                measured_value: value.trim(),
                unit: unit.trim(),
              });
              setValue("");
            }}
          >
            Record measurement
          </button>
        </div>
        )}
      </section>

      {/* ---------------------------------------------------------------- */}
      <section className="mt-6">
        <h2 className="text-sm font-semibold text-slate-900">Statistics</h2>
        <dl className="mt-2 grid gap-x-6 gap-y-1 text-xs text-slate-600 sm:grid-cols-3">
          <div className="flex gap-1.5">
            <dt className="font-medium text-slate-500">Recorded</dt>
            <dd className="tabular-nums">{stats.count}</dd>
          </div>
          <div className="flex gap-1.5">
            <dt className="font-medium text-slate-500">In the mean</dt>
            <dd className="tabular-nums">{stats.valid_count}</dd>
          </div>
          <div className="flex gap-1.5">
            <dt className="font-medium text-slate-500">Mean</dt>
            <dd className="tabular-nums">
              {stats.mean ?? <Absent what="no measurements" />}
            </dd>
          </div>
          {/*
            🔴 NULL RENDERS AS A NAMED ABSENCE, NEVER AS ZERO. A single
            replicate has no standard deviation, and "0" would assert perfect
            repeatability from one measurement.
          */}
          <div className="flex gap-1.5">
            <dt className="font-medium text-slate-500">Std dev (n−1)</dt>
            <dd className="tabular-nums">
              {stats.standard_deviation ?? (
                <Absent what="needs two or more replicates" />
              )}
            </dd>
          </div>
          <div className="flex gap-1.5">
            <dt className="font-medium text-slate-500">CV</dt>
            <dd className="tabular-nums">
              {stats.cv_percent === null ? (
                <Absent what="undefined at a mean of zero" />
              ) : (
                `${stats.cv_percent}%`
              )}
            </dd>
          </div>
        </dl>
      </section>

      {/* ---------------------------------------------------------------- */}
      <section className="mt-6">
        <h2 className="text-sm font-semibold text-slate-900">Approval route</h2>
        <div className="mt-2">
          <ApprovalLadder steps={test.approval_route} />
        </div>
      </section>

      {/* ---------------------------------------------------------------- */}
      {test.decisions.length > 0 && (
        <section className="mt-6">
          <h2 className="text-sm font-semibold text-slate-900">Review decisions</h2>
          <ul className="mt-2 grid gap-2">
            {test.decisions.map((d) => (
              <li key={d.id} className="rounded border border-slate-200 px-3 py-2 text-xs">
                <span className="font-medium text-slate-900">
                  {axis(d.decision).toUpperCase()}
                </span>{" "}
                <span className="text-slate-600">
                  · {axis(d.decision_stage)}
                  {d.decided_at ? ` · ${d.decided_at.slice(0, 10)}` : ""}
                </span>
                {d.condition_text !== null && (
                  <p className="mt-0.5 text-slate-700">Condition: {d.condition_text}</p>
                )}
                {d.rationale !== null && (
                  <p className="mt-0.5 text-slate-700">{d.rationale}</p>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* ---------------------------------------------------------------- */}
      <section className="mt-6">
        <h2 className="text-sm font-semibold text-slate-900">Lifecycle</h2>
        <p className="mt-1 text-xs text-slate-600">
          Every control is offered and the <strong>server decides</strong>. A refusal
          here may mean you lack the permission, or that you hold it and are barred on
          this test by your own earlier involvement — the server says which, and the
          message is shown verbatim.
        </p>

        <div className="mt-3 flex flex-wrap gap-2">
          {mayExecute && (
          <button
            type="button"
            className={BUTTON_QUIET}
            disabled={actions.isPending}
            onClick={actions.start}
          >
            Start execution
          </button>
          )}
          {/*
            No body, and nothing to add one to. The result is COMPUTED — the
            route "takes no body on purpose. There is nowhere to put a result,
            because the caller does not get to state one."
          */}
          {mayExecute && (
          <button
            type="button"
            className={BUTTON_QUIET}
            disabled={actions.isPending}
            onClick={actions.complete}
          >
            Complete execution (computes the result)
          </button>
          )}
          {mayConfirm && (
          <button
            type="button"
            className={BUTTON_QUIET}
            disabled={actions.isPending}
            onClick={actions.confirm}
          >
            Confirm as final
          </button>
          )}
        </div>

        {/* 🔴 SAY SO RATHER THAN RENDER AN EMPTY BAR. Every lifecycle control
            filtered out leaves a heading over nothing, which reads as a screen
            that failed to load rather than as a screen that is read-only for
            this reader. Naming the three permissions is deliberate: a chemist
            asking "why can I not start this?" gets an answer they can take to
            an administrator. */}
        {!mayExecute && !mayConfirm && (
          <p className="mt-3 text-sm text-slate-600">
            You hold neither <code className="text-xs">test.execute</code> nor{" "}
            <code className="text-xs">test.confirm</code>, so this test is
            read-only from here. The record above is complete; only the controls
            are withheld.
          </p>
        )}

        {/* 🔴 THE DECISION FORM IS GATED ON THE LADDER, NOT ON A GUESS.
            `test.review` covers the review stage; the approval stage is
            covered when the caller holds the permission named by any rung of
            THIS test's own snapshotted route. A caller holding neither can
            record nothing here, and the seven decision types are not a menu
            worth offering them. */}
        {mayDecide && (
        <div className="mt-4 grid gap-2 sm:max-w-2xl">
          <div className="flex flex-wrap gap-2">
            <div className="flex-1">
              <label className={LABEL} htmlFor="decision">
                Decision — seven types, not two
              </label>
              <select
                id="decision"
                className={INPUT}
                value={decision}
                onChange={(e) =>
                  setDecision(e.target.value as (typeof DECISIONS)[number][0])
                }
              >
                {DECISIONS.map(([v, l]) => (
                  <option key={v} value={v}>
                    {l}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className={LABEL} htmlFor="stage">
                Stage
              </label>
              <select
                id="stage"
                className={INPUT}
                value={effectiveStage}
                onChange={(e) => setStage(e.target.value as "review" | "approval")}
                // One option left is not a choice, and a select the caller
                // cannot change reads as a control that is not working.
                disabled={stages.length < 2}
              >
                {stages.map((available) => (
                  <option key={available} value={available}>
                    {available}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/*
            🔴 THERE IS NO AUTHORITY-LEVEL FIELD, AND THERE MUST NOT BE. The
            route was opened at the test's authority when review completed, and
            each rung names the permission it requires. The server REFUSES a
            supplied `authority_level` with a 422 rather than ignoring it —
            offering the field would let a reviewer believe their signature
            carried an authority they had chosen.
          */}
          {decision === "approve_with_condition" && (
            <div>
              <label className={LABEL} htmlFor="condition">
                Condition — travels with the result
              </label>
              <input
                id="condition"
                className={INPUT}
                value={condition}
                onChange={(e) => setCondition(e.target.value)}
              />
            </div>
          )}

          <div>
            <label className={LABEL} htmlFor="rationale">
              Rationale
            </label>
            <input
              id="rationale"
              className={INPUT}
              value={rationale}
              onChange={(e) => setRationale(e.target.value)}
            />
          </div>

          <div>
            <button
              type="button"
              className={BUTTON}
              disabled={actions.isPending}
              onClick={() =>
                actions.decide({
                  decision,
                  // `effectiveStage`, never `stage`. The state can hold the
                  // initial `review` for a caller who was never offered it.
                  stage: effectiveStage,
                  condition_text: condition.trim() === "" ? undefined : condition.trim(),
                  rationale: rationale.trim() === "" ? undefined : rationale.trim(),
                })
              }
            >
              Record decision
            </button>
          </div>
        </div>
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
            Recorded: {actions.lastAction}. The disposition above is re-derived by the
            server on every read.
          </p>
        )}
      </section>
    </>
  );
}

function TestScreen() {
  const params = useSearchParams();
  const testId = params.get("id") ?? "";
  const { data, isLoading, error, unavailable } = useTest(testId);

  return (
    <LiveOnlyPage
      title="Test"
      lede="One test, its raw measurements, and the disposition the server derived
            from them. The automatic evaluation and the final disposition are shown
            separately, always."
      unavailable={unavailable}
    >
      {testId === "" ? (
        <p className="text-sm text-slate-600">
          No test was named. Open one from <Link href="/testing" className="underline">the
          test queue</Link>.
        </p>
      ) : error !== null ? (
        <DataSourceError error={error} />
      ) : unavailable !== null ? (
        <p className="text-sm text-slate-600">
          This test cannot be shown until this build is pointed at an API.
        </p>
      ) : data === undefined ? (
        <p className="text-sm text-slate-600">
          {isLoading ? "Loading the test…" : "That test could not be found."}
        </p>
      ) : (
        <TestWorkspace test={data} />
      )}
    </LiveOnlyPage>
  );
}

/**
 * `useSearchParams` must sit inside a Suspense boundary, and under
 * `output: "export"` Next refuses to build without one. The fallback is a
 * sentence rather than a spinner: a blank frame is indistinguishable from a
 * screen that failed.
 */
export default function TestPage() {
  return (
    <Suspense fallback={<p className="p-6 text-sm text-slate-600">Loading the test…</p>}>
      <TestScreen />
    </Suspense>
  );
}
