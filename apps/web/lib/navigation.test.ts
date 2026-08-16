/**
 * Navigation contract tests.
 *
 * Serving the shell with an empty permission set showed only Work and
 * Governance — correct behaviour, but it proves only that the filter
 * *removes* things. A filter that returned nothing at all would look
 * identical. These assert both directions.
 *
 * The structural tests matter more than they look: the sidebar is
 * specified six times across the source documents with real drift
 * between the versions, and two of those differences (Messages, Product
 * Models) were caught only in review. Pinning them here means a future
 * edit that silently reverts to an earlier variant fails a test rather
 * than shipping.
 */

import { describe, expect, it } from "vitest";

import {
  ALL_NAV_ITEMS,
  CURRENT_SLICE,
  NAVIGATION,
  isAvailable,
  navItemByHref,
  visibleNavigation,
} from "./navigation";

describe("navigation structure", () => {
  it("has the six groups the source specifies, in order", () => {
    expect(NAVIGATION.map((g) => g.id)).toEqual([
      "work",
      "development",
      "resources",
      "industrialization",
      "intelligence",
      "governance",
    ]);
  });

  it("includes Messages in WORK", () => {
    // MASTER PROMPT §13 and Expanded Requirements §41 both list it;
    // Navigation narrative §66 omits it. Later and explicit wins (X5).
    const work = NAVIGATION.find((g) => g.id === "work");
    expect(work?.items.map((i) => i.id)).toContain("messages");
  });

  it("includes Product Models in INTELLIGENCE", () => {
    // Same drift, same resolution (X6).
    const intel = NAVIGATION.find((g) => g.id === "intelligence");
    expect(intel?.items.map((i) => i.id)).toContain("product-models");
  });

  it("has unique ids", () => {
    // A duplicate silently breaks React keys and produces a sidebar that
    // renders wrongly without erroring.
    const ids = ALL_NAV_ITEMS.map((i) => i.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it("has unique hrefs", () => {
    const hrefs = ALL_NAV_ITEMS.map((i) => i.href);
    expect(new Set(hrefs).size).toBe(hrefs.length);
  });

  it("uses absolute hrefs", () => {
    for (const item of ALL_NAV_ITEMS) {
      expect(item.href.startsWith("/")).toBe(true);
    }
  });
});

describe("permission filtering", () => {
  it("hides permissioned items when the user holds nothing", () => {
    const visible = visibleNavigation(new Set());
    const ids = visible.flatMap((g) => g.items.map((i) => i.id));

    expect(ids).toContain("dashboard");
    expect(ids).not.toContain("formulations");
    expect(ids).not.toContain("administration");
  });

  it("drops groups that end up empty", () => {
    // A Technician should not be shown an "Industrialization" heading
    // with nothing beneath it.
    const visible = visibleNavigation(new Set());
    for (const group of visible) {
      expect(group.items.length).toBeGreaterThan(0);
    }
    expect(visible.map((g) => g.id)).not.toContain("industrialization");
  });

  it("reveals items once the permission is held", () => {
    // The direction the empty-set render could not demonstrate.
    const chemist = new Set([
      "formula.view",
      "material.view",
      "batch.view",
      "test.view",
      "failure.view",
      "project.view",
    ]);
    const ids = visibleNavigation(chemist).flatMap((g) => g.items.map((i) => i.id));

    expect(ids).toContain("formulations");
    expect(ids).toContain("materials");
    expect(ids).toContain("laboratory");
    // Still not an administrator.
    expect(ids).not.toContain("administration");
  });

  it("shows Administration only with admin.users", () => {
    // ADR-021: Administration section 1 ships in Slice 1, so this must
    // be reachable from the start for someone who holds the permission.
    const admin = new Set(["admin.users"]);
    const ids = visibleNavigation(admin).flatMap((g) => g.items.map((i) => i.id));
    expect(ids).toContain("administration");
  });

  it("never leaks an item the user cannot hold", () => {
    // Exhaustive: for every permissioned item, a user without exactly
    // that permission must not see it.
    for (const item of ALL_NAV_ITEMS) {
      if (!item.permission) continue;
      const others = new Set(
        ALL_NAV_ITEMS.map((i) => i.permission).filter(
          (p): p is string => Boolean(p) && p !== item.permission,
        ),
      );
      const ids = visibleNavigation(others).flatMap((g) => g.items.map((i) => i.id));
      expect(ids).not.toContain(item.id);
    }
  });
});

describe("slice availability", () => {
  it("marks future-slice items unavailable", () => {
    const formulations = ALL_NAV_ITEMS.find((i) => i.id === "formulations");
    expect(formulations).toBeDefined();
    expect(isAvailable(formulations!)).toBe(false);
  });

  it("treats items with no slice as available now", () => {
    const dashboard = ALL_NAV_ITEMS.find((i) => i.id === "dashboard");
    expect(isAvailable(dashboard!)).toBe(true);
  });

  it("keeps Administration available from Slice 1", () => {
    const admin = ALL_NAV_ITEMS.find((i) => i.id === "administration");
    expect(isAvailable(admin!)).toBe(true);
  });

  it("declares no item below the current slice", () => {
    // Guards against an item being marked slice 0 or negative by typo,
    // which would render it live before its backend exists.
    for (const item of ALL_NAV_ITEMS) {
      expect(item.slice ?? 1).toBeGreaterThanOrEqual(1);
    }
    expect(CURRENT_SLICE).toBeGreaterThanOrEqual(1);
  });
});

describe("href resolution", () => {
  it("resolves a nested path to its parent item", () => {
    // Breadcrumbs and active-state highlighting depend on this: a user
    // deep inside /projects/RDP-2026-014/formulations must still see
    // Projects marked active in the sidebar.
    expect(navItemByHref("/projects/abc/formulations")?.id).toBe("projects");
  });

  it("returns undefined for an unknown path", () => {
    expect(navItemByHref("/nothing-here")).toBeUndefined();
  });
});
