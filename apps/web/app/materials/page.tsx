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

import { DemoPage } from "@/components/ui/demo-banner";
import { StatusBadge } from "@/components/ui/status-badge";
import { TechnicalDataGrid } from "@/components/ui/technical-data-grid";
import {
  MATERIALS,
  materialStatus,
  supplierByCode,
  type DemoMaterial,
} from "@/lib/demo/dataset";

export default function MaterialsPage() {
  const columns = useMemo<ColumnDef<DemoMaterial, unknown>[]>(
    () => [
      { accessorKey: "material_code", header: "Code" },
      { accessorKey: "name", header: "Material" },
      { accessorKey: "category", header: "Category" },
      {
        id: "status",
        header: "Status",
        cell: ({ row }) => {
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
        cell: ({ row }) => (
          <span className="tabular-nums">{row.original.density_g_cm3} g/cm³</span>
        ),
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
        cell: ({ row }) => (
          <span className="tabular-nums">{row.original.solids_percent}%</span>
        ),
      },
      {
        id: "voc",
        header: "VOC",
        cell: ({ row }) => (
          <span className="tabular-nums">{row.original.voc_percent}%</span>
        ),
      },
      {
        id: "cost",
        header: "Cost",
        cell: ({ row }) => (
          <span className="tabular-nums">{row.original.cost_per_kg} / kg</span>
        ),
      },
      {
        id: "suppliers",
        header: "Suppliers",
        cell: ({ row }) => (
          <span className="text-xs text-slate-600">
            {row.original.suppliers
              .map((c) => supplierByCode(c)?.name ?? c)
              .join(", ")}
          </span>
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

  return (
    <DemoPage
      title="Materials"
      lede="The raw material library. Density, solids, VOC and cost are the inputs the
            formulation engine consumes — a material missing any of them is a material
            whose formulas cannot be costed, weighed or checked against a VOC limit.
            Obsolete materials are retained rather than deleted, because historical
            batches still reference them."
    >
      <TechnicalDataGrid
        data={[...MATERIALS]}
        columns={columns}
        caption="Raw material library"
        emptyMessage="No materials."
      />
    </DemoPage>
  );
}
