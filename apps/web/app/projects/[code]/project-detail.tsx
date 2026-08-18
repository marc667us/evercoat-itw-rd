"use client";

/**
 * Project workspace — the heart of Slice 2.
 *
 * Answers the five questions `CLAUDE.md` §11 requires of every major page:
 * where am I in the process (the stage gate), what is the current status
 * (the requirement counts and the header badge), what changed (stage
 * history with dates), what requires action (open risks, open tasks,
 * failing requirements), and what evidence supports this (the
 * requirements verification matrix, with method and measured value).
 */

import Link from "next/link";
import { useMemo } from "react";

import type { ColumnDef } from "@tanstack/react-table";

import { DemoBanner } from "@/components/ui/demo-banner";
import { EntityHeader } from "@/components/ui/entity-header";
import { KpiCard, KpiRow } from "@/components/ui/kpi-card";
import { StatusBadge } from "@/components/ui/status-badge";
import { TechnicalDataGrid } from "@/components/ui/technical-data-grid";
import {
  STAGES,
  milestoneStatus,
  projectByCode,
  requirementCounts,
  requirementStatus,
  riskSeverity,
  stageName,
  tasksForProject,
  userName,
  type DemoRequirement,
} from "@/lib/demo/dataset";

function Section({
  title,
  note,
  children,
}: {
  title: string;
  note?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="mt-8">
      <h2 className="text-sm font-semibold text-slate-900">{title}</h2>
      {note && <p className="mt-1 max-w-3xl text-xs text-slate-600">{note}</p>}
      <div className="mt-3">{children}</div>
    </section>
  );
}

export function ProjectDetail({ code }: { code: string }) {
  const project = projectByCode(code);

  const requirementColumns = useMemo<ColumnDef<DemoRequirement, unknown>[]>(
    () => [
      { accessorKey: "requirement_code", header: "Code" },
      { accessorKey: "name", header: "Requirement" },
      { accessorKey: "criticality", header: "Criticality" },
      {
        id: "target",
        header: "Target",
        // Target, minimum and maximum in one column with the unit, because
        // a bare "1.15" answers nothing: a reader cannot tell a target from
        // a limit, or which direction is failing.
        cell: ({ row }) => {
          const r = row.original;
          const parts: string[] = [];
          if (r.target_value) parts.push(`target ${r.target_value}`);
          if (r.minimum_value) parts.push(`min ${r.minimum_value}`);
          if (r.maximum_value) parts.push(`max ${r.maximum_value}`);
          return (
            <span className="tabular-nums text-slate-700">
              {parts.join(" · ")} {r.canonical_unit ?? ""}
            </span>
          );
        },
      },
      {
        id: "measured",
        header: "Measured",
        cell: ({ row }) => {
          const r = row.original;
          // "Not measured", never a dash or a zero. §10 rule 3: a
          // prediction or an absence must never read as a measurement.
          return r.measured_value === null ? (
            <span className="text-xs italic text-slate-500">not measured</span>
          ) : (
            <span className="font-medium tabular-nums text-slate-900">
              {r.measured_value} {r.canonical_unit ?? ""}
            </span>
          );
        },
      },
      { accessorKey: "test_method_code", header: "Method" },
      {
        id: "status",
        header: "Verification",
        cell: ({ row }) => {
          const d = requirementStatus(row.original);
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
    ],
    [],
  );

  if (!project) {
    return (
      <>
        <DemoBanner />
        <div className="p-6">
          <h1 className="text-xl font-semibold text-slate-900">
            Project not found
          </h1>
          <p className="mt-1.5 text-sm text-slate-600">
            No demonstration project with code {code}.
          </p>
          <Link
            href="/projects"
            className="mt-3 inline-block text-sm underline underline-offset-2"
          >
            Back to projects
          </Link>
        </div>
      </>
    );
  }

  const counts = requirementCounts(project.requirements);
  const openRisks = project.risks.filter((r) => r.status !== "closed");
  const tasks = tasksForProject(project.project_code);
  const visited = new Map(project.stage_history.map((v) => [v.stage_code, v]));

  return (
    <>
      <DemoBanner />
      <EntityHeader
        eyebrow={`Project ${project.project_code}`}
        title={project.name}
        crumbs={[
          { label: "Projects", href: "/projects" },
          { label: project.project_code, href: `/projects/${project.project_code}` },
        ]}
        fields={[
          { label: "Family", value: project.product_family ?? "—" },
          { label: "Stage", value: stageName(project.current_stage) },
          { label: "Lead", value: userName(project.lead) },
          { label: "Director", value: userName(project.director) },
          { label: "Target release", value: project.target_release_date ?? "—" },
          { label: "Confidentiality", value: project.confidentiality },
        ]}
        status={
          counts.red > 0 ? (
            <StatusBadge status="red" label={`${counts.red} REQUIREMENT FAILED`} />
          ) : counts.yellow > 0 ? (
            <StatusBadge
              status="yellow"
              label="IN VERIFICATION"
              reason={`${counts.yellow} requirement(s) not yet confirmed.`}
            />
          ) : (
            <StatusBadge status="green" label="ALL REQUIREMENTS PASSED" />
          )
        }
      />

      <div className="p-6">
        <KpiRow>
          <KpiCard
            label="Requirements failed"
            value={counts.red}
            href={`/projects/${project.project_code}`}
            tone={counts.red > 0 ? "red" : "neutral"}
            context="Critical or high requirements with a measured failure."
          />
          <KpiCard
            label="Awaiting verification"
            value={counts.yellow}
            href={`/projects/${project.project_code}`}
            tone={counts.yellow > 0 ? "yellow" : "neutral"}
            context="Not yet measured, or passing on a low margin."
          />
          <KpiCard
            label="Open risks"
            value={openRisks.length}
            href={`/projects/${project.project_code}`}
            tone={openRisks.some((r) => riskSeverity(r).status === "red") ? "red" : "neutral"}
            context="Risks not yet closed."
          />
          <KpiCard
            label="Open tasks"
            value={tasks.filter((t) => t.status !== "complete").length}
            href="/my-work"
            context="Actions assigned on this project."
          />
        </KpiRow>

        <Section
          title="Objective"
          note="Technical and commercial objectives, kept side by side so a
                requirement change can be judged against both."
        >
          <div className="grid gap-3 md:grid-cols-2">
            <div className="rounded border border-slate-200 bg-white p-4">
              <div className="text-[11px] font-medium uppercase tracking-wide text-slate-500">
                Technical
              </div>
              <p className="mt-1 text-sm text-slate-700">
                {project.technical_objective}
              </p>
            </div>
            <div className="rounded border border-slate-200 bg-white p-4">
              <div className="text-[11px] font-medium uppercase tracking-wide text-slate-500">
                Commercial
              </div>
              <p className="mt-1 text-sm text-slate-700">
                {project.commercial_objective}
              </p>
            </div>
          </div>
        </Section>

        <Section
          title="Stage gate"
          note="Built from the project's stage HISTORY, not from a single
                current-stage field. That is what lets a project move backwards
                into Failure / Rework without the record of where it has been
                being overwritten."
        >
          <ol className="flex flex-wrap gap-2">
            {STAGES.map((s) => {
              const visit = visited.get(s.stage_code);
              const isCurrent = s.stage_code === project.current_stage;
              const tone = visit?.outcome === "failed"
                ? "border-red-300 bg-red-50 text-status-fail"
                : isCurrent
                  ? "border-slate-900 bg-slate-900 text-white"
                  : visit
                    ? "border-emerald-200 bg-emerald-50 text-status-pass"
                    : "border-slate-200 bg-white text-slate-500";
              return (
                <li
                  key={s.stage_code}
                  className={`rounded border px-3 py-2 text-xs ${tone}`}
                >
                  <div className="font-medium">
                    {/* Glyph as well as colour — §11 forbids colour-only status. */}
                    {visit?.outcome === "failed"
                      ? "✕ "
                      : isCurrent
                        ? "● "
                        : visit
                          ? "✓ "
                          : "○ "}
                    {s.sequence}. {s.name}
                  </div>
                  <div className="mt-0.5 opacity-80">
                    {visit
                      ? `${visit.entered_on} → ${visit.exited_on ?? "in progress"}`
                      : "not entered"}
                  </div>
                </li>
              );
            })}
          </ol>
        </Section>

        <Section
          title="Requirements verification matrix"
          note="Every requirement with its target, the measurement taken against it,
                the method used, and the derived verification state. The state is
                computed from the measurement — it is never a field anyone sets."
        >
          <TechnicalDataGrid
            data={[...project.requirements]}
            columns={requirementColumns}
            caption={`Requirements for ${project.project_code}`}
            emptyMessage="No requirements defined."
          />
        </Section>

        <Section title="Milestones">
          <ul className="divide-y divide-slate-200 rounded border border-slate-200 bg-white">
            {project.milestones.map((m) => {
              const d = milestoneStatus(m);
              return (
                <li key={m.name} className="flex flex-wrap items-center gap-3 p-3">
                  <span className="min-w-64 flex-1 text-sm text-slate-800">
                    {m.name}
                  </span>
                  <span className="text-xs tabular-nums text-slate-600">
                    planned {m.planned_date}
                    {m.actual_date ? ` · actual ${m.actual_date}` : ""}
                  </span>
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
        </Section>

        <Section title="Risks">
          <ul className="divide-y divide-slate-200 rounded border border-slate-200 bg-white">
            {project.risks.map((r) => {
              const d = riskSeverity(r);
              return (
                <li key={r.risk_code} className="p-3">
                  <div className="flex flex-wrap items-center gap-3">
                    <span className="text-xs font-medium tabular-nums text-slate-500">
                      {r.risk_code}
                    </span>
                    <span className="min-w-64 flex-1 text-sm text-slate-800">
                      {r.title}
                    </span>
                    <span className="text-xs text-slate-600">
                      owner {userName(r.owner)}
                    </span>
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
                  </div>
                  {r.mitigation && (
                    <p className="mt-1 text-xs text-slate-600">
                      Mitigation: {r.mitigation}
                    </p>
                  )}
                </li>
              );
            })}
          </ul>
        </Section>

        <Section title="Team">
          <ul className="flex flex-wrap gap-2">
            {project.members.map((m) => (
              <li
                key={m.username}
                className="rounded border border-slate-200 bg-white px-3 py-2 text-xs"
              >
                <div className="font-medium text-slate-900">
                  {userName(m.username)}
                </div>
                <div className="text-slate-600">{m.project_role}</div>
              </li>
            ))}
          </ul>
        </Section>
      </div>
    </>
  );
}
