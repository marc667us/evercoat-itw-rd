/**
 * The client's dashboard role names must match the server's registry.
 *
 * 🔴 TWO LITERALS IN TWO FILES CANNOT BE TYPE-CHECKED INTO AGREEMENT.
 *
 * `DASHBOARD_ROLES` here and `ROLE_DASHBOARDS` in
 * `apps/api/app/domains/dashboards/service.py` are the same fact written
 * twice. If the server renames or adds one, nothing in TypeScript notices —
 * the screen simply asks for a name the server does not know and gets a 404,
 * which renders as "this dashboard could not be loaded" rather than as a
 * broken build.
 *
 * So this test READS THE PYTHON, exactly as `knowledge.drift.test.ts` does.
 * A test comparing a hand-written list against another hand-written list
 * proves only that somebody typed twice.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { DASHBOARD_ROLES, dashboardForRoles } from "./dashboards";

const SERVICE = join(
  __dirname,
  "..",
  "..",
  "..",
  "..",
  "apps",
  "api",
  "app",
  "domains",
  "dashboards",
  "service.py",
);

/** The keys of `ROLE_DASHBOARDS = { "chemist": ..., ... }`. */
function serverRoles(): string[] {
  const source = readFileSync(SERVICE, "utf8");
  const start = source.indexOf("ROLE_DASHBOARDS = {");
  if (start === -1) return [];
  const end = source.indexOf("}", start);
  if (end === -1) return [];
  const block = source.slice(start, end);
  return [...block.matchAll(/"([a-z_]+)":/g)].map((m) => m[1] as string);
}

describe("the dashboard roles the client asks for exist on the server", () => {
  it("reads a real registry", () => {
    // 🔴 THE GUARD ON THE GUARD. If the Python is renamed or the shape of the
    // registry changes, `serverRoles()` returns nothing and every assertion
    // below passes vacuously — a check that walks through its own gap.
    expect(serverRoles().length).toBeGreaterThanOrEqual(4);
  });

  it("🔴 every role the client can request is one the server can build", () => {
    const server = serverRoles();
    const unknown = DASHBOARD_ROLES.filter((role) => !server.includes(role));
    expect(
      unknown,
      "the client would request these and receive a 404; add them to " +
        "ROLE_DASHBOARDS in the Python service or remove them here",
    ).toEqual([]);
  });

  it("🔴 and every dashboard the server builds is reachable from the client", () => {
    // The other direction. A role the server can build that no client name
    // maps to is a dashboard nobody can open — the defect this whole module
    // was written to fix, reintroduced one role at a time.
    const missing = serverRoles().filter(
      (role) => !(DASHBOARD_ROLES as readonly string[]).includes(role),
    );
    expect(missing, "the server builds these and nothing can ask for them").toEqual([]);
  });
});

describe("choosing which dashboard to open", () => {
  it("gives each development role its own view", () => {
    expect(dashboardForRoles(["product_development_chemist"])).toBe("chemist");
    expect(dashboardForRoles(["product_development_engineer"])).toBe("engineer");
    expect(dashboardForRoles(["product_development_lead"])).toBe("lead");
    expect(dashboardForRoles(["product_development_director"])).toBe("director");
  });

  it("🔴 a director does not get the chemist's screen", () => {
    // The exact symptom that started this: signed in as the director, the
    // chemist's dashboard appeared.
    expect(dashboardForRoles(["product_development_director"])).not.toBe("chemist");
  });

  it("prefers the wider view when somebody holds two", () => {
    expect(
      dashboardForRoles(["product_development_chemist", "product_development_lead"]),
    ).toBe("lead");
    expect(
      dashboardForRoles(["product_development_engineer", "product_development_director"]),
    ).toBe("director");
  });

  it("🔴 returns null rather than defaulting somebody into a role that is not theirs", () => {
    // Falling back to `chemist` would be the original defect written down as
    // a rule. An executive viewer has no role dashboard and the screen says so.
    expect(dashboardForRoles(["executive_viewer"])).toBeNull();
    expect(dashboardForRoles(["procurement_specialist"])).toBeNull();
    expect(dashboardForRoles(["administrator"])).toBeNull();
    expect(dashboardForRoles([])).toBeNull();
  });
});
