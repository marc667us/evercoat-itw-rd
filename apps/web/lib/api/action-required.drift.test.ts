import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

/**
 * The red "action required" marker names a ROLE. This asserts the seed
 * actually grants that role the permission the act is gated on.
 *
 * 🔴 NAMING THE WRONG ROLE IS WORSE THAN NAMING NONE.
 *
 * "Action required — Product Development Director must decide it" is a red,
 * confident instruction. If `opportunity.decide` moves to another role, the
 * banner keeps pointing at the Director, people go to the Director, the
 * Director cannot act, and nothing anywhere reports a fault. The string is
 * plain text; no compiler can relate it to a SQL grant.
 *
 * ⚠️ THE SEED IS THE SOURCE, because that is what actually grants the
 * permission. Reading the API's `require_permission(...)` would prove the act
 * is gated and say nothing about WHO holds the gate — which is the only claim
 * this banner makes.
 *
 * ⚠️ IT GUARDS ITSELF FIRST. A regex that stopped matching would compare two
 * empty sets and pass, which is this repository's most-repeated defect shape.
 * The parse is asserted non-empty before any comparison.
 */

const WEB = join(__dirname, "..", "..");
/**
 * EVERY migration, not just the original seed.
 *
 * 🔴 THE FIRST VERSION READ ONLY `002_seed_roles_permissions.sql`, and that
 * was wrong the moment a later migration granted a permission. `research.create`
 * is granted in **058**, so a banner naming it would have failed here with
 * "not granted" while the grant plainly exists — a guard that reports a defect
 * that is not there is as useless as one that misses a defect that is.
 */
const MIGRATIONS = join(WEB, "..", "api", "migrations");
const SCREEN = join(WEB, "app", "innovation", "page.tsx");

/** Role display name → the seed's role code. */
const ROLE_CODES: Readonly<Record<string, string>> = {
  "Product Development Lead": "product_development_lead",
  "Product Development Director": "product_development_director",
  "Product Development Chemist": "product_development_chemist",
};

/**
 * Permissions granted to a role by `SELECT core._grant('<role>', '<perm>', ...);`.
 *
 * ⚠️ STRING SCANNING, NOT A REGEX, AND THE FIRST ATTEMPT IS WHY. The pattern
 * was built with `new RegExp(`...`)` from a TEMPLATE literal, where `\s` is
 * simply `s` — so `[\s\S]` silently became `[sS]` and the pattern matched
 * nothing. The escaping bug was invisible in the source and the test would
 * have compared two empty sets and passed. The guard-the-guard assertion below
 * is the only reason it was caught, which is exactly what it is for.
 */
function grantedTo(sql: string, roleCode: string): Set<string> {
  const opening = "core._grant('" + roleCode + "'";
  const found = new Set<string>();

  // A role may be granted more than once, across more than one migration.
  // Taking only the first block would miss every later grant.
  let start = sql.indexOf(opening);
  while (start !== -1) {
    const end = sql.indexOf(");", start);
    if (end === -1) break;
    for (const quoted of sql.slice(start + opening.length, end).split("'")) {
      // A permission code is `domain.action` — the only quoted token in the
      // block with a dot in it. Commas and newlines fall out on their own.
      if (/^[a-z_]+\.[a-z_]+$/.test(quoted)) found.add(quoted);
    }
    start = sql.indexOf(opening, end);
  }
  return found;
}

describe("the action-required banner names a role that can actually act", () => {
  // Concatenated in filename order, which is migration order.
  const sql = readdirSync(MIGRATIONS)
    .filter((f) => f.endsWith(".sql"))
    .sort()
    .map((f) => readFileSync(join(MIGRATIONS, f), "utf8"))
    // Any separator does: a grant block runs from `core._grant(` to the
    // first `);`, so joining on a statement terminator can neither split a
    // real block nor manufacture a false one.
    .join(" ; ");
  const screen = readFileSync(SCREEN, "utf8");

  // Pull `{ permission: "...", role: "...", ... }` out of BLOCKED_ON.
  const entries = [
    ...screen.matchAll(
      /permission:\s*"([^"]+)",\s*\n\s*role:\s*"([^"]+)"/g,
    ),
  ].map((m) => ({ permission: m[1]!, role: m[2]! }));

  it("finds the mirror at all — a regex that matches nothing must not pass", () => {
    expect(entries.length).toBeGreaterThan(0);
    expect(sql.length).toBeGreaterThan(0);
  });

  it.each(
    [
      ...new Map(entries.map((e) => [`${e.role}::${e.permission}`, e])).values(),
    ].map((e) => [e.role, e.permission] as const),
  )("%s is granted %s by the seed", (role, permission) => {
    const code = ROLE_CODES[role];
    expect(code, `no seed role code known for "${role}"`).toBeDefined();

    const granted = grantedTo(sql, code!);
    // Guard the guard: an unparsed grant block would make every check vacuous.
    expect(granted.size, `parsed no permissions for ${code}`).toBeGreaterThan(0);

    expect(granted.has(permission)).toBe(true);
  });
});
