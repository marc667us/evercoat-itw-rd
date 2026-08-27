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

import type { SessionState } from "@/lib/api/session";

import { activeProfile, chooseOrganization, type OrganizationChoice } from "./auth-provider";

const ACME: OrganizationChoice = {
  organizationId: "11111111-1111-1111-1111-111111111111",
  name: "Acme Coatings",
  code: "ACME",
  email: "kwame.chemist@acme.example",
  displayName: "Kwame Chemist",
  roles: ["product_development_chemist"],
  // I79: per-tenant, like the roles beside them.
  permissions: ["project.view", "formula.submit"],
};

const BOREAL: OrganizationChoice = {
  organizationId: "22222222-2222-2222-2222-222222222222",
  name: "Boreal Adhesives",
  code: "BOR",
  email: "esi.lead@boreal.example",
  displayName: "Esi Lead",
  roles: ["product_development_lead"],
  permissions: ["project.view", "formula.approve_lab"],
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

/**
 * 🔴 THE PROFILE WAS STORED, AND STORING IT WAS THE DEFECT.
 *
 * Three findings, one cause. `signOut` cleared the session and the
 * organizations and never cleared the profile, so the previous user's name
 * stayed in the top bar of an anonymous application — both reviewers found
 * that one, and on a shared bench machine it is somebody else's name over your
 * work. Switching organization left it unchanged. And its value came from a
 * top-level `display_name` that `/api/me` filled from whichever tenant sorted
 * first, though migration 052 had deliberately moved that attribute onto the
 * membership.
 *
 * Derived from the active membership, none of the three is reachable: there is
 * no second copy to clear, none to refresh, and none to take from the wrong
 * row. These tests assert the properties, not the implementation.
 */
describe("activeProfile", () => {
  const authenticated = (organizationId: string): SessionState => ({
    status: "authenticated",
    credentials: {
      token: "not-a-real-token",
      organizationId,
      userId: "44444444-4444-4444-4444-444444444444",
    },
  });

  it("🔴 an anonymous session has no name, whatever is still in memory", () => {
    // The finding, exactly. The organizations list survives a failed refresh
    // in one path on purpose ("your session is intact -- retry in a moment"),
    // so "the list is empty" was never a safe proxy for "signed out".
    const profile = activeProfile(
      { status: "anonymous", reason: "you have signed out" },
      [ACME, BOREAL],
    );
    expect(profile).toBeNull();
  });

  it("🔴 follows the ACTIVE organization, not the first one", () => {
    expect(activeProfile(authenticated(ACME.organizationId), [ACME, BOREAL])?.displayName).toBe(
      "Kwame Chemist",
    );
    expect(activeProfile(authenticated(BOREAL.organizationId), [ACME, BOREAL])?.displayName).toBe(
      "Esi Lead",
    );
  });

  it("carries the user id from the session, which is the one global attribute", () => {
    expect(activeProfile(authenticated(ACME.organizationId), [ACME, BOREAL])?.userId).toBe(
      "44444444-4444-4444-4444-444444444444",
    );
  });

  it("🔴 a blank name is an absent name, not an empty top bar entry", () => {
    // The previous check was `!== undefined`, which `""` satisfies — so an API
    // returning a blank produced "signed in as ''", which reads as a rendering
    // fault rather than a missing field. The comment claimed this case was
    // excluded; Codex measured that it was not.
    const nameless: OrganizationChoice = { ...ACME, displayName: "  " };
    expect(activeProfile(authenticated(ACME.organizationId), [nameless])).toBeNull();

    const addressless: OrganizationChoice = { ...ACME, email: "" };
    expect(activeProfile(authenticated(ACME.organizationId), [addressless])).toBeNull();
  });

  it("has no name for an organization it holds no membership for", () => {
    // Reachable: a membership revoked between the token being issued and the
    // list being refreshed. Showing the old name would be asserting a
    // membership the server has already withdrawn.
    expect(activeProfile(authenticated("99999999-9999-9999-9999-999999999999"), [ACME])).toBeNull();
  });
});
