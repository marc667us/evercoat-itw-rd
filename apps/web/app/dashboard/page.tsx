import type { Metadata } from "next";

export const metadata: Metadata = { title: "Dashboard" };

/**
 * Role dashboards arrive in Slice 7 with real transactional data behind
 * them. This placeholder exists so the shell has a landing route and the
 * navigation can be exercised — it deliberately shows no fabricated
 * numbers. A dashboard of invented KPIs is indistinguishable from a
 * working one at a glance, and that is exactly how a feature ships
 * having never worked.
 */
export default function DashboardPage() {
  return (
    <div className="p-6">
      <h1 className="text-xl font-semibold text-slate-900">Dashboard</h1>
      <p className="mt-1.5 max-w-2xl text-sm text-slate-600">
        Slice 1 — application shell. Role dashboards for Chemist, Engineer,
        Lead and Director are built in Slice 7, drawing on real project,
        formula, batch, test and failure records rather than placeholder
        figures.
      </p>
      <div className="mt-6 rounded border border-dashed border-slate-300 bg-white p-5">
        <p className="text-sm text-slate-500">
          No data yet. Projects begin in Slice 2.
        </p>
      </div>
    </div>
  );
}
