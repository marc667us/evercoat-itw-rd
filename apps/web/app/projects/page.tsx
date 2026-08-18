"use client";

/**
 * Projects list.
 *
 * A client component because `TechnicalDataGrid` is one — column
 * definitions carry `cell` render functions, and functions cannot cross
 * the server/client boundary. Nothing here needs a server anyway: the
 * dataset is baked into the bundle at build time.
 */

import Link from "next/link";
import { useMemo } from "react";

import type { ColumnDef } from "@tanstack/react-table";

import { DemoPage } from "@/components/ui/demo-banner";
import { StatusBadge } from "@/components/ui/status-badge";
import { TechnicalDataGrid } from "@/components/ui/technical-data-grid";
import {
  PROJECTS,
  requirementCounts,
  stageName,
  stageProgress,
  userName,
  type DemoProject,
} from "@/lib/demo/dataset";

export default function ProjectsPage() {
  // useMemo so the column definitions are not rebuilt on every render.
  // TanStack resets internal table state when the columns identity
  // changes, which shows up as sorting being silently lost on interaction.
  const columns = useMemo<ColumnDef<DemoProject, unknown>[]>(
    () => [
      {
        accessorKey: "project_code",
        header: "Code",
        cell: ({ row }) => (
          <Link
            href={`/projects/${row.original.project_code}`}
            className="font-medium text-slate-900 underline underline-offset-2"
          >
            {row.original.project_code}
          </Link>
        ),
      },
      { accessorKey: "name", header: "Project" },
      { accessorKey: "product_family", header: "Family" },
      {
        id: "stage",
        header: "Current stage",
        accessorFn: (p) => stageName(p.current_stage),
      },
      {
        id: "progress",
        header: "Gate progress",
        cell: ({ row }) => {
          const { done, total } = stageProgress(row.original);
          return (
            <span className="tabular-nums text-slate-700">
              {done} of {total} complete
            </span>
          );
        },
      },
      {
        id: "requirements",
        header: "Requirements",
        cell: ({ row }) => {
          const c = requirementCounts(row.original.requirements);
          // Counts, not a single colour. A project with one failed and one
          // passing requirement is not "amber" — it is one failure and one
          // pass, and collapsing that loses the failure.
          return (
            <span className="flex items-center gap-2 text-xs tabular-nums">
              <span className="text-status-pass">✓ {c.green}</span>
              <span className="text-status-conditional">! {c.yellow}</span>
              <span className="text-status-fail">✕ {c.red}</span>
            </span>
          );
        },
      },
      {
        id: "lead",
        header: "Lead",
        accessorFn: (p) => userName(p.lead),
      },
      {
        id: "priority",
        header: "Priority",
        cell: ({ row }) =>
          row.original.priority === "high" ? (
            <StatusBadge status="neutral" label="HIGH" size="sm" />
          ) : (
            <span className="text-xs capitalize text-slate-600">
              {row.original.priority}
            </span>
          ),
      },
      {
        accessorKey: "target_release_date",
        header: "Target release",
      },
    ],
    [],
  );

  return (
    <DemoPage
      title="Projects"
      lede="Every development project in the organisation, with its position in the
            eight-stage gate and the state of its requirement set. Open a project to
            see its pipeline history, requirements verification matrix, milestones,
            risks and team."
    >
      <TechnicalDataGrid
        data={[...PROJECTS]}
        columns={columns}
        caption="Development projects"
        emptyMessage="No projects."
      />
    </DemoPage>
  );
}
