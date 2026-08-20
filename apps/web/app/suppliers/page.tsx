"use client";

/**
 * Suppliers, and how much depends on each one.
 *
 * 🔴 THE DEPENDENCY LIST BECAME A COUNT WHEN THIS WAS WIRED, AND THE PAGE
 * SAYS SO OUT LOUD.
 *
 * The demonstration version listed, under each supplier, every material it
 * sources and flagged the sole-sourced ones. That was the point of the
 * screen: a supplier is only interesting in terms of *what breaks if it
 * fails*, and single-sourcing is a live risk here (RSK-014-01, glass
 * microspheres).
 *
 * `GET /api/suppliers` returns `material_count` and not the names. The
 * names need the material↔supplier join, which the list endpoint
 * deliberately does not do — the same reason the materials list shows a
 * supplier COUNT rather than inventing names it had not fetched.
 *
 * Two things were refused here. Fetching every material to rebuild the
 * join in the browser: that is the N+1 the endpoint shape exists to
 * prevent, and §4 keeps derivation on the server. Quietly dropping the
 * sole-source flag: it would have looked like a tidier page while
 * removing the one signal a reader is here for.
 *
 * So the count is shown, and the missing analysis is NAMED on the page
 * rather than left as a silent absence. It is recorded as a gap in
 * `TODO.md`, and it closes when a supplier detail route exists.
 */

import { useMemo } from "react";

import { DataPage, DataSourceError } from "@/components/ui/data-source-banner";
import { StatusBadge } from "@/components/ui/status-badge";
import { useSuppliers } from "@/lib/api/hooks";
import type { Supplier } from "@/lib/api/materials";
import {
  SUPPLIERS,
  materialsFromSupplier,
  supplierStatus,
  type DemoSupplier,
} from "@/lib/demo/dataset";

/** One row, however it arrived. */
interface SupplierRow {
  readonly supplier_code: string;
  readonly name: string;
  readonly country: string | null;
  readonly status: string;
  readonly quality_rating: string | null;
  readonly material_count: number;
  /**
   * How many of those materials this supplier is the ONLY source of.
   *
   * Null means "not computed on this screen", which is the live case — it
   * needs the material↔supplier join. Null is NOT zero: rendering an
   * uncomputed risk as "0 sole-sourced" would be the single most
   * misleading thing this page could do.
   */
  readonly sole_sourced: number | null;
}

function fromApi(supplier: Supplier): SupplierRow {
  return {
    supplier_code: supplier.supplier_code,
    name: supplier.name,
    country: supplier.country,
    status: supplier.status,
    quality_rating: supplier.quality_rating,
    material_count: supplier.material_count,
    sole_sourced: null,
  };
}

function fromDemo(supplier: DemoSupplier): SupplierRow {
  const materials = materialsFromSupplier(supplier.supplier_code);
  return {
    supplier_code: supplier.supplier_code,
    name: supplier.name,
    country: supplier.country,
    status: supplier.status,
    quality_rating: supplier.quality_rating,
    material_count: materials.length,
    sole_sourced: materials.filter((m) => m.suppliers.length === 1).length,
  };
}

export default function SuppliersPage() {
  const demoRows = useMemo(() => SUPPLIERS.map(fromDemo), []);
  const { data, source, sourceReason, isLoading, error } = useSuppliers(demoRows, (live) =>
    live.map(fromApi),
  );

  const rows = data ?? [];
  // True when NO row could compute the risk — i.e. the live case. Derived
  // from the data rather than from `source`, so the notice cannot drift
  // out of step with what is actually on screen.
  const riskUncomputed = rows.length > 0 && rows.every((r) => r.sole_sourced === null);

  return (
    <DataPage
      title="Suppliers"
      lede="Approved and qualified sources, with how many materials depend on each.
            A supplier is only interesting in terms of what would be at risk if
            that source failed."
      source={source}
      sourceReason={sourceReason}
    >
      {error !== null ? (
        <DataSourceError error={error} />
      ) : (
        <>
          {riskUncomputed && (
            // role="note", not a bare paragraph: this is an absence of
            // analysis, and a reader must not conclude from a missing
            // flag that nothing is sole-sourced.
            <div
              role="note"
              aria-label="Sole-source analysis not available"
              className="mb-4 rounded border border-amber-300 bg-amber-50 px-4 py-2 text-xs text-amber-900"
            >
              <span aria-hidden>⚠ </span>
              Sole-source risk is <strong>not computed on this screen</strong>. It
              needs the material-to-supplier join, which this list endpoint does
              not return. A supplier showing no flag has <strong>not</strong> been
              checked — see the Materials screen for what each material depends on.
            </div>
          )}

          {rows.length === 0 ? (
            <p className="text-sm text-slate-600">
              {isLoading ? "Loading suppliers…" : "No suppliers."}
            </p>
          ) : (
            <ul className="grid gap-3 md:grid-cols-2">
              {rows.map((s) => (
                <li
                  key={s.supplier_code}
                  className="rounded border border-slate-200 bg-white p-4"
                >
                  <div className="flex flex-wrap items-baseline gap-2">
                    <span className="text-xs font-medium tabular-nums text-slate-500">
                      {s.supplier_code}
                    </span>
                    <h2 className="flex-1 text-sm font-semibold text-slate-900">{s.name}</h2>
                    {/* Derived, not a hardcoded else-arm. Every non-approved
                        status once rendered as "QUALIFIED", so a suspended or
                        disqualified source was presented as usable. */}
                    {(() => {
                      const d = supplierStatus({ status: s.status });
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
                    })()}
                  </div>

                  <dl className="mt-2 flex flex-wrap gap-x-6 gap-y-1 text-xs text-slate-600">
                    <div className="flex gap-1.5">
                      <dt className="font-medium text-slate-500">Country</dt>
                      <dd>{s.country ?? "—"}</dd>
                    </div>
                    <div className="flex gap-1.5">
                      <dt className="font-medium text-slate-500">Quality rating</dt>
                      <dd>{s.quality_rating ?? "—"}</dd>
                    </div>
                    <div className="flex gap-1.5">
                      <dt className="font-medium text-slate-500">Materials</dt>
                      <dd className="tabular-nums">
                        {s.material_count} supplied
                        {s.sole_sourced !== null && s.sole_sourced > 0 && (
                          <>
                            {" · "}
                            <span className="font-semibold text-status-conditional">
                              {s.sole_sourced} sole-sourced
                            </span>
                          </>
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
    </DataPage>
  );
}
