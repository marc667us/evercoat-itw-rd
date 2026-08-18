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

import { useMemo } from "react";

import type { ColumnDef } from "@tanstack/react-table";

import {
  DataPage,
  DataSourceError,
} from "@/components/ui/data-source-banner";
import { StatusBadge } from "@/components/ui/status-badge";
import { TechnicalDataGrid } from "@/components/ui/technical-data-grid";
import { useMaterials } from "@/lib/api/hooks";
import type { Material } from "@/lib/api/materials";
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
