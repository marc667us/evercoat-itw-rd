/**
 * The SECOND level of navigation, filtered by the caller's own permissions.
 *
 * 🔴 WHAT THIS IS PROVING, AND WHY IT DID NOT EXIST BEFORE.
 *
 * I79 gave the sidebar the caller's permissions on 2026-08-25 and stopped
 * there. `ContextSubmenu` had no `permission` field, no filter and no test, so
 * every workspace's sections were identical for everybody who could open the
 * page: Administration offered Roles, Permissions, Organization, Stage Gates,
 * Test Methods, Approval Templates, Notifications and Audit to any caller
 * holding `admin.users`, while the endpoints behind them require seven other
 * permissions.
 *
 * 🔴 IT ASSERTS BOTH DIRECTIONS, AND THE SECOND IS THE ONE THAT MATTERS.
 * "Roles is absent" passes just as happily when the filter returns nothing,
 * which would empty every submenu in the product — the failure that looks like
 * a page that did not load. So every case also names a section that must
 * REMAIN.
 */
import { describe, expect, it } from "vitest";

import { visibleSubmenu, type SubmenuItem } from "./context-submenu";

/** The real Administration sections, with the permissions their routes require. */
const ADMIN_SECTIONS: SubmenuItem[] = [
  { label: "Users & Members", href: "/admin", permission: "admin.users" },
  { label: "Roles", href: "/admin/roles", permission: "admin.roles" },
  { label: "Permissions", href: "/admin/permissions", permission: "admin.roles" },
  { label: "Organization", href: "/admin/organization", permission: "admin.organization" },
  { label: "Audit", href: "/admin/audit", permission: "admin.audit" },
];

const labels = (items: SubmenuItem[]): string[] => items.map((i) => i.label);

describe("visibleSubmenu", () => {
  it("offers only the sections whose permission the caller holds", () => {
    // A caller who may manage members and nothing else. `admin.users` is what
    // puts Administration in the sidebar, and it is NOT what the other four
    // sections require — which is the whole defect this closes.
    const result = visibleSubmenu(ADMIN_SECTIONS, new Set(["admin.users"]));

    expect(labels(result)).toEqual(["Users & Members"]);
  });

  it("offers every section to a caller who holds every permission", () => {
    // The other direction. Without this, a filter that returned `[]` for
    // everyone would pass the test above. Measured 2026-08-27: `admin.demo` is
    // the one seeded role holding all ten `admin.*` codes.
    const all = new Set([
      "admin.users",
      "admin.roles",
      "admin.organization",
      "admin.audit",
    ]);

    expect(labels(visibleSubmenu(ADMIN_SECTIONS, all))).toEqual([
      "Users & Members",
      "Roles",
      "Permissions",
      "Organization",
      "Audit",
    ]);
  });

  it("🔴 shows two sections that share one permission together, or neither", () => {
    // Roles and Permissions are both served by endpoints requiring
    // `admin.roles`. If the filter matched on label, href or position, these
    // two would separate — and one of them would be a live link to a section
    // its own endpoint refuses.
    const result = visibleSubmenu(ADMIN_SECTIONS, new Set(["admin.roles"]));

    expect(labels(result)).toEqual(["Roles", "Permissions"]);
  });

  it("offers a section that names no permission to anybody", () => {
    // Matches `visibleNavigation`'s treatment of a nav item with no
    // `permission`. Both levels have to answer the same way for one caller or
    // the sidebar and the submenu disagree about who they are talking to.
    const mixed: SubmenuItem[] = [
      { label: "Overview", href: "/x" },
      { label: "Settings", href: "/x/settings", permission: "admin.organization" },
    ];

    expect(labels(visibleSubmenu(mixed, new Set()))).toEqual(["Overview"]);
  });

  it("🔴 keeps `unavailable` and `state` as separate concerns from permission", () => {
    // A not-yet-built section the caller MAY see stays in the list and stays
    // inert — hiding it would erase the shape of the module, which is the
    // reason `unavailable` exists rather than simply omitting the entry. A
    // section the caller may NOT see goes, built or not.
    const sections: SubmenuItem[] = [
      { label: "Stage Gates", href: "/a", permission: "admin.stage_gates", unavailable: true, state: "not-started" },
      { label: "Audit", href: "/b", permission: "admin.audit", unavailable: true },
    ];

    const result = visibleSubmenu(sections, new Set(["admin.stage_gates"]));

    expect(labels(result)).toEqual(["Stage Gates"]);
    // Read through a named binding rather than `result[0]!`: under
    // `noUncheckedIndexedAccess` the assertion above already proves there is
    // exactly one, and a non-null assertion would silence the check that
    // proved it rather than rely on it.
    const [only] = result;
    expect(only?.unavailable).toBe(true);
    expect(only?.state).toBe("not-started");
  });

  it("returns nothing when the caller holds none of the permissions", () => {
    // The component renders `null` on this, rather than an empty sticky bar
    // with a border and no content.
    expect(visibleSubmenu(ADMIN_SECTIONS, new Set(["project.view"]))).toEqual([]);
  });
});
