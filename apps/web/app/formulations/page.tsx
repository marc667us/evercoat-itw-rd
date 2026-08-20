"use client";

/**
 * Formulations index.
 *
 * 🔴 THIS SCREEN CHANGED MEANING WHEN IT WAS WIRED, AND THE HEADING SAYS SO.
 *
 * It used to lead with the CURRENT version of each formula — the approved
 * one, deliberately not the highest-numbered, because §8 makes revisions
 * additive and the newest version is often an unapproved draft. Leading
 * with that draft would present an unapproved composition as though it
 * were the formula.
 *
 * `GET /api/formulations` cannot answer that question. `list_formulas`
 * returns the LATEST version by `version_number` (a LEFT JOIN LATERAL
 * ordered DESC) — which is precisely the thing the old page refused to
 * lead with. There is no list endpoint that returns "the current approved
 * version"; answering it per formula would need a query per row.
 *
 * So the column is labelled **Latest version** and always carries that
 * version's own status badge. A draft says DRAFT. A submitted one says
 * SUBMITTED with its reason. Nothing here implies approval that the
 * server did not report.
 *
 * 🔴 AND THE COMPUTED FIGURES ARE GONE FROM THE INDEX.
 *
 * Theoretical density, solids, VOC, binder:filler and cost came from
 * `version.computed` in the bundled fixture. Live they come from
 * `/api/formulations/versions/{id}/evaluation` — one call per version,
 * which an index of forty formulas must not make. They belong on the
 * formula detail screen, which already calls it.
 *
 * The alternative was to compute them here from whatever the list
 * returned. That is exactly how "an empty requirement set rendered ALL
 * REQUIREMENTS PASSED" happened on this project, and §4 forbids the
 * browser doing formulation arithmetic at all.
 */

import Link from "next/link";
import { useMemo } from "react";

import { DataPage, DataSourceError } from "@/components/ui/data-source-banner";
import { StatusBadge } from "@/components/ui/status-badge";
import { useFormulas } from "@/lib/api/hooks";
import type { Formula } from "@/lib/api/formulations";
import {
  FORMULAS,
  currentVersion,
  userName,
  versionStatus,
  type DemoFormula,
} from "@/lib/demo/dataset";

/** One row, however it arrived. */
interface FormulaRow {
  readonly formula_code: string;
  readonly name: string;
  readonly project_code: string;
  readonly product_family: string | null;
  readonly owner: string | null;
  readonly version_count: number;
  /** Null when the formula has no version yet — a real state, not an error. */
  readonly latest_version_code: string | null;
  readonly latest_version_status: string | null;
}

function fromApi(formula: Formula): FormulaRow {
  return {
    formula_code: formula.formula_code,
    name: formula.name,
    project_code: formula.project_code,
    product_family: formula.product_family,
    // The list returns an owner USER ID, not a name — resolving it needs a
    // join this endpoint does not do. An id is not a name, so rather than
    // print a UUID at a chemist, the field is omitted for live rows and
    // the cell says so.
    owner: null,
    version_count: formula.version_count,
    latest_version_code: formula.latest_version_code,
    latest_version_status: formula.latest_version_status,
  };
}

function fromDemo(formula: DemoFormula): FormulaRow {
  const latest = currentVersion(formula);
  return {
    formula_code: formula.formula_code,
    name: formula.name,
    project_code: formula.project_code,
    product_family: formula.product_family,
    owner: userName(formula.owner),
    version_count: formula.versions.length,
    latest_version_code: latest.version_code,
    latest_version_status: latest.status,
  };
}

/** `—` with a screen-reader label. Never a blank, never an invented value. */
function Absent({ what }: { what: string }): React.ReactNode {
  return (
    <span className="text-slate-500" title={what}>
      <span aria-hidden>—</span>
      <span className="sr-only">{what}</span>
    </span>
  );
}

function VersionBadge({ row }: { row: FormulaRow }): React.ReactNode {
  if (row.latest_version_code === null || row.latest_version_status === null) {
    return <Absent what="no version has been created for this formula yet" />;
  }
  // The SHARED derivation, narrowed to `{ status }` so a live row and a
  // demonstration row reach it without either being cast into the other's
  // shape. Two literals encoding one rule is how a released formula once
  // showed grey on one screen and green on another.
  const t = versionStatus({ status: row.latest_version_status });
  const label = `${row.latest_version_code} · ${t.label}`;
  return t.status === "yellow" ? (
    <StatusBadge status="yellow" label={label} reason={t.reason ?? ""} size="sm" />
  ) : (
    <StatusBadge status={t.status} label={label} size="sm" />
  );
}

export default function FormulationsPage() {
  const demoRows = useMemo(() => FORMULAS.map(fromDemo), []);
  const { data, source, sourceReason, isLoading, error } = useFormulas(demoRows, (live) =>
    live.map(fromApi),
  );

  return (
    <DataPage
      title="Formulations"
      lede="Every formula you can see, with its LATEST version and that version's
            own status. A draft says so. Open a formula for its composition,
            genealogy and the figures the calculation engine derived."
      source={source}
      sourceReason={sourceReason}
    >
      {error !== null ? (
        <DataSourceError error={error} />
      ) : data === undefined || data.length === 0 ? (
        <p className="text-sm text-slate-600">
          {isLoading ? "Loading formulas…" : "No formulas."}
        </p>
      ) : (
        <ul className="space-y-3">
          {data.map((f) => (
            <li key={f.formula_code} className="rounded border border-slate-200 bg-white p-4">
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
                  {f.version_count} version{f.version_count === 1 ? "" : "s"}
                </span>
                <VersionBadge row={f} />
              </div>

              <p className="mt-3 text-xs text-slate-600">
                Project{" "}
                <Link
                  href={`/projects/${f.project_code}`}
                  className="underline underline-offset-2"
                >
                  {f.project_code}
                </Link>
                {f.owner !== null && <> · owner {f.owner}</>}
                {f.product_family !== null && <> · {f.product_family}</>}
              </p>
            </li>
          ))}
        </ul>
      )}
    </DataPage>
  );
}
