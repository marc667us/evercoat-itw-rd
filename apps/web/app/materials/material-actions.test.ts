import { describe, expect, it } from "vitest";

import { heldMaterialDraft } from "./material-actions";
import type { MaterialDetail } from "@/lib/api/materials";

/**
 * Which record the edit form holds, across a change of material.
 *
 * 🔴 THE RULE THIS TESTS WAS WRONG WHEN FIRST WRITTEN, AND WRONG IN THE WAY
 * THAT DOES NOT SHOW UP: it adopted the fetched record whenever the record's
 * id changed and held the previous draft otherwise. Choosing a different
 * material changes `materialId` at once, but the new record is a new query key,
 * so `detail.data` is `undefined` until that request lands. Through that gap
 * the form went on showing the PREVIOUS material's name, description and
 * quantities, under the newly-chosen material's heading and code.
 *
 * `PUT /api/materials/{id}` replaces the row, so saving there is not a partial
 * update -- it writes one material's data onto another, and the only sign
 * anything happened is that the wrong material now has the right values.
 *
 * These are written against the pure rule rather than the component for the
 * reason `effectiveNavPermissions` is: the cases that matter are the ones that
 * look fine on screen, and they need a test that does not have to stand up two
 * React hooks and a query client to reach them.
 */

function material(id: string, name: string): MaterialDetail {
  return {
    id,
    material_code: `RM-${id}`,
    name,
    category: "resin",
    role: "resin",
    status: "approved",
    description: null,
    cas_number: null,
    density_g_cm3: null,
    solids_fraction: null,
    voc_fraction: null,
    cost_per_kg: null,
    epoxy_equivalent_weight: null,
    amine_hydrogen_equivalent_weight: null,
    hazard_summary: null,
    requires_sds: true,
    restriction_reason: null,
    notes: null,
    updated_at: null,
  };
}

const A = material("a", "Alpha resin");
const B = material("b", "Beta resin");

describe("the record the edit form holds", () => {
  it("has nothing to show before the record arrives", () => {
    expect(heldMaterialDraft("a", undefined, null)).toBeNull();
  });

  it("adopts the record once it arrives", () => {
    expect(heldMaterialDraft("a", A, null)).toBe(A);
  });

  it("keeps what the person typed rather than the record", () => {
    const typed = { ...A, name: "Alpha resin, corrected" };
    expect(heldMaterialDraft("a", A, typed)).toBe(typed);
  });

  /**
   * The regression. Both halves of the gap are asserted, because the bug is
   * not "the wrong record is shown once" -- it is that it is shown for exactly
   * as long as a fetch takes, which is long enough to press a button.
   */
  it("shows nothing from the previous material while the new one loads", () => {
    // The picker moved to B. The query for B has not answered, so `loaded` is
    // undefined; `held` is still A's record, edited or not.
    expect(heldMaterialDraft("b", undefined, A)).toBeNull();
  });

  it("shows nothing when the record that arrived is still the previous one", () => {
    // React Query can hand back the PREVIOUS key's data for a render. Keying
    // on `materialId` rather than on what arrived is what makes this null.
    expect(heldMaterialDraft("b", A, A)).toBeNull();
  });

  it("does not hold one material's edits under another's identity", () => {
    const edited = { ...A, name: "Alpha resin, corrected", notes: "a note" };
    const shown = heldMaterialDraft("b", B, edited);
    expect(shown).toBe(B);
    expect(shown?.name).not.toBe("Alpha resin, corrected");
  });

  it("returns to the unsaved edits when the same material is chosen again", () => {
    // Deliberate, and the other direction of the rule above: A → B → A must
    // not silently discard typing. It must only never show it under B.
    const edited = { ...A, name: "Alpha resin, corrected" };
    expect(heldMaterialDraft("b", B, edited)).toBe(B);
    expect(heldMaterialDraft("a", A, edited)).toBe(edited);
  });
});
