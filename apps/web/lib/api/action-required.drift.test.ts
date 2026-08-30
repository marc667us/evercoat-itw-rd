import { readFileSync } from "node:fs";
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
const SEED = join(
  WEB,
  "..",
  "api",
  "migrations",
  "002_seed_roles_permissions.sql",
);
const SCREEN = join(WEB, "app", "innovation", "page.tsx");

/** Role display name → the seed's role code. */
const ROLE_CODES: Readonly<Record<string, string>> = {
  "Product Development Lead": "product_development_lead",
  "Product Development Director": "product_development_director",
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
  const start = sql.indexOf(opening);
  if (start === -1) return new Set();
  // Each grant is one statement; it ends at the first `);` after the opening.
  const end = sql.indexOf(");", start);
  if (end === -1) return new Set();

  const body = sql.slice(start + opening.length, end);
  const found = new Set<string>();
  for (const quoted of body.split("'")) {
    // A permission code is `domain.action` — the only quoted token in the
    // block with a dot in it. Commas and newlines fall out on their own.
    if (/^[a-z_]+\.[a-z_]+$/.test(quoted)) found.add(quoted);
  }
  return found;
}

describe("the action-required banner names a role that can actually act", () => {
  const sql = readFileSync(SEED, "utf8");
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
