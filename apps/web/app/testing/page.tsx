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

import Link from "next/link";

import {
  CreateForm,
  CREATE_INPUT,
  CREATE_LABEL,
} from "@/components/ui/create-form";
import { LiveOnlyPage, DataSourceError } from "@/components/ui/data-source-banner";
import { formatDay, formatInstant } from "@/lib/format/date";
import { Absent } from "@/components/ui/record-link";
import { useState } from "react";

import {
  useBatch,
  useBatches,
  useCreateTest,
  useTestMethods,
  useTests,
} from "@/lib/api/hooks";
import type { Batch } from "@/lib/api/laboratory";
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
      <div className="mb-4">
        <PlanTestForm />
      </div>

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
                      {/*
                        The queue is a queue: its job is to get somebody to the
                        test. The disposition is NOT computed here and cannot be
                        (see this file's header) — the link is how a reader
                        reaches the screen where the server has computed it.
                      */}
                      <Link
                        href={`/testing/test?id=${t.id}`}
                        className="underline underline-offset-2"
                      >
                        {t.method_code} · {t.method_name}
                      </Link>
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
                    {/* WHEN THE TEST WAS RAISED. The list showed the three
                        result axes and the execution date but never said when
                        the test entered the pipeline, so a queue of pending
                        tests gave no clue which had been waiting longest. */}
                    <div className="flex gap-1.5">
                      <dt className="font-medium text-slate-500">Created</dt>
                      <dd title={formatInstant(t.created_at)}>{formatDay(t.created_at)}</dd>
                    </div>
                    <div className="flex gap-1.5">
                      <dt className="font-medium text-slate-500">Executed</dt>
                      <dd>
                        {/* Through the shared formatter. `.slice(0, 10)` left an
                            ISO `2026-08-30` beside dates formatted elsewhere as
                            `30 Aug 2026` — two conventions in one product. */}
                        {t.executed_at ? (
                          <span title={formatInstant(t.executed_at)}>
                            {formatDay(t.executed_at)}
                          </span>
                        ) : t.planned_for ? (
                          <span>planned {formatDay(t.planned_for)}</span>
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

/**
 * Plan a test.
 *
 * 🔴 BATCH FIRST, THEN SAMPLE — BECAUSE THAT IS THE THREAD, AND BECAUSE THERE
 * IS NO SAMPLES LIST.
 *
 * §2 runs `Formula Version → Lab Batch → Sample → Test`, and a test is planned
 * against a physical sample. There is no organization-wide samples endpoint —
 * samples are returned by the batch detail — so this picks a batch and then a
 * sample from it. That is not a workaround: choosing the sample without its
 * batch would ask a person to identify a sample number out of context, and the
 * batch is what they actually have in front of them.
 *
 * ⚠️ THE SAMPLE SELECT IS EMPTY UNTIL A BATCH IS CHOSEN, and says so rather
 * than rendering a blank dropdown that looks broken.
 *
 * 🔴 NOTHING HERE SETS A RESULT OR A STATUS. §10: the five axes are stored and
 * the colour is derived on the server. A form that offered "pass" at planning
 * time would be inventing the one thing the product exists not to let a person
 * pick.
 */
function PlanTestForm() {
  const writes = useCreateTest();
  const batches = useBatches<Batch[]>((live) => live);
  const methods = useTestMethods();
  const [batchId, setBatchId] = useState("");
  const batch = useBatch(batchId);

  const [testNumber, setTestNumber] = useState("");
  const [sampleId, setSampleId] = useState("");
  const [methodId, setMethodId] = useState("");
  const [purpose, setPurpose] = useState("screening");
  const [authority, setAuthority] = useState("preliminary");
  const [plannedFor, setPlannedFor] = useState("");

  const batchRows = batches.data ?? [];
  const methodRows = methods.data ?? [];
  const sampleRows = batchId === "" ? [] : (batch.data?.samples ?? []);

  return (
    <CreateForm
      title="Plan a test"
      permission="test.plan"
      submitLabel="Plan test"
      isPending={writes.isPending}
      error={writes.error}
      done={writes.created ? `${writes.created.test_number} planned.` : null}
      disabled={
        methodRows.length === 0
          ? "No test methods are configured yet, and a test cannot be planned without one."
          : false
      }
      onSubmit={() =>
        writes.create(
          {
            test_number: testNumber,
            sample_id: sampleId,
            method_id: methodId,
            test_purpose: purpose,
            authority_level: authority,
            planned_for: plannedFor === "" ? undefined : plannedFor,
          },
          () => {
            setTestNumber("");
            setPlannedFor("");
          },
        )
      }
    >
      <label className={CREATE_LABEL}>
        Test number
        <input
          className={CREATE_INPUT}
          required
          value={testNumber}
          onChange={(event) => setTestNumber(event.target.value)}
        />
      </label>
      <label className={CREATE_LABEL}>
        Batch
        <select
          className={CREATE_INPUT}
          required
          value={batchId}
          onChange={(event) => {
            setBatchId(event.target.value);
            // 🔴 CLEAR THE SAMPLE. It belonged to the OTHER batch, and leaving
            // it selected would submit a sample from a batch the person is no
            // longer looking at.
            setSampleId("");
          }}
        >
          <option value="">Choose a batch…</option>
          {batchRows.map((row) => (
            <option key={row.id} value={row.id}>
              {row.batch_number}
            </option>
          ))}
        </select>
      </label>
      <label className={CREATE_LABEL}>
        Sample
        <select
          className={CREATE_INPUT}
          required
          value={sampleId}
          disabled={batchId === ""}
          onChange={(event) => setSampleId(event.target.value)}
        >
          <option value="">
            {batchId === ""
              ? "Choose a batch first"
              : batch.isLoading
                ? "Loading samples…"
                : sampleRows.length === 0
                  ? "This batch has no samples yet"
                  : "Choose a sample…"}
          </option>
          {sampleRows.map((row) => (
            <option key={row.id} value={row.id}>
              {row.sample_number}
            </option>
          ))}
        </select>
      </label>
      <label className={CREATE_LABEL}>
        Method
        <select
          className={CREATE_INPUT}
          required
          value={methodId}
          onChange={(event) => setMethodId(event.target.value)}
        >
          <option value="">Choose a method…</option>
          {methodRows.map((row) => (
            <option key={row.id} value={row.id}>
              {row.method_code} — {row.name}
            </option>
          ))}
        </select>
      </label>
      <label className={CREATE_LABEL}>
        Purpose
        <select
          className={CREATE_INPUT}
          value={purpose}
          onChange={(event) => setPurpose(event.target.value)}
        >
          {/* §10: purpose is orthogonal to authority. A green SCREENING test is
              never qualification evidence, which is why both are chosen. */}
          <option value="screening">screening</option>
          <option value="oversight">oversight</option>
          <option value="confirmation">confirmation</option>
          <option value="improvement">improvement</option>
        </select>
      </label>
      <label className={CREATE_LABEL}>
        Authority level
        <select
          className={CREATE_INPUT}
          value={authority}
          onChange={(event) => setAuthority(event.target.value)}
        >
          <option value="preliminary">preliminary</option>
          <option value="development">development</option>
          <option value="controlled">controlled</option>
          <option value="validation">validation</option>
          <option value="qualification">qualification</option>
          <option value="release">release</option>
        </select>
      </label>
      <label className={CREATE_LABEL}>
        Planned for
        <input
          className={CREATE_INPUT}
          type="date"
          value={plannedFor}
          onChange={(event) => setPlannedFor(event.target.value)}
        />
      </label>
    </CreateForm>
  );
}
