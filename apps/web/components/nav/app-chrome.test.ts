/**
 * The public-route list must stay true, because the sidebar depends on it.
 *
 * 🔴 WHAT THIS GUARDS. `AppChrome` decides, from a hard-coded list, whether a
 * route gets the signed-in shell. Two ways that goes wrong, both silent:
 *
 *   - A path in the list stops existing, or is renamed. The entry then matches
 *     nothing, and if the page moved it comes back wearing the internal
 *     sidebar — the exact defect this component was written to fix, restored
 *     by a rename.
 *   - An authenticated route starts matching. Every one of them would lose its
 *     navigation, and the pages would still render, so a screenshot of any one
 *     screen looks merely odd rather than broken.
 *
 * Both are checked against the FILESYSTEM rather than against a second list,
 * because two lists in two files cannot be type-checked into agreement — a
 * defect shape this repository has hit repeatedly.
 */

import { existsSync, readdirSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { PUBLIC_ROUTES, isPublicRoute } from "./app-chrome";

const APP_DIR = join(__dirname, "..", "..", "app");

/** Every route segment that has a `page.tsx`, as a path. */
function routesOnDisk(dir: string, prefix = ""): string[] {
  const found: string[] = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    if (!entry.isDirectory()) continue;
    // Dynamic segments and private folders are not comparable to a literal
    // pathname, and the public list contains neither.
    if (entry.name.startsWith("[") || entry.name.startsWith("_")) continue;
    const path = `${prefix}/${entry.name}`;
    if (existsSync(join(dir, entry.name, "page.tsx"))) found.push(path);
    found.push(...routesOnDisk(join(dir, entry.name), path));
  }
  return found;
}

describe("the public route list", () => {
  it("names only routes that actually exist", () => {
    const onDisk = new Set(routesOnDisk(APP_DIR));
    // The root is `app/page.tsx` itself, which the walk above cannot report
    // because it has no directory of its own.
    expect(existsSync(join(APP_DIR, "page.tsx"))).toBe(true);

    for (const route of PUBLIC_ROUTES) {
      if (route === "/") continue;
      expect(onDisk, `${route} is listed as public but has no page.tsx`).toContain(route);
    }
  });

  it("does not capture any authenticated route", () => {
    const authenticated = routesOnDisk(APP_DIR).filter(
      (route) => !(PUBLIC_ROUTES as readonly string[]).includes(route),
    );
    // A real corpus, not a handful of examples: every other page in the app.
    expect(authenticated.length).toBeGreaterThan(10);

    const wrongly = authenticated.filter((route) => isPublicRoute(route));
    expect(wrongly, "these authenticated routes would lose the sidebar").toEqual([]);
  });

  it("treats a trailing slash as the same route, because the export build adds one", () => {
    // `trailingSlash` is on for `output: "export"` and off for standalone. A
    // check that handled only one form would put the internal sidebar back on
    // the public site in exactly one build mode.
    expect(isPublicRoute("/marketplace")).toBe(true);
    expect(isPublicRoute("/marketplace/")).toBe(true);
    expect(isPublicRoute("/")).toBe(true);
  });

  it("matches exactly, so a longer path with the same prefix is not public", () => {
    // `/marketplace-admin` and `/marketplace/settings` must NOT be treated as
    // public by a `startsWith` that looked reasonable.
    expect(isPublicRoute("/marketplace-admin")).toBe(false);
    expect(isPublicRoute("/marketplace/settings")).toBe(false);
    expect(isPublicRoute("/dashboard")).toBe(false);
  });
});
