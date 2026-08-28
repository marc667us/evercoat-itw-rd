/**
 * Role dashboards, over HTTP.
 *
 * 🔴 `GET /api/dashboards/{role}` HAD NO BROWSER CALLER AT ALL.
 *
 * The endpoint, four role builders (`chemist`, `engineer`, `lead`,
 * `director`), the analysis conductor behind it and `test_role_dashboards.py`
 * all existed. A `grep` for `api/dashboards` across `apps/web` returned
 * nothing. So every signed-in person saw the same fixed dashboard body no
 * matter who they were — the operator signed in as the **director** and got
 * the chemist's screen — while the sidebar, which is permission-driven, was
 * correctly showing them a director's navigation.
 *
 * That is this project's most-repeated defect: a route with no caller. The
 * live suite could not catch it, because nothing asserted that two roles see
 * different things.
 *
 * ⚠️ THE ROLE IS A VIEW, NOT A PRIVILEGE, AND THAT IS THE SERVER'S RULE.
 *
 * `dashboards.py`'s own header: *"asking for the director view does not show a
 * chemist the portfolio — it shows them the portfolio they can already
 * reach."* Every panel is filtered by RLS and the project-confidentiality
 * predicate regardless of which name is in the path. So choosing a view here
 * is a presentation decision and grants nothing, which is why this module may
 * pick one from the caller's roles without that being an authorization
 * decision in the frontend (§6 forbids those).
 */

import { z } from "zod";

import { apiRequest, type ApiCredentials } from "./client";

/**
 * One panel.
 *
 * 🔴 `available: false` IS NOT AN EMPTY LIST, AND THE SCREEN MUST NOT RENDER
 * IT AS ONE. The server is explicit: a panel whose engine is not built yet
 * comes back unavailable WITH the reason, because "nothing to report" and
 * "not built yet" are different answers and a reader cannot tell them apart
 * from an empty table.
 */
export const dashboardPanelSchema = z.object({
  available: z.boolean(),
  reason: z.string().nullable().optional(),
  // Rows are panel-shaped and differ between panels; each carries the id of
  // the source record so §2's drill-down is satisfiable without a second
  // round trip. Kept loose on purpose rather than enumerated wrongly.
  rows: z.array(z.record(z.string(), z.unknown())).default([]),
  count: z.number().nullable().optional(),
});

export type DashboardPanel = z.infer<typeof dashboardPanelSchema>;

/** The response is an object of named panels; the names differ per role. */
export const roleDashboardSchema = z.record(z.string(), z.unknown());

export type RoleDashboard = Record<string, unknown>;

/**
 * The four the server can build, in the order a person is most likely to want
 * their own view first.
 *
 * 🔴 DERIVED FROM THE SERVER'S `ROLE_DASHBOARDS`, and it must stay in step:
 * asking for a name it does not know is a 404. `dashboards.drift.test.ts`
 * reads the Python registry and fails if these disagree — the same shape as
 * `knowledge.drift.test.ts`, because two literals in two files cannot be
 * type-checked into agreement.
 */
export const DASHBOARD_ROLES = ["chemist", "engineer", "lead", "director"] as const;

export type DashboardRole = (typeof DASHBOARD_ROLES)[number];

/**
 * Which dashboard to open for a caller, from the realm roles they hold.
 *
 * The ten realm roles do not map one-to-one onto the four dashboards, so this
 * is a deliberate, stated mapping rather than a string match that would
 * silently fall through. Most-senior-first: somebody who is both a lead and a
 * chemist gets the lead view, because that is the wider one and they can
 * switch.
 *
 * Returns `null` when the caller holds no role with a dashboard — an
 * executive viewer or a procurement specialist — and the screen then says so
 * rather than showing them a chemist's queue that is not theirs.
 */
export function dashboardForRoles(roles: readonly string[]): DashboardRole | null {
  const held = new Set(roles);
  if (held.has("product_development_director")) return "director";
  if (held.has("product_development_lead")) return "lead";
  if (held.has("product_development_engineer")) return "engineer";
  if (held.has("product_development_chemist")) return "chemist";
  // 🔴 NOT A FALLBACK TO `chemist`. That is precisely the defect being fixed:
  // showing somebody a role's screen that is not theirs. An administrator or
  // an executive viewer has no role dashboard, and saying so is the honest
  // answer.
  return null;
}

export function fetchRoleDashboard(
  credentials: ApiCredentials,
  role: string,
  signal?: AbortSignal,
): Promise<RoleDashboard> {
  return apiRequest(
    { path: `/api/dashboards/${role}`, credentials, signal },
    (payload) => roleDashboardSchema.parse(payload),
  );
}
