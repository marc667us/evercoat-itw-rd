/**
 * I79 — which permissions the sidebar filters by.
 *
 * Before migration 045, `/api/me` returned roles and no permissions, so
 * `app/layout.tsx` handed the sidebar `ALL_NAV_PERMISSIONS` and EVERY caller
 * saw the whole module map. A laboratory technician was offered
 * Administration, Product Release and the director dashboard, and found the
 * limits by pressing one and receiving a 403.
 *
 * §6 is explicit that frontend permission checks are cosmetic and every route
 * is re-authorized server-side — and it is. This is about honesty, not
 * access: a control a caller cannot use should not be offered.
 *
 * 🔴 THE FALLBACK IS NOT A BUG, AND REMOVING IT IS. `layout.tsx` records what
 * happened when the shell was handed an EMPTY set instead: Projects,
 * Innovation and Pipeline disappeared from the sidebar and the pages existed
 * but were unreachable. So "no session" must keep the full map, while "a
 * session that holds nothing" must not — those two cases look identical if
 * you reach for `?.` and they are opposites.
 *
 * Verified failing before the fix: with `permissions` passed straight
 * through, the two cases that matter (a real caller, and a caller holding
 * nothing) both returned the full map.
 */
import { describe, expect, it } from "vitest";

import type { OrganizationChoice } from "@/components/providers/auth-provider";
import type { SessionState } from "@/lib/api/session";

import { effectiveNavPermissions, permits } from "./permissions";

const FULL_MAP: ReadonlySet<string> = new Set([
  "project.view",
  "formula.view",
  "admin.manage_users",
  "product.release",
]);

const ACME_ID = "11111111-1111-1111-1111-111111111111";
const OTHER_ID = "22222222-2222-2222-2222-222222222222";

function authenticated(organizationId: string): SessionState {
  // No `as SessionState`. The first draft cast a fixture with a `subject`
  // field and `tsc` rejected it: `ApiCredentials` carries `userId`, which
  // exists so a cached response cannot cross users. A cast would have
  // silenced that and left the fixture describing a shape the application
  // does not have.
  return {
    status: "authenticated",
    credentials: {
      token: "not-a-real-token",
      organizationId,
      userId: "44444444-4444-4444-4444-444444444444",
    },
  };
}

const TECHNICIAN: OrganizationChoice = {
  organizationId: ACME_ID,
  name: "Acme Coatings",
  code: "ACME",
  roles: ["laboratory_technician"],
  // The real figure, measured against the seeded realm on 2026-08-25:
  // tech.demo holds 11 permissions and lead.demo holds 38.
  permissions: ["batch.view", "batch.execute", "formula.view"],
};

describe("effectiveNavPermissions", () => {
  it("uses the signed-in caller's own permissions, not the whole map", () => {
    const result = effectiveNavPermissions(
      authenticated(ACME_ID),
      [TECHNICIAN],
      FULL_MAP,
    );

    expect([...result].sort()).toEqual([
      "batch.execute",
      "batch.view",
      "formula.view",
    ]);
    // The point of the whole change: a technician is not offered
    // Administration or Product Release.
    expect(result.has("admin.manage_users")).toBe(false);
    expect(result.has("product.release")).toBe(false);
  });

  it("🔴 treats an empty permission set as an ANSWER, not as 'unknown'", () => {
    // A member who holds no roles yet. The old code showed them everything.
    const noRoles: OrganizationChoice = {
      ...TECHNICIAN,
      roles: [],
      permissions: [],
    };

    const result = effectiveNavPermissions(
      authenticated(ACME_ID),
      [noRoles],
      FULL_MAP,
    );

    expect(result.size).toBe(0);
  });

  it("keeps the full map when there is no session at all", () => {
    // The static export / signed-out case. An empty set here makes real
    // pages unreachable — the regression layout.tsx warns about.
    const anonymous: SessionState = {
      status: "anonymous",
      reason: "you are not signed in",
    };

    expect(effectiveNavPermissions(anonymous, [], FULL_MAP)).toBe(FULL_MAP);
  });

  it("🔴 FAILS CLOSED when the active tenant is not in the list", () => {
    // Raised by Codex against the first version, which returned the full map
    // here and justified it as "we do not know". That contradicts the rule
    // in auth-provider.tsx -- an API that cannot report permissions must
    // show LESS, never everything -- and it masks a broken session behind a
    // menu on which every control 403s.
    //
    // The fallback is for ABSENCE OF A SESSION, not for a broken one.
    const result = effectiveNavPermissions(
      authenticated(OTHER_ID),
      [TECHNICIAN],
      FULL_MAP,
    );

    expect(result.size).toBe(0);
    expect(result).not.toBe(FULL_MAP);
  });

  it("🔴 FAILS CLOSED when the organization list is empty but a session exists", () => {
    // The fifth state Codex named: authenticated while `organizations` is
    // temporarily empty or stale. It used to collapse into the same
    // full-map branch.
    const result = effectiveNavPermissions(authenticated(ACME_ID), [], FULL_MAP);

    expect(result.size).toBe(0);
  });

  it("reads the ACTIVE tenant, never simply the first", () => {
    // Selecting `choices[0]` was a real defect in this provider once, and it
    // silently moved a chemist's writes into the wrong tenant. The same
    // mistake here would show one tenant's menu while acting in another.
    const lead: OrganizationChoice = {
      organizationId: OTHER_ID,
      name: "Boreal Adhesives",
      code: "BOR",
      roles: ["product_development_lead"],
      permissions: ["product.release"],
    };

    const result = effectiveNavPermissions(
      authenticated(OTHER_ID),
      [TECHNICIAN, lead],
      FULL_MAP,
    );

    expect([...result]).toEqual(["product.release"]);
  });
});

/**
 * `permits` — the "an item that names no permission is visible" half of the
 * rule, stated once instead of at every call site.
 *
 * 🔴 BOTH DIRECTIONS. "Hidden when not held" passes just as happily when the
 * function returns `false` for everything, which would empty every submenu in
 * the product.
 */
describe("permits", () => {
  const HELD: ReadonlySet<string> = new Set(["batch.view", "test.execute"]);

  it("allows a control that names no permission", () => {
    // Matches `visibleNavigation`: a nav item with no `permission` is offered
    // to any authenticated member. If the two disagreed, the sidebar and the
    // submenu would answer differently for the same caller.
    expect(permits(HELD, undefined)).toBe(true);
    expect(permits(new Set(), undefined)).toBe(true);
  });

  it("allows a permission the caller holds", () => {
    expect(permits(HELD, "batch.view")).toBe(true);
  });

  it("refuses a permission the caller does not hold", () => {
    expect(permits(HELD, "admin.roles")).toBe(false);
  });

  it("🔴 refuses on a near-miss rather than matching a prefix", () => {
    // `admin.role` is not `admin.roles`, and `batch` is not `batch.view`.
    // A `startsWith` implementation would pass every other test in this file
    // and hand `admin.roles` to anyone holding `admin.rolesomething`.
    expect(permits(new Set(["admin.rolesomething"]), "admin.roles")).toBe(false);
    expect(permits(HELD, "batch")).toBe(false);
  });
});
