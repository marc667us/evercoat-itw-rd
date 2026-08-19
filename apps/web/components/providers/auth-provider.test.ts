/**
 * Which tenant stays active across a token refresh.
 *
 * 🔴 WHAT THIS CATCHES
 *
 * `establish()` runs on sign-in AND on every token refresh. Its first
 * version always selected `choices[0]`, so a chemist working in their
 * SECOND organization was silently moved back to the first roughly once
 * per token lifetime — and every formula, batch and approval written
 * after that moment went to the wrong tenant.
 *
 * Nothing would have failed. The API accepts the request, because the
 * user IS a member of that organization; RLS is satisfied, because the
 * context is internally consistent; the only visible symptom is a name in
 * a corner of the top bar that nobody was watching. It is the exact shape
 * of defect this codebase keeps recording — a green path doing the wrong
 * thing quietly.
 *
 * Codex found it in review. These tests exist so it cannot come back.
 */

import { describe, expect, it } from "vitest";

import { chooseOrganization, type OrganizationChoice } from "./auth-provider";

const ACME: OrganizationChoice = {
  organizationId: "11111111-1111-1111-1111-111111111111",
  name: "Acme Coatings",
  code: "ACME",
  roles: ["product_development_chemist"],
};

const BOREAL: OrganizationChoice = {
  organizationId: "22222222-2222-2222-2222-222222222222",
  name: "Boreal Adhesives",
  code: "BOR",
  roles: ["product_development_lead"],
};

describe("chooseOrganization", () => {
  it("🔴 KEEPS the active tenant across a refresh", () => {
    // The whole finding, in one assertion. The user picked Boreal; a
    // refresh must not hand them back Acme.
    expect(chooseOrganization([ACME, BOREAL], BOREAL.organizationId)).toBe(BOREAL);
  });

  it("selects the first on a fresh sign-in, when nothing is preferred", () => {
    expect(chooseOrganization([ACME, BOREAL], undefined)).toBe(ACME);
  });

  it("falls back to the first when the preferred membership has gone", () => {
    // Deliberate: a preferred id that is no longer in the list means the
    // membership was revoked between refreshes. Staying on it is not an
    // option, and refusing to choose would sign the user out of an
    // account they still legitimately hold.
    expect(chooseOrganization([ACME], BOREAL.organizationId)).toBe(ACME);
  });

  it("is not fooled by a preferred id that merely looks similar", () => {
    expect(chooseOrganization([ACME, BOREAL], `${BOREAL.organizationId}x`)).toBe(ACME);
  });

  it("refuses to invent a tenant when there are none", () => {
    // Throwing beats returning undefined: the caller already treats an
    // empty membership list as "signed in, nothing to show", and a silent
    // undefined here would flow into credentials as `organizationId:
    // undefined` and be sent as the string "undefined".
    expect(() => chooseOrganization([], undefined)).toThrow(/no organizations/);
  });
});
