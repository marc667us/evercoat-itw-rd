import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

/**
 * Every permission a screen's `MAY` block names must be one its API module
 * actually gates on.
 *
 * 🔴 A MIRROR THAT DRIFTS IS A GATE ON NOTHING, AND IT FAILS OPEN OR CLOSED
 * WITH EQUAL SILENCE.
 *
 * Three screens now carry a `MAY` constant mirroring the permissions their
 * routes require, so the screen can avoid offering a control the server will
 * refuse. Nothing type-checks those strings. A renamed permission, a typo, or
 * a route that moves to a different code leaves the mirror pointing at a code
 * nobody holds — in which case the control is dead for everyone — or at one
 * everybody holds, in which case the gate is decoration and the 403 comes
 * back after the form is filled in. Neither shows up as an error anywhere.
 *
 * So this reads both sides. For each screen it takes the codes out of the
 * `MAY` literal and asserts each appears inside a `require_permission(...)`
 * call in that screen's own API module. Not "exists somewhere in the API":
 * a `MAY` on the competitors screen naming a permission only the laboratory
 * router uses would be just as wrong, and would pass a laxer check.
 *
 * ⚠️ THE SERVER STILL DECIDES. `CLAUDE.md` §6: hiding a control is honesty,
 * not access control, and every route re-authorizes regardless. This asserts
 * the mirrors are HONEST, not that they are load-bearing.
 *
 * ⚠️ IT PARSES A TS OBJECT LITERAL AND A PYTHON CALL, which is brittle on
 * purpose, and guards the guard first — a regex that stopped matching would
 * compare two empty sets and pass.
 */

const WEB = join(__dirname, "..", "..");
const API = join(WEB, "..", "api", "app", "api");

/** Each screen carrying a `MAY` mirror, and the router it mirrors. */
const MIRRORS: ReadonlyArray<{ name: string; screen: string; router: string }> = [
  {
    name: "material-safety",
    screen: join(WEB, "app", "material-safety", "page.tsx"),
    router: join(API, "material_safety.py"),
  },
  {
    name: "competitors",
    screen: join(WEB, "app", "material-safety", "competitors", "page.tsx"),
    router: join(API, "competitors.py"),
  },
  {
    name: "research",
    screen: join(WEB, "app", "material-safety", "research", "page.tsx"),
    router: join(API, "research.py"),
  },
];

/** The permission codes inside a screen's `const MAY = { ... } as const;`. */
function mirroredCodes(screen: string): Set<string> {
  const source = readFileSync(screen, "utf8");
  const start = source.indexOf("const MAY = {");
  expect(start, `no MAY block in ${screen} — has it been renamed?`).toBeGreaterThan(-1);
  // 🔴 THE TERMINATOR IS ASSERTED BEFORE IT IS USED. `indexOf` returns -1 when
  // it is not found, and `slice(start, -1)` then quietly yields the whole rest
  // of the file -- so the "mirror" would be harvested from every quoted `x.y`
  // string on the screen (route paths, test ids, other permission codes), and
  // the size guard below would still be satisfied. `} as const satisfies …`,
  // or a reflow, is enough to trigger it. Both reviewers found this.
  const end = source.indexOf("} as const;", start);
  expect(
    end,
    `the MAY block in ${screen} does not end with "} as const;"`,
  ).toBeGreaterThan(start);
  const literal = source.slice(start, end);
  return new Set(literal.match(/"[a-z_]+\.[a-z_]+"/g)?.map((q) => q.slice(1, -1)) ?? []);
}

/** The permission codes any `require_permission(...)` in a router names. */
function gatedCodes(router: string): Set<string> {
  const source = readFileSync(router, "utf8");
  const out = new Set<string>();
  for (const call of source.matchAll(/require_permission\(([^)]*)\)/gs)) {
    const args = call[1];
    if (args === undefined) continue;
    for (const quoted of args.match(/"[a-z_]+\.[a-z_]+"/g) ?? []) {
      out.add(quoted.slice(1, -1));
    }
  }
  return out;
}

describe("the screen permission mirrors", () => {
  it("finds the blocks it is meant to be checking", () => {
    // The guard on the guard. Empty on either side and every assertion below
    // passes without comparing anything.
    for (const { screen, router } of MIRRORS) {
      expect(mirroredCodes(screen).size, `no codes parsed out of ${screen}`).toBeGreaterThan(1);
      expect(gatedCodes(router).size, `no codes parsed out of ${router}`).toBeGreaterThan(1);
    }
  });

  it.each(MIRRORS)("the $name screen mirrors only codes its router gates on", ({ screen, router }) => {
    const gated = gatedCodes(router);
    const stray = [...mirroredCodes(screen)].filter((code) => !gated.has(code));
    expect(
      stray,
      "the screen gates a control on a permission this router does not require — " +
        "the mirror has drifted, so the control is either dead for everyone or " +
        "open to everyone",
    ).toEqual([]);
  });
});
