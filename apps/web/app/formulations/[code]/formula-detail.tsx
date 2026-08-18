"use client";

/**
 * Formula workspace.
 *
 * 🔴 THIS FILE PERFORMS NO FORMULATION ARITHMETIC. Every number it shows
 * comes from `version.computed`, produced by the Python engine at build
 * time. `CLAUDE.md` rule 2 gives deterministic scientific calculation to
 * Python; recomputing a density or even a percentage delta here would be a
 * second implementation of a controlled calculation, which is precisely
 * what that rule forbids. If a figure is missing, the fix is in the engine
 * or the build script — never a calculation added to this component.
 */

import Link from "next/link";
import { useState } from "react";

import { DemoBanner } from "@/components/ui/demo-banner";
import { EntityHeader } from "@/components/ui/entity-header";
import { KpiCard, KpiRow } from "@/components/ui/kpi-card";
import { StatusBadge } from "@/components/ui/status-badge";
import {
  currentVersion,
  formulaByCode,
  materialName,
  submissionStatus,
  userName,
  versionStatus,
  type DemoDiffRow,
  type DemoFormulaVersion,
} from "@/lib/demo/dataset";

function Section({
  id,
  title,
  note,
  children,
}: {
  id?: string;
  title: string;
  note?: string;
  children: React.ReactNode;
}) {
  return (
    <section id={id} className="mt-8 scroll-mt-4">
      <h2 className="text-sm font-semibold text-slate-900">{title}</h2>
      {note && <p className="mt-1 max-w-3xl text-xs text-slate-600">{note}</p>}
      <div className="mt-3">{children}</div>
    </section>
  );
}

export function FormulaDetail({ code }: { code: string }) {
  const formula = formulaByCode(code);

  // Which version the reader is inspecting. Defaults to the approved one,
  // never simply the newest — see `currentVersion`.
  const [selectedCode, setSelectedCode] = useState<string | null>(null);

  if (!formula) {
    return (
      <>
        <DemoBanner />
        <div className="p-6">
          <h1 className="text-xl font-semibold text-slate-900">Formula not found</h1>
          <Link
            href="/formulations"
            className="mt-3 inline-block text-sm underline underline-offset-2"
          >
            Back to formulations
          </Link>
        </div>
      </>
    );
  }

  const fallback = currentVersion(formula);
  const version: DemoFormulaVersion =
    formula.versions.find((v) => v.version_code === selectedCode) ?? fallback;
  const c = version.computed;
  const submission = submissionStatus(version);
  // Null when the version is blocked — a formula outside tolerance has no
  // weigh-up, because scaling it would print masses that contradict its own
  // stated percentages.
  const batch = c.batch;

  return (
    <>
      <DemoBanner />
      <EntityHeader
        eyebrow={`Formula ${formula.formula_code} · ${version.version_code}`}
        title={formula.name}
        crumbs={[
          { label: "Formulations", href: "/formulations" },
          { label: formula.formula_code, href: `/formulations/${formula.formula_code}` },
        ]}
        fields={[
          { label: "Project", value: formula.project_code },
          { label: "Family", value: formula.product_family },
          { label: "Owner", value: userName(formula.owner) },
          { label: "Version", value: `${version.version_code} (${version.status})` },
          { label: "Created", value: `${version.created_on} by ${userName(version.created_by)}` },
          {
            label: "Approved",
            value: version.approved_by
              ? `${version.approved_on} by ${userName(version.approved_by)}`
              : "—",
          },
        ]}
        // The yellow arm is handled explicitly because StatusBadge is a
        // DISCRIMINATED UNION that refuses a yellow without a reason —
        // §10's "a yellow with no explanation is a defect", enforced by the
        // type system rather than by review. `submissionStatus` returns only
        // green or red today; this stays correct if that changes.
        status={
          submission.status === "yellow" ? (
            <StatusBadge
              status="yellow"
              label={submission.label}
              reason={submission.reason ?? ""}
            />
          ) : (
            <StatusBadge status={submission.status} label={submission.label} />
          )
        }
      />

      <div className="p-6">
        {/* Submission blockers first. A chemist opening a draft needs to know
            why it cannot move before they read anything else about it. */}
        {c.submission_blocks.length > 0 && (
          <div className="mb-6 rounded border border-red-300 bg-red-50 p-4">
            <h2 className="text-sm font-semibold text-status-fail">
              <span aria-hidden>✕ </span>
              This version cannot be submitted
            </h2>
            <p className="mt-1 text-xs text-red-900">
              Every blocker is listed at once. A form that reveals one per attempt
              teaches a chemist to distrust the software.
            </p>
            <ul className="mt-2 space-y-1">
              {/* Keyed by code AND index: validate_for_submission emits one
                  block PER offending component, so two restricted materials
                  produce two RESTRICTED_MATERIAL entries and a code-only key
                  duplicates. Raised by the Supervisor. */}
              {c.submission_blocks.map((b, i) => (
                <li key={`${b.code}-${i}`} className="text-xs text-red-900">
                  <span className="font-mono font-semibold">{b.code}</span> —{" "}
                  {b.message}
                </li>
              ))}
            </ul>
          </div>
        )}

        <KpiRow>
          <KpiCard
            label="Theoretical density"
            value={`${c.theoretical_density_g_cm3} g/cm³`}
            href={`/formulations/${formula.formula_code}#composition`}
            context="Volume-additive. CALCULATED, never measured — see the observed effect below."
          />
          <KpiCard
            label="Solids"
            value={`${c.solids_percent}%`}
            href={`/formulations/${formula.formula_code}#composition`}
            context="Non-volatile content by mass."
          />
          <KpiCard
            label="VOC"
            value={`${c.voc_g_per_l} g/L`}
            href={`/formulations/${formula.formula_code}#composition`}
            context="Per litre, because that is the unit regulators use."
          />
          <KpiCard
            label="Raw material cost"
            value={`${c.raw_material_cost_per_kg} / kg`}
            href={`/formulations/${formula.formula_code}#composition`}
            context="Raw material only — excludes labour, energy, packaging and yield loss."
          />
        </KpiRow>

        <Section
          title="Version genealogy"
          note="Revisions are additive. An approved formula is never edited in place —
                §8 — so the history below is the whole record of how this formula
                reached its current composition, including the branches that failed."
        >
          <ol className="space-y-2">
            {[...formula.versions]
              .sort((a, b) => a.version_number - b.version_number)
              .map((v) => {
                const isShown = v.version_code === version.version_code;
                return (
                  <li key={v.version_code}>
                    <button
                      type="button"
                      onClick={() => setSelectedCode(v.version_code)}
                      aria-pressed={isShown}
                      className={[
                        "w-full rounded border p-3 text-left transition-colors",
                        isShown
                          ? "border-slate-900 bg-white"
                          : "border-slate-200 bg-white hover:border-slate-400",
                      ].join(" ")}
                    >
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-xs font-semibold tabular-nums text-slate-900">
                          {v.version_code}
                        </span>
                        {(() => {
                          // Shared with the formulations index, so the two
                          // screens cannot disagree about what a status means.
                          const t = versionStatus(v);
                          return t.status === "yellow" ? (
                            <StatusBadge
                              status="yellow"
                              label={t.label}
                              reason={t.reason ?? ""}
                              size="sm"
                            />
                          ) : (
                            <StatusBadge status={t.status} label={t.label} size="sm" />
                          );
                        })()}
                        {v.parent_version && (
                          <span className="text-[11px] text-slate-500">
                            from {v.parent_version}
                          </span>
                        )}
                        <span className="ml-auto text-[11px] tabular-nums text-slate-500">
                          {v.created_on}
                        </span>
                        {isShown && (
                          <span className="text-[11px] font-medium text-slate-900">
                            shown below
                          </span>
                        )}
                      </div>

                      <dl className="mt-2 space-y-1 text-xs">
                        <div>
                          <dt className="inline font-medium text-slate-500">
                            Change reason:{" "}
                          </dt>
                          <dd className="inline text-slate-700">{v.change_reason}</dd>
                        </div>
                        <div>
                          <dt className="inline font-medium text-slate-500">
                            Hypothesis:{" "}
                          </dt>
                          <dd className="inline text-slate-700">
                            {v.technical_hypothesis}
                          </dd>
                        </div>
                        <div>
                          <dt className="inline font-medium text-slate-500">
                            Expected:{" "}
                          </dt>
                          <dd className="inline text-slate-700">{v.expected_effect}</dd>
                        </div>
                        <div>
                          <dt className="inline font-medium text-slate-500">
                            Observed:{" "}
                          </dt>
                          <dd className="inline text-slate-700">
                            {/* Never blank. An untested revision is a different
                                thing from one that produced no effect. */}
                            {v.observed_effect ?? (
                              <span className="italic text-slate-500">
                                not yet tested
                              </span>
                            )}
                          </dd>
                        </div>
                      </dl>
                    </button>
                  </li>
                );
              })}
          </ol>
        </Section>

        <Section
          id="composition"
          title={`Composition — ${version.version_code}`}
          note={
            batch
              ? `Percentages are mass percent. The weigh-up column is a ${batch.batch_mass_kg} kg batch scaled by the engine, and the component masses sum exactly to the batch mass — rounding each line independently would drift, and a technician reconciling the sheet would find a discrepancy the software invented.`
              : "Percentages are mass percent. NO WEIGH-UP IS SHOWN: this version cannot be submitted, and scaling a formula whose components do not total 100% would print masses that contradict the percentages beside them."
          }
        >
          <div className="overflow-x-auto rounded border border-slate-200 bg-white">
            <table className="w-full border-collapse text-xs">
              <caption className="sr-only">
                Composition of {version.version_code}
                {batch ? ` with a ${batch.batch_mass_kg} kg weigh-up` : ""}
              </caption>
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50 text-left">
                  <th scope="col" className="px-3 py-2 font-medium text-slate-600">Code</th>
                  <th scope="col" className="px-3 py-2 font-medium text-slate-600">Material</th>
                  <th scope="col" className="px-3 py-2 text-right font-medium text-slate-600">%</th>
                  {batch && (
                    <th scope="col" className="px-3 py-2 text-right font-medium text-slate-600">
                      {batch.batch_mass_kg} kg batch
                    </th>
                  )}
                </tr>
              </thead>
              <tbody>
                {version.components.map((line) => (
                  <tr key={line.material_code} className="border-b border-slate-100">
                    <td className="px-3 py-2 tabular-nums text-slate-500">
                      <Link
                        href="/materials"
                        className="underline underline-offset-2"
                      >
                        {line.material_code}
                      </Link>
                    </td>
                    <td className="px-3 py-2 text-slate-800">
                      {materialName(line.material_code)}
                    </td>
                    <td className="px-3 py-2 text-right font-medium tabular-nums text-slate-900">
                      {line.percentage}
                    </td>
                    {batch && (
                      <td className="px-3 py-2 text-right tabular-nums text-slate-700">
                        {batch.masses_kg[line.material_code] ?? "—"} kg
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="bg-slate-50 font-semibold">
                  <td className="px-3 py-2" colSpan={2}>
                    Total
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {c.total_percentage}
                  </td>
                  {batch && (
                    <td className="px-3 py-2 text-right tabular-nums">
                      {batch.batch_mass_kg} kg
                    </td>
                  )}
                </tr>
              </tfoot>
            </table>
          </div>
        </Section>

        {c.diff_vs_parent.length > 0 && (
          <Section
            title={`Difference from ${version.parent_version}`}
            note="Old, new, absolute change and percentage change per component — all
                  computed by the engine. A component present in one version and absent
                  from the other shows an empty cell, not a zero: zero means none was
                  used, empty means the line did not exist."
          >
            <DiffTable rows={c.diff_vs_parent} />
          </Section>
        )}
      </div>
    </>
  );
}

function DiffTable({ rows }: { rows: readonly DemoDiffRow[] }) {
  const changed = rows.filter((r) => r.change !== "unchanged");
  return (
    <div className="overflow-x-auto rounded border border-slate-200 bg-white">
      <table className="w-full border-collapse text-xs">
        <caption className="sr-only">Component differences from the parent version</caption>
        <thead>
          <tr className="border-b border-slate-200 bg-slate-50 text-left">
            <th scope="col" className="px-3 py-2 font-medium text-slate-600">Material</th>
            <th scope="col" className="px-3 py-2 font-medium text-slate-600">Change</th>
            <th scope="col" className="px-3 py-2 text-right font-medium text-slate-600">Old %</th>
            <th scope="col" className="px-3 py-2 text-right font-medium text-slate-600">New %</th>
            <th scope="col" className="px-3 py-2 text-right font-medium text-slate-600">Δ</th>
            <th scope="col" className="px-3 py-2 text-right font-medium text-slate-600">%Δ</th>
          </tr>
        </thead>
        <tbody>
          {changed.length === 0 && (
            <tr>
              <td className="px-3 py-3 text-slate-600" colSpan={6}>
                No component changed between these versions.
              </td>
            </tr>
          )}
          {changed.map((r) => (
            <tr key={r.material_code} className="border-b border-slate-100">
              <td className="px-3 py-2 text-slate-800">
                <span className="tabular-nums text-slate-500">{r.material_code}</span>{" "}
                {materialName(r.material_code)}
              </td>
              <td className="px-3 py-2">
                {/* Word as well as colour — §11 forbids colour-only status. */}
                <span
                  className={
                    r.change === "added"
                      ? "font-medium text-status-pass"
                      : r.change === "removed"
                        ? "font-medium text-status-fail"
                        : "font-medium text-slate-700"
                  }
                >
                  {r.change === "added" ? "+ added" : r.change === "removed" ? "− removed" : "changed"}
                </span>
              </td>
              <td className="px-3 py-2 text-right tabular-nums text-slate-600">
                {r.old_percentage ?? ""}
              </td>
              <td className="px-3 py-2 text-right tabular-nums text-slate-900">
                {r.new_percentage ?? ""}
              </td>
              <td className="px-3 py-2 text-right tabular-nums text-slate-900">
                {r.delta ?? ""}
              </td>
              <td className="px-3 py-2 text-right tabular-nums text-slate-700">
                {r.percent_delta === null ? "" : `${r.percent_delta}%`}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
