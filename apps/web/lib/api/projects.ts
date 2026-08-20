/**
 * Projects, over HTTP.
 *
 * Parsed rather than cast, for the reason set out at length in
 * `materials.ts`: a server that renamed a field would hand back rows whose
 * value is `undefined`, and the grid would render a column of blanks that
 * looks exactly like a database with nothing recorded. Parsing turns that
 * into a named error on the screen that consumes it.
 *
 * 🔴 WHAT THE LIST ENDPOINT DOES **NOT** RETURN
 *
 * `ProjectSummary` (apps/api/app/api/projects.py:80) carries the project's
 * own columns and nothing else. It has no gate progress, no requirement
 * counts and no team lead — each of those needs a separate query, and the
 * API exposes them on separate routes (`/dashboard`,
 * `/requirements/matrix`, `/members`) precisely so a list of forty
 * projects does not run forty sub-queries.
 *
 * The demonstration dataset DOES carry them, because it is a bundled
 * fixture with no cost to joining. That difference is the trap: a grid
 * built to the fixture's shape would show three rich columns on
 * demonstration data and three empty ones on live data, and the obvious
 * "fix" is to invent something to put in them.
 *
 * So those columns are not on the list at all. They belong to the project
 * detail screen, where the routes that answer them are already called.
 * Same judgement as `materials.ts` making the supplier column a COUNT
 * rather than inventing names it had not fetched.
 */

import { z } from "zod";

import { apiRequest, type ApiCredentials } from "./client";

export const projectSchema = z.object({
  id: z.string(),
  project_code: z.string(),
  name: z.string(),
  product_family: z.string().nullable(),
  status: z.string(),
  priority: z.string(),
  current_stage: z.string().nullable(),
  confidentiality: z.string(),
  // Serialised from a DATE, or absent entirely — the field is declared
  // `object | None = None` on the model, so it may be missing rather than
  // null. `.optional().nullable()` covers both; treating "missing" as a
  // parse failure would reject perfectly valid rows.
  target_release_date: z.string().nullable().optional(),
});

export type Project = z.infer<typeof projectSchema>;

const projectList = z.array(projectSchema);

export function fetchProjects(
  credentials: ApiCredentials,
  signal?: AbortSignal,
): Promise<Project[]> {
  return apiRequest({ path: "/api/projects", credentials, signal }, (payload) =>
    projectList.parse(payload),
  );
}
