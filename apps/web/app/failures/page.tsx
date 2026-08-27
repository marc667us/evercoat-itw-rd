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

import { DataSourceError, LiveOnlyPage } from "@/components/ui/data-source-banner";
import { useFailures } from "@/lib/api/hooks";
import type { FailureSummary } from "@/lib/api/failures";

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
  if (row.status === "closed") {
    return "Closed";
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
