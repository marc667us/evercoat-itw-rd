import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { ASSIGNABLE_ROLES } from "./tasks";

/**
 * The roles a task can be addressed to must be the roles that exist.
 *
 * 🔴 A TASK ADDRESSED TO A ROLE NOBODY HOLDS REACHES NOBODY, AND NOTHING SAYS SO.
 *
 * `my_work` selects `assigned_user_id = :uid OR (assigned_user_id IS NULL AND
 * assigned_role = ANY(:roles))`. A misspelt or retired code in this list is
 * therefore not an error at any layer: the POST succeeds, the row is written,
 * the CHECK constraint is satisfied because the field is non-empty, and the
 * task simply never appears in anybody's queue. The person who raised it
 * believes they assigned work.
 *
 * So this reads the seed migration — the same technique as
 * `materials.drift.test.ts`, for the same reason: two literals in two files
 * cannot be type-checked into agreement, and the failure mode here is silence.
 *
 * ⚠️ IT ASSERTS BOTH DIRECTIONS. A code here that the seed does not have is the
 * silent-black-hole case above. A seeded role MISSING from here is the quieter
 * one: work simply cannot be addressed to that role, and nothing anywhere
 * reports a role that never receives any.
 */

const SEED = join(
  __dirname,
  "..",
  "..",
  "..",
  "api",
  "migrations",
  "002_seed_roles_permissions.sql",
);

/** The codes in `INSERT INTO core.roles (code, name, is_seeded, description)`. */
function seededRoles(): Set<string> {
  const source = readFileSync(SEED, "utf8");
  const start = source.indexOf("INSERT INTO core.roles (code, name, is_seeded, description)");
  expect(start, "the roles INSERT was not found — has the seed been restructured?").toBeGreaterThan(
    -1,
  );
  const end = source.indexOf("ON CONFLICT", start);
  expect(end, "the roles INSERT does not end where this parser expects").toBeGreaterThan(start);

  // `('product_development_chemist',  'Product Development Chemist',  TRUE,`
  const block = source.slice(start, end);
  return new Set(
    [...block.matchAll(/\(\s*'([a-z_]+)'\s*,/g)].flatMap((m) => (m[1] === undefined ? [] : [m[1]])),
  );
}

describe("the roles a task can be addressed to", () => {
  it("finds the seeded roles it is meant to be checking", () => {
    // The guard on the guard. An empty set would make both directions below
    // pass by comparing nothing, and CLAUDE.md §6 fixes the number at ten.
    const seeded = seededRoles();
    expect(seeded.size).toBe(10);
    expect(seeded.has("product_development_chemist")).toBe(true);
  });

  it("offers no role the database does not have", () => {
    const seeded = seededRoles();
    const invented = ASSIGNABLE_ROLES.map((r) => r.code).filter((code) => !seeded.has(code));
    expect(
      invented,
      "a task addressed to one of these would be written, accepted, and appear " +
        "in nobody's queue — the POST succeeds and the work vanishes",
    ).toEqual([]);
  });

  it("offers every role the database has", () => {
    // Widened to `string` deliberately: `ASSIGNABLE_ROLES` is `as const`, so
    // a `Set` of its literal union would refuse a comparison against a code
    // read out of the SQL -- and refusing the comparison is refusing the
    // test. The whole point is to compare against something TypeScript
    // cannot see.
    const offered = new Set<string>(ASSIGNABLE_ROLES.map((r) => r.code));
    const unreachable = [...seededRoles()].filter((code) => !offered.has(code));
    expect(
      unreachable,
      "work cannot be addressed to these roles at all, and nothing reports a " +
        "role that never receives any",
    ).toEqual([]);
  });

  it("labels every role rather than showing a code", () => {
    // `product_development_chemist` in a dropdown is a database identifier
    // leaking into a person's decision. Each entry carries the seed's own name.
    for (const role of ASSIGNABLE_ROLES) {
      expect(role.label).not.toContain("_");
      expect(role.label.length).toBeGreaterThan(0);
    }
  });
});
