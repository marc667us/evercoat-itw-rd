/**
 * My Work, over HTTP.
 *
 * 🔴 THIS LIST IS AN INBOX, NOT A TABLE OF TASKS.
 *
 * `my_work` returns the caller's own tasks PLUS unclaimed tasks addressed
 * to their roles, ordered overdue-first. Two consequences the UI must not
 * flatten:
 *
 *   * `assigned_user_id` is null on a role-addressed item. That is not
 *     missing data — it is the definition of "nobody has claimed this
 *     yet", and it is why the item is in this list at all.
 *   * `is_overdue` is computed by the SERVER against `CURRENT_DATE`.
 *     The browser must not re-derive it from `due_date`: the two clocks
 *     disagree across time zones, and a task that the server calls
 *     overdue while the screen calls it due today is a contradiction the
 *     reader cannot resolve.
 *
 * `CLAUDE.md` §11 also requires that counts here be ACTIONABLE items
 * rather than totals — which is what this endpoint already returns, since
 * it filters to actionable statuses unless `include_done` is set.
 */

import { z } from "zod";

import { apiRequest, type ApiCredentials } from "./client";

export const taskSchema = z.object({
  id: z.string(),
  task_type: z.string(),
  title: z.string(),
  description: z.string().nullable(),
  priority: z.string(),
  status: z.string(),
  due_date: z.string().nullable(),
  required_action: z.string().nullable(),
  entity_type: z.string().nullable(),
  entity_id: z.string().nullable(),
  project_id: z.string().nullable(),
  assigned_user_id: z.string().nullable(),
  assigned_role: z.string().nullable(),
  // NOT NULL in `workflow.tasks`. See the formulations schema for why a
  // needlessly nullable field hides a contract regression.
  created_at: z.string(),
  // From the LEFT JOIN: null for a task that belongs to no project.
  project_code: z.string().nullable(),
  project_name: z.string().nullable(),
  // Server-computed. See the header: do NOT re-derive this in the browser.
  is_overdue: z.boolean(),
});

export type Task = z.infer<typeof taskSchema>;

const taskList = z.array(taskSchema);

export function fetchMyWork(
  credentials: ApiCredentials,
  signal?: AbortSignal,
): Promise<Task[]> {
  return apiRequest({ path: "/api/my-work", credentials, signal }, (payload) =>
    taskList.parse(payload),
  );
}

/*
 * 🔴 `/api/my-work`, NOT `/api/tasks`. THE ROUTER IS MOUNTED UNDER THE QUEUE.
 *
 * `main.py` does `include_router(tasks_router, prefix="/api/my-work")`, so
 * every task route -- create, claim, complete, reassign -- lives under the
 * name of the SCREEN rather than of the table. `createTask` was written
 * against `/api/tasks` and 404'd on every press. The live suite found it: a
 * 404 from a path that does not exist looks exactly like a refusal from one
 * that does, and nothing below the browser was wrong.
 *
 * ⚠️ AND THE PREFIX IS WRITTEN OUT IN FULL AT EACH CALL, NOT HOISTED INTO A
 * CONSTANT. Hoisting it was the obvious tidy-up and it silently disabled the
 * guard that catches this: `every path the web client calls is a path the API
 * serves` reads these literals out of the source, and `path: TASKS` and
 * `` `${TASKS}/${id}/claim` `` are invisible to it -- measured, by putting the
 * wrong base back and watching the check report nothing missing. A literal
 * that a reader and a test can both see beats a constant neither can.
 */
export interface TaskCreateRequest {
  readonly task_type: string;
  readonly title: string;
  readonly description?: string;
  readonly priority?: string;
  /**
   * 🔴 ONE OF THESE TWO IS REQUIRED, AND THE SERVER REFUSES A TASK WITHOUT ONE.
   *
   * `create_task` raises *"a task needs an owner: give it an assigned user or
   * an assigned role"*, and a CHECK constraint backs it. They were absent from
   * this type, so the Raise-a-task form sent neither and every press returned
   * 409 — the form had never once created a task. `my-work` selects on both
   * (`assigned_user_id = :uid OR (assigned_user_id IS NULL AND assigned_role =
   * ANY(:roles))`), so a role-addressed task reaches everyone holding it until
   * somebody takes it.
   *
   * Not modelled as a union: the server takes both fields and this mirrors the
   * server. The FORM is what enforces "exactly one", because that is a question
   * about the control, not about the wire.
   */
  readonly assigned_user_id?: string;
  readonly assigned_role?: string;
  readonly project_id?: string;
  readonly due_date?: string;
  readonly required_action?: string;
}

export const TASK_PRIORITIES = ["low", "medium", "high", "critical"] as const;

/**
 * The ten seeded realm roles, for addressing a task to a role rather than a
 * person.
 *
 * ⚠️ A MIRROR OF `apps/api/migrations/002_seed_roles_permissions.sql`, and
 * `tasks.roles.drift.test.ts` reads that file to prove it still matches. Two
 * literals in two files cannot be type-checked into agreement.
 *
 * 🔴 THE REASON THIS LIST CAN EXIST AT ALL is that a role is not a person.
 * `RaiseTaskForm` recorded that it had no assignee field because no endpoint
 * lists the organization's people for a non-administrator — true, and it never
 * applied to roles. The catalogue is fixed, seeded, and not confidential;
 * `GET /api/admin/roles` needs `admin.roles` only because it also reports each
 * role's GRANTS, which is a different question from what the roles are called.
 */
export const ASSIGNABLE_ROLES = [
  { code: "product_development_chemist", label: "Product Development Chemist" },
  { code: "product_development_engineer", label: "Product Development Engineer" },
  { code: "product_development_lead", label: "Product Development Lead" },
  { code: "product_development_director", label: "Product Development Director" },
  { code: "qa_compliance_officer", label: "QA / Compliance Officer" },
  { code: "laboratory_technician", label: "Laboratory Technician" },
  { code: "procurement_specialist", label: "Procurement / Material Specialist" },
  { code: "production_engineer", label: "Production Engineer" },
  { code: "executive_viewer", label: "Executive Viewer" },
  { code: "administrator", label: "Administrator" },
] as const;

export function createTask(
  credentials: ApiCredentials,
  request: TaskCreateRequest,
): Promise<{ id: string }> {
  return apiRequest(
    { path: "/api/my-work", method: "POST", credentials, body: request },
    (payload) => z.object({ id: z.string() }).passthrough().parse(payload),
  );
}
/**
 * Take an unclaimed, role-addressed task for yourself.
 *
 * 🔴 THIS ROUTE, `/complete` AND `/reassign` HAD NO CLIENT AT ALL. A task could
 * be raised and could never be picked up, finished or handed on through the
 * browser — the whole second half of the task lifecycle was unreachable, and
 * `/reassign` IS "assign this task to that person".
 *
 * No permission on the route on purpose: claiming is scoped by what the queue
 * already shows you, and `my_work` filters that by your roles.
 */
export function claimTask(credentials: ApiCredentials, taskId: string): Promise<unknown> {
  return apiRequest(
    { path: `/api/my-work/${taskId}/claim`, method: "POST", credentials, body: {} },
    (payload) => payload,
  );
}

/** Mark a task done, optionally saying what came of it. */
export function completeTask(
  credentials: ApiCredentials,
  taskId: string,
  outcomeNote?: string,
): Promise<unknown> {
  return apiRequest(
    {
      path: `/api/my-work/${taskId}/complete`,
      method: "POST",
      credentials,
      body: outcomeNote === undefined ? {} : { outcome_note: outcomeNote },
    },
    (payload) => payload,
  );
}

/*
 * ⚠️ `POST /api/my-work/{id}/reassign` HAS NO CLIENT HERE, ON PURPOSE.
 *
 * It is the third orphaned route on this module and the one that most deserves
 * a control -- handing work to a named colleague. It is not built yet because
 * it needs a PEOPLE source and there is exactly one a non-administrator can
 * read: `GET /api/projects/{id}/members`. So the control belongs beside a task
 * that HAS a project, and `TaskRow` does not carry `project_id` today.
 *
 * Writing the client now and the control later is precisely the defect this
 * module's own history records -- a request function is not a caller, and an
 * uncalled one reads like a feature that exists. It ships with its form.
 */
