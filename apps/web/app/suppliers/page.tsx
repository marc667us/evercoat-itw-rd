import type { Metadata } from "next";

import { DemoPage } from "@/components/ui/demo-banner";
import { StatusBadge } from "@/components/ui/status-badge";
import {
  SUPPLIERS,
  materialStatus,
  materialsFromSupplier,
  supplierStatus,
} from "@/lib/demo/dataset";

export const metadata: Metadata = { title: "Suppliers" };

/**
 * Suppliers, and what each one is the source of.
 *
 * The material list under each supplier is the point, not decoration. A
 * supplier page that lists only names and ratings cannot answer the
 * question anybody actually asks of it — *what breaks if this supplier
 * fails* — and single-sourcing is a live risk on this project
 * (RSK-014-01, glass microspheres).
 */
export default function SuppliersPage() {
  return (
    <DemoPage
      title="Suppliers"
      lede="Approved and qualified sources, with the materials each one supplies. A
            supplier is only interesting in terms of what depends on it — the
            materials listed under each are what would be at risk if that source
            failed."
    >
      <ul className="grid gap-3 md:grid-cols-2">
        {SUPPLIERS.map((s) => {
          const materials = materialsFromSupplier(s.supplier_code);
          const soleSource = materials.filter(
            (m) => m.suppliers.length === 1,
          );
          return (
            <li
              key={s.supplier_code}
              className="rounded border border-slate-200 bg-white p-4"
            >
              <div className="flex flex-wrap items-baseline gap-2">
                <span className="text-xs font-medium tabular-nums text-slate-500">
                  {s.supplier_code}
                </span>
                <h2 className="flex-1 text-sm font-semibold text-slate-900">
                  {s.name}
                </h2>
                {/* Derived, not a hardcoded else-arm. Every non-approved
                    status previously rendered as "QUALIFIED", so a suspended
                    or disqualified source would have been presented as
                    usable. Raised by the Supervisor. */}
                {(() => {
                  const d = supplierStatus(s);
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
                  <dd>{s.country}</dd>
                </div>
                <div className="flex gap-1.5">
                  <dt className="font-medium text-slate-500">Quality rating</dt>
                  <dd>{s.quality_rating}</dd>
                </div>
              </dl>

              <p className="mt-2 text-xs text-slate-600">{s.note}</p>

              <h3 className="mt-3 text-[11px] font-medium uppercase tracking-wide text-slate-500">
                Supplies {materials.length} material
                {materials.length === 1 ? "" : "s"}
              </h3>
              <ul className="mt-1.5 space-y-1">
                {materials.map((m) => {
                  const d = materialStatus(m);
                  return (
                    <li
                      key={m.material_code}
                      className="flex flex-wrap items-center gap-2 text-xs"
                    >
                      <span className="tabular-nums text-slate-500">
                        {m.material_code}
                      </span>
                      <span className="flex-1 text-slate-800">{m.name}</span>
                      {d.status === "yellow" ? (
                        <StatusBadge
                          status="yellow"
                          label={d.label}
                          reason={d.reason ?? ""}
                          size="sm"
                        />
                      ) : (
                        <StatusBadge status={d.status} label={d.label} size="sm" />
                      )}
                    </li>
                  );
                })}
              </ul>

              {soleSource.length > 0 && (
                /* Named explicitly, because this is the thing a supplier page
                   exists to surface. A concentration risk that is only
                   visible by cross-referencing two screens is a risk nobody
                   sees until the source fails. */
                <p className="mt-3 rounded border border-amber-200 bg-amber-50 p-2 text-[11px] text-amber-900">
                  <span aria-hidden>⚠ </span>
                  <span className="font-semibold">Sole source</span> for{" "}
                  {soleSource.map((m) => m.material_code).join(", ")}. No
                  alternative supplier is qualified for these.
                </p>
              )}
            </li>
          );
        })}
      </ul>
    </DemoPage>
  );
}
