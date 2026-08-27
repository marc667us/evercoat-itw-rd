"use client";

/**
 * Formulations — one version, live.
 *
 * 🔴 WHY THIS EXISTS BESIDE `/formulations/[code]`.
 *
 * `app/formulations/[code]` renders `lib/demo/dataset.ts` — a BUILD-TIME
 * fixture — and structurally cannot do anything else. Under
 * `output: "export"` a `[code]` route must enumerate its params at build
 * time, so it can only ever show the formulas that existed when the bundle
 * was compiled. It is a demonstration of the workspace, not the workspace.
 *
 * This screen is the workspace: it takes a live `version_id` and reads the
 * tenant's own records over HTTP.
 *
 * 🔴 AND UNTIL TODAY THE LIST COULD NOT HAND IT ONE (I86). Twelve of the
 * thirteen formulation routes are keyed by `version_id`, and `list_formulas`
 * returned the latest version's code, number and status — but never its id. A
 * `version_code` is a label, unique per formula rather than per organization,
 * so it is not a key. That missing column is the structural reason this
 * screen was never built and the fixture stood in for it. `latest_version_id`
 * was added server-side; this page is its first caller.
 *
 * 🔴 THIS FILE PERFORMS NO FORMULATION ARITHMETIC. Not one subtraction.
 *
 * Every number shown — total percentage, theoretical density, binder/filler
 * ratio, solids, VOC, cost, every weigh-up mass, and **both delta columns** —
 * is computed by the Python engine and arrives already decided. `CLAUDE.md`
 * rule 2 gives deterministic scientific calculation to Python, and this
 * project has now caught `fraction * 100` in a React component, a percentage
 * delta in a React component, and the same delta in a build script. The rule
 * that keeps catching them is that the arithmetic has exactly one home.
 *
 * If a figure is missing, the fix is in the engine or the API — never a
 * calculation added here.
 *
 * 🔴 EVERY MEASUREMENT IS A STRING AND IS RENDERED VERBATIM (I84). Component
 * percentages, densities, costs and derived properties were all leaving the
 * API as **floats** until this screen was written and something finally
 * parsed them — `theoretical_density_g_cm3` arrived as
 * `1.0906918323011936`, sixteen digits of binary-float noise in place of a
 * `Decimal` quantized to four. No `Number()`, no `toFixed`, no `parseFloat`.
 *
 * 🔴 A PROPERTY IS A VALUE **OR** A STATED REASON IT COULD NOT BE COMPUTED.
 * Never a blank cell. The engine raises "density unknown for: RM-FIL-07" and
 * the API carries that sentence through as `unavailable_reason`, because a
 * blank would leave a chemist believing the property had been calculated and
 * had come out empty.
 */

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { DataSourceError, LiveOnlyPage } from "@/components/ui/data-source-banner";
import { serverMessage } from "@/lib/api/client";
import { Absent } from "@/components/ui/record-link";
import { StatusBadge, type StatusBadgeInput } from "@/components/ui/status-badge";
import {
  type ComparisonRow,
  type DerivedProperty,
  type FormulaComponent,
  type FormulaVersionDetail,
  type RevisionDriver,
  type VersionComparison,
  type VersionEvaluation,
} from "@/lib/api/formulations";
import { permits, usePermissions } from "@/lib/permissions";
import {
  useClassifications,
  useClassifyFormula,
  useCreateBatch,
  useFormulaActions,
  useFormulaComparison,
  useFormulaEvaluation,
  useFormulaVersion,
  useWeighUp,
} from "@/lib/api/hooks";

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

function words(value: string): string {
  return value.replace(/_/g, " ");
}

/** The human name and unit for each derived property the engine returns. */
const PROPERTY_LABELS: Record<string, { name: string; unit: string }> = {
  total_percentage: { name: "Total", unit: "%" },
  theoretical_density_g_cm3: { name: "Theoretical density", unit: "g/cm³" },
  binder_to_filler_ratio: { name: "Binder : filler", unit: "" },
  solids_content_pct: { name: "Solids content", unit: "%" },
  voc_content_g_per_l: { name: "VOC content", unit: "g/L" },
  raw_material_cost_per_kg: { name: "Raw-material cost", unit: "/kg" },
};

/**
 * A version's lifecycle status.
 *
 * `draft` is neutral rather than amber: a draft is work in progress, not a
 * problem, and a screen where everything unfinished is amber teaches people
 * to ignore amber — which is the colour that matters on a test result.
 */
function versionStatus(status: string): StatusBadgeInput {
  switch (status) {
    case "approved":
      return { status: "green", label: "APPROVED" };
    case "released":
      return { status: "green", label: "RELEASED" };
    case "rejected":
      return {
        status: "red",
        label: "REJECTED",
        reason: "this version does not proceed",
      };
    case "submitted":
      return {
        status: "yellow",
        label: "SUBMITTED",
        reason: "awaiting approval — the composition is frozen",
      };
    case "superseded":
      return { status: "neutral", label: "SUPERSEDED" };
    default:
      return { status: "neutral", label: words(status).toUpperCase() };
  }
}

/**
 * One derived property.
 *
 * 🔴 THE UNAVAILABLE CASE IS THE IMPORTANT ONE and it is rendered as the
 * engine's own sentence, not as a dash. "density unknown for: RM-FIL-07" tells
 * a chemist exactly which line to fix; an empty cell tells them nothing and
 * looks like a computed blank.
 */
function PropertyCell({
  propertyKey,
  property,
}: {
  propertyKey: string;
  property: DerivedProperty;
}) {
  const meta = PROPERTY_LABELS[propertyKey] ?? {
    name: words(propertyKey),
    unit: "",
  };

  return (
    <div className={CARD}>
      <h3 className={LABEL}>{meta.name}</h3>
      {property.value === null ? (
        <p className="mt-1 text-xs text-amber-800">
          <span aria-hidden>⊘ </span>
          Not calculated — {property.unavailable_reason ?? "no reason given"}
        </p>
      ) : (
        <p className="mt-1 text-sm font-semibold tabular-nums text-slate-900">
          {/* Verbatim. The string IS the value. */}
          {property.value}
          {meta.unit && <span className="ml-1 text-xs font-normal text-slate-600">{meta.unit}</span>}
        </p>
      )}
    </div>
  );
}

/** One composition line. */
function ComponentRow({ line }: { line: FormulaComponent }) {
  return (
    <tr className="border-b border-slate-100 align-top">
      <td className="py-2 pr-4">
        <span className="font-medium tabular-nums text-slate-900">{line.material_code}</span>
        <span className="block text-xs text-slate-600">{line.material_name}</span>
      </td>
      <td className="py-2 pr-4 text-xs text-slate-600">
        {line.effective_role ?? <Absent what="no role" />}
      </td>
      <td className="py-2 pr-4 tabular-nums text-slate-900">{line.percentage}</td>
      <td className="py-2 pr-4 tabular-nums text-slate-700">
        {line.density_g_cm3 ?? <Absent what="unknown" />}
      </td>
      <td className="py-2 pr-4">
        {/*
          A restricted or obsolete material is a submission block, and the
          chemist needs to see WHICH line caused it rather than only that the
          formula was refused.
        */}
        {line.material_status === "approved" ? (
          <span className="text-xs text-slate-600">approved</span>
        ) : (
          <StatusBadge
            status="yellow"
            label={words(line.material_status).toUpperCase()}
            reason="this material status can block submission"
            size="sm"
          />
        )}
      </td>
      <td className="py-2 tabular-nums text-slate-700">
        {/*
          ABSENT means "not permitted to see cost"; null means "permitted, none
          recorded". The server removes the key rather than nulling it, and the
          two are rendered differently because they are different facts.
        */}
        {line.cost_per_kg === undefined ? (
          <Absent what="cost not visible to you" />
        ) : (
          (line.cost_per_kg ?? <Absent what="none recorded" />)
        )}
      </td>
    </tr>
  );
}

/** One row of the difference engine. */
function ComparisonRowView({ row }: { row: ComparisonRow }) {
  return (
    <tr className="border-b border-slate-100">
      <td className="py-2 pr-4">
        <span className="font-medium tabular-nums text-slate-900">{row.material_code}</span>
        <span className="block text-xs text-slate-600">{row.material_name}</span>
      </td>
      <td className="py-2 pr-4 tabular-nums text-slate-700">
        {row.previous_percentage ?? <Absent what="not present" />}
      </td>
      <td className="py-2 pr-4 tabular-nums text-slate-900">
        {row.new_percentage ?? <Absent what="removed" />}
      </td>
      {/*
        🔴 BOTH DELTAS COME FROM THE PYTHON ENGINE. `null` here is not zero:
        an added or removed component HAS no delta, and printing one would
        claim it "increased by 2.5 points" when it was not there to increase.
      */}
      <td className="py-2 pr-4 tabular-nums text-slate-900">
        {row.delta ?? <Absent what="—" />}
      </td>
      <td className="py-2 pr-4 tabular-nums text-slate-700">
        {row.percent_delta === null ? <Absent what="—" /> : `${row.percent_delta}%`}
      </td>
      <td className="py-2 text-xs text-slate-600">{row.change}</td>
    </tr>
  );
}

function DifferencePanel({ comparison }: { comparison: VersionComparison }) {
  const changed = comparison.components.filter((c) => c.change !== "unchanged");

  return (
    <>
      <dl className="grid gap-x-6 gap-y-2 text-xs sm:grid-cols-2">
        <div>
          <dt className="font-medium text-slate-500">Change reason</dt>
          <dd className="text-slate-800">
            {comparison.change_reason ?? <Absent what="none recorded" />}
          </dd>
        </div>
        <div>
          <dt className="font-medium text-slate-500">Technical hypothesis</dt>
          <dd className="text-slate-800">
            {comparison.technical_hypothesis ?? <Absent what="none recorded" />}
          </dd>
        </div>
        <div>
          <dt className="font-medium text-slate-500">Expected effect</dt>
          <dd className="text-slate-800">
            {comparison.expected_effect ?? <Absent what="none recorded" />}
          </dd>
        </div>
        <div>
          {/*
            🔴 THE FIELD THAT CLOSES THE SCIENTIFIC LOOP, AND ITS ABSENCE IS
            HONEST. `expected_effect` is a prediction made before the work;
            `observed_effect` is the outcome. They are separate columns so a
            hypothesis can never be quietly rewritten into a result once the
            answer is known.
          */}
          <dt className="font-medium text-slate-500">Observed effect</dt>
          <dd className="text-slate-800">
            {comparison.observed_effect ?? (
              <Absent what="the laboratory has not reported yet" />
            )}
          </dd>
        </div>
      </dl>

      <p className="mt-3 text-xs text-slate-600">
        {changed.length === 0
          ? "No component differs between these two versions."
          : `${changed.length} of ${comparison.components.length} components differ.`}
      </p>

      <div className="mt-2 overflow-x-auto">
        <table className="w-full min-w-[42rem] text-left text-sm">
          <thead>
            <tr className="border-b border-slate-300 text-xs uppercase tracking-wide text-slate-600">
              <th className="py-2 pr-4 font-medium">Material</th>
              <th className="py-2 pr-4 font-medium">Old %</th>
              <th className="py-2 pr-4 font-medium">New %</th>
              <th className="py-2 pr-4 font-medium">Δ points</th>
              <th className="py-2 pr-4 font-medium">Δ relative</th>
              <th className="py-2 font-medium">Change</th>
            </tr>
          </thead>
          <tbody>
            {comparison.components.map((c) => (
              <ComparisonRowView key={c.material_code} row={c} />
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

/**
 * The weigh-up sheet.
 *
 * A POST that writes nothing: the batch mass is an input, so it cannot be a
 * GET, but it is a read. Its result is held here rather than in the query
 * cache because it is a question the user asks on demand.
 */
function WeighUpPanel({ versionId }: { versionId: string }) {
  const [mass, setMass] = useState("10");
  const sheet = useWeighUp(versionId);

  return (
    <>
      <div className="flex flex-wrap items-end gap-2">
        <div>
          <label className={LABEL} htmlFor="batch-mass">
            Batch mass (kg)
          </label>
          {/*
            Text, not `type="number"`. A number input lets the browser
            normalise "10.500" to "10.5", and the recorded scale would be gone
            before the request was made.
          */}
          <input
            id="batch-mass"
            className={INPUT + " w-32"}
            inputMode="decimal"
            value={mass}
            onChange={(e) => setMass(e.target.value)}
          />
        </div>
        <button
          type="button"
          className={BUTTON_QUIET}
          disabled={sheet.isPending || mass.trim() === ""}
          onClick={() => sheet.run(mass.trim())}
        >
          Scale the formula
        </button>
      </div>

      {sheet.error !== null && (
        <p
          role="alert"
          className="mt-3 rounded border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-900"
        >
          {/*
            The server's own sentence. It refuses an off-100% formula and
            explains why, which is far more useful than "could not scale".
          */}
          {serverMessage(sheet.error)}
        </p>
      )}

      {sheet.error === null && sheet.data !== null && (
        <div className="mt-3 overflow-x-auto">
          <p className="mb-2 text-xs text-slate-600">
            Masses for <span className="tabular-nums">{sheet.data.batch_mass_kg}</span> kg.
            They sum exactly to the batch mass — the engine places the rounding remainder
            on the largest line, so <strong>do not re-add them here</strong>.
          </p>
          <table className="w-full min-w-[28rem] text-left text-sm">
            <thead>
              <tr className="border-b border-slate-300 text-xs uppercase tracking-wide text-slate-600">
                <th className="py-2 pr-4 font-medium">Material</th>
                <th className="py-2 pr-4 font-medium">%</th>
                <th className="py-2 font-medium">Mass (kg)</th>
              </tr>
            </thead>
            <tbody>
              {sheet.data.lines.map((l) => (
                <tr key={l.material_code} className="border-b border-slate-100">
                  <td className="py-2 pr-4">
                    <span className="font-medium tabular-nums text-slate-900">
                      {l.material_code}
                    </span>
                    <span className="block text-xs text-slate-600">{l.material_name}</span>
                  </td>
                  <td className="py-2 pr-4 tabular-nums text-slate-700">{l.percentage}</td>
                  <td className="py-2 tabular-nums text-slate-900">{l.mass_kg}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

/**
 * Create a lab batch from THIS version.
 *
 * 🔴 THE CONTROL LIVES HERE BECAUSE THE VERSION ID DOES. `POST /batches`
 * needs a `formula_version_id`, and the batch queue is the one screen that
 * does not have one — which is why `POST /api/laboratory/batches` sat with no
 * caller while the other ten laboratory routes had one, and every batch on
 * screen had been written by a seeding script. §2's thread runs formula
 * version -> batch; putting the control where the version already is means
 * the link is never typed by hand and never typed wrong.
 */
function CreateBatchPanel({
  versionId,
  versionCode,
}: {
  versionId: string;
  versionCode: string;
}) {
  const [number, setNumber] = useState("");
  const [mass, setMass] = useState("");
  const batch = useCreateBatch();
  const permissions = usePermissions();

  // `POST /api/laboratory/batches` declares `batch.create` — the Chemist's
  // permission, not the Technician's. The technician EXECUTES a batch that
  // somebody else authorised, which is the separation §9 is built around and
  // which this panel used to render identically for both.
  if (!permits(permissions, "batch.create")) {
    return null;
  }

  return (
    <>
      <div className="flex flex-wrap items-end gap-2">
        <div>
          <label className={LABEL} htmlFor="batch-number">
            Batch number
          </label>
          <input
            id="batch-number"
            className={INPUT + " w-48"}
            value={number}
            onChange={(e) => setNumber(e.target.value)}
            placeholder="LB-2026-001"
          />
        </div>
        <div>
          <label className={LABEL} htmlFor="planned-kg">
            Planned quantity (kg)
          </label>
          {/* Text, not number — a controlled mass keeps its recorded scale. */}
          <input
            id="planned-kg"
            className={INPUT + " w-36"}
            inputMode="decimal"
            value={mass}
            onChange={(e) => setMass(e.target.value)}
            placeholder="10.0000"
          />
        </div>
        <button
          type="button"
          className={BUTTON}
          disabled={batch.isPending || number.trim().length < 3 || mass.trim() === ""}
          onClick={() =>
            batch.create({
              formula_version_id: versionId,
              batch_number: number.trim(),
              planned_quantity_kg: mass.trim(),
              purpose: `Batch of ${versionCode}`,
            })
          }
        >
          Create batch
        </button>
      </div>

      {batch.error !== null && (
        <p
          role="alert"
          className="mt-3 rounded border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-900"
        >
          {serverMessage(batch.error)}
        </p>
      )}
      {batch.error === null && batch.created !== null && (
        <p role="status" className="mt-3 text-sm text-slate-700">
          Created.{" "}
          <Link
            href={`/laboratory/batch?id=${batch.created.id}`}
            className="font-medium underline underline-offset-2"
          >
            Open it on the bench →
          </Link>
        </p>
      )}
    </>
  );
}

/**
 * Reclassify the formula.
 *
 * ⚠️ THE LEVELS COME FROM THE SERVER, IN RANK ORDER. Free text here would
 * make a confidentiality decision available to a typo, and the export ceiling
 * is a rank comparison — so the order shown is the order that matters.
 * `reason` is mandatory server-side and audited.
 */
function ClassifyPanel({ formulaId }: { formulaId: string }) {
  const levels = useClassifications();
  const [code, setCode] = useState("");
  const [reason, setReason] = useState("");
  const classify = useClassifyFormula(formulaId);
  const permissions = usePermissions();

  const options = levels.data ?? [];

  // `formula.classify` — held by the Administrator, Lead, QA and Director, and
  // not by the Chemist who wrote the formula. Confidentiality is somebody
  // else's decision, and the screen now says so by not offering the control.
  if (!permits(permissions, "formula.classify")) {
    return null;
  }

  return (
    <>
      <div className="flex flex-wrap items-end gap-2">
        <div>
          <label className={LABEL} htmlFor="classification">
            Classification
          </label>
          <select
            id="classification"
            className={INPUT + " w-56"}
            value={code}
            onChange={(e) => setCode(e.target.value)}
          >
            <option value="">
              {levels.isLoading ? "Loading levels…" : "Choose a level"}
            </option>
            {options.map((c) => (
              <option key={c.code} value={c.code}>
                {c.code}
              </option>
            ))}
          </select>
        </div>
        <div className="flex-1">
          <label className={LABEL} htmlFor="classify-reason">
            Reason (required, and audited)
          </label>
          <input
            id="classify-reason"
            className={INPUT}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="why this level is correct now"
          />
        </div>
        <button
          type="button"
          className={BUTTON_QUIET}
          disabled={classify.isPending || code === "" || reason.trim().length < 3}
          onClick={() => classify.classify({ classification: code, reason: reason.trim() })}
        >
          Reclassify
        </button>
      </div>

      {levels.error !== null && <DataSourceError error={levels.error} />}
      {classify.error !== null && (
        <p
          role="alert"
          className="mt-3 rounded border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-900"
        >
          {serverMessage(classify.error)}
        </p>
      )}
      {classify.error === null && classify.done && (
        <p role="status" className="mt-3 text-sm text-slate-700">
          Classification recorded.
        </p>
      )}
    </>
  );
}

function FormulaWorkspace({
  version,
  evaluation,
  evaluationError,
  evaluationLoading,
}: {
  version: FormulaVersionDetail;
  evaluation: VersionEvaluation | undefined;
  evaluationError: Error | null;
  evaluationLoading: boolean;
}) {
  const actions = useFormulaActions(version.id);
  const comparison = useFormulaComparison(version.id, version.parent_version_id);
  const [reason, setReason] = useState("");
  const [hypothesis, setHypothesis] = useState("");
  const [driver, setDriver] = useState<RevisionDriver | "">("");
  const [observed, setObserved] = useState("");

  const components = [...version.components].sort(
    (a, b) => a.display_order - b.display_order,
  );

  return (
    <>
      <div className="mb-4 flex flex-wrap items-baseline gap-3">
        <h1 className="text-lg font-semibold text-slate-900">{version.version_code}</h1>
        <StatusBadge {...versionStatus(version.status)} />
        <span className="text-sm text-slate-600">
          {version.formula_code} · {version.formula_name}
        </span>
        <Link href="/formulations" className="text-sm text-slate-600 underline">
          ← all formulas
        </Link>
      </div>

      {/* ---------------------------------------------------------------- */}
      <section>
        <h2 className="text-sm font-semibold text-slate-900">Derived properties</h2>
        <p className="mt-1 text-xs text-slate-600">
          Every figure below is computed by the Python engine and rendered exactly as
          received. Nothing on this page performs formulation arithmetic.
        </p>
        {evaluationError !== null ? (
          <div className="mt-2">
            <DataSourceError error={evaluationError} />
          </div>
        ) : evaluation === undefined ? (
          <p className="mt-2 text-sm text-slate-600">
            {evaluationLoading
              ? "Calculating…"
              : "The derived properties could not be loaded."}
          </p>
        ) : Object.keys(evaluation.properties).length === 0 ? (
          <p className="mt-2 text-sm text-slate-600">
            This version has no components yet, so there is nothing to calculate.
          </p>
        ) : (
          <div className="mt-2 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {Object.entries(evaluation.properties).map(([k, p]) => (
              <PropertyCell key={k} propertyKey={k} property={p} />
            ))}
          </div>
        )}
      </section>

      {/* ---------------------------------------------------------------- */}
      {evaluation !== undefined && (
        <section className="mt-6">
          <h2 className="text-sm font-semibold text-slate-900">Submission</h2>
          {evaluation.submittable ? (
            <p className="mt-1 text-sm text-slate-700">
              <StatusBadge status="green" label="SUBMITTABLE" size="sm" /> No blocking
              condition. Submission remains subject to server-side permission.
            </p>
          ) : (
            <>
              <p className="mt-1 text-xs text-slate-600">
                Submission is <strong>hard-blocked</strong> until each of these is
                resolved. The server re-checks them on submit; this list is what it
                would say.
              </p>
              <ul className="mt-2 grid gap-2">
                {evaluation.submission_blocks.map((b) => (
                  <li
                    key={b.code}
                    className="rounded border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-slate-800"
                  >
                    <span className="font-medium">{b.code}</span> — {b.message}
                  </li>
                ))}
              </ul>
            </>
          )}
        </section>
      )}

      {/* ---------------------------------------------------------------- */}
      <section className="mt-6">
        <h2 className="text-sm font-semibold text-slate-900">
          Composition — {components.length} components
        </h2>
        <div className="mt-2 overflow-x-auto">
          <table className="w-full min-w-[44rem] text-left text-sm">
            <thead>
              <tr className="border-b border-slate-300 text-xs uppercase tracking-wide text-slate-600">
                <th className="py-2 pr-4 font-medium">Material</th>
                <th className="py-2 pr-4 font-medium">Role</th>
                <th className="py-2 pr-4 font-medium">%</th>
                <th className="py-2 pr-4 font-medium">Density</th>
                <th className="py-2 pr-4 font-medium">Material status</th>
                <th className="py-2 font-medium">Cost/kg</th>
              </tr>
            </thead>
            <tbody>
              {components.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-3 text-sm text-slate-600">
                    No components recorded on this version.
                  </td>
                </tr>
              ) : (
                components.map((c) => <ComponentRow key={c.id} line={c} />)
              )}
            </tbody>
          </table>
        </div>
      </section>

      {/* ---------------------------------------------------------------- */}
      <section className="mt-6">
        <h2 className="text-sm font-semibold text-slate-900">Weigh-up sheet</h2>
        <div className="mt-2">
          <WeighUpPanel versionId={version.id} />
        </div>
      </section>

      {/* ---------------------------------------------------------------- */}
      <section className="mt-6">
        <h2 className="text-sm font-semibold text-slate-900">
          Difference against {version.parent_version_code ?? "the parent version"}
        </h2>
        <div className="mt-2">
          {version.parent_version_id === null ? (
            <p className="text-sm text-slate-600">
              This is a first version — there is nothing to compare it against. That is
              not an error, and an empty table here would look like &ldquo;nothing
              changed&rdquo;.
            </p>
          ) : comparison.error !== null ? (
            <DataSourceError error={comparison.error} />
          ) : comparison.data === undefined ? (
            <p className="text-sm text-slate-600">
              {comparison.isLoading ? "Loading the difference…" : "No comparison available."}
            </p>
          ) : (
            <DifferencePanel comparison={comparison.data} />
          )}
        </div>
      </section>

      {/* ---------------------------------------------------------------- */}
      <section className="mt-6">
        <h2 className="text-sm font-semibold text-slate-900">Take it to the bench</h2>
        <p className="mt-1 text-xs text-slate-600">
          A lab batch is made against a formula <strong>version</strong>, which is why
          this control lives here and not on the batch queue.
        </p>
        <div className="mt-2">
          <CreateBatchPanel versionId={version.id} versionCode={version.version_code} />
        </div>
      </section>

      {/* ---------------------------------------------------------------- */}
      <section className="mt-6">
        <h2 className="text-sm font-semibold text-slate-900">Classification</h2>
        <div className="mt-2">
          <ClassifyPanel formulaId={version.formula_id} />
        </div>
      </section>

      {/* ---------------------------------------------------------------- */}
      <section className="mt-6">
        <h2 className="text-sm font-semibold text-slate-900">Lifecycle</h2>
        <p className="mt-1 text-xs text-slate-600">
          An approved formulation is <strong>never edited in place</strong>. It is
          superseded by a revision that records why. Every control is offered and the
          server decides.
        </p>

        <div className="mt-3 flex flex-wrap gap-2">
          <button
            type="button"
            className={BUTTON_QUIET}
            disabled={actions.isPending}
            onClick={() => actions.submit()}
          >
            Submit for approval
          </button>
          <button
            type="button"
            className={BUTTON_QUIET}
            disabled={actions.isPending}
            onClick={() => actions.decide({ decision: "approve" })}
          >
            Approve
          </button>
          <button
            type="button"
            className={BUTTON_QUIET}
            disabled={actions.isPending}
            onClick={() => actions.decide({ decision: "reject" })}
          >
            Reject
          </button>
        </div>

        <div className="mt-4 grid gap-3 sm:max-w-2xl">
          {/*
            🔴 THREE FIELDS, BECAUSE THE SERVER REQUIRES THREE. This form used
            to send only `change_reason` and returned 422 every time — on the
            operation this page calls "the only way a formula changes".

            `driver_type` is not defaulted here for the same reason it is not
            defaulted on the server: §2 requires a revision to show which
            objective caused it, and a default would answer that on the
            chemist's behalf.
          */}
          <div className="grid gap-2 rounded border border-slate-200 p-3">
            <p className="text-xs font-medium text-slate-700">
              Revise — an approved formula is never edited in place
            </p>
            <div>
              <label className={LABEL} htmlFor="change-reason">
                Change reason
              </label>
              <input
                id="change-reason"
                className={INPUT}
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="why this formula needs to change"
              />
            </div>
            <div>
              <label className={LABEL} htmlFor="hypothesis">
                Technical hypothesis
              </label>
              <input
                id="hypothesis"
                className={INPUT}
                value={hypothesis}
                onChange={(e) => setHypothesis(e.target.value)}
                placeholder="what you expect the change to do, and why"
              />
            </div>
            <div>
              <label className={LABEL} htmlFor="driver">
                What drove this revision
              </label>
              <select
                id="driver"
                className={INPUT}
                value={driver}
                onChange={(e) => setDriver(e.target.value as RevisionDriver)}
              >
                <option value="">Choose a driver</option>
                {(
                  [
                    "failure",
                    "requirement",
                    "optimization",
                    "cost",
                    "regulatory",
                    "customer_request",
                    "other",
                  ] as const
                ).map((d) => (
                  <option key={d} value={d}>
                    {words(d)}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <button
                type="button"
                className={BUTTON}
                disabled={
                  actions.isPending ||
                  reason.trim().length < 3 ||
                  hypothesis.trim().length < 3 ||
                  driver === ""
                }
                onClick={() =>
                  actions.revise({
                    change_reason: reason.trim(),
                    technical_hypothesis: hypothesis.trim(),
                    driver_type: driver as RevisionDriver,
                  })
                }
              >
                Create revision
              </button>
            </div>
          </div>

          <div>
            <label className={LABEL} htmlFor="observed">
              Observed effect — what actually happened
            </label>
            <input
              id="observed"
              className={INPUT}
              value={observed}
              onChange={(e) => setObserved(e.target.value)}
              placeholder="the measured outcome, not the prediction"
            />
            <button
              type="button"
              className={BUTTON_QUIET + " mt-2"}
              disabled={actions.isPending || observed.trim() === ""}
              onClick={() => actions.recordObserved(observed.trim())}
            >
              Record observed effect
            </button>
          </div>
        </div>

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
      </section>
    </>
  );
}

function FormulaScreen() {
  const params = useSearchParams();
  const versionId = params.get("version") ?? "";
  const { data, isLoading, error, unavailable } = useFormulaVersion(versionId);
  const evaluation = useFormulaEvaluation(versionId);

  return (
    <LiveOnlyPage
      title="Formula version"
      lede="One version of a controlled formulation — its composition, everything the
            engine derives from it, the weigh-up sheet, and the difference against the
            version it came from."
      unavailable={unavailable}
    >
      {versionId === "" ? (
        <p className="text-sm text-slate-600">
          No version was named. Open one from{" "}
          <Link href="/formulations" className="underline">
            the formula list
          </Link>
          .
        </p>
      ) : error !== null ? (
        <DataSourceError error={error} />
      ) : unavailable !== null ? (
        <p className="text-sm text-slate-600">
          This formula cannot be shown until this build is pointed at an API.
        </p>
      ) : data === undefined ? (
        <p className="text-sm text-slate-600">
          {isLoading ? "Loading the version…" : "That version could not be found."}
        </p>
      ) : (
        <FormulaWorkspace
          version={data}
          evaluation={evaluation.data}
          // 🔴 THE EVALUATION'S FAILURE WAS BEING DISCARDED. Only `.data` was
          // passed, so a 403 or 500 on `/evaluation` left `undefined` forever
          // and the derived-properties panel showed "Calculating…"
          // indefinitely — while the composition and weigh-up kept working, so
          // it read as a slow calculation rather than a failure. Found by the
          // Supervisor. A gap that is named is a gap; one that looks like
          // progress is a defect.
          evaluationError={evaluation.error}
          evaluationLoading={evaluation.isLoading}
        />
      )}
    </LiveOnlyPage>
  );
}

/**
 * `useSearchParams` must sit inside a Suspense boundary, and under
 * `output: "export"` Next refuses to build without one.
 */
export default function FormulaVersionPage() {
  return (
    <Suspense fallback={<p className="p-6 text-sm text-slate-600">Loading the version…</p>}>
      <FormulaScreen />
    </Suspense>
  );
}
