"use client";

/**
 * Projects list.
 *
 * A client component because `TechnicalDataGrid` is one — column
 * definitions carry `cell` render functions, and functions cannot cross
 * the server/client boundary.
 *
 * 🔴 THREE COLUMNS LEFT THIS SCREEN WHEN IT WAS WIRED, ON PURPOSE.
 *
 * It used to show gate progress, requirement counts and the team lead.
 * The demonstration dataset carries all three because it is a bundled
 * fixture. `GET /api/projects` returns `ProjectSummary` — the project's
 * own columns and nothing more — because each of those three needs a
 * separate query, and the API exposes them on `/dashboard`,
 * `/requirements/matrix` and `/members` precisely so a list of forty
 * projects does not run forty sub-queries.
 *
 * Keeping them would have meant one of two things, and both are worse
 * than removing them: three empty columns on live data that look like a
 * database with nothing in it, or three columns computed from whatever
 * the browser could scrape together — which is how "an empty requirement
 * set rendered ALL REQUIREMENTS PASSED" happened on this project.
 *
 * They belong to the project detail screen, which already calls the
 * routes that answer them. Same judgement as the materials list showing
 * a supplier COUNT rather than inventing names it had not fetched.
 */

import Link from "next/link";
import { useMemo } from "react";

import type { ColumnDef } from "@tanstack/react-table";

import { DataPage, DataSourceError } from "@/components/ui/data-source-banner";
import { StatusBadge } from "@/components/ui/status-badge";
import { TechnicalDataGrid } from "@/components/ui/technical-data-grid";
import { useProjects } from "@/lib/api/hooks";
import type { Project } from "@/lib/api/projects";
import { PROJECTS, stageName, type DemoProject } from "@/lib/demo/dataset";

/**
 * One row, however it arrived.
 *
 * The grid is written against THIS and not against either source, so the
 * live and demonstration views cannot drift into showing different
 * columns — which would make the banner the only thing distinguishing
 * them.
 */
interface ProjectRow {
  readonly project_code: string;
  readonly name: string;
  readonly product_family: string | null;
  readonly status: string;
  readonly priority: string;
  readonly stage: string;
  readonly target_release_date: string | null;
  readonly confidentiality: string;
}

function fromApi(project: Project): ProjectRow {
  return {
    project_code: project.project_code,
    name: project.name,
    product_family: project.product_family,
    status: project.status,
    priority: project.priority,
    // `stageName` maps a stage CODE to its human label and is shared with
    // the demonstration path, so both sources render the same words for
    // the same stage. A project with no stage yet is a real state.
    stage: project.current_stage === null ? "" : stageName(project.current_stage),
    target_release_date: project.target_release_date ?? null,
    confidentiality: project.confidentiality,
  };
}

function fromDemo(project: DemoProject): ProjectRow {
  return {
    project_code: project.project_code,
    name: project.name,
    product_family: project.product_family,
    status: project.status,
    priority: project.priority,
    stage: stageName(project.current_stage),
    target_release_date: project.target_release_date,
    confidentiality: project.confidentiality,
  };
}

/** `—` with a screen-reader label. Never a blank cell, never an invented value. */
function Absent({ what }: { what: string }): React.ReactNode {
  return (
    // text-slate-500, not slate-400: slate-400 on white is about 2.9:1
    // against a required 4.5:1, the exact failure axe-core found on this
    // project's sidebar headings.
    <span className="text-slate-500" title={what}>
      <span aria-hidden>—</span>
      <span className="sr-only">{what}</span>
    </span>
  );
}

export default function ProjectsPage() {
  const demoRows = useMemo(() => PROJECTS.map(fromDemo), []);
  const { data, source, sourceReason, isLoading, error } = useProjects(demoRows, (live) =>
    live.map(fromApi),
  );

  // useMemo so the column definitions are not rebuilt on every render.
  // TanStack resets internal table state when the columns identity
  // changes, which shows up as sorting being silently lost on interaction.
  const columns = useMemo<ColumnDef<ProjectRow, unknown>[]>(
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
      {
        id: "product_family",
        header: "Family",
        cell: ({ row }) =>
          row.original.product_family ?? <Absent what="no product family recorded" />,
      },
      {
        id: "stage",
        header: "Current stage",
        cell: ({ row }) =>
          row.original.stage === "" ? (
            <Absent what="not yet entered a stage" />
          ) : (
            row.original.stage
          ),
      },
      {
        id: "status",
        header: "Status",
        cell: ({ row }) => (
          <span className="text-xs capitalize text-slate-700">
            {row.original.status.replace(/_/g, " ")}
          </span>
        ),
      },
      {
        id: "confidentiality",
        header: "Access",
        // Shown because it changes who can see the project at all, and a
        // reader comparing two lists should be able to tell why a
        // colleague sees a different number of rows. RLS enforces it; this
        // only reports it.
        cell: ({ row }) =>
          row.original.confidentiality === "restricted" ? (
            <StatusBadge status="neutral" label="RESTRICTED" size="sm" />
          ) : (
            <span className="text-xs text-slate-500">Normal</span>
          ),
      },
      {
        id: "priority",
        header: "Priority",
        cell: ({ row }) =>
          row.original.priority === "high" || row.original.priority === "critical" ? (
            <StatusBadge status="neutral" label={row.original.priority.toUpperCase()} size="sm" />
          ) : (
            <span className="text-xs capitalize text-slate-600">{row.original.priority}</span>
          ),
      },
      {
        id: "target_release_date",
        header: "Target release",
        cell: ({ row }) =>
          row.original.target_release_date ?? <Absent what="no target release date set" />,
      },
    ],
    [],
  );

  return (
    <DataPage
      title="Projects"
      lede="Every development project you can see, with its position in the
            eight-stage gate. Open a project for its pipeline history,
            requirements verification matrix, milestones, risks and team."
      source={source}
      sourceReason={sourceReason}
    >
      {/* Order matters: the error takes precedence over rows. A screen
          whose request failed shows that it failed and substitutes
          nothing — the hook returns `undefined`, never the demonstration
          rows, when a request it actually made comes back broken. */}
      {error !== null ? (
        <DataSourceError error={error} />
      ) : (
        <TechnicalDataGrid
          data={data ?? []}
          columns={columns}
          caption="Development projects"
          emptyMessage={isLoading ? "Loading projects…" : "No projects."}
        />
      )}
    </DataPage>
  );
}
