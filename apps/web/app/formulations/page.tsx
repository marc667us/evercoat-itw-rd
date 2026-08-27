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

import { useMemo } from "react";

import Link from "next/link";
import { useState } from "react";

import { DataPage, DataSourceError } from "@/components/ui/data-source-banner";
import { serverMessage } from "@/lib/api/client";
import { Absent, RecordLink } from "@/components/ui/record-link";
import { StatusBadge } from "@/components/ui/status-badge";
import { useCreateFormula, useFormulas, useProjects } from "@/lib/api/hooks";
import { permits, usePermissions } from "@/lib/permissions";
import type { Formula } from "@/lib/api/formulations";
import {
  FORMULAS,

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
  /**
   * The live key the workspace opens with, or null.
   *
   * 🔴 NULL ON EVERY DEMONSTRATION ROW, AND THAT IS DELIBERATE. A fixture
   * formula has no `version_id` on the server, so a link built from one would
   * 404 against a live API — a link that works in the demo and breaks in use,
   * which this file has already been burned by once. The card offers the
   * workspace only when it genuinely has a key for it, and says why when it
   * does not.
   */
  readonly latest_version_id: string | null;
}

function fromApi(formula: Formula): FormulaRow {
  return {
    formula_code: formula.formula_code,
    name: formula.name,
    project_code: formula.project_code,
    product_family: formula.product_family,
    // The list returns an owner USER ID, not a name — resolving it needs a
    // join this endpoint does not do, and printing a UUID at a chemist is
    // not an improvement.
    //
    // 🔴 The comment here used to claim "the cell says so". It did not:
    // the render simply omitted the field, so a reader comparing a
    // demonstration card (owner shown) with a live one concluded the
    // formula had no owner. The Supervisor found the comment describing
    // behaviour the code did not have. It says so now.
    owner: null,
    version_count: formula.version_count,
    latest_version_code: formula.latest_version_code,
    latest_version_status: formula.latest_version_status,
    latest_version_id: formula.latest_version_id,
  };
}

function fromDemo(formula: DemoFormula): FormulaRow {
  // 🔴 THE HIGHEST-NUMBERED VERSION, NOT `currentVersion`.
  //
  // `currentVersion` deliberately prefers the newest APPROVED or RELEASED
  // version. That is the right answer to a different question, and using
  // it here put the approved version under a column labelled "Latest
  // version" — so a fixture formula with v1 approved and v2 draft showed
  // "v1 · APPROVED" while the identical live formula showed "v2 · DRAFT".
  // One heading, two meanings, decided by which environment you were in:
  // exactly the drift this file's header claims to have closed. Both
  // reviewers found it independently.
  //
  // `list_formulas` orders by `version_number DESC`, so the demonstration
  // path must do the same.
  const latest = [...formula.versions].sort(
    (a, b) => b.version_number - a.version_number,
  )[0];
  if (latest === undefined) {
    return {
      formula_code: formula.formula_code,
      name: formula.name,
      project_code: formula.project_code,
      product_family: formula.product_family,
      owner: userName(formula.owner),
      version_count: 0,
      latest_version_code: null,
      latest_version_status: null,
      latest_version_id: null,
    };
  }
  return {
    formula_code: formula.formula_code,
    name: formula.name,
    project_code: formula.project_code,
    product_family: formula.product_family,
    owner: userName(formula.owner),
    version_count: formula.versions.length,
    latest_version_code: latest.version_code,
    latest_version_status: latest.status,
    // A fixture has no live version id. See `FormulaRow`.
    latest_version_id: null,
  };
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

/**
 * Create a formula inside a project.
 *
 * 🔴 A PROJECT IS REQUIRED AND IS CHOSEN, NOT TYPED. `POST /api/formulations`
 * takes a `project_id`, and §2's thread runs project -> formula: a formula
 * outside a project is the "isolated data island" the whole design forbids.
 * The project list is already a live call on this application, so the picker
 * costs nothing and removes the only field a person could get wrong.
 *
 * ⚠️ THE CONTROL IS ALWAYS OFFERED AND THE SERVER DECIDES. `formula.create`
 * is not held by every role, and §6 makes a frontend check cosmetic. A
 * refusal is shown as the sentence the server sent.
 */
interface ProjectOption {
  readonly id: string;
  readonly project_code: string;
  readonly name: string;
}

function CreateFormulaPanel() {
  // `useProjects` is a SOURCED list (demo fallback + live), not a live-only
  // one, so it takes the demonstration rows first. An empty array is the
  // honest fallback here: this panel creates a real record, and offering a
  // fixture project to create it against would produce a request the server
  // rejects with an id that means nothing.
  const projects = useProjects<ProjectOption[]>([], (live) =>
    live.map((p) => ({ id: p.id, project_code: p.project_code, name: p.name })),
  );
  const [open, setOpen] = useState(false);
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [projectId, setProjectId] = useState("");
  const create = useCreateFormula();
  const permissions = usePermissions();

  // 🔴 `formula.create`, WHICH `POST /api/formulations` DECLARES. Measured on
  // the seeded realm 2026-08-27: the Chemist holds it and the Lead, Director,
  // QA, Technician, Engineer, Procurement, Production and Executive do not. A
  // "New formula" button offered to the other nine was a control that could
  // only ever answer 403.
  if (!permits(permissions, "formula.create")) {
    return null;
  }

  if (!open) {
    return (
      <button
        type="button"
        className="rounded border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-800 hover:bg-slate-50"
        onClick={() => setOpen(true)}
      >
        New formula
      </button>
    );
  }

  const options = projects.data ?? [];
  const input =
    "mt-1 w-full rounded border border-slate-300 px-2 py-1.5 text-sm text-slate-900 " +
    "focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500";
  const label = "block text-xs font-medium text-slate-600";

  return (
    <div className="grid max-w-xl gap-2 rounded border border-slate-200 bg-white p-4">
      <div>
        <label className={label} htmlFor="new-project">
          Project
        </label>
        <select
          id="new-project"
          className={input}
          value={projectId}
          onChange={(e) => setProjectId(e.target.value)}
        >
          <option value="">
            {projects.isLoading ? "Loading projects…" : "Choose a project"}
          </option>
          {options.map((p) => (
            <option key={p.id} value={p.id}>
              {p.project_code} · {p.name}
            </option>
          ))}
        </select>
      </div>
      <div>
        <label className={label} htmlFor="new-code">
          Formula code
        </label>
        <input
          id="new-code"
          className={input}
          value={code}
          onChange={(e) => setCode(e.target.value)}
          placeholder="FRM-020"
        />
      </div>
      <div>
        <label className={label} htmlFor="new-name">
          Name
        </label>
        <input
          id="new-name"
          className={input}
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Lightweight polyester filler"
        />
      </div>
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          className="rounded bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-700 disabled:bg-slate-400"
          disabled={
            create.isPending || projectId === "" || code.trim() === "" || name.trim() === ""
          }
          onClick={() =>
            create.create({
              formula_code: code.trim(),
              name: name.trim(),
              project_id: projectId,
            })
          }
        >
          Create formula
        </button>
        <button
          type="button"
          className="rounded border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-800 hover:bg-slate-50"
          onClick={() => setOpen(false)}
        >
          Cancel
        </button>
      </div>

      {projects.error !== null && <DataSourceError error={projects.error} />}
      {create.error !== null && (
        <p
          role="alert"
          className="rounded border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-900"
        >
          {serverMessage(create.error)}
        </p>
      )}
      {create.error === null && create.created !== null && (
        <p role="status" className="text-sm text-slate-700">
          Created. It has no version yet — a formula and its first composition are
          separate records.
        </p>
      )}
    </div>
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
      <div className="mb-4">
        <CreateFormulaPanel />
      </div>

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
                  <RecordLink
                    kind="formula"
                    code={f.formula_code}
                    className="underline underline-offset-2"
                  />
                </span>
                <h2 className="flex-1 text-sm font-semibold text-slate-900">{f.name}</h2>
                <span className="text-xs text-slate-600">
                  {f.version_count} version{f.version_count === 1 ? "" : "s"}
                </span>
                <VersionBadge row={f} />
              </div>

              <p className="mt-3 text-xs text-slate-600">
                Project{" "}
                <RecordLink
                  kind="project"
                  code={f.project_code}
                  className="underline underline-offset-2"
                />
                {f.owner === null ? (
                  <> · owner <Absent what="the owner's name is not available on this screen" /></>
                ) : (
                  <> · owner {f.owner}</>
                )}
                {f.product_family !== null && <> · {f.product_family}</>}
              </p>

              {f.latest_version_id !== null && (
                <p className="mt-2 text-xs">
                  <Link
                    href={`/formulations/formula?version=${f.latest_version_id}`}
                    className="font-medium text-slate-800 underline underline-offset-2"
                  >
                    Open {f.latest_version_code} →
                  </Link>{" "}
                  <span className="text-slate-600">
                    composition, derived properties, weigh-up sheet and the difference
                    against its parent
                  </span>
                </p>
              )}
            </li>
          ))}
        </ul>
      )}
    </DataPage>
  );
}
