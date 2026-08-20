/**
 * The response parsers, tested for the thing they exist to do.
 *
 * 🔴 `as Project[]` COSTS NOTHING AND PROVES NOTHING.
 *
 * `materials.ts` states the argument: a server that renamed a field hands
 * back rows whose value is `undefined`, and the grid renders a column of
 * blanks that looks exactly like a database with nothing recorded in it.
 * Parsing is what turns that into a named error on the screen.
 *
 * That argument is only worth anything if the schemas actually reject.
 * These tests are the proof — each one renames or drops a field the UI
 * depends on and asserts the parse fails, rather than asserting that a
 * correct payload parses, which is the version of this test that cannot
 * fail.
 */

import { describe, expect, it } from "vitest";

import { formulaSchema, formulaWithCoherentVersion } from "./formulations";
import { materialSchema, supplierSchema } from "./materials";
import { projectSchema } from "./projects";
import { taskSchema } from "./tasks";

const PROJECT = {
  id: "11111111-1111-1111-1111-111111111111",
  project_code: "RDP-2026-014",
  name: "Lightweight filler",
  product_family: "polyester filler",
  status: "active",
  priority: "high",
  current_stage: "development",
  confidentiality: "normal",
  target_release_date: "2026-11-01",
};

const FORMULA = {
  id: "22222222-2222-2222-2222-222222222222",
  formula_code: "FRM-014",
  name: "Lightweight body filler",
  product_family: "polyester filler",
  status: "active",
  project_id: PROJECT.id,
  project_code: PROJECT.project_code,
  // 🔴 NOT NULL. The fixture used to set `owner_user_id: null` while
  // describing itself as an API row -- so a contract regression in a
  // NOT NULL column would have passed. Codex found it.
  owner_user_id: "44444444-4444-4444-4444-444444444444",
  updated_at: "2026-08-01T10:00:00Z",
  latest_version_code: "FRM-014-v3",
  latest_version_number: 3,
  latest_version_status: "draft",
  version_count: 3,
};

const TASK = {
  id: "33333333-3333-3333-3333-333333333333",
  task_type: "approval",
  title: "Approve lab batch",
  description: null,
  priority: "high",
  status: "open",
  due_date: "2026-08-20",
  required_action: "Approve or return",
  entity_type: "formula_version",
  entity_id: null,
  project_id: PROJECT.id,
  assigned_user_id: null,
  assigned_role: "product_development_lead",
  created_at: "2026-08-01T10:00:00Z",
  project_code: PROJECT.project_code,
  project_name: "Lightweight filler",
  is_overdue: true,
};

describe("projectSchema", () => {
  it("accepts a row the API actually sends", () => {
    expect(projectSchema.parse(PROJECT).project_code).toBe("RDP-2026-014");
  });

  it("🔴 REJECTS a row with target_release_date absent entirely", () => {
    // It used to ACCEPT this. Pydantic serialises defaulted fields, so the
    // key is always present -- either a date or null. Accepting its
    // absence meant a dropped or renamed column parsed cleanly and the
    // grid stated "no target release date set": a claim about the
    // PROJECT, made from a fact about the RESPONSE. Codex found it.
    const { target_release_date: _omitted, ...rest } = PROJECT;
    expect(() => projectSchema.parse(rest)).toThrow();
  });

  it("accepts a null target_release_date, which is a real state", () => {
    expect(() => projectSchema.parse({ ...PROJECT, target_release_date: null })).not.toThrow();
  });

  it("🔴 REJECTS a renamed code field rather than rendering blanks", () => {
    const { project_code: _old, ...rest } = PROJECT;
    expect(() => projectSchema.parse({ ...rest, code: "RDP-2026-014" })).toThrow();
  });

  it("🔴 REJECTS a null where the UI requires a value", () => {
    // `confidentiality` decides whether a RESTRICTED badge is shown. A
    // null would render as no badge, which is the reassuring answer.
    expect(() => projectSchema.parse({ ...PROJECT, confidentiality: null })).toThrow();
  });
});

describe("formulaSchema", () => {
  it("accepts a formula with no version yet", () => {
    const parsed = formulaWithCoherentVersion.parse({
      ...FORMULA,
      latest_version_code: null,
      latest_version_number: null,
      latest_version_status: null,
      version_count: 0,
    });
    expect(parsed.latest_version_code).toBeNull();
  });

  it("🔴 REJECTS a HALF-populated latest version", () => {
    // A code with a null status parsed cleanly before, and VersionBadge
    // then announced "no version has been created for this formula yet"
    // about a formula that plainly has seven. The LEFT JOIN LATERAL either
    // matches or it does not. Codex found it.
    expect(() =>
      formulaWithCoherentVersion.parse({ ...FORMULA, latest_version_status: null }),
    ).toThrow();
  });

  it("🔴 REJECTS a null owner, which the column forbids", () => {
    expect(() => formulaSchema.parse({ ...FORMULA, owner_user_id: null })).toThrow();
  });

  it("🔴 REJECTS a version count sent as a string", () => {
    // It is a bigint from count(*) and arrives as a JSON number. A string
    // would sort as text in the grid -- "10" before "9" -- which reads as
    // a data error rather than a type error.
    expect(() => formulaSchema.parse({ ...FORMULA, version_count: "3" })).toThrow();
  });

  it("🔴 REJECTS a missing project_code", () => {
    // The card links to /projects/{code}. Missing, it would render a link
    // to /projects/undefined.
    const { project_code: _old, ...rest } = FORMULA;
    expect(() => formulaSchema.parse(rest)).toThrow();
  });
});

describe("taskSchema", () => {
  it("accepts an unclaimed role task", () => {
    // assigned_user_id null is not missing data -- it is the definition of
    // "nobody has claimed this", and it is why the row is in the inbox.
    expect(taskSchema.parse(TASK).assigned_user_id).toBeNull();
  });

  it("🔴 REJECTS a missing is_overdue rather than defaulting it", () => {
    // Defaulting to false would silently downgrade every overdue task to
    // on-time, and the browser must not re-derive it from due_date.
    const { is_overdue: _old, ...rest } = TASK;
    expect(() => taskSchema.parse(rest)).toThrow();
  });

  it("🔴 REJECTS is_overdue sent as a string", () => {
    // `Boolean("false")` is true. A string here would mark every task
    // overdue, including the ones that are not.
    expect(() => taskSchema.parse({ ...TASK, is_overdue: "false" })).toThrow();
  });
});

describe("materialSchema and supplierSchema", () => {
  it("🔴 REJECT a quantity sent as a JSON number", () => {
    // Quantities are NUMERIC in PostgreSQL and stay STRINGS all the way to
    // the screen. A JSON number is an IEEE 754 double -- exactly the round
    // trip the engine's Decimal discipline exists to prevent, on a figure
    // that ends up on a technical datasheet.
    const material = {
      id: "1",
      material_code: "RM-001",
      name: "Resin",
      category: "resin",
      role: "binder",
      status: "approved",
      density_g_cm3: 1.1,
      solids_fraction: null,
      voc_fraction: null,
      solids_percent: null,
      voc_percent: null,
      cost_per_kg: null,
      cas_number: null,
      restriction_reason: null,
      requires_sds: true,
      hazard_summary: null,
      supplier_count: 2,
      updated_at: null,
    };
    expect(() => materialSchema.parse(material)).toThrow();
  });

  it("🔴 REJECT a supplier missing its material_count", () => {
    const supplier = {
      id: "1",
      supplier_code: "SUP-001",
      name: "Acme",
      country: "DE",
      status: "approved",
      quality_rating: "A",
      contact_name: null,
      contact_email: null,
      updated_at: null,
    };
    expect(() => supplierSchema.parse(supplier)).toThrow();
  });
});
