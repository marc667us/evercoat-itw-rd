"use client";

/**
 * Laboratory — one batch on the bench.
 *
 * This is the screen the batch queue could not be: the weigh-up sheet, what
 * was actually put on the balance against it, the process data, the
 * deviations, the samples, and every step of the lifecycle as something a
 * person can actually do.
 *
 * 🔴 WHY THIS IS `/laboratory/batch?id=…` AND NOT `/laboratory/[id]`.
 *
 * ADR-025 ships the web tier as a STATIC EXPORT (`output: "export"`). There is
 * no server to resolve a dynamic segment at request time, so a `[id]` route
 * must enumerate its params at build time via `generateStaticParams` — which
 * is exactly what `app/projects/[code]` and `app/formulations/[code]` do, from
 * the demonstration fixture.
 *
 * That works for fixture codes and CANNOT work here. A batch id is a live
 * UUID created at the bench, minutes ago, by somebody else. Pre-rendering
 * "every batch" at build time would pre-render the seeded ones and 404 every
 * real one — a deep link that works in the demo and breaks in use, which is
 * worse than not offering it. A query parameter needs no build-time knowledge
 * and behaves identically in `next dev`, in the export, and behind the tunnel.
 *
 * 🔴 MASSES ARE STRINGS AND STAY STRINGS. `planned_mass_kg` is
 * `NUMERIC(14,4)`; it arrives as a string so its scale survives and is
 * rendered verbatim. No `Number()`, no `toFixed`. The one place a number is
 * unavoidable — the weighing input — is a text field whose value is passed
 * through untouched, so the browser never rounds a controlled mass. §4 keeps
 * derivation on the server and §5 forbids float on a measured value.
 *
 * 🔴 AN UNWEIGHED LINE IS NOT A ZERO DEVIATION. The server sends
 * `deviation: null` for a line nobody has weighed, and says why in its own
 * comment: reporting 0.00% within tolerance *"would make an incomplete batch
 * look finished"*. This screen renders the two differently and never fills the
 * gap with a dash that could be mistaken for a measurement.
 *
 * 🔴 EVERY ACTION IS OFFERED AND THE SERVER DECIDES. Buttons are shown for the
 * steps the batch's own status allows, but nothing here is an authorization
 * check: `batch.reject` is held only by the Engineer, and §6 makes frontend
 * checks cosmetic with the server authoritative. A 403 is surfaced as the
 * sentence the server sent. Hiding controls properly needs `/api/me` to report
 * permissions, which it does not — that is I79, and pretending otherwise here
 * would be a second, wrong, copy of the permission model.
 */

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { DataSourceError, LiveOnlyPage } from "@/components/ui/data-source-banner";
import { Absent } from "@/components/ui/record-link";
import { StatusBadge, type StatusBadgeInput } from "@/components/ui/status-badge";
import { useBatch, useBatchActions } from "@/lib/api/hooks";
import type { BatchComponent, BatchDetail } from "@/lib/api/laboratory";

/**
 * The batch lifecycle as a status a reader can act on.
 *
 * Deliberately the SAME mapping the queue uses, and for the same reason given
 * there: `weighing` and `mixing` are progress, not trouble, so they stay
 * neutral. A screen where every active batch is amber teaches people to
 * ignore amber, and amber is what matters on a test result.
 *
 * ⚠️ Duplicated from `app/laboratory/page.tsx` rather than shared, and that is
 * a known cost written down rather than hidden: §12 says do not rebuild shared
 * infrastructure, and two copies of a status mapping is exactly the
 * "two literals in two files cannot be type-checked into agreement" defect
 * this project has recorded. Lifting it into `components/ui` is the right fix
 * and is left as a marked follow-up rather than done mid-screen.
 */
function batchStatus(status: string): StatusBadgeInput {
  switch (status) {
    case "completed":
      return {
        status: "yellow",
        label: "AWAITING CHEMIST REVIEW",
        reason: "execution finished; a chemist must accept or reject it",
      };
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
      return { status: "neutral", label: status.replace(/_/g, " ").toUpperCase() };
  }
}

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

/** One weigh-up line, with the entry field the technician actually uses. */
function ComponentRow({
  line,
  canWeigh,
  onWeigh,
  pending,
}: {
  line: BatchComponent;
  canWeigh: boolean;
  onWeigh: (componentId: string, mass: string) => void;
  pending: boolean;
}) {
  const [mass, setMass] = useState("");

  return (
    <tr className="border-b border-slate-100 align-top">
      <td className="py-2 pr-4">
        <span className="font-medium tabular-nums text-slate-900">
          {line.material_code}
        </span>
        <span className="block text-xs text-slate-600">{line.material_name}</span>
        {line.role !== null && (
          <span className="block text-xs text-slate-500">{line.role}</span>
        )}
      </td>

      {/* Verbatim. The string IS the value. */}
      <td className="py-2 pr-4 tabular-nums text-slate-900">{line.planned_mass_kg}</td>

      <td className="py-2 pr-4 tabular-nums text-slate-900">
        {line.actual_mass_kg ?? <Absent what="not weighed" />}
      </td>

      <td className="py-2 pr-4">
        {/*
          🔴 THREE STATES, NOT TWO. `deviation === null` means nobody has
          weighed this line — it is NOT a zero deviation, and rendering it as
          one would make an incomplete batch look finished. The server draws
          this distinction explicitly; so does this cell.
        */}
        {line.deviation === null ? (
          <Absent what="—" />
        ) : line.deviation.within_tolerance ? (
          <StatusBadge
            status="green"
            label={`${line.deviation.delta_percent}%`}
            size="sm"
          />
        ) : (
          <StatusBadge
            status="red"
            label={`${line.deviation.delta_percent}%`}
            reason={`${line.deviation.delta_kg} kg outside the batch tolerance`}
            size="sm"
          />
        )}
      </td>

      <td className="py-2 pr-4 text-xs text-slate-600">
        {line.lot_number ?? <Absent what="no lot recorded" />}
        {line.lot_status !== null && (
          <span className="block text-slate-500">{line.lot_status}</span>
        )}
      </td>

      <td className="py-2">
        {canWeigh ? (
          <form
            className="flex items-center gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              if (mass.trim().length > 0) {
                onWeigh(line.id, mass.trim());
                setMass("");
              }
            }}
          >
            <label className="sr-only" htmlFor={`mass-${line.id}`}>
              Actual mass in kilograms for {line.material_code}
            </label>
            {/*
              `inputMode="decimal"` with a TEXT input, not `type="number"`.
              A number input hands back a JavaScript number and would destroy
              the stored scale of a controlled mass before it ever left the
              browser — the exact defect `_decimal_strings` was written to fix
              on the server side.
            */}
            <input
              id={`mass-${line.id}`}
              type="text"
              inputMode="decimal"
              value={mass}
              onChange={(e) => setMass(e.target.value)}
              placeholder="kg"
              className="w-24 rounded border border-slate-300 px-2 py-1 text-sm tabular-nums"
            />
            <button type="submit" className={BUTTON_QUIET} disabled={pending}>
              {line.actual_mass_kg === null ? "Weigh" : "Correct"}
            </button>
          </form>
        ) : (
          <span className="text-xs text-slate-500">
            {line.weighed_at === null ? "—" : line.weighed_at.slice(0, 16).replace("T", " ")}
          </span>
        )}
      </td>
    </tr>
  );
}

function BatchWorkspace({ batch }: { batch: BatchDetail }) {
  const actions = useBatchActions(batch.id);
  const d = batchStatus(batch.status);

  const unweighed = batch.components.filter((c) => c.actual_mass_kg === null).length;
  // The statuses the server accepts a weighing in (`_RECORDABLE` in the
  // service). Offered from the status, refused by the server — never both.
  const canWeigh = ["in_progress", "weighing", "mixing"].includes(batch.status);

  const [deviation, setDeviation] = useState({ description: "", severity: "minor" });
  const [sample, setSample] = useState({ sample_number: "", quantity_g: "", purpose: "" });
  const [parameter, setParameter] = useState({ parameter_code: "", value: "", unit: "" });
  const [reviewNote, setReviewNote] = useState("");

  return (
    <div className="space-y-8">
      {/* ---------------------------------------------------------------- */}
      {/* Header                                                            */}
      {/* ---------------------------------------------------------------- */}
      <section className={CARD}>
        <div className="flex flex-wrap items-baseline gap-3">
          <span className="text-xs font-medium tabular-nums text-slate-500">
            {batch.batch_number}
          </span>
          {/*
            Spread, not destructured into props. `StatusBadgeInput` is a
            discriminated union in which a yellow MUST carry a reason —
            "an unexplained yellow cannot be written in the first place" —
            and rebuilding the props by hand is what loses that guarantee.
            `batchStatus` returns the union already satisfied.
          */}
          <StatusBadge {...d} size="sm" />
        </div>

        <dl className="mt-3 flex flex-wrap gap-x-6 gap-y-1 text-xs text-slate-600">
          <div className="flex gap-1.5">
            <dt className="font-medium text-slate-500">Planned</dt>
            <dd className="tabular-nums">
              {batch.planned_quantity_kg} kg
              <span className="text-slate-400"> ±{batch.tolerance_percent}%</span>
            </dd>
          </div>
          <div className="flex gap-1.5">
            <dt className="font-medium text-slate-500">Unweighed</dt>
            <dd className="tabular-nums">
              {unweighed > 0 ? (
                <span className="font-semibold text-status-conditional">
                  {unweighed} of {batch.components.length}
                </span>
              ) : (
                `0 of ${batch.components.length}`
              )}
            </dd>
          </div>
          <div className="flex gap-1.5">
            <dt className="font-medium text-slate-500">Started</dt>
            <dd>{batch.started_at?.slice(0, 10) ?? <Absent what="not started" />}</dd>
          </div>
          <div className="flex gap-1.5">
            <dt className="font-medium text-slate-500">Completed</dt>
            <dd>{batch.completed_at?.slice(0, 10) ?? <Absent what="not completed" />}</dd>
          </div>
        </dl>

        {batch.purpose !== null && (
          <p className="mt-3 max-w-3xl text-sm text-slate-700">{batch.purpose}</p>
        )}
        {batch.review_note !== null && (
          <p className="mt-3 max-w-3xl rounded bg-slate-50 p-2 text-sm text-slate-700">
            <span className="font-medium">Review note: </span>
            {batch.review_note}
          </p>
        )}

        {/* The lifecycle, as the steps this status actually permits. */}
        <div className="mt-4 flex flex-wrap items-center gap-2">
          {batch.status === "draft" && (
            <button
              type="button"
              className={BUTTON}
              onClick={actions.authorize}
              disabled={actions.isPending}
            >
              Issue weigh-up sheet
            </button>
          )}
          {batch.status === "authorized" && (
            <button
              type="button"
              className={BUTTON}
              onClick={actions.start}
              disabled={actions.isPending}
            >
              Start execution
            </button>
          )}
          {canWeigh && (
            <button
              type="button"
              className={BUTTON}
              onClick={actions.complete}
              disabled={actions.isPending}
              // NOT disabled on `unweighed > 0`. The SERVER refuses while any
              // line is unweighed, and it owns that rule; a button disabled
              // here would be a second copy of it, free to drift. The title
              // explains, the server enforces.
              title={
                unweighed > 0
                  ? `${unweighed} line(s) still unweighed — the server will refuse`
                  : undefined
              }
            >
              Close execution
            </button>
          )}
          {(batch.status === "completed" || batch.status === "under_review") && (
            <>
              <button
                type="button"
                className={BUTTON}
                onClick={() => actions.review({ decision: "accept", note: reviewNote || undefined })}
                disabled={actions.isPending}
              >
                Accept for testing
              </button>
              <button
                type="button"
                className={BUTTON_QUIET}
                onClick={() => actions.review({ decision: "reject", note: reviewNote || undefined })}
                disabled={actions.isPending}
              >
                Reject — process deviation
              </button>
              <label className="sr-only" htmlFor="review-note">
                Review note
              </label>
              <input
                id="review-note"
                type="text"
                value={reviewNote}
                onChange={(e) => setReviewNote(e.target.value)}
                placeholder="Review note (optional)"
                className="min-w-[16rem] flex-1 rounded border border-slate-300 px-2 py-1.5 text-sm"
              />
            </>
          )}
        </div>

        {/*
          The server's refusal, verbatim. A 409 here is not a bug — it is the
          state machine saying this step is not available yet, and the message
          names the batch and its status. Swallowing it and greying a button
          would hide the only explanation the user gets.
        */}
        {actions.error !== null && (
          <p role="alert" className="mt-3 text-sm text-red-700">
            {actions.error.message}
          </p>
        )}
      </section>

      {/* ---------------------------------------------------------------- */}
      {/* The weigh-up sheet                                                */}
      {/* ---------------------------------------------------------------- */}
      <section aria-labelledby="sheet-heading">
        <h2 id="sheet-heading" className="text-sm font-semibold text-slate-900">
          Weigh-up sheet
        </h2>
        <p className="mt-1 max-w-3xl text-sm text-slate-600">
          Planned quantities froze when the sheet was issued. The deviation on
          each line is computed by the server against this batch&rsquo;s
          tolerance at read time — it is not stored, so a correction is
          reflected immediately rather than leaving a stale figure behind.
        </p>

        {batch.components.length === 0 ? (
          <p className="mt-2 text-sm text-slate-600">
            No components on this sheet. A batch with no lines cannot be
            executed; the formula version it was created from had no
            composition.
          </p>
        ) : (
          <div className="mt-2 overflow-x-auto">
            <table className="w-full min-w-[52rem] text-left text-sm">
              <caption className="sr-only">
                Planned against actual mass for every component of batch{" "}
                {batch.batch_number}
              </caption>
              <thead>
                <tr className="border-b border-slate-300 text-xs uppercase tracking-wide text-slate-500">
                  <th scope="col" className="py-2 pr-4 font-medium">Material</th>
                  <th scope="col" className="py-2 pr-4 font-medium">Planned kg</th>
                  <th scope="col" className="py-2 pr-4 font-medium">Actual kg</th>
                  <th scope="col" className="py-2 pr-4 font-medium">Deviation</th>
                  <th scope="col" className="py-2 pr-4 font-medium">Lot</th>
                  <th scope="col" className="py-2 font-medium">
                    {canWeigh ? "Record" : "Weighed"}
                  </th>
                </tr>
              </thead>
              <tbody>
                {batch.components.map((line) => (
                  <ComponentRow
                    key={line.id}
                    line={line}
                    canWeigh={canWeigh}
                    pending={actions.isPending}
                    onWeigh={(componentId, mass) =>
                      actions.weigh(componentId, { actual_mass_kg: mass })
                    }
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* ---------------------------------------------------------------- */}
      {/* Process parameters                                                */}
      {/* ---------------------------------------------------------------- */}
      <section aria-labelledby="process-heading">
        <h2 id="process-heading" className="text-sm font-semibold text-slate-900">
          Process data
        </h2>
        <p className="mt-1 max-w-3xl text-sm text-slate-600">
          Mixing RPM, mixing time, temperature, vacuum. Recorded as{" "}
          <strong>value and unit</strong>, never a free string — §5, and the
          reason scale-up can be re-derived later rather than guessed.
        </p>

        {batch.process_parameters.length === 0 ? (
          <p className="mt-2 text-sm text-slate-600">Nothing recorded.</p>
        ) : (
          <ul className="mt-2 flex flex-wrap gap-2">
            {batch.process_parameters.map((p) => (
              <li key={p.id} className="rounded border border-slate-200 bg-white px-3 py-1.5 text-sm">
                <span className="font-medium text-slate-900">{p.parameter_code}</span>{" "}
                <span className="tabular-nums text-slate-900">{p.value}</span>{" "}
                <span className="text-slate-600">{p.unit}</span>
                {p.stage !== null && <span className="text-slate-500"> · {p.stage}</span>}
              </li>
            ))}
          </ul>
        )}

        {canWeigh && (
          <form
            className="mt-3 flex flex-wrap items-end gap-3"
            onSubmit={(e) => {
              e.preventDefault();
              if (parameter.parameter_code && parameter.value && parameter.unit) {
                actions.addProcessParameter(parameter);
                setParameter({ parameter_code: "", value: "", unit: "" });
              }
            }}
          >
            <div className="w-40">
              <label className={LABEL} htmlFor="param-code">Parameter</label>
              <input
                id="param-code"
                className={INPUT}
                value={parameter.parameter_code}
                onChange={(e) => setParameter({ ...parameter, parameter_code: e.target.value })}
                placeholder="MIX_RPM"
              />
            </div>
            <div className="w-28">
              <label className={LABEL} htmlFor="param-value">Value</label>
              <input
                id="param-value"
                className={`${INPUT} tabular-nums`}
                inputMode="decimal"
                value={parameter.value}
                onChange={(e) => setParameter({ ...parameter, value: e.target.value })}
              />
            </div>
            <div className="w-24">
              <label className={LABEL} htmlFor="param-unit">Unit</label>
              <input
                id="param-unit"
                className={INPUT}
                value={parameter.unit}
                onChange={(e) => setParameter({ ...parameter, unit: e.target.value })}
                placeholder="rpm"
              />
            </div>
            <button type="submit" className={BUTTON_QUIET} disabled={actions.isPending}>
              Record
            </button>
          </form>
        )}
      </section>

      {/* ---------------------------------------------------------------- */}
      {/* Deviations                                                        */}
      {/* ---------------------------------------------------------------- */}
      <section aria-labelledby="deviation-heading">
        <h2 id="deviation-heading" className="text-sm font-semibold text-slate-900">
          Deviations
        </h2>
        <p className="mt-1 max-w-3xl text-sm text-slate-600">
          Anything that departed from the procedure. The person at the bench and
          the person reviewing may both raise one — a deviation noticed at
          review is the evidence the review exists to act on, and refusing it
          there would push it onto paper.
        </p>

        {batch.deviations.length === 0 ? (
          <p className="mt-2 text-sm text-slate-600">None recorded.</p>
        ) : (
          <ul className="mt-2 space-y-2">
            {batch.deviations.map((dev) => (
              <li key={dev.id} className={CARD}>
                <div className="flex flex-wrap items-baseline gap-2">
                  {/*
                    A minor deviation is amber WITH its reason; anything
                    above it is red. Written as two branches because the
                    badge's union requires the reason on the amber one, and
                    a ternary inside the props would defeat that check.
                  */}
                  {dev.severity === "minor" ? (
                    <StatusBadge
                      status="yellow"
                      label="MINOR"
                      reason="recorded against the batch; it does not by itself stop testing"
                      size="sm"
                    />
                  ) : (
                    <StatusBadge
                      status="red"
                      label={dev.severity.toUpperCase()}
                      reason="a chemist must decide whether this batch may proceed"
                      size="sm"
                    />
                  )}
                  <span className="text-xs text-slate-500">
                    {dev.raised_at.slice(0, 16).replace("T", " ")}
                  </span>
                </div>
                <p className="mt-1 text-sm text-slate-800">{dev.description}</p>
                {dev.resolution !== null && (
                  <p className="mt-1 text-sm text-slate-600">
                    <span className="font-medium">Resolution: </span>
                    {dev.resolution}
                  </p>
                )}
              </li>
            ))}
          </ul>
        )}

        <form
          className="mt-3 flex flex-wrap items-end gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            if (deviation.description.trim().length >= 3) {
              actions.addDeviation(deviation);
              setDeviation({ description: "", severity: "minor" });
            }
          }}
        >
          <div className="min-w-[20rem] flex-1">
            <label className={LABEL} htmlFor="dev-description">What departed from the procedure</label>
            <input
              id="dev-description"
              className={INPUT}
              value={deviation.description}
              onChange={(e) => setDeviation({ ...deviation, description: e.target.value })}
            />
          </div>
          <div className="w-36">
            <label className={LABEL} htmlFor="dev-severity">Severity</label>
            <select
              id="dev-severity"
              className={INPUT}
              value={deviation.severity}
              onChange={(e) => setDeviation({ ...deviation, severity: e.target.value })}
            >
              <option value="minor">minor</option>
              <option value="major">major</option>
              <option value="critical">critical</option>
            </select>
          </div>
          <button type="submit" className={BUTTON_QUIET} disabled={actions.isPending}>
            Raise deviation
          </button>
        </form>
      </section>

      {/* ---------------------------------------------------------------- */}
      {/* Samples                                                           */}
      {/* ---------------------------------------------------------------- */}
      <section aria-labelledby="sample-heading">
        <h2 id="sample-heading" className="text-sm font-semibold text-slate-900">
          Samples
        </h2>
        <p className="mt-1 max-w-3xl text-sm text-slate-600">
          A sample is the physical thing a test result is traced back to. §2:
          no test result without traceability to the sample that produced it.
        </p>

        {batch.samples.length === 0 ? (
          <p className="mt-2 text-sm text-slate-600">
            None taken. Nothing from this batch can be tested until one is.
          </p>
        ) : (
          <ul className="mt-2 flex flex-wrap gap-2">
            {batch.samples.map((s) => (
              <li key={s.id} className="rounded border border-slate-200 bg-white px-3 py-1.5 text-sm">
                <span className="font-medium tabular-nums text-slate-900">
                  {s.sample_number}
                </span>
                <span className="text-slate-600">
                  {s.quantity_g !== null && ` · ${s.quantity_g} g`}
                  {` · ${s.status}`}
                </span>
                {s.purpose !== null && (
                  <span className="block text-xs text-slate-500">{s.purpose}</span>
                )}
              </li>
            ))}
          </ul>
        )}

        <form
          className="mt-3 flex flex-wrap items-end gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            if (sample.sample_number.trim().length >= 3) {
              actions.addSample({
                sample_number: sample.sample_number.trim(),
                // Omitted rather than sent empty: the server treats absence as
                // "not recorded" and "" as a validation failure.
                quantity_g: sample.quantity_g.trim() || undefined,
                purpose: sample.purpose.trim() || undefined,
              });
              setSample({ sample_number: "", quantity_g: "", purpose: "" });
            }
          }}
        >
          <div className="w-48">
            <label className={LABEL} htmlFor="sample-number">Sample number</label>
            <input
              id="sample-number"
              className={INPUT}
              value={sample.sample_number}
              onChange={(e) => setSample({ ...sample, sample_number: e.target.value })}
              placeholder="SMP-0001"
            />
          </div>
          <div className="w-28">
            <label className={LABEL} htmlFor="sample-qty">Quantity g</label>
            <input
              id="sample-qty"
              className={`${INPUT} tabular-nums`}
              inputMode="decimal"
              value={sample.quantity_g}
              onChange={(e) => setSample({ ...sample, quantity_g: e.target.value })}
            />
          </div>
          <div className="min-w-[14rem] flex-1">
            <label className={LABEL} htmlFor="sample-purpose">Purpose</label>
            <input
              id="sample-purpose"
              className={INPUT}
              value={sample.purpose}
              onChange={(e) => setSample({ ...sample, purpose: e.target.value })}
            />
          </div>
          <button type="submit" className={BUTTON_QUIET} disabled={actions.isPending}>
            Take sample
          </button>
        </form>
      </section>
    </div>
  );
}

function BatchScreen() {
  const params = useSearchParams();
  const batchId = params.get("id") ?? "";
  const { data, isLoading, error, unavailable } = useBatch(batchId);

  return (
    <LiveOnlyPage
      title="Batch"
      lede="The weigh-up sheet, what was actually weighed against it, and every
            step from issuing the sheet to a chemist accepting the batch for
            testing."
      unavailable={unavailable}
    >
      <p className="mb-4 text-sm">
        <Link href="/laboratory" className="text-slate-600 underline hover:text-slate-900">
          ← Back to the batch queue
        </Link>
      </p>

      {batchId.length === 0 ? (
        <p className="text-sm text-slate-600">
          No batch chosen. Open one from the{" "}
          <Link href="/laboratory" className="underline">
            batch queue
          </Link>
          .
        </p>
      ) : error !== null ? (
        <DataSourceError error={error} />
      ) : unavailable !== null ? (
        <p className="text-sm text-slate-600">
          This batch cannot be shown until this build is pointed at an API.
        </p>
      ) : data === undefined ? (
        <p className="text-sm text-slate-600">
          {isLoading ? "Loading the batch…" : "That batch could not be found."}
        </p>
      ) : (
        <BatchWorkspace batch={data} />
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
export default function BatchPage() {
  return (
    <Suspense fallback={<p className="p-6 text-sm text-slate-600">Loading the batch…</p>}>
      <BatchScreen />
    </Suspense>
  );
}
