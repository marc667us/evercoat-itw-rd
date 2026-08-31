"use client";

/**
 * Material library.
 *
 * Every property shown here is an INPUT to the formulation engine, not an
 * output of it: density, solids, VOC and cost are what the engine consumes
 * to produce a formula's theoretical properties. That is why the columns
 * are the same ones `Component` takes — a material whose density is unknown
 * is a material no formula containing it can be costed or weighed.
 */

import { useMemo, useState } from "react";

import type { ColumnDef } from "@tanstack/react-table";

import {
  CreateForm,
  CREATE_INPUT,
  CREATE_LABEL,
} from "@/components/ui/create-form";
import {
  DataPage,
  DataSourceError,
} from "@/components/ui/data-source-banner";
import Link from "next/link";

import { StatusBadge } from "@/components/ui/status-badge";
import { TechnicalDataGrid } from "@/components/ui/technical-data-grid";
import { useCreateMaterial, useMaterials } from "@/lib/api/hooks";
import { MATERIAL_ROLES, type Material } from "@/lib/api/materials";
import { MaterialActions } from "./material-actions";
import {
  MATERIALS,
  materialStatus,
  supplierByCode,
  type DemoMaterial,
} from "@/lib/demo/dataset";

/**
 * One row, however it arrived.
 *
 * The grid is written against THIS and not against either source, so the
 * live and demonstration views cannot drift into showing different
 * columns — which would make the banner the only thing distinguishing
 * them, and a reader comparing two screenshots would have no idea the
 * shapes differed.
 *
 * Every quantity is a STRING. They are NUMERIC in PostgreSQL and stay
 * strings the whole way to the screen: parsing "34.75" into a JavaScript
 * number and formatting it back is the exact round trip the engine's
 * `Decimal` discipline exists to prevent. Nothing on this page computes.
 */
interface MaterialRow {
  readonly material_code: string;
  readonly name: string;
  readonly category: string;
  readonly status: string;
  readonly density_g_cm3: string | null;
  readonly solids_percent: string | null;
  readonly voc_percent: string | null;
  readonly cost_per_kg: string | null;
  readonly restriction_reason: string | null;
  readonly suppliers: string;
  readonly note: string;
}

/** A live API row, as the grid wants it. */
function fromApi(material: Material): MaterialRow {
  return {
    material_code: material.material_code,
    name: material.name,
    category: material.category,
    status: material.status,
    density_g_cm3: material.density_g_cm3,
    solids_percent: material.solids_percent,
    voc_percent: material.voc_percent,
    cost_per_kg: material.cost_per_kg,
    restriction_reason: material.restriction_reason,
    // The list endpoint returns a COUNT, not the names -- the names need a
    // join this screen does not need. Saying "3 suppliers" is honest;
    // inventing names to fill the column would not be.
    suppliers:
      material.supplier_count === 1
        ? "1 supplier"
        : `${material.supplier_count} suppliers`,
    note: material.hazard_summary ?? "",
  };
}

/** A demonstration row, as the grid wants it. */
function fromDemo(material: DemoMaterial): MaterialRow {
  return {
    material_code: material.material_code,
    name: material.name,
    category: material.category,
    status: material.status,
    density_g_cm3: material.density_g_cm3,
    // Already baked as a percentage by scripts/build_demo_formulations.py,
    // which calls the same engine function the API now calls. One
    // implementation of the arithmetic, two callers.
    solids_percent: material.solids_percent,
    voc_percent: material.voc_percent,
    cost_per_kg: material.cost_per_kg,
    restriction_reason: null,
    suppliers: material.suppliers
      .map((code) => supplierByCode(code)?.name ?? code)
      .join(", "),
    note: material.note,
  };
}

export default function MaterialsPage() {
  const columns = useMemo<ColumnDef<MaterialRow, unknown>[]>(
    () => [
      { accessorKey: "material_code", header: "Code" },
      { accessorKey: "name", header: "Material" },
      { accessorKey: "category", header: "Category" },
      {
        id: "status",
        header: "Status",
        cell: ({ row }) => {
          // One derivation for both sources: `materialStatus` now takes
          // only the status field, so a live row and a demonstration row
          // reach it without either being cast into the other's shape.
          const d = materialStatus(row.original);
          return d.status === "yellow" ? (
            <StatusBadge
              status="yellow"
              label={d.label}
              reason={d.reason ?? ""}
              size="sm"
            />
          ) : (
            <StatusBadge status={d.status} label={d.label} size="sm" />
          );
        },
      },
      {
        id: "density",
        header: "Density",
        // Units in the cell, not only in the header. A column of bare
        // numbers is unreadable once it is sorted or copied out.
        // An unmeasured density is NOT zero and must not render as one.
        // The engine refuses to compute a density it does not have; this
        // is the same refusal on screen.
        cell: ({ row }) => <Quantity value={row.original.density_g_cm3} unit="g/cm³" />,
      },
      // Baked strings, NOT `Number(fraction) * 100`.
      //
      // The first version did the conversion here in JavaScript floating
      // point — on a controlled percentage, in a commit whose stated premise
      // is that the frontend performs no formulation arithmetic. §5 forbids
      // float for percentages outright. The percentage is now computed in
      // Python by the build script and rendered verbatim. Raised by Codex.
      {
        id: "solids",
        header: "Solids",
        cell: ({ row }) => <Quantity value={row.original.solids_percent} unit="%" />,
      },
      {
        id: "voc",
        header: "VOC",
        cell: ({ row }) => <Quantity value={row.original.voc_percent} unit="%" />,
      },
      {
        id: "cost",
        header: "Cost",
        cell: ({ row }) => <Quantity value={row.original.cost_per_kg} unit="/ kg" />,
      },
      {
        id: "suppliers",
        header: "Suppliers",
        cell: ({ row }) => (
          <span className="text-xs text-slate-600">{row.original.suppliers}</span>
        ),
      },
      {
        accessorKey: "note",
        header: "Note",
        cell: ({ row }) => (
          <span className="text-xs text-slate-600">{row.original.note}</span>
        ),
      },
    ],
    [],
  );

  const materials = useMaterials<MaterialRow[]>(
    MATERIALS.map(fromDemo),
    (live) => live.map(fromApi),
  );

  return (
    <DataPage
      title="Materials"
      source={materials.source}
      sourceReason={materials.sourceReason}
      lede="The raw material library. Density, solids, VOC and cost are the inputs the
            formulation engine consumes — a material missing any of them is a material
            whose formulas cannot be costed, weighed or checked against a VOC limit.
            Obsolete materials are retained rather than deleted, because historical
            batches still reference them."
    >
      <div className="mb-4">
        <NewMaterialForm />
      </div>

      {materials.error ? (
        // NOT a fall back to the demonstration rows. A request that was
        // made and failed shows that it failed; substituting synthetic
        // figures here would make an outage look like a working product.
        <DataSourceError error={materials.error} />
      ) : (
        <TechnicalDataGrid
          data={materials.data ?? []}
          columns={columns}
          caption="Raw material library"
          emptyMessage={
            materials.isLoading ? "Loading materials…" : "No materials."
          }
        />
      )}

      {/* 🔴 A PANEL RATHER THAN AN EXPANDING ROW. `TechnicalDataGrid` is the
          shared grid for every technical table in the product and has no
          row-expansion; teaching it one to serve a single screen is the
          "rebuild infrastructure per module" §12 forbids, in reverse. Picking
          the material here costs one select and touches nothing shared. */}
      <div className="mt-6">
        <ManageMaterialPanel />
      </div>
    </DataPage>
  );
}

/**
 * A quantity, or an explicit statement that there is not one.
 *
 * `—` with a screen-reader label, never a blank cell and never 0. An
 * unmeasured density and a density of zero are different facts; this
 * project has already shipped a defect in which a blank measurement
 * rendered a green PASS, and `Number("")` is 0.
 */
function Quantity({
  value,
  unit,
}: {
  value: string | null;
  unit: string;
}): React.ReactNode {
  if (value === null || value === "") {
    return (
      // `text-slate-500`, NOT `text-slate-400`.
      //
      // slate-400 on white is about 2.9:1 against a required 4.5:1 — the
      // exact failure axe-core found on this project's sidebar headings.
      // And axe CANNOT catch it here: the glyph is `aria-hidden`, and axe
      // skips hidden nodes for contrast, which is how the `not-started`
      // marker at 1.5:1 survived a scan. A scanner not flagging something
      // is not evidence that it passes.
      <span className="text-slate-500" title="not recorded">
        <span aria-hidden>—</span>
        <span className="sr-only">not recorded</span>
      </span>
    );
  }
  return (
    <span className="tabular-nums">
      {value} {unit}
    </span>
  );
}


/**
 * Create a raw material.
 *
 * 🔴 THE NUMBERS ARE COLLECTED AND SENT AS TEXT.
 *
 * Density, solids fraction and cost are `NUMERIC` in PostgreSQL and `Decimal`
 * in Pydantic. Parsing them to `number` here would push a controlled value
 * through binary floating point before the server ever saw it — `CLAUDE.md` §5
 * forbids exactly that, and `inputMode="decimal"` gets the right keyboard
 * without changing the type.
 *
 * ⚠️ NO `status` FIELD. Creation always yields `development`; offering the
 * choice would imply one that does not exist. Nothing here derives a status,
 * either — §10 keeps that on the server.
 */
function NewMaterialForm() {
  const writes = useCreateMaterial();
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [category, setCategory] = useState("");
  const [role, setRole] = useState<string>("other");
  const [density, setDensity] = useState("");
  const [solids, setSolids] = useState("");
  const [cost, setCost] = useState("");
  const [hazard, setHazard] = useState("");
  const [requiresSds, setRequiresSds] = useState(true);

  return (
    <CreateForm
      title="New material"
      permission="material.create"
      submitLabel="Create material"
      isPending={writes.isPending}
      error={writes.error}
      done={writes.created ? `${writes.created.material_code} created.` : null}
      onSubmit={() =>
        writes.create(
          {
            material_code: code,
            name,
            category,
            role,
            density_g_cm3: density === "" ? undefined : density,
            solids_fraction: solids === "" ? undefined : solids,
            cost_per_kg: cost === "" ? undefined : cost,
            hazard_summary: hazard === "" ? undefined : hazard,
            requires_sds: requiresSds,
          },
          () => {
            setCode("");
            setName("");
            setCategory("");
            setDensity("");
            setSolids("");
            setCost("");
            setHazard("");
          },
        )
      }
    >
      <label className={CREATE_LABEL}>
        Material code
        <input
          className={CREATE_INPUT}
          required
          minLength={2}
          value={code}
          onChange={(event) => setCode(event.target.value)}
        />
      </label>
      <label className={CREATE_LABEL}>
        Name
        <input
          className={CREATE_INPUT}
          required
          value={name}
          onChange={(event) => setName(event.target.value)}
        />
      </label>
      <label className={CREATE_LABEL}>
        Category
        <input
          className={CREATE_INPUT}
          required
          placeholder="Resin, Filler, Pigment…"
          value={category}
          onChange={(event) => setCategory(event.target.value)}
        />
      </label>
      <label className={CREATE_LABEL}>
        Role
        <select
          className={CREATE_INPUT}
          value={role}
          onChange={(event) => setRole(event.target.value)}
        >
          {MATERIAL_ROLES.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      </label>
      <label className={CREATE_LABEL}>
        Density (g/cm³)
        <input
          className={CREATE_INPUT}
          inputMode="decimal"
          placeholder="1.0900"
          value={density}
          onChange={(event) => setDensity(event.target.value)}
        />
      </label>
      <label className={CREATE_LABEL}>
        Solids fraction (0–1)
        <input
          className={CREATE_INPUT}
          inputMode="decimal"
          placeholder="0.98"
          value={solids}
          onChange={(event) => setSolids(event.target.value)}
        />
      </label>
      <label className={CREATE_LABEL}>
        Cost per kg
        <input
          className={CREATE_INPUT}
          inputMode="decimal"
          value={cost}
          onChange={(event) => setCost(event.target.value)}
        />
      </label>
      <label className={CREATE_LABEL}>
        Hazard summary
        <input
          className={CREATE_INPUT}
          value={hazard}
          onChange={(event) => setHazard(event.target.value)}
        />
      </label>
      <label className="flex items-center gap-2 text-xs font-medium text-slate-700 sm:col-span-2">
        <input
          type="checkbox"
          checked={requiresSds}
          onChange={(event) => setRequiresSds(event.target.checked)}
        />
        {/* Default ON, matching the server. A material whose SDS is not
            required is the exception, and the formula-submission gate reads
            this — so the safe default is the one that asks for the sheet. */}
        A Safety Data Sheet is required for this material
      </label>
    </CreateForm>
  );
}


/**
 * Act on one material: its status ladder and its suppliers.
 *
 * Both endpoints existed with no control anywhere in the application, and two
 * roles held the permissions — procurement and the chemist for
 * `supplier.manage`, QA for `material.restrict`. They could not do the thing
 * their permission named.
 */
function ManageMaterialPanel() {
  // 🔴 IT FETCHES ITS OWN ROWS RATHER THAN TAKING THE GRID'S.
  //
  // The grid is fed `MaterialRow`, a DISPLAY shape with no `id` — deliberately,
  // because it merges live and demonstration rows. The status and supplier
  // endpoints are addressed by id, so this needs the live records. React Query
  // dedupes by key, so asking again costs no request.
  const live = useMaterials<Material[]>([], (rows) => rows);
  const materials = live.data ?? [];
  const [selected, setSelected] = useState("");
  const material = materials.find((row) => row.id === selected);

  return (
    <section
      aria-labelledby="manage-material"
      className="rounded border border-slate-200 bg-white p-4"
    >
      <h3 id="manage-material" className="text-sm font-semibold text-slate-900">
        Manage a material
      </h3>
      <label className={`${CREATE_LABEL} mt-2 max-w-md`}>
        Material
        <select
          className={CREATE_INPUT}
          value={selected}
          onChange={(event) => setSelected(event.target.value)}
        >
          <option value="">
            {materials.length === 0 ? "No materials to manage" : "Choose a material…"}
          </option>
          {materials.map((row) => (
            <option key={row.id} value={row.id}>
              {row.material_code} — {row.name} ({row.status})
            </option>
          ))}
        </select>
      </label>

      {material !== undefined && (
        <div className="mt-4 border-t border-slate-200 pt-4">
          <MaterialActions
            materialId={material.id}
            materialCode={material.material_code}
            status={material.status}
          />
          {/* §25 CONTEXTUAL ENTRY POINT — "Research Material".
              The spec's point is that the Research Center should be reachable
              WITHOUT going through its landing page and starting from nothing.
              This carries the material through, so the workspace records what
              motivated it and the material is how somebody finds the research
              later — the back-link the Research Center now renders.

              A link, not a button: it navigates, it can be opened in a new tab,
              and it writes nothing until the workspace form is submitted. */}
          <p className="mt-4 border-t border-slate-200 pt-4 text-sm">
            <Link
              href={`/material-safety/research?material=${material.id}`}
              className="font-medium text-slate-900 underline"
            >
              Research this material →
            </Link>
            <span className="ml-2 text-xs text-slate-600">
              Opens a research workspace linked to {material.material_code}.
            </span>
          </p>
        </div>
      )}
    </section>
  );
}
