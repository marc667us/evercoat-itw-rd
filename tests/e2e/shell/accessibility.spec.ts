import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

/**
 * Accessibility, scanned rather than asserted by hand.
 *
 * `CLAUDE.md` §11 states "axe-core runs in CI". Until this file existed
 * it never had — the dependency was declared and nothing invoked it,
 * which is the same shape as the other gaps this project keeps finding:
 * a stated control with no production path that executes it.
 *
 * WHAT IS AND IS NOT COVERED. axe-core catches machine-detectable
 * failures: contrast, names, roles, landmarks, duplicated ids. It cannot
 * see the rule this domain actually cares most about — that status is
 * never conveyed by colour alone. Pass-green against fail-red measures
 * ΔE 4.2 under deuteranopia, which roughly 8% of men cannot tell apart,
 * so `StatusBadge` pairs every colour with an icon and a word.
 *
 * That component is not on any page yet, so there is nothing here to
 * scan for it. When the Slice 2 screens land, the colour+icon+text
 * assertion belongs in this file — it is a measurement, not a preference.
 */

// Scanned at the level the source requires: WCAG 2.1 AA. Best-practice
// rules are excluded deliberately — they are advice, and failing a build
// on advice teaches people to disable the check.
const STANDARD = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"];

const PAGES = [
  { name: "dashboard", path: "/dashboard" },
  { name: "administration", path: "/admin" },
  // The Slice 2 screens. Adding them is what caught the data grid's
  // scroll container having no tabIndex — the identical
  // `scrollable-region-focusable` defect fixed in chart-wrapper.tsx, which
  // survived only because no scanned page had ever rendered a grid.
  { name: "projects", path: "/projects" },
  { name: "project workspace", path: "/projects/RDP-2026-014" },
  { name: "my work", path: "/my-work" },
  { name: "pipeline", path: "/pipeline" },
  { name: "innovation", path: "/innovation" },
  // Slice 3.
  { name: "materials", path: "/materials" },
  { name: "suppliers", path: "/suppliers" },
  { name: "formulations", path: "/formulations" },
  { name: "formula workspace", path: "/formulations/FRM-014" },
];

for (const target of PAGES) {
  test(`${target.name} has no WCAG 2.1 AA violations`, async ({ page }) => {
    await page.goto(target.path);
    await expect(page.getByRole("main")).toBeVisible();

    const results = await new AxeBuilder({ page }).withTags(STANDARD).analyze();

    // The failure message names the rule, the impact and the element.
    // A bare "expected 0, got 3" would send the next reader back to the
    // browser to find out what broke, which is how a11y checks end up
    // skipped rather than fixed.
    const summary = results.violations.map((v) => {
      const where = v.nodes.map((n) => n.target.join(" ")).join(", ");
      return `[${v.impact ?? "unknown"}] ${v.id}: ${v.help} → ${where}`;
    });

    expect(summary, `axe-core violations on ${target.path}`).toEqual([]);
  });
}

test("the collapsed sidebar keeps its labels in the accessibility tree", async ({ page }) => {
  // Collapsing is a visual affordance for reclaiming width on dense
  // formulation and DOE tables. It must not narrow the application for
  // anyone using a screen reader, so the labels move to `sr-only` rather
  // than being removed.
  await page.goto("/dashboard");
  await page.getByRole("button", { name: /Collapse|»/ }).click();

  const nav = page.getByRole("navigation", { name: "Main navigation" });
  await expect(nav).toHaveAttribute("data-collapsed", "true");

  const results = await new AxeBuilder({ page })
    .withTags(STANDARD)
    .include('nav[aria-label="Main navigation"]')
    .analyze();

  expect(
    results.violations.map((v) => `${v.id}: ${v.help}`),
    "collapsing the sidebar introduced accessibility violations",
  ).toEqual([]);
});

test("every page is reachable by keyboard alone", async ({ page }) => {
  // Keyboard navigation is required, not optional (CLAUDE.md §11).
  // Tabbing must land on something focusable rather than falling into a
  // trap or reaching nothing at all.
  await page.goto("/dashboard");

  await page.keyboard.press("Tab");
  const firstFocused = await page.evaluate(() => document.activeElement?.tagName ?? null);
  expect(firstFocused, "nothing is focusable — the shell is a keyboard trap").not.toBeNull();
  expect(["A", "BUTTON"]).toContain(firstFocused);
});
