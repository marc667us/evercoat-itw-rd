"use client";

/**
 * Failures — the investigation queue.
 *
 * 🔴 THE MODULE THE SYSTEM WRITES TO AND NOBODY COULD READ.
 *
 * §10: *"A RED confirmation result automatically opens or links a Failure
 * Investigation."* That has been true since Slice 6's backend shipped — the
 * engine opens the investigation, the tables fill, and until this screen
 * existed **no person could see one**. Eleven write endpoints and two reads,
 * permission-gated and tested, with no browser caller: the exact shape this
 * project found twenty-three times on 2026-08-24 in four other modules, in the
 * one module where the record is created without anybody asking for it.
 *
 * 🔴 THE COUNTS ARE THE POINT OF A QUEUE, AND THEY ARE THE SERVER'S.
 *
 * `hypothesis_count`, `has_root_cause` and `open_actions` come back on every
 * row because §11 requires a count to represent items needing action rather
 * than total rows. An investigation with four hypotheses and no accepted root
 * cause is a different piece of work from one with none, and a queue that did
 * not say so would sort by date and tell a lead nothing.
 *
 * ⚠️ `has_root_cause` WAS A COUNT UNTIL THIS SCREEN WAS WRITTEN. Its name asks
 * a yes/no question; `list_failures` answered with `count(*)`. Nothing had
 * validated the payload because nothing had ever consumed it. Fixed in the
 * service, pinned by `tests/db/test_054_has_root_cause_is_a_boolean.py`.
 *
 * 🔴 AND NO TRAFFIC LIGHT IS INVENTED HERE, for the same reason `/testing`
 * shows none. `severity` is a stored field — critical, major, minor — and it
 * is NOT a disposition. Rendering it as a colour would let a reader infer that
 * a `minor` failure is acceptable, which is a judgement no column on this
 * endpoint has made.
 */

import Link from "next/link";

import { useState } from "react";

import { DataSourceError, LiveOnlyPage } from "@/components/ui/data-source-banner";
import { serverMessage } from "@/lib/api/client";
import { useFailures, useOpenInvestigation, useProjects } from "@/lib/api/hooks";
import type { FailureSummary } from "@/lib/api/failures";
import { permits, usePermissions } from "@/lib/permissions";

interface ProjectOption {
  readonly id: string;
  readonly project_code: string;
  readonly name: string;
}

/** A stored value as a readable word, without implying a judgement. */
function words(value: string): string {
  return value.replace(/_/g, " ");
}

/**
 * What this row needs somebody to do, in words.
 *
 * 🔴 DERIVED FROM COUNTS THE SERVER RETURNED, AND NOTHING ELSE. Each branch
 * restates a fact already on the row; none of them decides whether the
 * investigation is going well. "No hypothesis yet" is a count of zero said in
 * English — it is not a criticism, and it is not a status.
 *
 * ⚠️ ORDERED, first match wins, because more than one can be true at once. An
 * investigation with an accepted root cause and three open actions is waiting
 * on the ACTIONS; saying "root cause accepted" and stopping would read as
 * finished work.
 */
export function nextStep(row: FailureSummary): string {
  // 🔴 SIX STATUSES, NOT TWO. Raised by Codex. `quality.failures.status` is
  // CHECKed against open · investigating · root_cause_accepted ·
  // action_in_progress · closed · cancelled (migration 021), and this rule
  // recognised only `closed` — so a CANCELLED investigation was described as
  // needing a hypothesis and offered mutation controls that then 409'd.
  //
  // Both are SETTLED and neither needs work, but they are not the same
  // sentence: "closed" means somebody concluded it, "cancelled" means nobody
  // will. Collapsing them would lose the difference a reader is looking for.
  if (row.status === "closed") {
    return "Closed";
  }
  if (row.status === "cancelled") {
    return "Cancelled";
  }
  if (row.open_actions > 0) {
    return `${row.open_actions} corrective action${row.open_actions === 1 ? "" : "s"} open`;
  }
  if (row.has_root_cause) {
    return "Root cause accepted — no open actions";
  }
  if (row.hypothesis_count === 0) {
    return "No hypothesis yet";
  }
  return `${row.hypothesis_count} hypothes${row.hypothesis_count === 1 ? "is" : "es"}, none accepted`;
}

/**
 * Opening an investigation by hand — the eleventh write, and the one the
 * queue's own copy promised before the control existed.
 *
 * 🔴 RAISED BY CODEX. This page said investigations are opened *"by hand when a
 * problem is found another way"* while `POST /api/quality/failures` had no
 * client function and no control anywhere. A sentence on a screen describing a
 * capability the product does not have is the same defect as a comment
 * asserting a rule that does not exist, except that a user reads this one.
 *
 * §10 opens an investigation automatically on a RED confirmation result, and
 * that is the common path rather than the only one: a problem found in the
 * field, in a complaint, or by a technician mid-batch has no failing test to
 * hang off. `failure.create` exists for exactly that, and is held by the
 * Chemist, Engineer and QA — measured on the seeded realm 2026-08-27.
 *
 * ⚠️ THE PROJECT IS CHOSEN FROM A LIST, NEVER TYPED. `project_id` is a UUID and
 * a free-text field for one is how a form becomes unusable — the same reason
 * `PlanTestForSample` takes its method from `GET /api/testing/methods` rather
 * than asking for an id.
 */
function OpenInvestigation() {
  const permissions = usePermissions();
  const projects = useProjects<ProjectOption[]>([], (live) =>
    live.map((p) => ({ id: p.id, project_code: p.project_code, name: p.name })),
  );
  const open = useOpenInvestigation();
  const [expanded, setExpanded] = useState(false);
  const [projectId, setProjectId] = useState("");
  const [code, setCode] = useState("");
  const [title, setTitle] = useState("");
  const [severity, setSeverity] = useState<"critical" | "major" | "minor">("major");

  if (!permits(permissions, "failure.create")) {
    return null;
  }

  const options = projects.data ?? [];

  if (!expanded) {
    return (
      <button
        type="button"
        className="mb-4 rounded border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-800 hover:bg-slate-50"
        onClick={() => setExpanded(true)}
      >
        Open an investigation
      </button>
    );
  }

  return (
    <section aria-labelledby="open-investigation" className="mb-4 rounded border border-slate-200 bg-white p-4">
      <h2 id="open-investigation" className="text-sm font-semibold text-slate-900">
        Open an investigation
      </h2>
      <p className="mt-1 text-xs text-slate-600">
        For a problem found outside a failing test. A RED confirmation result
        opens one automatically.
      </p>

      <div className="mt-3 grid max-w-2xl gap-3">
        <div>
          <label className="block text-xs font-medium text-slate-700" htmlFor="failure-project">
            Project
          </label>
          <select
            id="failure-project"
            className="mt-1 w-full rounded border border-slate-300 px-2 py-1.5 text-sm text-slate-900 focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
            value={projectId}
            onChange={(e) => setProjectId(e.target.value)}
          >
            <option value="">Choose a project</option>
            {options.map((p) => (
              <option key={p.id} value={p.id}>
                {p.project_code} · {p.name}
              </option>
            ))}
          </select>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <label className="block text-xs font-medium text-slate-700" htmlFor="failure-code">
              Failure code
            </label>
            <input
              id="failure-code"
              className="mt-1 w-full rounded border border-slate-300 px-2 py-1.5 text-sm text-slate-900 focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              placeholder="FL-2026-001"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-700" htmlFor="failure-severity">
              Severity
            </label>
            <select
              id="failure-severity"
              className="mt-1 w-full rounded border border-slate-300 px-2 py-1.5 text-sm text-slate-900 focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
              value={severity}
              onChange={(e) => setSeverity(e.target.value as "critical" | "major" | "minor")}
            >
              <option value="critical">critical</option>
              <option value="major">major</option>
              <option value="minor">minor</option>
            </select>
          </div>
        </div>

        <div>
          <label className="block text-xs font-medium text-slate-700" htmlFor="failure-title">
            What went wrong
          </label>
          <input
            id="failure-title"
            className="mt-1 w-full rounded border border-slate-300 px-2 py-1.5 text-sm text-slate-900 focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            className="rounded bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-700 disabled:cursor-not-allowed disabled:bg-slate-300"
            // The server requires 3 characters on the code and the title, and a
            // real project. Matching that here avoids a round trip to be told
            // so; the server still refuses either way.
            disabled={
              open.isPending ||
              projectId === "" ||
              code.trim().length < 3 ||
              title.trim().length < 3
            }
            onClick={() =>
              open.submit({
                project_id: projectId,
                failure_code: code.trim(),
                title: title.trim(),
                severity,
              })
            }
          >
            {open.isPending ? "Opening…" : "Open"}
          </button>
          <button
            type="button"
            className="rounded border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-800 hover:bg-slate-50"
            onClick={() => setExpanded(false)}
          >
            Cancel
          </button>
        </div>

        {open.error !== null && (
          <p role="alert" className="text-sm text-red-700">
            The investigation was not opened: {serverMessage(open.error)}
          </p>
        )}
      </div>
    </section>
  );
}

export default function FailuresPage() {
  const { data, isLoading, error, unavailable } = useFailures((live) => live);
  const rows: FailureSummary[] = data ?? [];

  return (
    <LiveOnlyPage
      title="Failure investigations"
      lede="Opened automatically by a RED confirmation result, and by hand when a
            problem is found another way. Every investigation carries its
            hypotheses, the evidence for and against each one, and the corrective
            actions raised from it."
      unavailable={unavailable}
      notInvented="failure investigations"
    >
      {error !== null ? (
        <DataSourceError error={error} />
      ) : unavailable !== null ? (
        <p className="text-sm text-slate-600">
          No investigations can be shown until this build is pointed at an API.
        </p>
      ) : (
        <>
          {/* role="note" for the same reason the testing queue carries one: a
              reader must not conclude from the absence of a colour that a
              failure is unremarkable. */}
          <div
            role="note"
            aria-label="Severity is not a disposition"
            className="mb-4 rounded border border-slate-300 bg-slate-50 px-4 py-2 text-xs text-slate-800"
          >
            <span aria-hidden>⊘ </span>
            <strong>Severity is a stored field, not a traffic light.</strong> It
            says how bad the problem was judged to be when the investigation was
            opened; it says nothing about whether the investigation is finished
            or whether the product is safe. An <strong>AI hypothesis is never an
            accepted root cause</strong> — only a person accepts one, and the
            investigation records who.
          </div>

          <OpenInvestigation />

          {rows.length === 0 ? (
            <p className="text-sm text-slate-600">
              {isLoading ? "Loading investigations…" : "No failure investigations recorded."}
            </p>
          ) : (
            <ul className="grid gap-3">
              {rows.map((f) => (
                <li key={f.id} className="rounded border border-slate-200 bg-white p-4">
                  <div className="flex flex-wrap items-baseline gap-2">
                    <span className="text-xs font-medium tabular-nums text-slate-500">
                      {f.failure_code}
                    </span>
                    <h2 className="flex-1 text-sm font-semibold text-slate-900">
                      <Link
                        href={`/failures/investigation?id=${f.id}`}
                        className="underline underline-offset-2"
                      >
                        {f.title}
                      </Link>
                    </h2>
                    <span className="rounded border border-slate-300 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-slate-600">
                      {words(f.severity)}
                    </span>
                    <span className="rounded border border-slate-300 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-slate-600">
                      {words(f.status)}
                    </span>
                  </div>

                  <dl className="mt-2 grid gap-x-6 gap-y-1 text-xs text-slate-600 sm:grid-cols-2 lg:grid-cols-4">
                    <div className="flex gap-1.5">
                      <dt className="font-medium text-slate-500">Opened</dt>
                      <dd className="tabular-nums">{f.opened_at.slice(0, 10)}</dd>
                    </div>
                    <div className="flex gap-1.5">
                      <dt className="font-medium text-slate-500">Hypotheses</dt>
                      <dd className="tabular-nums">{f.hypothesis_count}</dd>
                    </div>
                    <div className="flex gap-1.5">
                      <dt className="font-medium text-slate-500">Root cause</dt>
                      {/* Text, never a tick alone. §10's rule that colour is
                          never the sole indicator applies to a glyph too: a ✓
                          with no word beside it says nothing in a printed
                          report or to a screen reader. */}
                      <dd>{f.has_root_cause ? "accepted" : "not accepted"}</dd>
                    </div>
                    <div className="flex gap-1.5">
                      <dt className="font-medium text-slate-500">Open actions</dt>
                      <dd className="tabular-nums">{f.open_actions}</dd>
                    </div>
                  </dl>

                  <p className="mt-2 text-xs font-medium text-slate-700">{nextStep(f)}</p>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </LiveOnlyPage>
  );
}
