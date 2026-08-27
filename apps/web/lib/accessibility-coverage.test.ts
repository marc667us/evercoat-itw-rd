/**
 * 🔴 A PAGE ABSENT FROM THE ACCESSIBILITY SWEEP IS A PAGE NOBODY CHECKED.
 *
 * `tests/e2e/shell/accessibility.spec.ts` runs axe-core against WCAG 2.1 AA on
 * a hand-maintained list of paths. §11 requires accessibility of the product,
 * not of a list — and the list grows only when somebody remembers to add to it.
 *
 * The Supervisor found `/admin/roles` and `/admin/permissions` missing, shipped
 * in the same commit as the sweep entries beside them. Asking the wider
 * question — which routes exist, and which are in the list — found **eight
 * more**: `/analytics`, `/knowledge`, `/reports` and all five workspace routes,
 * some uncovered since the slice that built them. The list has always looked
 * complete, because a list that grows by memory looks exactly like a list that
 * is finished.
 *
 * So the list is derived from the filesystem and compared. This is the same
 * shape as `sections.catalogue.test.ts` reading the seed SQL and
 * `decisions.test.ts` reading `Field(pattern=…)`: the test reads the OTHER
 * tier rather than a copy of it. A hand-written list checked against a
 * hand-written list proves only that somebody typed twice.
 *
 * ⚠️ EXEMPTIONS ARE NAMED HERE, WITH A REASON, and there are two. An exemption
 * that is merely a filter would let the next reader delete a page from the
 * sweep by adding a pattern.
 */
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

const APP = join(__dirname, "..", "app");
const SPEC = join(__dirname, "..", "..", "..", "tests", "e2e", "shell", "accessibility.spec.ts");

/**
 * Routes the sweep does not cover, and why.
 *
 * Not "pages that are awkward to test" — pages that axe-core running against
 * the application shell cannot meaningfully assert.
 */
const EXEMPT = new Map<string, string>([
  [
    "/",
    "the front door redirects on mount, so by the time axe could run the " +
      "browser is on the landing screen — which IS swept. Its no-JavaScript " +
      "content is one heading and one link.",
  ],
  [
    "/auth/callback",
    "reached only with a live authorization code from Keycloak. Opened " +
      "directly it renders its own refusal, and the sweep drives no OIDC flow.",
  ],
]);

/** Every route with a `page.tsx`, as the router will serve it. */
function routes(directory: string, prefix = ""): string[] {
  const found: string[] = [];
  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    if (entry.isDirectory()) {
      found.push(...routes(join(directory, entry.name), `${prefix}/${entry.name}`));
    } else if (entry.name === "page.tsx") {
      found.push(prefix === "" ? "/" : prefix);
    }
  }
  return found;
}

/** The paths the sweep actually visits. */
function swept(): string[] {
  const spec = readFileSync(SPEC, "utf8");
  return [...spec.matchAll(/path:\s*"([^"]+)"/g)].map((match) => match[1] as string);
}

describe("the accessibility sweep covers the application", () => {
  it("reads a real spec with a real list", () => {
    // 🔴 THE GUARD ON THE GUARD. If the spec is renamed or the shape of its
    // list changes, `swept()` returns nothing and every assertion below passes
    // vacuously — a check that walks through its own gap.
    expect(swept().length).toBeGreaterThan(20);
    expect(routes(APP).length).toBeGreaterThan(20);
  });

  it("🔴 every route is either swept or exempt with a stated reason", () => {
    const paths = swept();

    const uncovered = routes(APP).filter((route) => {
      if (EXEMPT.has(route)) return false;
      // A dynamic segment is covered by any concrete path under the same
      // prefix — the sweep visits `/projects/RDP-2026-014` for
      // `/projects/[code]`, which is the only way to visit it at all.
      const dynamic = route.indexOf("/[");
      if (dynamic !== -1) {
        const parent = route.slice(0, dynamic);
        return !paths.some((path) => path.startsWith(`${parent}/`) && path !== parent);
      }
      return !paths.includes(route);
    });

    expect(
      uncovered.sort(),
      "these routes render in a browser and no accessibility check has ever " +
        "run against them. Add them to tests/e2e/shell/accessibility.spec.ts, " +
        "or exempt them in EXEMPT above with the reason",
    ).toEqual([]);
  });

  it("sweeps nothing that does not exist", () => {
    // The other direction. A path left behind by a deleted or renamed route
    // makes the sweep visit a 404, which axe-core reports as clean — coverage
    // that measures a Next.js error page.
    const existing = routes(APP);
    const stale = swept().filter((path) => {
      if (existing.includes(path)) return false;
      // Concrete instances of a dynamic route: `/projects/RDP-2026-014`.
      const parent = path.slice(0, path.lastIndexOf("/"));
      return !existing.some((route) => route.startsWith(`${parent}/[`));
    });

    expect(stale, "the sweep visits paths that no longer have a page").toEqual([]);
  });

  it("every exemption names a route that exists", () => {
    // An exemption for a deleted route is a hole nobody can see: it silences
    // nothing today and silences whatever takes that path tomorrow.
    const existing = new Set(routes(APP));
    expect([...EXEMPT.keys()].filter((route) => !existing.has(route))).toEqual([]);
  });
});
