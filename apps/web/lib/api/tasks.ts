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
  created_at: z.string().nullable(),
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
