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

import { useMemo } from "react";

import type { ColumnDef } from "@tanstack/react-table";

import { DataPage, DataSourceError } from "@/components/ui/data-source-banner";
import Link from "next/link";

import { Absent, RecordLink } from "@/components/ui/record-link";
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
  /**
   * The server's id, or null for a demonstration row.
   *
   * 🔴 THE LIVE WORKSPACE IS REACHED BY ID, NOT BY CODE. `/projects/[code]` is
   * a static export of the bundled fixture — `generateStaticParams` prerenders
   * three codes and there is no server to resolve a fourth — so a live project
   * has no page under that route. `/projects/workspace?id=` is the live one,
   * and it needs the id this row previously threw away.
   */
  readonly id: string | null;
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
    id: project.id,
    project_code: project.project_code,
    name: project.name,
    product_family: project.product_family,
    status: project.status,
    priority: project.priority,
    // `stageName` maps a stage CODE to its human label and is shared with
    // the demonstration path, so both sources render the same words for
    // the same stage. A project with no stage yet is a real state.
    // 🔴 THE FIXTURE'S STAGE NAMES ARE NOT THIS ORGANIZATION'S.
    //
    // `stageName` looks a code up in the bundled eight-stage fixture and
    // falls back to the raw code. Real stage definitions live per
    // organization in `projects.stage_definitions` and are editable
    // through /api/admin/stage-gates — so a tenant that keeps a colliding
    // code but renames the stage would have seen the FIXTURE's name
    // rendered as if it were their data. The Supervisor found it.
    //
    // The live path therefore shows the code the server sent, verbatim,
    // until the list endpoint joins `stage_definitions.name`.
    stage: project.current_stage ?? "",
    target_release_date: project.target_release_date ?? null,
    confidentiality: project.confidentiality,
  };
}

function fromDemo(project: DemoProject): ProjectRow {
  return {
    // A fixture row has no database record behind it, so there is nothing for
    // the live workspace to open. `RecordLink` says so in words.
    id: null,
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
        // 🔴 A LIVE ROW OPENS THE LIVE WORKSPACE; A FIXTURE ROW SAYS WHY IT
        // CANNOT. Until Slice 2's write half was built there was no live
        // project screen at all, so every live row fell through to
        // `RecordLink`'s refusal — correct at the time and now only correct for
        // the demonstration path, where there is no database record to open.
        cell: ({ row }) =>
          row.original.id === null ? (
            <RecordLink kind="project" code={row.original.project_code} />
          ) : (
            <Link
              href={`/projects/workspace?id=${row.original.id}`}
              className="underline underline-offset-2"
            >
              {row.original.project_code}
            </Link>
          ),
      },
      { accessorKey: "name", header: "Project" },
      {
        // `accessorFn` as well as `cell`. Converting these to display-only
        // columns silently removed their sort buttons: TanStack's
        // `getCanSort()` requires an accessor, so Family, Current stage
        // and Target release stopped being sortable — and sorting a
        // project list by target release is the obvious thing to do with
        // it. The Supervisor found it.
        id: "product_family",
        accessorFn: (p) => p.product_family ?? "",
        header: "Family",
        cell: ({ row }) =>
          row.original.product_family ?? <Absent what="no product family recorded" />,
      },
      {
        id: "stage",
        accessorFn: (p) => p.stage,
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
        accessorFn: (p) => p.status,
        header: "Status",
        cell: ({ row }) => (
          <span className="text-xs capitalize text-slate-700">
            {row.original.status.replace(/_/g, " ")}
          </span>
        ),
      },
      {
        id: "confidentiality",
        accessorFn: (p) => p.confidentiality,
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
        accessorFn: (p) => p.priority,
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
        accessorFn: (p) => p.target_release_date ?? "",
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
        // `loading` renders a skeleton. Putting the loading text into
        // `emptyMessage` drew it inside the dashed "no records" box, which
        // reads as a RESULT — "no projects" — while the request is still in
        // flight. The Supervisor found it.
        <TechnicalDataGrid
          data={data ?? []}
          columns={columns}
          loading={isLoading}
          caption="Development projects"
          emptyMessage="No projects."
        />
      )}
    </DataPage>
  );
}
