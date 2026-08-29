import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { MATERIAL_TRANSITIONS } from "./materials";

/**
 * The client's material status ladder must match the server's.
 *
 * 🔴 TWO LITERALS IN TWO FILES CANNOT BE TYPE-CHECKED INTO AGREEMENT.
 *
 * `MATERIAL_TRANSITIONS` here and `TRANSITION_PERMISSION` in
 * `apps/api/app/domains/materials/service.py` are the same fact written twice.
 * If the server adds a rung, tightens a permission, or decides that demoting a
 * `preferred` material straight to `development` is allowed after all, nothing
 * in TypeScript notices — the screen simply offers the wrong set of moves, and
 * the ones it offers wrongly come back as 403s that look like a bug in
 * authorization rather than a stale copy.
 *
 * So this READS THE PYTHON, exactly as `dashboards.drift.test.ts` and
 * `knowledge.drift.test.ts` do. A test comparing one hand-written list against
 * another proves only that somebody typed twice.
 *
 * ⚠️ IT PARSES A DICT LITERAL, WHICH IS BRITTLE ON PURPOSE. If the Python is
 * restructured so this regex stops matching, the guard below fails rather than
 * silently finding zero transitions and passing — a check that cannot see is
 * the failure mode this whole file exists to prevent.
 */

const SERVICE = join(
  __dirname,
  "..",
  "..",
  "..",
  "api",
  "app",
  "domains",
  "materials",
  "service.py",
);

/** `("development", "approved"): "material.approve_lab",` */
const ROW = /\(\s*"(\w+)"\s*,\s*"(\w+)"\s*\)\s*:\s*"([a-z_]+\.[a-z_]+)"/g;

function serverTransitions(): Map<string, Map<string, string>> {
  const source = readFileSync(SERVICE, "utf8");
  const start = source.indexOf("TRANSITION_PERMISSION: dict[tuple[str, str], str] = {");
  expect(start, "TRANSITION_PERMISSION was not found — has it been renamed?").toBeGreaterThan(-1);
  const body = source.slice(start, source.indexOf("\n}", start));

  const out = new Map<string, Map<string, string>>();
  for (const match of body.matchAll(ROW)) {
    // `noUncheckedIndexedAccess` is on, and the groups are typed as possibly
    // undefined even though the regex cannot match without them. Checked
    // rather than asserted: a `!` here would be the one place this file tells
    // TypeScript to stop looking.
    const [, from, to, permission] = match;
    if (from === undefined || to === undefined || permission === undefined) continue;
    const forSource = out.get(from) ?? new Map<string, string>();
    forSource.set(to, permission);
    out.set(from, forSource);
  }
  return out;
}

describe("the material status ladder", () => {
  it("finds the transitions it is meant to be checking", () => {
    // The guard on the guard. A regex that stops matching would turn every
    // assertion below into a comparison of two empty things.
    const server = serverTransitions();
    const rows = [...server.values()].reduce((n, m) => n + m.size, 0);
    expect(rows).toBeGreaterThanOrEqual(12);
  });

  it("🔴 offers exactly the moves the server allows, from every status", () => {
    const server = serverTransitions();
    for (const [from, targets] of server) {
      const client = MATERIAL_TRANSITIONS[from] ?? [];
      expect(
        [...client].map((t) => t.to).sort(),
        `the client offers a different set of moves from "${from}"`,
      ).toEqual([...targets.keys()].sort());
    }
  });

  it("🔴 requires exactly the permission the server requires for each move", () => {
    const server = serverTransitions();
    for (const [from, targets] of server) {
      for (const [to, permission] of targets) {
        const line = (MATERIAL_TRANSITIONS[from] ?? []).find((t) => t.to === to);
        expect(line?.permission, `${from} → ${to} names the wrong permission`).toBe(permission);
      }
    }
  });

  it("does not invent a status the server has never heard of", () => {
    const server = serverTransitions();
    for (const from of Object.keys(MATERIAL_TRANSITIONS)) {
      expect(server.has(from), `the client offers moves from "${from}"`).toBe(true);
    }
  });

  it("keeps the rule that a preferred material is demoted one rung at a time", () => {
    // Stated as its own case because it is a DECISION, not an accident of the
    // table: reversing two decisions in one action hides which was reversed.
    // If somebody adds `preferred → development` to the server, the equality
    // tests above will fail — and this says why that would matter.
    expect(MATERIAL_TRANSITIONS.preferred?.map((t) => t.to)).not.toContain("development");
  });
});
