"use client";

/**
 * My Work — the actionable task queue.
 *
 * `CLAUDE.md` §11: sidebar counts and queues represent items needing
 * ACTION, never total rows. So completed tasks are excluded rather than
 * shown greyed out, and every row states the action required — a queue
 * that lists a title without saying what is being asked of you is a list,
 * not a queue.
 */

import Link from "next/link";
import { useMemo } from "react";

import type { ColumnDef } from "@tanstack/react-table";

import { DemoPage } from "@/components/ui/demo-banner";
import { StatusBadge } from "@/components/ui/status-badge";
import { TechnicalDataGrid } from "@/components/ui/technical-data-grid";
import {
  DEMO_VIEWER,
  openTasks,
  tasksAssignedTo,
  userName,
  type DemoTask,
} from "@/lib/demo/dataset";

export default function MyWorkPage() {
  const columns = useMemo<ColumnDef<DemoTask, unknown>[]>(
    () => [
      {
        accessorKey: "title",
        header: "Task",
        cell: ({ row }) => (
          <span className="text-slate-900">{row.original.title}</span>
        ),
      },
      {
        id: "type",
        header: "Type",
        accessorFn: (t) => t.task_type.replace(/_/g, " "),
      },
      {
        id: "project",
        header: "Project",
        cell: ({ row }) => (
          <Link
            href={`/projects/${row.original.project_code}`}
            className="underline underline-offset-2"
          >
            {row.original.project_code}
          </Link>
        ),
      },
      {
        id: "assignee",
        header: "Assigned to",
        accessorFn: (t) => userName(t.assigned_to),
      },
      { accessorKey: "due_date", header: "Due" },
      {
        id: "state",
        header: "State",
        cell: ({ row }) =>
          row.original.status === "in_progress" ? (
            <StatusBadge
              status="yellow"
              label="IN PROGRESS"
              reason="Started; not yet complete."
              size="sm"
            />
          ) : (
            <StatusBadge status="neutral" label="OPEN" size="sm" />
          ),
      },
      {
        accessorKey: "required_action",
        header: "Required action",
        cell: ({ row }) => (
          <span className="text-xs text-slate-600">
            {row.original.required_action}
          </span>
        ),
      },
    ],
    [],
  );

  // MINE, then everyone else's — and the two are labelled separately.
  //
  // The page previously showed the whole organisation's queue under the
  // heading "My Work", while the sidebar badge counted the same set. §11
  // is that a count is items needing action BY THE HOLDER, so a single
  // undifferentiated list under that title was simply mislabelled. Raised
  // by the Supervisor.
  const mine = tasksAssignedTo(DEMO_VIEWER);
  const others = openTasks().filter((t) => t.assigned_to !== DEMO_VIEWER);

  return (
    <DemoPage
      title="My Work"
      lede={`Assigned to ${userName(DEMO_VIEWER)}, then everything else awaiting
             action across the organisation. Each row states what is being asked,
             who holds it and when it is due — a queue that only lists titles
             tells you nothing about what to do next.`}
    >
      <h2 className="text-sm font-semibold text-slate-900">
        Assigned to {userName(DEMO_VIEWER)}
      </h2>
      <div className="mt-3">
        <TechnicalDataGrid
          data={[...mine]}
          columns={columns}
          caption={`Tasks assigned to ${userName(DEMO_VIEWER)}`}
          emptyMessage="Nothing assigned to you."
        />
      </div>

      <h2 className="mt-8 text-sm font-semibold text-slate-900">
        Elsewhere in the organisation
      </h2>
      <p className="mt-1 text-xs text-slate-600">
        Held by other people. Shown for context — these are not counted in the
        My Work badge.
      </p>
      <div className="mt-3">
        <TechnicalDataGrid
          data={[...others]}
          columns={columns}
          caption="Open tasks held by others"
          emptyMessage="Nothing outstanding elsewhere."
        />
      </div>
    </DemoPage>
  );
}
