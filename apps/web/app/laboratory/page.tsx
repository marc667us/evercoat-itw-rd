"use client";

/**
 * Laboratory — the batch queue.
 *
 * A batch is the bridge between a formula version and a physical sample:
 * `Formula Version → Lab Batch → Material Lot → Sample → Test` (§2). So
 * the two questions this screen answers are *what is on the bench* and
 * *what is holding each one up*.
 *
 * 🔴 THE MASSES ARE STRINGS AND STAY STRINGS.
 *
 * `planned_quantity_kg` is `NUMERIC(14,4)`. It arrives as a string
 * precisely so its stored scale survives, and it is rendered verbatim.
 * No `Number()`, no `toFixed`, no unit arithmetic — §4 keeps derivation
 * on the server, and this screen would be the obvious wrong place to
 * start doing it. See `lib/api/laboratory.ts`.
 *
 * 🔴 WHAT THIS SCREEN DOES NOT CLAIM.
 *
 * `list_batches` returns the batch's own columns plus four sub-counts.
 * There is no weigh-up sheet here, no per-component planned-vs-actual
 * deviation, and no process parameters — those need the batch detail
 * route, and a queue of forty batches must not run forty sub-queries.
 * `unweighed_count` is shown because it is the one number that answers
 * "can this batch move on", and it is a count the endpoint really does
 * return rather than one derived in the browser.
 */

import Link from "next/link";

import { LiveOnlyPage, DataSourceError } from "@/components/ui/data-source-banner";
import { Absent } from "@/components/ui/record-link";
import { StatusBadge, type DisplayStatus } from "@/components/ui/status-badge";
import { useBatches } from "@/lib/api/hooks";
import type { Batch } from "@/lib/api/laboratory";

/**
 * The batch lifecycle, as a status a reader can act on.
 *
 * Derived from the STORED status, never chosen — the same rule the
 * traffic light follows (§10). `weighing` and `mixing` are not "in
 * trouble", they are in progress, so they are neutral rather than amber:
 * a queue where every active batch is yellow trains people to ignore
 * yellow, which is the state that matters on a test result.
 */
function batchStatus(status: string): {
  status: DisplayStatus;
  label: string;
  reason?: string;
} {
  switch (status) {
    case "completed":
      return { status: "green", label: "COMPLETED" };
    case "accepted":
      return { status: "green", label: "ACCEPTED FOR TESTING" };
    case "rejected":
      return {
        status: "red",
        label: "REJECTED",
        reason: "process deviation — this batch does not proceed to testing",
      };
    case "abandoned":
      return { status: "red", label: "ABANDONED" };
    case "draft":
      return {
        status: "yellow",
        label: "DRAFT",
        reason: "not yet authorised for the bench",
      };
    case "authorized":
      return {
        status: "yellow",
        label: "AUTHORISED",
        reason: "cleared to start; not yet begun",
      };
    case "under_review":
      return {
        status: "yellow",
        label: "AWAITING CHEMIST REVIEW",
        reason: "execution finished; a chemist must accept or reject it",
      };
    default:
      // in_progress, weighing, mixing and anything a later migration adds.
      // Neutral and LABELLED WITH THE REAL VALUE rather than mapped to a
      // cheerful default — an unknown status must not render as a known
      // one. The suppliers screen was bitten by exactly that.
      return { status: "neutral", label: status.replace(/_/g, " ").toUpperCase() };
  }
}

export default function LaboratoryPage() {
  const { data, isLoading, error, unavailable } = useBatches((live) => live);
  const rows: Batch[] = data ?? [];

  return (
    <LiveOnlyPage
      title="Laboratory"
      lede="Batches on the bench, and what is holding each one up. A batch turns an
            approved formula version into a physical sample that a test can be
            traced back to."
      unavailable={unavailable}
    >
      {error !== null ? (
        <DataSourceError error={error} />
      ) : unavailable !== null ? (
        <p className="text-sm text-slate-600">
          No batches can be shown until this build is pointed at an API.
        </p>
      ) : rows.length === 0 ? (
        <p className="text-sm text-slate-600">
          {isLoading ? "Loading batches…" : "No laboratory batches recorded."}
        </p>
      ) : (
        <ul className="grid gap-3 lg:grid-cols-2">
          {rows.map((b) => {
            const d = batchStatus(b.status);
            return (
              <li
                key={b.id}
                className="rounded border border-slate-200 bg-white p-4"
              >
                <div className="flex flex-wrap items-baseline gap-2">
                  <span className="text-xs font-medium tabular-nums text-slate-500">
                    {b.batch_number}
                  </span>
                  <h2 className="flex-1 text-sm font-semibold text-slate-900">
                    {/*
                      The queue is a list of things to DO, so every row opens
                      the bench workspace. Before this link existed the eleven
                      lifecycle routes had no caller anywhere in the browser —
                      the same "a route nobody calls" defect this project
                      recorded on the knowledge ingest endpoint.

                      A query parameter, not a path segment: see the workspace
                      page's header for why a live batch UUID cannot be
                      pre-rendered under `output: "export"`.
                    */}
                    <Link
                      href={`/laboratory/batch?id=${encodeURIComponent(b.id)}`}
                      className="underline decoration-slate-300 underline-offset-2 hover:decoration-slate-900"
                    >
                      {b.formula_code} · {b.formula_name}
                    </Link>
                  </h2>
                  {d.status === "yellow" ? (
                    <StatusBadge
                      status="yellow"
                      label={d.label}
                      reason={d.reason ?? ""}
                      size="sm"
                    />
                  ) : (
                    <StatusBadge
                      status={d.status}
                      label={d.label}
                      reason={d.reason}
                      size="sm"
                    />
                  )}
                </div>

                <dl className="mt-2 flex flex-wrap gap-x-6 gap-y-1 text-xs text-slate-600">
                  <div className="flex gap-1.5">
                    <dt className="font-medium text-slate-500">Version</dt>
                    <dd className="tabular-nums">{b.version_code}</dd>
                  </div>
                  <div className="flex gap-1.5">
                    <dt className="font-medium text-slate-500">Planned</dt>
                    {/* Rendered verbatim. The string IS the value. */}
                    <dd className="tabular-nums">
                      {b.planned_quantity_kg} kg
                      <span className="text-slate-400"> ±{b.tolerance_percent}%</span>
                    </dd>
                  </div>
                  <div className="flex gap-1.5">
                    <dt className="font-medium text-slate-500">Components</dt>
                    <dd className="tabular-nums">
                      {b.component_count}
                      {b.unweighed_count > 0 && (
                        <>
                          {" · "}
                          <span className="font-semibold text-status-conditional">
                            {b.unweighed_count} unweighed
                          </span>
                        </>
                      )}
                    </dd>
                  </div>
                  <div className="flex gap-1.5">
                    <dt className="font-medium text-slate-500">Samples</dt>
                    <dd className="tabular-nums">{b.sample_count}</dd>
                  </div>
                  <div className="flex gap-1.5">
                    <dt className="font-medium text-slate-500">Deviations</dt>
                    <dd className="tabular-nums">
                      {b.deviation_count > 0 ? (
                        <span className="font-semibold text-status-conditional">
                          {b.deviation_count} recorded
                        </span>
                      ) : (
                        "none recorded"
                      )}
                    </dd>
                  </div>
                  <div className="flex gap-1.5">
                    <dt className="font-medium text-slate-500">Started</dt>
                    <dd>
                      {b.started_at ? (
                        b.started_at.slice(0, 10)
                      ) : (
                        <Absent what="not started" />
                      )}
                    </dd>
                  </div>
                </dl>
              </li>
            );
          })}
        </ul>
      )}
    </LiveOnlyPage>
  );
}
