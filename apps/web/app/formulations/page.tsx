import type { Metadata } from "next";

import Link from "next/link";

import { DemoPage } from "@/components/ui/demo-banner";
import { StatusBadge } from "@/components/ui/status-badge";
import {
  FORMULAS,
  currentVersion,
  submissionStatus,
  userName,
  versionStatus,
} from "@/lib/demo/dataset";

export const metadata: Metadata = { title: "Formulations" };

/**
 * Formulations index.
 *
 * Shows the CURRENT version of each formula — the approved one, not simply
 * the highest-numbered. §8 makes revisions additive and released
 * formulations immutable, so the newest version is often an unapproved
 * draft; leading with it would present an unapproved composition as though
 * it were the formula.
 */
export default function FormulationsPage() {
  return (
    <DemoPage
      title="Formulations"
      lede="Each formula with its currently approved version. Every derived figure —
            theoretical density, solids, VOC, cost — is computed by the Python
            calculation engine at build time, never by this page."
    >
      <ul className="space-y-3">
        {FORMULAS.map((f) => {
          const v = currentVersion(f);
          const c = v.computed;
          const draftCount = f.versions.filter((x) => x.status === "draft").length;
          return (
            <li
              key={f.formula_code}
              className="rounded border border-slate-200 bg-white p-4"
            >
              <div className="flex flex-wrap items-baseline gap-3">
                <span className="text-xs font-medium tabular-nums text-slate-500">
                  {f.formula_code}
                </span>
                <h2 className="flex-1 text-sm font-semibold text-slate-900">
                  <Link
                    href={`/formulations/${f.formula_code}`}
                    className="underline underline-offset-2"
                  >
                    {f.name}
                  </Link>
                </h2>
                <span className="text-xs text-slate-600">
                  {f.versions.length} version{f.versions.length === 1 ? "" : "s"}
                </span>
                {/* The SHARED derivation. This greened only `approved` while
                    the workspace greened `released` too, so a released formula
                    showed grey here and green there — two literals encoding one
                    rule, disagreeing. Raised by the Supervisor. */}
                {(() => {
                  const t = versionStatus(v);
                  return t.status === "yellow" ? (
                    <StatusBadge
                      status="yellow"
                      label={`${v.version_code} · ${t.label}`}
                      reason={t.reason ?? ""}
                      size="sm"
                    />
                  ) : (
                    <StatusBadge
                      status={t.status}
                      label={`${v.version_code} · ${t.label}`}
                      size="sm"
                    />
                  );
                })()}
              </div>

              <div className="mt-3 grid grid-cols-2 gap-3 text-xs md:grid-cols-5">
                {[
                  ["Theoretical density", `${c.theoretical_density_g_cm3} g/cm³`],
                  ["Solids", `${c.solids_percent}%`],
                  ["VOC", `${c.voc_g_per_l} g/L`],
                  ["Binder : filler", c.binder_to_filler],
                  ["Raw material cost", `${c.raw_material_cost_per_kg} / kg`],
                ].map(([label, value]) => (
                  <div key={label} className="rounded border border-slate-200 p-2">
                    <div className="text-[10px] font-medium uppercase tracking-wide text-slate-500">
                      {label}
                    </div>
                    <div className="mt-0.5 font-semibold tabular-nums text-slate-900">
                      {value}
                    </div>
                  </div>
                ))}
              </div>

              <p className="mt-3 text-xs text-slate-600">
                Project{" "}
                <Link
                  href={`/projects/${f.project_code}`}
                  className="underline underline-offset-2"
                >
                  {f.project_code}
                </Link>{" "}
                · owner {userName(f.owner)} · {f.product_family}
              </p>

              {draftCount > 0 && (
                <p className="mt-2 text-xs text-slate-600">
                  {draftCount} draft version
                  {draftCount === 1 ? "" : "s"} not shown above.{" "}
                  {f.versions
                    .filter((x) => x.status === "draft")
                    .map((x) => {
                      const s = submissionStatus(x);
                      // The yellow arm is spelled out because StatusBadge
                      // is a discriminated union that will not accept a
                      // yellow without a reason — §10 enforced by the type
                      // system rather than by anyone remembering.
                      return (
                        <span key={x.version_code} className="ml-1 inline-block">
                          {s.status === "yellow" ? (
                            <StatusBadge
                              status="yellow"
                              label={`${x.version_code} — ${s.label}`}
                              reason={s.reason ?? ""}
                              size="sm"
                            />
                          ) : (
                            <StatusBadge
                              status={s.status}
                              label={`${x.version_code} — ${s.label}`}
                              size="sm"
                            />
                          )}
                        </span>
                      );
                    })}
                </p>
              )}
            </li>
          );
        })}
      </ul>
    </DemoPage>
  );
}
