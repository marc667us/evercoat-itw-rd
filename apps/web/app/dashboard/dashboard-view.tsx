"use client";

/**
 * The dashboard body.
 *
 * Order is fixed by the UI narrative and `KpiRow`'s own note: KPIs first,
 * then the work needing intervention, and analytics AFTER both. A chart at
 * the top looks impressive and answers nothing — the first question on
 * opening the product is "what needs me", not "how are we trending".
 *
 * Every figure here is derived from the demo dataset. None is a constant
 * typed into this file. `CLAUDE.md` §10: a dashboard of invented numbers
 * is indistinguishable from a working one at a glance, and the way to stay
 * on the right side of that is for the dashboard to be a projection of
 * records that exist — even when those records are synthetic.
 */

import Link from "next/link";

import { ChartWrapper } from "@/components/ui/chart-wrapper";
import { trafficLightOption } from "@/components/ui/chart-builders";
import { DemoBanner } from "@/components/ui/demo-banner";
import { KpiCard, KpiRow } from "@/components/ui/kpi-card";
import { StatusBadge } from "@/components/ui/status-badge";
import {
  OPPORTUNITIES,
  PROJECTS,
  allRequirements,
  openTasks,
  requirementCounts,
  requirementsNeedingAction,
  stageName,
  userName,
} from "@/lib/demo/dataset";

export function DashboardView() {
  const counts = requirementCounts(allRequirements());
  const attention = requirementsNeedingAction();
  const tasks = openTasks();
  const openOpportunities = OPPORTUNITIES.filter((o) => o.status !== "converted");

  const failing = attention.filter((a) => a.derived.status === "red");

  return (
    <>
      <DemoBanner />
      <div className="p-6">
        <h1 className="text-xl font-semibold text-slate-900">Dashboard</h1>
        <p className="mt-1.5 max-w-3xl text-sm text-slate-600">
          Across {PROJECTS.length} active development projects. Every figure below
          is derived from the underlying records — click any of them to reach the
          records themselves.
        </p>

        <div className="mt-6">
          <KpiRow>
            <KpiCard
              label="Requirements failed"
              value={counts.red}
              href="/projects"
              tone={counts.red > 0 ? "red" : "neutral"}
              context="Measured against target and outside tolerance."
            />
            <KpiCard
              label="Awaiting verification"
              value={counts.yellow}
              href="/projects"
              tone={counts.yellow > 0 ? "yellow" : "neutral"}
              context="Not yet measured, or passing on a low margin."
            />
            <KpiCard
              label="Tasks awaiting action"
              value={tasks.length}
              href="/my-work"
              context="Items assigned and not complete. Not a row count."
            />
            <KpiCard
              label="Opportunities open"
              value={openOpportunities.length}
              href="/innovation"
              context="Proposed or under review, not yet converted."
            />
          </KpiRow>
        </div>

        {/* Work needing intervention, before any analytics. */}
        <section className="mt-8">
          <h2 className="text-sm font-semibold text-slate-900">
            Requirements needing attention
          </h2>
          <p className="mt-1 max-w-3xl text-xs text-slate-600">
            Failures first, then anything unverified. A requirement that has never
            been measured is listed here rather than counted as passing — an
            absent measurement is not a pass.
          </p>
          <ul className="mt-3 divide-y divide-slate-200 rounded border border-slate-200 bg-white">
            {attention.length === 0 && (
              <li className="p-4 text-sm text-slate-600">
                Every requirement across every project has passed.
              </li>
            )}
            {attention.map(({ project, requirement, derived }) => (
              <li
                key={`${project.project_code}-${requirement.requirement_code}`}
                className="flex flex-wrap items-center gap-3 p-3"
              >
                <Link
                  href={`/projects/${project.project_code}`}
                  className="text-xs font-medium tabular-nums text-slate-500 underline underline-offset-2"
                >
                  {project.project_code}
                </Link>
                <span className="min-w-56 flex-1 text-sm text-slate-800">
                  {requirement.name}
                </span>
                <span className="text-xs tabular-nums text-slate-600">
                  {requirement.measured_value === null
                    ? "not measured"
                    : `${requirement.measured_value} ${requirement.canonical_unit ?? ""}`}
                </span>
                {derived.status === "yellow" ? (
                  <StatusBadge
                    status="yellow"
                    label={derived.label}
                    reason={derived.reason ?? ""}
                    size="sm"
                  />
                ) : (
                  <StatusBadge status={derived.status} label={derived.label} size="sm" />
                )}
              </li>
            ))}
          </ul>
        </section>

        {/* Analytics last. */}
        <section className="mt-8">
          <h2 className="text-sm font-semibold text-slate-900">
            Requirement verification across the portfolio
          </h2>
          <div className="mt-3 max-w-3xl">
            <ChartWrapper
              title="Requirement verification state"
              caption={`All ${counts.green + counts.yellow + counts.red} requirements across ${PROJECTS.length} projects. Every segment carries its icon and count, so the chart is readable without relying on colour.`}
              option={trafficLightOption(counts)}
              tableColumns={[
                { key: "state", label: "State" },
                { key: "count", label: "Requirements", numeric: true },
              ]}
              tableRows={[
                { state: "✓ Passed", count: counts.green },
                { state: "! Unverified or low margin", count: counts.yellow },
                { state: "✕ Failed", count: counts.red },
              ]}
              drillDownHref="/projects"
              height={160}
            />
          </div>
        </section>

        <section className="mt-8">
          <h2 className="text-sm font-semibold text-slate-900">Projects</h2>
          <ul className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {PROJECTS.map((p) => {
              const c = requirementCounts(p.requirements);
              return (
                <li key={p.project_code}>
                  <Link
                    href={`/projects/${p.project_code}`}
                    className="block rounded border border-slate-200 bg-white p-4 transition-colors hover:border-slate-400 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-900"
                  >
                    <div className="text-[11px] tabular-nums text-slate-500">
                      {p.project_code}
                    </div>
                    <div className="mt-0.5 text-sm font-medium text-slate-900">
                      {p.name}
                    </div>
                    <div className="mt-1 text-xs text-slate-600">
                      {stageName(p.current_stage)} · lead {userName(p.lead)}
                    </div>
                    <div className="mt-2 flex items-center gap-2 text-xs tabular-nums">
                      <span className="text-status-pass">✓ {c.green}</span>
                      <span className="text-status-conditional">! {c.yellow}</span>
                      <span className="text-status-fail">✕ {c.red}</span>
                    </div>
                  </Link>
                </li>
              );
            })}
          </ul>
        </section>

        {failing.length > 0 && (
          <p className="mt-8 text-xs text-slate-500">
            {failing.length} failed requirement
            {failing.length === 1 ? "" : "s"} would open a Failure Investigation in
            the full product — that workflow arrives in a later slice, and is not
            represented here rather than being faked.
          </p>
        )}
      </div>
    </>
  );
}
