import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

/**
 * The unit fixture and the E2E stub describe the SAME API response. This
 * asserts they carry the same fields.
 *
 * 🔴 THIS EXACT DEFECT HAS NOW HAPPENED FOUR TIMES, AND THE STUB'S OWN COMMENT
 * PREDICTED THE FOURTH.
 *
 * There are three copies of every list-response shape: the real server, the
 * unit fixture in `schemas.test.ts`, and the Playwright stub in
 * `tests/e2e/shell/api-wiring.spec.ts`. When a field is added, the first two
 * get updated and the third does not — so the live suite passes (it talks to
 * the real API, which sends the field) while CI fails, or worse, the screen
 * silently renders NOTHING because a required Zod field is missing and a parse
 * failure is not an error anybody sees.
 *
 * *Two literals in two files cannot be type-checked into agreement*, and here
 * there are three. Nothing in TypeScript relates a stub object to the schema
 * it must satisfy, because the stub is a plain literal handed to
 * `page.route()` and serialised to JSON.
 *
 * ⚠️ IT COMPARES KEYS, NOT VALUES. The two fixtures describe different rows on
 * purpose — the E2E one is named "only exists in the API" precisely so a
 * screen rendering the bundled demonstration data cannot pass. What must match
 * is the SHAPE.
 *
 * ⚠️ IT GUARDS ITSELF FIRST. A parse that stopped finding either literal would
 * compare two empty sets and pass — this repository's most-repeated defect.
 */

const WEB = join(__dirname, "..", "..");
const UNIT = join(WEB, "lib", "api", "schemas.test.ts");
const E2E = join(WEB, "..", "..", "tests", "e2e", "shell", "api-wiring.spec.ts");

/**
 * The top-level keys of an object literal named `name`.
 *
 * Depth-aware: a nested object's keys belong to the nested object, and
 * counting them at the top level would make two identical fixtures disagree.
 */
function keysOf(source: string, name: string): Set<string> {
  const marker = "const " + name + " = {";
  const start = source.indexOf(marker);
  if (start === -1) return new Set();

  const keys = new Set<string>();
  let depth = 0;
  let i = start + marker.length - 1;
  let lineStart = true;
  let current = "";

  for (; i < source.length; i++) {
    const ch = source[i]!;
    if (ch === "{" || ch === "[") depth++;
    else if (ch === "}" || ch === "]") {
      depth--;
      if (depth === 0) break;
    } else if (ch === "\n") {
      lineStart = true;
      current = "";
      continue;
    }
    if (depth === 1) {
      if (lineStart && /[A-Za-z_]/.test(ch)) {
        current = ch;
        lineStart = false;
      } else if (current !== "" && /[A-Za-z0-9_]/.test(ch)) {
        current += ch;
      } else if (current !== "" && ch === ":") {
        keys.add(current);
        current = "";
      } else if (current !== "") {
        current = "";
      }
    }
  }
  return keys;
}

/** Each response shape, and the literal that carries it on each side. */
const SHAPES: ReadonlyArray<{ shape: string; unit: string; e2e: string }> = [
  { shape: "project summary", unit: "PROJECT", e2e: "LIVE_PROJECT" },
  { shape: "formula list row", unit: "FORMULA", e2e: "LIVE_FORMULA" },
];

describe("the unit fixture and the E2E stub agree on the response shape", () => {
  const unit = readFileSync(UNIT, "utf8");
  const e2e = readFileSync(E2E, "utf8");

  it.each(SHAPES)("$shape", ({ unit: unitName, e2e: e2eName }) => {
    const a = keysOf(unit, unitName);
    const b = keysOf(e2e, e2eName);

    // Guard the guard: an unparsed literal must not pass as "they agree".
    expect(a.size, `parsed no keys from ${unitName}`).toBeGreaterThan(3);
    expect(b.size, `parsed no keys from ${e2eName}`).toBeGreaterThan(3);

    const missingFromStub = [...a].filter((k) => !b.has(k)).sort();
    expect(
      missingFromStub,
      `${e2eName} is missing fields the API sends; a required Zod field that ` +
        `is absent makes the screen render NOTHING, silently`,
    ).toEqual([]);
  });
});
