"use client";

/**
 * The signed-in caller's OWN dashboard, from source records.
 *
 * 🔴 WHY THIS EXISTS: THE DIRECTOR WAS SEEING THE CHEMIST'S SCREEN.
 *
 * `GET /api/dashboards/{role}` has existed for slices, with four builders
 * (chemist, engineer, lead, director), the analysis conductor behind it and
 * `test_role_dashboards.py` covering it. A `grep` for `api/dashboards` across
 * `apps/web` returned **nothing**. So the dashboard body was one fixed
 * demonstration layout for everybody, and the operator signing in as the
 * director got a chemist's view — while the sidebar, which is permission
 * driven, correctly showed them a director's navigation. The two disagreed
 * about who was looking.
 *
 * That is the "route with no caller" defect this project has counted 23 prior
 * instances of, and no test caught it because nothing asserted that two roles
 * see different things.
 *
 * ⚠️ THE ROLE IS A VIEW, NOT A PRIVILEGE. `dashboards.py` is explicit that
 * asking for a view does not widen what you can see: every panel is filtered
 * by RLS and the project-confidentiality predicate regardless. So this
 * component picking a view is presentation, and grants nothing — §6 keeps
 * authorization on the server, where it is.
 *
 * ⚠️ `available: false` IS RENDERED AS ITSELF, NEVER AS AN EMPTY TABLE. The
 * server returns unavailable panels WITH a reason precisely because a reader
 * cannot tell "nothing to report" from "not built yet", and an empty table
 * says the first while meaning the second.
 */

import { useDashboardRole, useRoleDashboard } from "@/lib/api/hooks";
import {
  incompleteVisibilityOf,
  panelsOf,
  type DashboardPanel,
} from "@/lib/api/dashboards";
import { serverMessage } from "@/lib/api/client";

/** Panel keys are snake_case; a heading is not. */
function words(key: string): string {
  const spaced = key.replace(/_/g, " ");
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

const ROLE_LABEL: Record<string, string> = {
  chemist: "Product Development Chemist",
  engineer: "Product Development Engineer",
  lead: "Product Development Lead",
  director: "Product Development Director",
};

function Panel({ name, panel }: { name: string; panel: DashboardPanel }) {
  return (
    <li className="rounded border border-slate-200 bg-white p-4">
      <div className="flex flex-wrap items-baseline gap-2">
        <h3 className="flex-1 text-sm font-semibold text-slate-900">{words(name)}</h3>
        {panel.available && typeof panel.count === "number" && (
          /* 🔴 `50+` WHEN THE SERVER SAYS THE QUERY HIT ITS LIMIT. Rendering a
             capped count as an exact one understates a backlog with nothing to
             say it did — which is the whole reason `truncated` is on the wire.
             The title carries the long form for a screen reader. */
          <span
            className="rounded border border-slate-300 px-1.5 py-0.5 text-xs font-medium tabular-nums text-slate-700"
            title={
              panel.truncated
                ? `At least ${panel.count}; the query stopped at its limit.`
                : undefined
            }
          >
            {panel.count}
            {panel.truncated ? "+" : ""}
          </span>
        )}
      </div>

      {!panel.available ? (
        /* 🔴 THE REASON, IN WORDS. Not an empty list: "nothing to report" and
           "not built yet" are different answers and only one of them means
           the reader can stop looking. */
        <p className="mt-2 text-xs text-slate-600">
          Not available yet{panel.reason ? ` — ${panel.reason}` : "."}
        </p>
      ) : panel.rows.length === 0 ? (
        <p className="mt-2 text-sm text-slate-600">Nothing here needs you.</p>
      ) : (
        <ul className="mt-2 space-y-1">
          {panel.rows.slice(0, 5).map((row, index) => (
            <li key={String(row.id ?? index)} className="text-sm text-slate-800">
              {String(
                row.title ??
                  row.name ??
                  row.project_code ??
                  row.formula_code ??
                  row.id ??
                  "a record",
              )}
            </li>
          ))}
          {panel.rows.length > 5 && (
            <li className="text-xs text-slate-600">
              and {panel.rows.length - 5} more
            </li>
          )}
        </ul>
      )}
    </li>
  );
}

export function RoleDashboard() {
  const role = useDashboardRole();
  const { data, isLoading, error, unavailable } = useRoleDashboard(role);

  // Not signed in, or this build has no API. The demonstration body below
  // still renders and says what it is; adding a second banner here would be
  // noise.
  if (unavailable !== null && role === null) return null;

  if (role === null) {
    return (
      <section
        aria-labelledby="role-dashboard-heading"
        className="rounded border border-slate-200 bg-white p-4"
      >
        <h2 id="role-dashboard-heading" className="text-sm font-semibold text-slate-900">
          No role dashboard for your roles
        </h2>
        {/* 🔴 SAID PLAINLY RATHER THAN DEFAULTING. Showing an executive viewer
            the chemist's queue is the exact defect this component fixes; doing
            it as a "sensible fallback" would just be the same bug with a
            comment. */}
        <p className="mt-1 text-xs text-slate-600">
          Role dashboards exist for the chemist, engineer, lead and director.
          Your membership holds none of those, so nothing role-specific is
          shown — rather than showing you somebody else&rsquo;s screen.
        </p>
      </section>
    );
  }

  // 🔴 `panelsOf`, NOT A TOP-LEVEL WALK. The previous version iterated the
  // response's top-level keys and SKIPPED `panels` — which is where every
  // panel lives — so this component rendered "returned no panels" for every
  // role while the server was sending 21 of them. See `panelsOf`'s comment.
  const panels = panelsOf(data);
  const incomplete = incompleteVisibilityOf(data);

  return (
    <section aria-labelledby="role-dashboard-heading" className="mb-6">
      <div className="flex flex-wrap items-baseline gap-2">
        <h2 id="role-dashboard-heading" className="text-sm font-semibold text-slate-900">
          {ROLE_LABEL[role] ?? words(role)} view
        </h2>
        {/* Naming the view is half the fix: the previous screen never said
            whose dashboard it was, which is why nobody noticed it was always
            the same one. */}
        <span className="text-xs text-slate-600">from your source records</span>
      </div>

      {/* 🔴 THE CAVEAT SITS ABOVE EVERY PANEL, BECAUSE IT QUALIFIES ALL OF THEM.
          A lead who leads a restricted project they are not a MEMBER of cannot
          see its risks, milestones or research — so those panels are SHORT, not
          empty, and without this they read as a clean bill of health. The
          server has always sent it at the top level for exactly this reason;
          the screen dropped it, which recreated the false all-clear the field
          exists to prevent. Codex found it. */}
      {incomplete.length > 0 && (
        <div role="note" className="mt-2 rounded border border-amber-300 bg-amber-200 p-3">
          <p className="text-xs font-semibold text-amber-900">
            The panels below are incomplete for {incomplete.length}{" "}
            {incomplete.length === 1 ? "project" : "projects"}.
          </p>
          <ul className="mt-1 list-disc space-y-1 pl-4">
            {incomplete.map((row, index) => (
              <li key={index} className="text-xs text-amber-900">
                {row.reason}
              </li>
            ))}
          </ul>
        </div>
      )}

      {error !== null ? (
        <p role="alert" className="mt-2 text-sm text-red-900">
          This dashboard could not be loaded: {serverMessage(error)}
        </p>
      ) : data === undefined ? (
        <p className="mt-2 text-sm text-slate-600">
          {isLoading ? "Loading your dashboard…" : ""}
        </p>
      ) : panels.length === 0 ? (
        <p className="mt-2 text-sm text-slate-600">
          This role&rsquo;s dashboard returned no panels.
        </p>
      ) : (
        <ul className="mt-3 grid gap-3 md:grid-cols-2">
          {panels.map(([name, panel]) => (
            <Panel key={name} name={name} panel={panel} />
          ))}
        </ul>
      )}
    </section>
  );
}
