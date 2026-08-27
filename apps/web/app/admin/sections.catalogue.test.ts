/**
 * Every Administration section names a permission the DATABASE actually seeds.
 *
 * 🔴 RAISED BY THE SUPERVISOR, AND IT NAMED THE EXACT GAP.
 *
 * `context-submenu.test.ts` proves the filter and, once `ADMIN_SECTIONS` was
 * imported rather than re-typed, that the real list is the one being filtered.
 * It still could not catch a WRONG code: its "offers every section" case builds
 * its permission set *from `ADMIN_SECTIONS` itself*, so it is tautological with
 * respect to the strings, and the `/^admin\./` case only checks the prefix.
 *
 * So `admin.stage_gate`, `admin.audits` or `admin.organisation` would pass
 * every test in that file while making the section **invisible to every real
 * caller forever** — which is precisely the failure
 * `context-submenu.tsx`'s own docstring warns about, left undetectable by the
 * tests written to close it. *A guard that cannot fail is not a guard.*
 *
 * 🔴 SO THIS READS THE SEED, WHICH IS THE ONLY THING THAT MAKES A CODE REAL.
 *
 * `apps/api/migrations/002_seed_roles_permissions.sql` is where a permission
 * comes into existence. Anything not in it cannot be held by anybody, whatever
 * the TypeScript says. Reading across the tier boundary is deliberate: the two
 * halves of this rule live in two languages and cannot be type-checked into
 * agreement, so the only alternative to reading one from the other is a third
 * copy — this repository's most repeated defect, one more time.
 *
 * ⚠️ IT ASSERTS THE FILE WAS FOUND AND PARSED FIRST. A regex that matches
 * nothing yields an empty catalogue, against which "every section's code is in
 * the catalogue" is false for everything — but a `.every()` over an empty
 * expectation, or a silently-empty read, is how this class of test passes while
 * measuring nothing. The count is asserted before anything is compared to it.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { ADMIN_SECTIONS } from "./sections";

/** Where a permission comes into existence. */
const SEED = join(
  process.cwd(),
  "..",
  "..",
  "apps",
  "api",
  "migrations",
  "002_seed_roles_permissions.sql",
);

/**
 * Every permission code the seed inserts.
 *
 * The rows read `('admin.users', 'admin', 'Manage users and memberships'),` —
 * a quoted code first on the line. Matching the quoted token at the start of a
 * tuple is narrow enough not to sweep up the role names and descriptions that
 * share the file.
 */
function seededPermissions(): Set<string> {
  const sql = readFileSync(SEED, "utf8");
  const codes = new Set<string>();
  for (const match of sql.matchAll(/\(\s*'([a-z_]+\.[a-z_]+)'\s*,/g)) {
    const code = match[1];
    if (code !== undefined) {
      codes.add(code);
    }
  }
  return codes;
}

describe("ADMIN_SECTIONS against the seeded permission catalogue", () => {
  it("🔴 finds the seed and reads a plausible number of permissions from it", () => {
    // The guard on the guard. If the path moves or the insert is reformatted,
    // this fails HERE — with a message naming the file — instead of turning
    // the real assertion below into a comparison against an empty set.
    const seeded = seededPermissions();

    expect(
      seeded.size,
      `read no permission codes from ${SEED} — the path or the INSERT format changed`,
    ).toBeGreaterThan(50);
    // Two spot checks in opposite directions: one code that must be there, and
    // one shaped like a code that must not, so a regex matching everything is
    // caught too.
    expect(seeded.has("admin.users")).toBe(true);
    expect(seeded.has("admin.definitely_not_a_permission")).toBe(false);
  });

  it("every section names a code the database seeds", () => {
    const seeded = seededPermissions();

    const unknown = ADMIN_SECTIONS.filter(
      (section) => section.permission !== undefined && !seeded.has(section.permission),
    ).map((section) => `${section.label} → ${section.permission}`);

    expect(
      unknown,
      "these Administration sections are gated on a permission no role can " +
        "ever hold, so they are invisible to every caller forever",
    ).toEqual([]);
  });

  it("🔴 and the sections are not gated on the same code as each other by accident", () => {
    // 🔴 THIS GUARD FIRED ON A REAL CHANGE, WHICH IS WHAT IT IS FOR.
    //
    // Building the Reference Data section on 2026-08-27 made it share
    // `admin.reference_data` with Test Methods, and this test went red. That is
    // the correct outcome: two sections on one permission is either a typo or a
    // decision, and the difference is not visible in the array. It is a
    // decision here — units and product families live under `/api/admin`, test
    // methods under `/api/testing`, so they are separate SECTIONS served by
    // separate endpoints that happen to require the same code.
    //
    // The expectation is widened deliberately rather than the assertion
    // loosened. A test that stopped checking would not have caught the next
    // one.
    //
    // Roles and Permissions share `admin.roles` for the same kind of reason:
    // both are served by endpoints requiring it. Everything else must differ,
    // because a section silently copying its neighbour's code is the typo this
    // file exists to catch and it would not show up as an unknown code.
    const byCode = new Map<string, string[]>();
    for (const section of ADMIN_SECTIONS) {
      if (section.permission === undefined) continue;
      byCode.set(section.permission, [...(byCode.get(section.permission) ?? []), section.label]);
    }

    const shared = [...byCode.entries()]
      .filter(([, labels]) => labels.length > 1)
      .map(([code, labels]) => `${code}: ${labels.join(", ")}`);

    expect(shared, "unexpected sections sharing a permission").toEqual([
      "admin.roles: Roles, Permissions",
      "admin.reference_data: Reference Data, Test Methods",
    ]);
  });
});
