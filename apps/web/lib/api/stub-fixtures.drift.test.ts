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

  // 🔴 STRING- AND COMMENT-AWARE, BECAUSE BRACES LIVE INSIDE BOTH. SUPERVISOR.
  //
  // The first version counted every `{ } [ ]` it saw, including ones inside
  // string values and comments.
  //
  // ⚠️ A BALANCED PAIR IN A STRING IS HARMLESS, AND THAT MATTERS FOR HOW THIS
  // IS TESTED. "?id={id}" takes depth 1→2→1 and loses nothing; a sample built
  // from one proves nothing, and the first version of the test below was
  // exactly that and stayed green with this guard removed. What breaks the
  // scanner is an UNBALANCED brace -- a single "}" in a value drops depth to 0
  // and the loop breaks there, silently returning only the keys seen so far.
  //
  // ⚠️ AND THE `size > 3` SELF-GUARD DOES NOT CATCH EITHER FAILURE MODE, which
  // is why the property is asserted directly at the bottom of this file. A
  // guard that only checks for too few is half a guard.
  //
  // A comment line whose first word is followed by ":" also became a phantom
  // key — harmless where extra keys are ignored, a spurious failure elsewhere.
  let inString: string | null = null;
  let inLineComment = false;
  let inBlockComment = false;

  for (; i < source.length; i++) {
    const ch = source[i]!;
    const nextCh = source[i + 1];

    if (inLineComment) {
      if (ch === "\n") {
        inLineComment = false;
        lineStart = true;
        current = "";
      }
      continue;
    }
    if (inBlockComment) {
      if (ch === "*" && nextCh === "/") {
        inBlockComment = false;
        i++;
      }
      continue;
    }
    if (inString !== null) {
      // A backslash escapes the next character, so an escaped quote does not
      // end the string.
      if (ch === "\\") i++;
      else if (ch === inString) inString = null;
      continue;
    }
    if (ch === "/" && nextCh === "/") {
      inLineComment = true;
      current = "";
      continue;
    }
    if (ch === "/" && nextCh === "*") {
      inBlockComment = true;
      current = "";
      i++;
      continue;
    }
    if (ch === '"' || ch === "'" || ch === "`") {
      inString = ch;
      current = "";
      continue;
    }

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

/**
 * 🔴 THE PARSER'S OWN FALSIFICATION, AND THE FIRST VERSION OF IT COULD NOT FAIL.
 *
 * `keysOf` used to count every brace it saw, including ones inside string
 * values and comments. The obvious sample to prove that -- a path template
 * like "?id={id}" -- **does not exercise it at all**, because those braces are
 * BALANCED: depth goes 2 then back to 1 and nothing is lost. Disabling the
 * string tracking and re-running left all four tests green.
 *
 * So the sample below carries the two shapes that actually break it:
 *
 *  1. an UNBALANCED brace inside a string. One "}" in a value drops depth to 0
 *     and the scan stops there, silently returning only the keys seen so far.
 *  2. a comment whose first word is followed by ":", which the old scanner
 *     collected as a key that exists in no object.
 *
 * Falsified: reverting either guard turns one of these red.
 */
describe("keysOf survives braces and colons that are not structure", () => {
  const sample = [
    "const SAMPLE = {",
    "  before: 1,",
    "  // note: this comment must not become a key",
    '  label: "an unbalanced } brace in a value",',
    '  path: "/projects/workspace?id={id}",',
    "  after: 2,",
    "};",
    "const LATER = { leaked: 3 };",
  ].join("\n");

  const keys = keysOf(sample, "SAMPLE");

  it("does not stop early on an unbalanced brace inside a string", () => {
    // `after` comes AFTER the offending value. Without string tracking the
    // scan has already broken out of the loop by the time it is reached.
    expect(keys.has("after")).toBe(true);
    expect(keys.has("label")).toBe(true);
    expect(keys.has("path")).toBe(true);
  });

  it("does not collect a comment's leading word as a key", () => {
    expect(keys.has("note")).toBe(false);
  });

  it("reads exactly the literal's own top-level keys", () => {
    expect([...keys].sort()).toEqual(["after", "before", "label", "path"]);
  });
});
