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
 * So this reads the Python and the form and asserts every link in that chain:
 *
 *   1. every column the UPDATE writes is one the detail SELECT returns,
 *      so the form can load it;
 *   2. every one of those is a field of `materialDetailSchema`, so the form
 *      actually parses and holds it;
 *   3. every one of those is a field the form SUBMITS — the hop both reviewers
 *      pointed out was claimed here and never asserted, and the one where a
 *      column can be loaded, shown, and still left out of the request;
 *   4. the LIST schema is not the one to build the form from — recorded as a
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

const FORM = join(__dirname, "..", "..", "app", "materials", "material-actions.tsx");

/**
 * The field names the edit form actually puts in the request body.
 *
 * 🔴 THE THIRD LINK, WHICH THIS FILE'S HEADER CLAIMED AND DID NOT ASSERT.
 *
 * Both reviewers made the same point: proving `UPDATE columns ⊆ detail SELECT
 * ⊆ schema keys` leaves the last hop unchecked. A column could reach the
 * schema, be shown by the form, and still be left OUT of the submitted object
 * -- and because the PUT replaces the row, every save would then write it
 * null. That is the exact failure the file exists to prevent, and three green
 * tests would have sat over it.
 */
function submittedFields(): Set<string> {
  const source = readFileSync(FORM, "utf8");
  const start = source.indexOf("writes.edit(");
  expect(start, "no call to writes.edit in the form — has it been renamed?").toBeGreaterThan(
    -1,
  );
  const end = source.indexOf("() => setEdited(null)", start);
  expect(end, "the writes.edit call does not end the way this parser expects").toBeGreaterThan(
    start,
  );
  const body = source.slice(start, end);
  return new Set(
    [...body.matchAll(/^\s{12}(\w+):/gm)].flatMap((m) => (m[1] === undefined ? [] : [m[1]])),
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

  it("finds the fields the form submits", () => {
    // The guard on the guard, again: an empty set would make the assertion
    // below pass by comparing nothing.
    const fields = submittedFields();
    expect(fields.size).toBeGreaterThan(10);
    expect(fields.has("name")).toBe(true);
  });

  it("submits every column the update replaces", () => {
    const fields = submittedFields();
    const missing = [...writtenColumns()].filter((column) => !fields.has(column));
    expect(
      missing,
      "the form does not send a column the PUT replaces — the server defaults " +
        "it to None and the save writes it null, which is the silent data loss " +
        "this whole file exists to prevent",
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

/**
 * The CREATE response must carry what the browser parses out of it.
 *
 * 🔴 THE WRITE SUCCEEDED AND THE RESPONSE DID NOT PARSE, WHICH IS THE WORST
 * SHAPE THIS CLASS OF BUG COMES IN.
 *
 * `post_material` returned `{"id": ...}` alone. `createMaterial` parses
 * `{ id, material_code }` with `material_code` REQUIRED, because the screen
 * reports the server's own code — "RM-014 created" — rather than echoing what
 * was typed. So every creation wrote its row and then failed on its own
 * response, and the screen said "the client and the server disagree about this
 * endpoint" while the new material sat in the table behind the error.
 *
 * No server test failed: the write was correct. No client test failed: it
 * stubs the response, so it parsed exactly what it expected. Only pressing the
 * button against a real API could find it — the recorded lesson on this project
 * is *the SQL is not the contract; the response is*, and this is its fourth
 * instance.
 */
describe("the material create response", () => {
  /** `post_material` lives in the ROUTE module, not the service. */
  function routeBody(name: string): string {
    const routes = join(__dirname, "..", "..", "..", "api", "app", "api", "materials.py");
    const src = readFileSync(routes, "utf8");
    const start = src.indexOf(`def ${name}(`);
    expect(start, `${name} was not found in api/materials.py`).toBeGreaterThan(-1);
    const next = src.indexOf("\n@router.", start + 1);
    return src.slice(start, next === -1 ? src.length : next);
  }

  function createReturn(): string {
    const body = routeBody("post_material");
    const start = body.lastIndexOf("return {");
    expect(start, "post_material does not end in a dict literal").toBeGreaterThan(-1);
    return body.slice(start);
  }

  it("finds the return it is meant to be checking", () => {
    // The guard on the guard: a restructured route would otherwise make the
    // assertion below read an empty string and pass.
    expect(createReturn()).toContain('"id"');
  });

  it("carries every key the browser requires", () => {
    const returned = createReturn();
    // Mirrored from `createMaterial`'s parse in `materials.ts`. Both are
    // required there, so both must be here.
    for (const key of ["id", "material_code"]) {
      expect(
        returned.includes(`"${key}"`),
        `POST /api/materials does not return "${key}", which the client parses ` +
          "as required — the material is created and the response then fails to " +
          "parse, so the screen reports a contract mismatch over a successful write",
      ).toBe(true);
    }
  });
});
