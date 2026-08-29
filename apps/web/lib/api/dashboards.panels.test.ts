import { describe, expect, it } from "vitest";

import { incompleteVisibilityOf, panelsOf } from "./dashboards";

/**
 * 🔴 THE ROLE DASHBOARD RENDERED NOTHING, FOR EVERY ROLE, AND NOTHING CAUGHT IT.
 *
 * `role-dashboard.tsx` walked the response's TOP-LEVEL keys and explicitly
 * skipped `panels` — the one key that holds every panel. So the component
 * rendered "this role's dashboard returned no panels" while the server was
 * sending twenty-one of them.
 *
 * It survived because the API suite asserts the RESPONSE and the component had
 * no test at all. That is this project's most-repeated shape — a producer with
 * no reader — moved one layer up from the database, where it is harder to see
 * and where "the tests are green" is least informative.
 *
 * ⚠️ THE FIXTURE BELOW IS THE SERVER'S REAL SHAPE, not a convenient one. It was
 * copied from what `chemist_dashboard` returns: `role` and `panels` at the top,
 * every panel `{available, reason, rows, count, truncated}` inside. A test
 * written against a flattened shape would have passed against the broken code,
 * which is exactly how the defect stayed invisible.
 */

const CHEMIST_RESPONSE = {
  role: "chemist",
  panels: {
    my_active_formulations: {
      available: true,
      reason: null,
      rows: [{ id: "v1", version_code: "F-001-V1" }],
      count: 1,
      truncated: false,
    },
    doe_experiments: {
      available: false,
      reason: "DOE arrives in Slice 12 (pyDOE3, runs linked to formula and batch).",
      rows: [],
      count: 0,
      truncated: false,
    },
    research_investigations: {
      available: false,
      reason: "requires the research.view permission",
      rows: [],
      count: 0,
      truncated: false,
    },
    material_alerts: {
      available: true,
      reason: null,
      rows: [{ id: "a1", severity: "critical" }],
      count: 1,
      truncated: false,
    },
  },
};

describe("panelsOf", () => {
  it("🔴 finds the panels the server nests under `panels`", () => {
    const panels = panelsOf(CHEMIST_RESPONSE);
    expect(panels.map(([name]) => name)).toEqual([
      "my_active_formulations",
      "doe_experiments",
      "research_investigations",
      "material_alerts",
    ]);
  });

  it("keeps the three states apart, because a screen cannot infer them", () => {
    const byName = Object.fromEntries(panelsOf(CHEMIST_RESPONSE));

    // Answered.
    expect(byName.my_active_formulations?.available).toBe(true);
    expect(byName.my_active_formulations?.rows).toHaveLength(1);

    // Not built — and the reason is what distinguishes it from an empty queue.
    expect(byName.doe_experiments?.available).toBe(false);
    expect(byName.doe_experiments?.reason).toContain("Slice 12");

    // Not yours to act on. Same empty rows, different statement.
    expect(byName.research_investigations?.available).toBe(false);
    expect(byName.research_investigations?.reason).toContain("research.view");
  });

  it("does not treat `role` as a panel", () => {
    expect(panelsOf(CHEMIST_RESPONSE).map(([name]) => name)).not.toContain("role");
  });

  it("does not treat the lead's `incomplete_visibility` caveat as a panel", () => {
    // It qualifies EVERY panel, which is why the server puts it at the top
    // level. Rendering it as a panel would bury a caveat inside one of six.
    const lead = {
      role: "lead",
      incomplete_visibility: [{ id: "p1", reason: "you lead it but are not a member" }],
      panels: {
        assigned_projects: {
          available: true,
          reason: null,
          rows: [],
          count: 0,
          truncated: false,
        },
      },
    };
    expect(panelsOf(lead).map(([name]) => name)).toEqual(["assigned_projects"]);
  });

  it("survives the shapes a failed request actually produces", () => {
    // `useRoleDashboard` yields `undefined` while loading and on error, and the
    // component called this before checking. Returning [] beats throwing: the
    // screen then says "no panels", which is true of what it received.
    expect(panelsOf(undefined)).toEqual([]);
    expect(panelsOf(null)).toEqual([]);
    expect(panelsOf({ role: "chemist" })).toEqual([]);
    expect(panelsOf({ role: "chemist", panels: null })).toEqual([]);
    expect(panelsOf("not an object")).toEqual([]);
  });

  it("skips a malformed panel rather than dropping the whole dashboard", () => {
    const mixed = {
      role: "chemist",
      panels: {
        good: { available: true, reason: null, rows: [], count: 0, truncated: false },
        // `available` is required; a panel missing it is not a panel.
        bad: { rows: "not an array" },
      },
    };
    expect(panelsOf(mixed).map(([name]) => name)).toEqual(["good"]);
  });

  it("🔴 carries `truncated`, so a capped count can be rendered as capped", () => {
    // The server sets it when a panel's query hit its LIMIT. Dropping it here
    // is what let the renderer show "50" as an exact backlog.
    const capped = panelsOf({
      role: "lead",
      panels: {
        pending_approvals: {
          available: true,
          reason: null,
          rows: [],
          count: 50,
          truncated: true,
        },
      },
    });
    expect(capped[0]?.[1].truncated).toBe(true);
  });
});

describe("incompleteVisibilityOf", () => {
  it("🔴 returns the caveat the screen was throwing away", () => {
    // A lead who leads a restricted project they are not a MEMBER of gets
    // SHORT panels, not empty ones — and without this they read as a clean
    // bill of health.
    const lead = {
      role: "lead",
      incomplete_visibility: [
        { id: "p1", reason: "you lead this restricted project but are not a member of it" },
        { id: "p2", reason: "same again" },
      ],
      panels: {},
    };
    expect(incompleteVisibilityOf(lead).map((r) => r.reason)).toEqual([
      "you lead this restricted project but are not a member of it",
      "same again",
    ]);
  });

  it("is empty for the roles that do not have one, and for a failed request", () => {
    expect(incompleteVisibilityOf({ role: "chemist", panels: {} })).toEqual([]);
    expect(incompleteVisibilityOf(undefined)).toEqual([]);
    expect(incompleteVisibilityOf({ incomplete_visibility: "not an array" })).toEqual([]);
    // A row with no readable reason is dropped rather than rendered blank.
    expect(incompleteVisibilityOf({ incomplete_visibility: [{ id: "p1" }] })).toEqual([]);
  });
});
