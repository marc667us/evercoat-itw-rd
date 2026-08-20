import fs from "node:fs";
import path from "node:path";

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
    const ids = visibleNavigation(chemist).flatMap((g) =>
      g.items.map((i) => i.id),
    );

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
    const ids = visibleNavigation(admin).flatMap((g) =>
      g.items.map((i) => i.id),
    );
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
      const ids = visibleNavigation(others).flatMap((g) =>
        g.items.map((i) => i.id),
      );
      expect(ids).not.toContain(item.id);
    }
  });
});

describe("slice availability", () => {
  it("marks future-slice items unavailable and shipped ones available", () => {
    // A PROPERTY OVER EVERY ITEM, not an assertion about one named
    // destination.
    //
    // This test used to name "formulations" as the future-slice example.
    // Slice 3 built it and the test failed — correctly, but for a reason
    // that has nothing to do with the rule it exists to protect. Naming a
    // specific item means editing this test every slice, and a test edited
    // that often is a test people stop reading.
    //
    // Stated as a property it holds forever: availability is exactly
    // "slice <= CURRENT_SLICE", for all items, whatever CURRENT_SLICE is.
    const future = ALL_NAV_ITEMS.filter((i) => (i.slice ?? 1) > CURRENT_SLICE);
    const shipped = ALL_NAV_ITEMS.filter(
      (i) => (i.slice ?? 1) <= CURRENT_SLICE,
    );

    // Both sides must be non-empty, or the property is vacuously true — a
    // green test asserting nothing is worse than a red one.
    expect(
      future.length,
      "no future-slice items left to check",
    ).toBeGreaterThan(0);
    expect(shipped.length, "no shipped items to check").toBeGreaterThan(0);

    for (const item of future) {
      expect(
        isAvailable(item),
        `${item.id} is slice ${item.slice} and should be inert`,
      ).toBe(false);
    }
    for (const item of shipped) {
      expect(
        isAvailable(item),
        `${item.id} has shipped and should be a link`,
      ).toBe(true);
    }
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

describe("an available destination has a page behind it", () => {
  /**
   * 🔴 THE GUARD THAT `CURRENT_SLICE`'s COMMENT ASKED FOR.
   *
   * `isAvailable` decides whether a sidebar entry is a LINK or an inert
   * span, and it decides it from a slice NUMBER. Nothing connected that
   * number to whether the page it points at exists — the comment above
   * the constant simply asked the next person to remember, which is the
   * same shape as every "two literals in two files cannot be
   * type-checked into agreement" defect recorded on this platform.
   *
   * Raising CURRENT_SLICE one slice too far would silently turn a set of
   * inert items into live links into 404s. The repository's own rule is
   * that a dead link is worse than no link: it reads as a missing record
   * rather than an unbuilt screen.
   *
   * So this reads the filesystem. It is the only test here that touches
   * disk, and that is the point — the fact it is checking lives on disk.
   */
  const APP_DIR = path.join(__dirname, "..", "app");

  it("every available item resolves to a real page.tsx", () => {
    const missing = ALL_NAV_ITEMS.filter((item) => {
      if (!isAvailable(item)) return false;
      // href is always root-relative and never has a query or hash.
      const segments = item.href.replace(/^\//, "").split("/");
      return !fs.existsSync(path.join(APP_DIR, ...segments, "page.tsx"));
    });

    expect(
      missing.map((i) => `${i.id} -> ${i.href}`),
      "these navigation items are AVAILABLE (so the sidebar renders them as " +
        "links) but have no page.tsx, so clicking one reaches a 404. Either " +
        "build the screen or raise its `slice` above CURRENT_SLICE.",
    ).toEqual([]);
  });

  it("the two screens built for slices 4 and 5 are the ones that became available", () => {
    // Named explicitly, unlike the generic test above, because this is a
    // claim about THIS change rather than about the invariant: raising
    // CURRENT_SLICE to 5 must expose Laboratory and Testing and nothing
    // else. If a later slice-4 or slice-5 item is added without a screen,
    // the generic test catches it; this one catches the reverse mistake of
    // the constant being raised for an unrelated reason.
    const newlyAvailable = ALL_NAV_ITEMS.filter(
      (i) => (i.slice ?? 1) === 4 || (i.slice ?? 1) === 5,
    );
    expect(newlyAvailable.map((i) => i.id).sort()).toEqual([
      "laboratory",
      "testing",
    ]);
    for (const item of newlyAvailable) {
      expect(isAvailable(item), `${item.id} should now be a link`).toBe(true);
    }
  });
});
