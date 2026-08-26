"use client";

/**
 * Reports — test results by their derived disposition.
 *
 * 🔴 THIS IS THE CALLER `GET /api/analysis/reports/test-results` NEVER HAD.
 *
 * That endpoint shipped on 2026-08-25 and was the first place in the whole
 * application to enforce `report.generate` — a permission granted to five
 * roles and read by nothing. It was tested and correct and **no production
 * path reached it**: the Reports destination sits at slice 20 in
 * `navigation.ts` and rendered disabled, so the route existed and no person
 * could press anything that called it.
 *
 * That is this project's most-repeated defect, one day old at the time: *a
 * route with no caller is the same defect as a table with no writer*, and *a
 * client function is not a caller — a route is reachable when a person can
 * press something*. This page is the press.
 *
 * ---------------------------------------------------------------------------
 * 🔴 IT READS §10's DERIVATION. IT DOES NOT REPEAT IT.
 * ---------------------------------------------------------------------------
 *
 * Every colour, label, reason and rule number on this page came from the
 * server, which got it from `derive_disposition` — the single ordered
 * algorithm §10 requires. Nothing here inspects a row to decide a status, and
 * the row schema deliberately lacks the inputs that would let it try.
 *
 * ⚠️ THE TWO EVALUATIONS ARE COLUMNS SIDE BY SIDE, NEVER ONE COLUMN.
 * §10 requires `Automatic evaluation: PASS` beside `Final disposition: YELLOW
 * — Awaiting Lead approval`. A report that merged them would be the exact
 * misreading the rule exists to prevent, at the scale where it matters most:
 * somebody exports this and sends it onwards.
 *
 * ⚠️ EVERY YELLOW SHOWS ITS NEXT ACTION. §3.3: *"a yellow with no explanation
 * is a defect."* The zod schema in `lib/api/testing.ts` already refuses a
 * bare amber from the test detail endpoint; here the reason and next action
 * are rendered rather than merely carried.
 */

import Link from "next/link";
import type { ReactNode } from "react";

import { DataSourceError, LiveOnlyPage } from "@/components/ui/data-source-banner";
import { useTestResultsReport } from "@/lib/api/hooks";
import type { AnalysisRow, TestResultsReport } from "@/lib/api/analysis";

const DISPOSITION: Record<string, { label: string; icon: string; className: string }> = {
  green: { label: "GREEN", icon: "✓", className: "text-status-pass" },
  yellow: { label: "YELLOW", icon: "!", className: "text-status-conditional" },
  red: { label: "RED", icon: "✕", className: "text-status-fail" },
  unknown: { label: "NOT DERIVED", icon: "–", className: "text-slate-500" },
};

/**
 * Colour + icon + word, always together (§11).
 *
 * Never the colour alone: this project measured its own pass-green against
 * its fail-red at ΔE 4.2 under deuteranopia, and a report is precisely the
 * artefact somebody prints in greyscale.
 */
function Disposition({ row }: { row: AnalysisRow }): ReactNode {
  const d = DISPOSITION[row.disposition.colour] ?? {
    label: row.disposition.colour.toUpperCase(),
    icon: "•",
    className: "text-slate-900",
  };
  return (
    <div>
      <p className={`font-semibold ${d.className}`}>
        <span aria-hidden className="mr-1">
          {d.icon}
        </span>
        {d.label}
        {row.disposition.label ? (
          <span className="ml-1 font-normal text-slate-700">— {row.disposition.label}</span>
        ) : null}
      </p>
      {row.disposition.reason ? (
        <p className="mt-0.5 text-xs text-slate-600">{row.disposition.reason}</p>
      ) : null}
      {row.disposition.next_action ? (
        // §3.3: every YELLOW states why AND what the next required action is.
        <p className="mt-0.5 text-xs font-medium text-slate-800">
          Next: {row.disposition.next_action}
        </p>
      ) : null}
    </div>
  );
}

export default function ReportsPage(): ReactNode {
  const { data, isLoading, error, unavailable } = useTestResultsReport<TestResultsReport>(
    (live) => live,
  );

  return (
    <LiveOnlyPage
      title="Reports"
      lede="Test results grouped by the disposition the server derived. Generated from records this account can open."
      unavailable={unavailable}
      notInvented="test results and their dispositions"
    >
      <div className="space-y-6 px-6 py-6">
        {/*
          🔴 ONE OF THIRTEEN, AND THE SCREEN SAYS SO.

          `IMPLEMENTATION_PLAN.md` §I slice 20 and master §41 name THIRTEEN
          controlled reports: Product Development Status · Formula Development
          History · Formula Comparison · Lab Batch · Test · Failure
          Investigation · DOE · Validation · Stability · Pilot · Qualification
          Dossier · Product Release · Portfolio.

          This screen delivers the Test report. A Reports destination that
          listed one report and said nothing would imply twelve others had
          been considered and found empty — which is a different claim, and a
          false one. An absence that is NAMED is a gap; an absence papered
          over is a defect, and that rule is why `_NOT_YET` exists in the
          dashboards service.
        */}
        <p
          data-testid="reports-scope"
          className="rounded border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700"
        >
          <span aria-hidden className="mr-1 font-bold">
            i
          </span>
          This is the <strong>Test</strong> report — one of the thirteen controlled reports the
          product defines. The other twelve (Product Development Status, Formula Development
          History, Formula Comparison, Lab Batch, Failure Investigation, DOE, Validation,
          Stability, Pilot, Qualification Dossier, Product Release, Portfolio) are not built yet.
        </p>

        {error ? <DataSourceError error={error} /> : null}

        {isLoading ? (
          <p className="text-sm text-slate-600">Loading…</p>
        ) : data === undefined ? null : (
          <>
            <section aria-labelledby="summary-heading" className="space-y-3">
              <h2 id="summary-heading" className="text-lg font-semibold text-slate-900">
                Test results
              </h2>
              <p className="text-sm text-slate-700">
                {data.counted} test{data.counted === 1 ? "" : "s"} counted
                {data.truncated ? (
                  // 🔴 NOT DECORATION. The server runs one detail read per row
                  // to read the derivation rather than copy it, so the report
                  // is bounded — and a report that hid its own cap would be
                  // counting something other than what it claims.
                  <span
                    data-testid="report-truncated"
                    className="ml-1 font-semibold text-amber-800"
                  >
                    — capped at {data.limit}; more tests exist than are shown
                  </span>
                ) : null}
                .
              </p>

              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {Object.entries(data.by_colour).map(([colour, n]) => {
                  const d = DISPOSITION[colour] ?? {
                    label: colour.toUpperCase(),
                    icon: "•",
                    className: "text-slate-900",
                  };
                  return (
                    <div key={colour} className="rounded border border-slate-200 bg-white p-4">
                      <p className="text-xs font-semibold tracking-wide text-slate-600">
                        <span aria-hidden className="mr-1">
                          {d.icon}
                        </span>
                        {d.label}
                      </p>
                      <p className={`mt-2 font-mono text-3xl tabular-nums ${d.className}`}>{n}</p>
                    </div>
                  );
                })}
              </div>
            </section>

            <section aria-labelledby="rows-heading" className="space-y-3">
              <h2 id="rows-heading" className="text-lg font-semibold text-slate-900">
                The tests behind these numbers
              </h2>
              <p className="text-xs text-slate-600">
                §2 requires analytics to drill down to real source records. Every row opens the
                test it counts.
              </p>

              {data.rows.length === 0 ? (
                // An empty report is an answer — never a placeholder row.
                <p className="text-sm text-slate-600">
                  No tests are visible in this scope. This is a real result, not a loading state.
                </p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[52rem] border-collapse text-sm">
                    <caption className="sr-only">
                      Tests with their automatic evaluation and final disposition
                    </caption>
                    <thead>
                      <tr className="border-b border-slate-300 text-left text-xs uppercase tracking-wide text-slate-600">
                        <th scope="col" className="py-2 pr-4">
                          Test
                        </th>
                        <th scope="col" className="py-2 pr-4">
                          Method
                        </th>
                        <th scope="col" className="py-2 pr-4">
                          Purpose / authority
                        </th>
                        {/* 🔴 TWO COLUMNS, NOT ONE. See the module docstring. */}
                        <th scope="col" className="py-2 pr-4">
                          Automatic evaluation
                        </th>
                        <th scope="col" className="py-2 pr-4">
                          Final disposition
                        </th>
                        <th scope="col" className="py-2 pr-4 text-right">
                          Rule
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.rows.map((row) => (
                        <tr key={row.test_id} className="border-b border-slate-100 align-top">
                          <td className="py-2 pr-4">
                            <Link
                              href={`/testing/test?id=${row.test_id}`}
                              className="font-medium text-slate-900 underline decoration-slate-300 underline-offset-2"
                            >
                              {row.test_number}
                            </Link>
                          </td>
                          <td className="py-2 pr-4 text-slate-700">{row.method_code ?? "—"}</td>
                          <td className="py-2 pr-4 text-slate-700">
                            {(row.test_purpose ?? "—").replace(/_/g, " ")}
                            <span className="block text-xs text-slate-500">
                              {(row.authority_level ?? "—").replace(/_/g, " ")}
                            </span>
                          </td>
                          <td className="py-2 pr-4 text-slate-800">
                            {/* NULL means "not yet evaluated", never
                                "inconclusive" — those are different facts and
                                rendering one as the other would be a claim. */}
                            {row.calculated_result === null ? (
                              <span className="text-slate-500">not yet evaluated</span>
                            ) : (
                              row.calculated_result.replace(/_/g, " ")
                            )}
                          </td>
                          <td className="py-2 pr-4">
                            <Disposition row={row} />
                          </td>
                          <td className="py-2 pr-4 text-right font-mono tabular-nums text-slate-700">
                            {row.disposition.rule ?? "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          </>
        )}
      </div>
    </LiveOnlyPage>
  );
}
