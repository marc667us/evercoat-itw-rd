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

import { useMemo, useState } from "react";

import type { ColumnDef } from "@tanstack/react-table";

import {
  CreateForm,
  CREATE_INPUT,
  CREATE_LABEL,
} from "@/components/ui/create-form";
import { DataPage, DataSourceError } from "@/components/ui/data-source-banner";
import { serverMessage } from "@/lib/api/client";
import { ASSIGNABLE_ROLES, TASK_PRIORITIES } from "@/lib/api/tasks";

const ROW_BUTTON =
  "rounded border border-slate-300 px-2 py-1 text-xs font-medium text-slate-800 " +
  "hover:bg-slate-100 disabled:cursor-not-allowed disabled:text-slate-400";
import { Absent, RecordLink } from "@/components/ui/record-link";
import { StatusBadge } from "@/components/ui/status-badge";
import { TechnicalDataGrid } from "@/components/ui/technical-data-grid";
import { useCreateTask, useMyWork, useTaskWrites } from "@/lib/api/hooks";
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
  const writes = useTaskWrites();
  const live = source === "live";

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
      {
        id: "actions",
        header: "",
        /* 🔴 THE PAGE PROMISED THIS AND DID NOT HAVE IT. The heading below
           already read *"Claiming one makes it yours and removes it from
           everyone else's queue"* while `POST /tasks/{id}/claim` had no client
           anywhere in the application — prose stating a rule the product did
           not implement. `/complete` was the same.

           ⚠️ DISABLED OVER DEMONSTRATION ROWS. Their ids are `demo-0`, `demo-1`
           — a React key for a bundled fixture, not a task the API knows. Left
           live, these buttons would send a 404 for a row that looks exactly
           like every other row. */
        cell: ({ row }) =>
          row.original.status === "done" ? (
            <span className="text-xs text-slate-500">Done</span>
          ) : row.original.claimed ? (
            <button
              type="button"
              className={ROW_BUTTON}
              disabled={!live || writes.isPending}
              title={live ? undefined : "Demonstration row — not a task the API knows"}
              onClick={() => writes.complete(row.original.id)}
            >
              Complete
            </button>
          ) : (
            <button
              type="button"
              className={ROW_BUTTON}
              disabled={!live || writes.isPending}
              title={live ? undefined : "Demonstration row — not a task the API knows"}
              onClick={() => writes.claim(row.original.id)}
            >
              Claim
            </button>
          ),
      },
    ],
    [live, writes],
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
      <div className="mb-4">
        <RaiseTaskForm />
      </div>

      {writes.error !== null && (
        <p
          role="alert"
          className="mb-4 rounded border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-900"
        >
          {serverMessage(writes.error)}
        </p>
      )}
      {writes.error === null && writes.lastAction !== null && (
        <p
          role="status"
          className="mb-4 rounded border border-slate-300 bg-slate-50 px-3 py-2 text-sm text-slate-800"
        >
          {writes.lastAction}
        </p>
      )}

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

/**
 * Raise a task.
 *
 * 🔴 THIS FORM HAD NO ASSIGNEE FIELD AND THEREFORE HAD NEVER RAISED A TASK.
 *
 * The comment here used to record that as a deliberate limit, on the grounds
 * that `assigned_user_id` takes a UUID and no endpoint lists the
 * organization's people for a non-administrator — and it closed by saying *"a
 * task raised unassigned is a real, useful state, and it appears in the
 * queue"*.
 *
 * That last sentence was not true. `create_task` opens with:
 *
 *     if data.assigned_user_id is None and not data.assigned_role:
 *         raise TaskStateError("a task needs an owner: give it an assigned
 *                              user or an assigned role")
 *
 * and a CHECK constraint backs it. So every press of this form returned 409.
 * A comment asserting a rule the code does not have — and the rule it asserted
 * was the opposite of the real one.
 *
 * ⚠️ THE STATED BLOCKER WAS REAL AND NEVER APPLIED TO ROLES. A role is not a
 * person: the ten codes are seeded, fixed and not confidential, so addressing
 * work to one needs no people-picker at all. `my_work` selects
 * `assigned_user_id = :uid OR (assigned_user_id IS NULL AND assigned_role =
 * ANY(:roles))`, so a role-addressed task reaches everyone holding that role
 * until one of them claims it — which is what the Claim control below is for.
 */
function RaiseTaskForm() {
  const writes = useCreateTask();
  const [title, setTitle] = useState("");
  const [taskType, setTaskType] = useState("review");
  const [assignedRole, setAssignedRole] = useState<string>("");
  const [priority, setPriority] = useState<string>("medium");
  const [due, setDue] = useState("");
  const [action, setAction] = useState("");

  return (
    <CreateForm
      title="Raise a task"
      permission="project.edit"
      submitLabel="Raise task"
      isPending={writes.isPending}
      error={writes.error}
      done={writes.created ? "Task raised — it will appear in the queue." : null}
      onSubmit={() =>
        writes.create(
          {
            task_type: taskType,
            title,
            priority,
            // Required by the server, and by a CHECK constraint. The form
            // cannot submit without it -- see the `required` on the select.
            assigned_role: assignedRole,
            due_date: due === "" ? undefined : due,
            required_action: action === "" ? undefined : action,
          },
          () => {
            setTitle("");
            setDue("");
            setAction("");
            setAssignedRole("");
          },
        )
      }
    >
      <label className={CREATE_LABEL}>
        Title
        <input
          className={CREATE_INPUT}
          required
          value={title}
          onChange={(event) => setTitle(event.target.value)}
        />
      </label>
      <label className={CREATE_LABEL}>
        Type
        <input
          className={CREATE_INPUT}
          required
          placeholder="review, retest, correction…"
          value={taskType}
          onChange={(event) => setTaskType(event.target.value)}
        />
      </label>
      <label className={CREATE_LABEL}>
        Priority
        <select
          className={CREATE_INPUT}
          value={priority}
          onChange={(event) => setPriority(event.target.value)}
        >
          {TASK_PRIORITIES.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      </label>
      <label className={CREATE_LABEL}>
        Assign to
        <select
          className={CREATE_INPUT}
          required
          value={assignedRole}
          onChange={(event) => setAssignedRole(event.target.value)}
        >
          {/* No "unassigned" option, because the server has no such state.
              Offering one would put the 409 back. */}
          <option value="">Choose a role…</option>
          {ASSIGNABLE_ROLES.map((role) => (
            <option key={role.code} value={role.code}>
              {role.label}
            </option>
          ))}
        </select>
        <span className="mt-1 block text-[11px] font-normal text-slate-600">
          Everyone holding this role sees the task until one of them claims it.
        </span>
      </label>
      <label className={CREATE_LABEL}>
        Due date
        <input
          className={CREATE_INPUT}
          type="date"
          value={due}
          onChange={(event) => setDue(event.target.value)}
        />
      </label>
      <label className={`${CREATE_LABEL} sm:col-span-2`}>
        Required action
        <input
          className={CREATE_INPUT}
          placeholder="What has to happen for this to be done?"
          value={action}
          onChange={(event) => setAction(event.target.value)}
        />
      </label>
    </CreateForm>
  );
}
