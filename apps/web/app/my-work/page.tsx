"use client";

/**
 * My Work — the actionable task queue.
 *
 * `CLAUDE.md` §11: queues and counts represent items needing ACTION,
 * never total rows. Every row states the action required — a queue that
 * lists a title without saying what is being asked of you is a list, not
 * a queue.
 *
 * 🔴 "ELSEWHERE IN THE ORGANISATION" WAS REMOVED WHEN THIS WAS WIRED.
 *
 * The demonstration version showed a second table of open tasks held by
 * other people. `GET /api/my-work` cannot produce it, and that is not a
 * gap in the endpoint — it is the endpoint being right. `my_work` returns
 * the caller's own tasks plus UNCLAIMED tasks addressed to their roles,
 * and nothing else, because a task somebody else has claimed "must leave
 * everyone else's inbox, or five people work the same item".
 *
 * Faking that section from the caller's own rows would have shown their
 * work twice under two headings. Fetching every task in the organisation
 * to fill it would have contradicted §11 on the one screen §11 is about.
 *
 * So the split that survives is the one the data actually supports and
 * that a person actually needs: what is YOURS, and what is waiting for
 * SOMEONE with your role to pick up.
 */

import { useMemo } from "react";

import type { ColumnDef } from "@tanstack/react-table";

import { DataPage, DataSourceError } from "@/components/ui/data-source-banner";
import { Absent, RecordLink } from "@/components/ui/record-link";
import { StatusBadge } from "@/components/ui/status-badge";
import { TechnicalDataGrid } from "@/components/ui/technical-data-grid";
import { useMyWork } from "@/lib/api/hooks";
import type { Task } from "@/lib/api/tasks";
import { DEMO_VIEWER, tasksAssignedTo, type DemoTask } from "@/lib/demo/dataset";

/** One row, however it arrived. */
interface TaskRow {
  readonly id: string;
  readonly title: string;
  readonly task_type: string;
  readonly project_code: string | null;
  readonly priority: string;
  readonly status: string;
  readonly due_date: string | null;
  readonly required_action: string | null;
  /** False means unclaimed role work: addressed to a role, held by nobody. */
  readonly claimed: boolean;
  /**
   * Server-computed against `CURRENT_DATE`.
   *
   * 🔴 NOT re-derived from `due_date` in the browser. The two clocks
   * disagree across time zones, and a task the server calls overdue while
   * the screen calls it due today is a contradiction the reader cannot
   * resolve.
   */
  readonly is_overdue: boolean;
}

function fromApi(task: Task): TaskRow {
  return {
    id: task.id,
    title: task.title,
    task_type: task.task_type,
    project_code: task.project_code,
    priority: task.priority,
    status: task.status,
    due_date: task.due_date,
    required_action: task.required_action,
    claimed: task.assigned_user_id !== null,
    is_overdue: task.is_overdue,
  };
}

function fromDemo(task: DemoTask, index: number): TaskRow {
  return {
    // The fixture has no ids. Index is stable for a bundled constant and
    // is used only as a React key.
    id: `demo-${index}`,
    title: task.title,
    task_type: task.task_type,
    project_code: task.project_code,
    priority: task.priority,
    status: task.status,
    due_date: task.due_date,
    required_action: task.required_action,
    // Every fixture task names an assignee, so the demonstration view has
    // no unclaimed role work to show. Stated rather than faked.
    claimed: true,
    // 🔴 DERIVED HERE, AND ONLY FOR FIXTURE ROWS.
    //
    // Hardcoding `false` meant a fixture task whose due date had passed
    // rendered as an ordinary date while an identical LIVE task rendered
    // OVERDUE — the same column meaning two things depending on source,
    // and the misleading direction: a missing verdict presented as
    // "on time". Codex found it.
    //
    // This does NOT contradict the rule on the field above. That rule
    // exists because the browser and the SERVER can disagree about the
    // date; a bundled fixture has no server to disagree with, so there is
    // exactly one clock. Live rows still take the server's word and never
    // recompute it.
    is_overdue: task.due_date < new Date().toISOString().slice(0, 10),
  };
}

export default function MyWorkPage() {
  const demoRows = useMemo(() => tasksAssignedTo(DEMO_VIEWER).map(fromDemo), []);
  const { data, source, sourceReason, isLoading, error } = useMyWork(demoRows, (live) =>
    live.map(fromApi),
  );

  const columns = useMemo<ColumnDef<TaskRow, unknown>[]>(
    () => [
      {
        accessorKey: "title",
        header: "Task",
        cell: ({ row }) => <span className="text-slate-900">{row.original.title}</span>,
      },
      {
        id: "type",
        header: "Type",
        accessorFn: (t) => t.task_type.replace(/_/g, " "),
      },
      {
        id: "project",
        header: "Project",
        cell: ({ row }) =>
          row.original.project_code === null ? (
            <Absent what="not attached to a project" />
          ) : (
            <RecordLink
              kind="project"
              code={row.original.project_code}
              className="underline underline-offset-2"
            />
          ),
      },
      {
        // `accessorFn` as well as `cell`: converting this to a display-only
        // column removed the sort button, and a task queue you cannot sort
        // by due date is a real regression. The Supervisor found it.
        id: "due",
        accessorFn: (t) => t.due_date ?? "",
        header: "Due",
        cell: ({ row }) => {
          const { due_date, is_overdue } = row.original;
          if (due_date === null) {
            return <Absent what="no due date" />;
          }
          // Overdue is a WARNING with a stated reason, not a red date. §10:
          // colour is never the sole indicator — colour + icon + text.
          return is_overdue ? (
            <StatusBadge
              status="yellow"
              label={`${due_date} · OVERDUE`}
              reason="Past its due date and still awaiting action."
              size="sm"
            />
          ) : (
            <span className="tabular-nums text-slate-700">{due_date}</span>
          );
        },
      },
      {
        id: "state",
        accessorFn: (t) => t.status,
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
            <StatusBadge status="neutral" label={row.original.status.toUpperCase()} size="sm" />
          ),
      },
      {
        id: "required_action",
        accessorFn: (t) => t.required_action ?? "",
        header: "Required action",
        cell: ({ row }) => (
          <span className="text-xs text-slate-600">
            {row.original.required_action ?? (
              <Absent what="no required action recorded" />
            )}
          </span>
        ),
      },
    ],
    [],
  );

  const rows = data ?? [];
  const mine = rows.filter((t) => t.claimed);
  const unclaimed = rows.filter((t) => !t.claimed);

  return (
    <DataPage
      title="My Work"
      lede="What is assigned to you, then what is waiting for someone with your
            role to pick up. Each row states what is being asked and when it is
            due — a queue that only lists titles tells you nothing about what to
            do next."
      source={source}
      sourceReason={sourceReason}
    >
      {error !== null ? (
        <DataSourceError error={error} />
      ) : (
        <>
          <h2 className="text-sm font-semibold text-slate-900">Assigned to you</h2>
          <div className="mt-3">
            <TechnicalDataGrid
              data={mine}
              columns={columns}
              loading={isLoading}
              caption="Tasks assigned to you"
              emptyMessage="Nothing assigned to you."
            />
          </div>

          <h2 className="mt-8 text-sm font-semibold text-slate-900">
            Unclaimed, addressed to your role
          </h2>
          <p className="mt-1 text-xs text-slate-600">
            Held by nobody yet. Claiming one makes it yours and removes it from
            everyone else&rsquo;s queue.
          </p>
          <div className="mt-3">
            <TechnicalDataGrid
              data={unclaimed}
              columns={columns}
              loading={isLoading}
              caption="Unclaimed tasks addressed to your role"
              emptyMessage="Nothing is waiting to be picked up."
            />
          </div>
        </>
      )}
    </DataPage>
  );
}
