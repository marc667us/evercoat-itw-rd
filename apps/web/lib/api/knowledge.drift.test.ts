/**
 * The knowledge screen's literals, checked against the files they were copied
 * from.
 *
 * 🔴 TWO LITERALS IN TWO FILES CANNOT BE TYPE-CHECKED INTO AGREEMENT, and this
 * screen now holds THREE such copies: the classification lattice (PostgreSQL),
 * the source vocabulary (a CHECK constraint), and the relevance boundary (a
 * Python constant). TypeScript cannot see any of them.
 *
 * That is not hypothetical here. `R_AND_D_RESTRICTED` was written in the tone
 * map where the real code is `R&D_RESTRICTED`; it matched nothing, fell through
 * to the default colour, and rendered rank 40 identically to the rank 60
 * ceiling — while a docstring claimed "the shading ascends with sensitivity".
 * A reviewer caught it. This file is what catches the next one.
 *
 * It reads the real sources off disk, the way `navigation.test.ts` reads the
 * app directory, so it needs no database and no running server.
 */

import fs from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

const REPO = path.resolve(__dirname, "..", "..", "..", "..");
const API = path.join(REPO, "apps", "api");
const SCREEN = path.join(REPO, "apps", "web", "app", "knowledge", "page.tsx");

function read(...segments: string[]): string {
  return fs.readFileSync(path.join(...segments), "utf8");
}

/**
 * The first capture group of `pattern` in `text`, or a failed expectation.
 *
 * `noUncheckedIndexedAccess` types every regex group as `string | undefined`,
 * so without this each call site would carry a `!` — and a `!` on a match that
 * silently stopped matching is exactly how a drift test starts passing over
 * nothing.
 */
function captured(text: string, pattern: RegExp, what: string): string {
  const match = pattern.exec(text);
  expect(match?.[1], `${what} is not in the expected form`).toBeTypeOf("string");
  return match![1]!;
}

/** Every first capture group of a global `pattern`. */
function allCaptured(text: string, pattern: RegExp): string[] {
  return [...text.matchAll(pattern)].map((m) => m[1]!).filter((v) => v !== undefined);
}

/** The `as const` array named `name` in the screen. */
function screenList(name: string): string[] {
  const body = captured(
    read(SCREEN),
    new RegExp(`const ${name} = \\[([\\s\\S]*?)\\] as const;`),
    name,
  );
  return allCaptured(body, /"([^"]+)"/g);
}

describe("the knowledge screen agrees with the database", () => {
  it("offers exactly the classifications migration 039 seeds", () => {
    const sql = read(API, "migrations", "039_one_classification_lattice.sql");
    // Rows look like:  ('R&D_RESTRICTED',      40, 'Proprietary ...'),
    const seeded = [...sql.matchAll(/\(\s*'([A-Z&_]+)',\s*(\d+),/g)].map((m) => ({
      code: m[1]!,
      rank: Number(m[2]),
    }));
    expect(seeded.length, "no classification rows found in 039").toBeGreaterThan(0);

    const inOrder = [...seeded].sort((a, b) => a.rank - b.rank).map((row) => row.code);
    expect(screenList("CLASSIFICATIONS")).toEqual(inOrder);
  });

  it("has a distinct colour for every classification, none falling through", () => {
    // 🔴 THE ASSERTION THAT WOULD HAVE CAUGHT `R_AND_D_RESTRICTED`.
    //
    // A missing key is invisible: the `??` default renders it, in the
    // DIRECTOR_CONTROLLED purple, so the most sensitive styling is what an
    // unknown code silently gets. Every seeded code must have its OWN entry.
    const toneBlock = captured(
      read(SCREEN),
      /const CLASSIFICATION_TONE[^=]*= \{([\s\S]*?)\n\};/,
      "CLASSIFICATION_TONE",
    );
    const keys = allCaptured(toneBlock, /^\s*"?([A-Z&_]+)"?:/gm);

    for (const code of screenList("CLASSIFICATIONS")) {
      expect(keys, `${code} has no colour of its own and falls through to the default`).toContain(
        code,
      );
    }
  });

  it("offers exactly the sources migration 042's CHECK constraint allows", () => {
    const sql = read(API, "migrations", "042_knowledge_retrieval.sql");
    const check = captured(sql, /source IN \(([^)]*)\)/, "documents_source_check");
    const allowed = allCaptured(check, /'([a-z_]+)'/g);

    expect(new Set(screenList("SOURCES"))).toEqual(new Set(allowed));
  });

  it("bands overlap on the same boundary the assistant refuses at", () => {
    // `MAX_DISTANCE` carries an explicit warning that it is calibrated for the
    // LEXICAL embedder and must be RE-DERIVED, not inherited, when ADR-013's
    // model lands. Re-deriving it in Python would otherwise leave this screen
    // labelling every result against the stale number — the same figure
    // meaning two different things in two tiers, silently.
    const declared = captured(
      read(API, "app", "agents", "tools", "knowledge.py"),
      /^MAX_DISTANCE = ([\d.]+)$/m,
      "MAX_DISTANCE in knowledge.py",
    );
    // `\s*` throughout, not `\n`: these files are CRLF on this host and an
    // LF-only pattern matched nothing, which made the test fail for a reason
    // that had nothing to do with drift.
    const band = captured(
      read(SCREEN),
      /distance <= ([\d.]+)\)\s*\{\s*return \{\s*label: "Some word overlap"/,
      "the 'Some word overlap' band",
    );

    expect(
      Number(band),
      "the screen's weak-overlap boundary and the assistant's MAX_DISTANCE have drifted",
    ).toBe(Number(declared));
  });
});
