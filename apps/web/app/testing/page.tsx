"use client";

/**
 * Testing — the queue.
 *
 * 🔴 THIS SCREEN SHOWS NO TRAFFIC LIGHT, AND THAT IS THE WHOLE DESIGN.
 *
 * `CLAUDE.md` §10: status is **derived and server-owned**, by an ordered
 * first-match-wins algorithm, and it is *"never a field a user picks"*.
 * Four of that algorithm's fourteen rules need inputs this endpoint does
 * not return — `cv > method.cv_limit`, `margin < requirement.warning_threshold`,
 * `trend_alert`, and the replicate statistics behind them.
 *
 * `list_tests` withholds them deliberately and says why in its own
 * docstring: deriving a disposition per row would cost a statistics query
 * per test, and *"a list view that silently costs N round trips is how a
 * queue becomes unusable at fifty rows"*.
 *
 * So a browser colouring these rows would be doing exactly what §10
 * forbids — deciding a traffic light on the client, from an incomplete
 * input. The temptation is real, because a `calculated_result` of `pass`
 * looks like a green light. It is not one: §6 says *"a technically
 * PASSING test stays YELLOW while mandatory approvals are incomplete"*,
 * and this screen cannot see whether they are.
 *
 * What it does instead is show the **five stored axes as facts**, which
 * is what they are, and state on the page that the disposition is not
 * computed here. An absence that is named is a gap; an absence that is
 * papered over with a colour is a safety defect.
 */

import { LiveOnlyPage, DataSourceError } from "@/components/ui/data-source-banner";
import { Absent } from "@/components/ui/record-link";
import { useTests } from "@/lib/api/hooks";
import type { Test } from "@/lib/api/testing";

/** An axis value as a readable word, without implying a judgement. */
function axis(value: string): string {
  return value.replace(/_/g, " ");
}

/**
 * The one thing this screen may legitimately say about progress.
 *
 * `replicates_valid` and `replicates_required` are both returned, so
 * "2 of 3" is a fact rather than a derivation. §10 rule 5 makes an
 * incomplete replicate set a YELLOW, but that is the SERVER's conclusion
 * to reach — here it is only ever reported as a count.
 */
function replicateNote(t: Test): string {
  return `${t.replicates_valid} of ${t.replicates_required}`;
}

export default function TestingPage() {
  const { data, isLoading, error, unavailable } = useTests((live) => live);
  const rows: Test[] = data ?? [];

  return (
    <LiveOnlyPage
      title="Testing"
      lede="The test queue, traceable to the physical sample each result came from.
            Every test carries five independent stored axes; the final traffic
            light is derived from them by the server, not on this screen."
      unavailable={unavailable}
    >
      {error !== null ? (
        <DataSourceError error={error} />
      ) : unavailable !== null ? (
        <p className="text-sm text-slate-600">
          No tests can be shown until this build is pointed at an API.
        </p>
      ) : (
        <>
          {/* role="note", not a bare paragraph. A reader must not conclude
              from the absence of a colour that a result is unremarkable —
              that is precisely the inference this notice exists to block. */}
          <div
            role="note"
            aria-label="Traffic-light status not computed on this screen"
            className="mb-4 rounded border border-slate-300 bg-slate-50 px-4 py-2 text-xs text-slate-800"
          >
            <span aria-hidden>⊘ </span>
            The <strong>GREEN / YELLOW / RED disposition is not computed here</strong>.
            It is derived by the server from replicate statistics, the method&rsquo;s
            variability limit, the requirement margin and the approval state — three
            of which this queue does not carry. The stored axes below are shown as
            recorded. A test with no colour has <strong>not</strong> been judged
            acceptable; open the test to see its disposition.
          </div>

          {rows.length === 0 ? (
            <p className="text-sm text-slate-600">
              {isLoading ? "Loading tests…" : "No tests recorded."}
            </p>
          ) : (
            <ul className="grid gap-3">
              {rows.map((t) => (
                <li key={t.id} className="rounded border border-slate-200 bg-white p-4">
                  <div className="flex flex-wrap items-baseline gap-2">
                    <span className="text-xs font-medium tabular-nums text-slate-500">
                      {t.test_number}
                    </span>
                    <h2 className="flex-1 text-sm font-semibold text-slate-900">
                      {t.method_code} · {t.method_name}
                    </h2>
                    {/* Purpose and authority together, always. §10: a green
                        SCREENING test is never qualification evidence, so the
                        authority is not an optional detail. */}
                    <span className="rounded border border-slate-300 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-slate-600">
                      {axis(t.test_purpose)} · {axis(t.authority_level)}
                    </span>
                  </div>

                  <dl className="mt-2 grid gap-x-6 gap-y-1 text-xs text-slate-600 sm:grid-cols-2 lg:grid-cols-3">
                    <div className="flex gap-1.5">
                      <dt className="font-medium text-slate-500">Sample</dt>
                      <dd className="tabular-nums">{t.sample_number}</dd>
                    </div>
                    <div className="flex gap-1.5">
                      <dt className="font-medium text-slate-500">Unit</dt>
                      <dd>{t.canonical_unit}</dd>
                    </div>
                    <div className="flex gap-1.5">
                      <dt className="font-medium text-slate-500">Replicates</dt>
                      <dd className="tabular-nums">{replicateNote(t)}</dd>
                    </div>

                    <div className="flex gap-1.5">
                      <dt className="font-medium text-slate-500">Execution</dt>
                      <dd>{axis(t.execution_status)}</dd>
                    </div>
                    <div className="flex gap-1.5">
                      <dt className="font-medium text-slate-500">Validity</dt>
                      <dd>{axis(t.validity_status)}</dd>
                    </div>
                    <div className="flex gap-1.5">
                      <dt className="font-medium text-slate-500">Result</dt>
                      <dd>
                        {/* NULL is "not yet evaluated", never "inconclusive".
                            Rendering it as a word would invent an outcome. */}
                        {t.calculated_result === null ? (
                          <Absent what="not yet evaluated" />
                        ) : (
                          axis(t.calculated_result)
                        )}
                      </dd>
                    </div>
                    <div className="flex gap-1.5">
                      <dt className="font-medium text-slate-500">Review</dt>
                      <dd>{axis(t.review_state)}</dd>
                    </div>
                    <div className="flex gap-1.5">
                      <dt className="font-medium text-slate-500">Approval</dt>
                      <dd>{axis(t.approval_state)}</dd>
                    </div>
                    <div className="flex gap-1.5">
                      <dt className="font-medium text-slate-500">Executed</dt>
                      <dd>
                        {t.executed_at ? (
                          t.executed_at.slice(0, 10)
                        ) : t.planned_for ? (
                          <span>planned {t.planned_for.slice(0, 10)}</span>
                        ) : (
                          <Absent what="not scheduled" />
                        )}
                      </dd>
                    </div>
                  </dl>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </LiveOnlyPage>
  );
}
