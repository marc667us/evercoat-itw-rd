import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

/**
 * The messaging client's schemas, against the service that answers them — I12.
 *
 * 🔴 THIS TEST EXISTS BECAUSE THE FIRST DRAFT GOT TWO OF THREE SHAPES WRONG.
 *
 * Writing `lib/api/messaging.ts` from the route signatures alone produced:
 *
 *   · `promoteMessage` parsing `{id, task_type}` when `promote_message`
 *     returns `{task_id, message_id}` — that one THROWS at parse, so the
 *     control would have failed the moment anybody pressed it;
 *   · a message link parsed as `{entity_type, entity_id, reference}` when
 *     `_resolve_references` returns `{code, entity_type, entity_id}` — and
 *     Zod STRIPS unknown keys, so this one is silent: every link renders
 *     blank and nothing anywhere reports a mismatch;
 *   · `mentions` omitted from the post response entirely — also silent, and
 *     it carries `notified: false`, the state that tells an author their
 *     mention did NOT reach anyone.
 *
 * Two of those three fail invisibly. *The response is the contract, and only
 * a live press checks it* — this project lost an afternoon to three defects of
 * exactly this shape on 2026-08-29. So the contract is asserted here instead.
 *
 * ⚠️ IT READS THE PYTHON. A test comparing one hand-written list against
 * another proves only that somebody typed twice.
 */

const SERVICE = join(
  __dirname,
  "..",
  "..",
  "..",
  "api",
  "app",
  "domains",
  "messaging",
  "service.py",
);
const CLIENT = join(__dirname, "messaging.ts");

/**
 * The keys of the `return { ... }` dict that ends a named Python function.
 *
 * Deliberately brittle: if the Python is restructured so this stops matching,
 * the guard-the-guard assertion below fails rather than quietly comparing two
 * empty sets — the failure mode this file exists to prevent.
 */
function returnedKeys(source: string, functionName: string): Set<string> {
  const start = source.indexOf(`\ndef ${functionName}(`);
  if (start === -1) return new Set();

  // The function ends where the next top-level `def` begins.
  const nextDef = source.indexOf("\ndef ", start + 1);
  const body = source.slice(start, nextDef === -1 ? undefined : nextDef);

  // The LAST `return {` in the body is the success path; earlier ones are
  // usually early exits.
  const returnAt = body.lastIndexOf("return {");
  if (returnAt === -1) return new Set();

  const keys = new Set<string>();
  let depth = 0;
  for (let i = returnAt + "return ".length; i < body.length; i++) {
    const ch = body[i]!;
    if (ch === "{") depth++;
    else if (ch === "}") {
      depth--;
      if (depth === 0) break;
    }
  }
  const block = body.slice(returnAt, body.indexOf("}", returnAt) + 1);
  for (const match of block.matchAll(/"([a-z_]+)":/g)) keys.add(match[1]!);
  return keys;
}

/**
 * The TOP-LEVEL keys a `z.object({ ... })` literal named `name` declares.
 *
 * 🔴 COMMENT-AWARE, AND THE FIRST VERSION WAS NOT — FOR THE SECOND TIME TODAY.
 *
 * `stub-fixtures.drift.test.ts` was made string- and comment-aware this
 * morning for exactly this reason, and writing a SECOND parser here
 * reintroduced the defect immediately: the doc comment above `mentions` reads
 * "`notified: false` IS A REAL AND IMPORTANT STATE", and a scanner that does
 * not know it is inside a comment collects `notified` as a top-level key.
 *
 * The lesson is not "be careful with regexes" — it is that a parser written
 * twice drifts twice. The only reason this was caught at all is that the
 * assertion compares against the SERVICE rather than against a second
 * hand-written list.
 */
function schemaKeys(source: string, name: string): Set<string> {
  const marker = `const ${name} = z.object({`;
  const start = source.indexOf(marker);
  if (start === -1) return new Set();

  const keys = new Set<string>();
  let depth = 0;
  let lineStart = true;
  let current = "";
  let inLineComment = false;
  let inBlockComment = false;
  let inString: string | null = null;

  for (let i = start + marker.length - 1; i < source.length; i++) {
    const ch = source[i]!;
    const next = source[i + 1];

    if (inLineComment) {
      if (ch === "\n") {
        inLineComment = false;
        lineStart = true;
        current = "";
      }
      continue;
    }
    if (inBlockComment) {
      if (ch === "*" && next === "/") {
        inBlockComment = false;
        i++;
      }
      continue;
    }
    if (inString !== null) {
      if (ch === "\\") i++;
      else if (ch === inString) inString = null;
      continue;
    }
    if (ch === "/" && next === "/") {
      inLineComment = true;
      current = "";
      continue;
    }
    if (ch === "/" && next === "*") {
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

    if (ch === "{" || ch === "[" || ch === "(") depth++;
    else if (ch === "}" || ch === "]" || ch === ")") {
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
      } else if (current !== "" && /[A-Za-z0-9_]/.test(ch)) current += ch;
      else if (current !== "" && ch === ":") {
        keys.add(current);
        current = "";
      } else if (current !== "") current = "";
    }
  }
  return keys;
}

describe("the messaging client parses what the service returns", () => {
  const service = readFileSync(SERVICE, "utf8");
  const client = readFileSync(CLIENT, "utf8");

  it("promote_message returns task_id and message_id, and the client parses those", () => {
    const returned = returnedKeys(service, "promote_message");
    // 🔴 GUARD THE GUARD — a parse that stopped matching would compare two
    // empty sets and pass.
    expect(returned.size, "parsed no keys from promote_message").toBeGreaterThan(0);
    expect([...returned].sort()).toEqual(["message_id", "task_id"]);

    // The client's inline parse for this route. Asserted as text because the
    // schema is declared at the call site rather than as a named constant.
    expect(client).toContain("task_id: z.string()");
    expect(client).toContain("message_id: z.string()");
    expect(client).not.toContain("z.object({ id: z.string(), task_type: z.string() })");
  });

  it("post_message returns id, links and mentions, and the client parses all three", () => {
    const returned = returnedKeys(service, "post_message");
    expect(returned.size, "parsed no keys from post_message").toBeGreaterThan(0);
    expect([...returned].sort()).toEqual(["id", "links", "mentions"]);

    const declared = schemaKeys(client, "postedMessageSchema");
    expect(declared.size, "parsed no keys from postedMessageSchema").toBeGreaterThan(0);
    expect([...declared].sort()).toEqual([...returned].sort());
  });

  it("a resolved link carries the CODE, which is the key that renders", () => {
    // `_resolve_references` appends {"code", "entity_type", "entity_id"}. The
    // first draft parsed `reference` instead of `code`; Zod strips unknown
    // keys, so every link would have rendered blank with nothing reporting it.
    expect(service).toContain('found.append({"code": code, "entity_type": entity_type');
    expect(client).toContain("code: z.string()");
  });

  it("a mention carries whether the person was actually notified", () => {
    // `notified: false` means the handle resolved to a real person who is not
    // a member of this channel. Dropping the field would tell the author their
    // message reached somebody it did not.
    expect(service).toContain('"notified": False');
    expect(client).toContain("notified: z.boolean()");
  });
});
