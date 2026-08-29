import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { materialDetailSchema, materialSchema } from "./materials";

/**
 * The edit form must be able to send back every column the server replaces.
 *
 * 🔴 THE DEFECT THIS EXISTS TO PREVENT IS SILENT DATA LOSS, NOT A 4xx.
 *
 * `PUT /api/materials/{id}` is a complete replacement: `update_material` sets
 * every editable column in one UPDATE, and a field absent from the request
 * body is not "left alone" — Pydantic defaults it to `None` and the column is
 * written null. So the edit form is only correct while it can SHOW every
 * column the UPDATE writes. The moment the server gains an editable column the
 * form does not carry, every save through that form quietly erases it. Nothing
 * fails, nothing 500s, and the person who corrected a material's name deletes
 * its notes.
 *
 * That is exactly how the form was nearly built: `GET /api/materials` omits
 * `description`, `notes`, `epoxy_equivalent_weight` and
 * `amine_hydrogen_equivalent_weight`, and prefilling from the grid rows
 * already in memory would have blanked all four on every save.
 *
 * So this reads the Python and asserts the three links in that chain:
 *
 *   1. every column the UPDATE writes is one the detail SELECT returns,
 *      so the form can load it;
 *   2. every one of those is a field of `materialDetailSchema`, so the form
 *      actually parses and holds it;
 *   3. the LIST schema is not the one to build the form from — recorded as a
 *      fact about the two shapes rather than as a rule about the future.
 *
 * ⚠️ IT PARSES SQL OUT OF A PYTHON STRING, WHICH IS BRITTLE ON PURPOSE, and
 * it follows `materials.drift.test.ts` in guarding the guard first: a regex
 * that stopped matching would otherwise compare two empty sets and pass.
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

function source(): string {
  return readFileSync(SERVICE, "utf8");
}

/** The block of one function, from its `def` to the next top-level `def`. */
function functionBody(name: string): string {
  const src = source();
  const start = src.indexOf(`def ${name}(`);
  expect(start, `${name} was not found — has it been renamed?`).toBeGreaterThan(-1);
  const next = src.indexOf("\ndef ", start + 1);
  return src.slice(start, next === -1 ? src.length : next);
}

/**
 * The columns `update_material`'s UPDATE assigns.
 *
 * `SET name = :name, category = :category, ...` — every assignment up to the
 * `FROM` that ends the SET clause.
 */
function writtenColumns(): Set<string> {
  const body = functionBody("update_material");
  const start = body.indexOf("SET ");
  expect(start, "the SET clause was not found in update_material").toBeGreaterThan(-1);
  const clause = body.slice(start, body.indexOf("FROM prev", start));

  const out = new Set<string>();
  for (const match of clause.matchAll(/(\w+)\s*=\s*(?::\w+|now\(\))/g)) {
    const column = match[1];
    if (column !== undefined) out.add(column);
  }
  // `updated_at = now()` is written by the server, never sent by a caller.
  out.delete("updated_at");
  return out;
}

/** The columns `get_material`'s SELECT returns. */
function detailColumns(): Set<string> {
  const body = functionBody("get_material");
  const start = body.indexOf("SELECT ");
  expect(start, "the SELECT was not found in get_material").toBeGreaterThan(-1);
  const clause = body.slice(start + "SELECT ".length, body.indexOf("FROM materials.materials", start));

  return new Set(
    clause
      .split(",")
      .map((part) => part.trim())
      .filter((part) => /^\w+$/.test(part)),
  );
}

describe("the material edit contract", () => {
  it("finds the SQL it is meant to be checking", () => {
    // The guard on the guard. Both of these would be empty if the Python were
    // restructured, and every assertion below would then pass vacuously.
    const written = writtenColumns();
    const returned = detailColumns();
    expect(written.size).toBeGreaterThan(10);
    expect(returned.size).toBeGreaterThan(written.size);
    // Two columns named in `update_material`'s own docstring as NOT editable.
    expect(written.has("material_code")).toBe(false);
    expect(written.has("status")).toBe(false);
  });

  it("returns from the detail endpoint every column the update replaces", () => {
    const returned = detailColumns();
    const missing = [...writtenColumns()].filter((column) => !returned.has(column));
    expect(
      missing,
      "the update writes columns the detail endpoint does not return, so no form " +
        "can load them and every save through one would blank them",
    ).toEqual([]);
  });

  it("parses into the detail schema every column the update replaces", () => {
    const fields = new Set(Object.keys(materialDetailSchema.shape));
    const missing = [...writtenColumns()].filter((column) => !fields.has(column));
    expect(
      missing,
      "materialDetailSchema is missing a column the PUT replaces — the edit " +
        "form cannot show it, so saving would write it null",
    ).toEqual([]);
  });

  it("records that the LIST schema is not enough to edit from", () => {
    // Not a rule about the future: if the list endpoint is one day widened,
    // this becomes false and should be deleted along with the reason for the
    // detail fetch. It is here so the reason is measured rather than asserted
    // in a comment that could quietly expire.
    const list = new Set(Object.keys(materialSchema.shape));
    const absent = [...writtenColumns()].filter((column) => !list.has(column));
    expect(absent.length).toBeGreaterThan(0);
    expect(absent).toContain("description");
    expect(absent).toContain("notes");
  });
});
