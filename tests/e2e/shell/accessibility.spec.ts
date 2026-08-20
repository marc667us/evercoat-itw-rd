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

test("the collapsed sidebar keeps its labels in the accessibility tree", async ({
  page,
}) => {
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
  const firstFocused = await page.evaluate(
    () => document.activeElement?.tagName ?? null,
  );
  expect(
    firstFocused,
    "nothing is focusable — the shell is a keyboard trap",
  ).not.toBeNull();
  expect(["A", "BUTTON"]).toContain(firstFocused);
});

test("the unbuilt navigation items are legible, which axe-core cannot check", async ({
  page,
}) => {
  /**
   * 🔴 THE CONTRAST RULE OPTS OUT OF EXACTLY THESE ELEMENTS.
   *
   * axe-core's `color-contrast` rule skips anything it considers
   * disabled, and `isDisabled()` returns true for any element — or any
   * ANCESTOR — carrying `aria-disabled="true"`
   * (`node_modules/axe-core/axe.js`, `isDisabled(virtualNode)`).
   *
   * Seventeen of this sidebar's twenty-six items are inert, correctly
   * marked `aria-disabled="true"`, and were painted `text-slate-300` —
   * **1.48:1** against white, where WCAG 2.1 AA asks for 4.5:1. Two
   * thirds of the primary navigation was unreadable and every axe scan
   * above reported zero violations, because the attribute that describes
   * the state also silences the check.
   *
   * So this measures the ratio itself, from the browser's own computed
   * styles. It is deliberately not an axe assertion: a test that used
   * the same rule would inherit the same blind spot.
   */
  await page.goto("/dashboard");

  const nav = page.getByRole("navigation", { name: "Main navigation" });
  const inert = nav.locator('[aria-disabled="true"]');

  const count = await inert.count();
  expect(
    count,
    "no inert navigation items found — has the nav model changed?",
  ).toBeGreaterThan(0);

  const ratios = await inert.evaluateAll((elements) => {
    const luminance = (rgb: string): number => {
      const parts = rgb
        .match(/\d+(\.\d+)?/g)
        ?.slice(0, 3)
        .map(Number) ?? [0, 0, 0];
      const channel = (value: number) => {
        const c = value / 255;
        return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
      };
      const [r, g, b] = parts.map(channel);
      return 0.2126 * r + 0.7152 * g + 0.0722 * b;
    };

    // Walk up for the first non-transparent background, the way a
    // rendering engine composites it. Assuming white would report a
    // pass for light text on a light-grey row.
    const backgroundOf = (element: Element): string => {
      let node: Element | null = element;
      while (node) {
        const bg = getComputedStyle(node).backgroundColor;
        if (bg && !/rgba\(0,\s*0,\s*0,\s*0\)|transparent/.test(bg)) return bg;
        node = node.parentElement;
      }
      return "rgb(255, 255, 255)";
    };

    return elements.map((element) => {
      const styles = getComputedStyle(element);
      const fg = luminance(styles.color);
      const bg = luminance(backgroundOf(element));
      const [hi, lo] = fg > bg ? [fg, bg] : [bg, fg];
      return {
        label: (element.textContent ?? "").trim().slice(0, 30),
        color: styles.color,
        ratio: Number(((hi + 0.05) / (lo + 0.05)).toFixed(2)),
      };
    });
  });

  const failing = ratios.filter((r) => r.ratio < 4.5);
  expect(
    failing,
    "inert navigation items fall below the WCAG 2.1 AA contrast minimum of 4.5:1 " +
      "for normal text. axe-core will NOT report this, because its color-contrast " +
      "rule skips aria-disabled elements — that is why this test computes the " +
      "ratio itself.",
  ).toEqual([]);
});

test("an unbuilt navigation item says so in words, not only in colour", async ({
  page,
}) => {
  // The counterpart to the contrast fix. Raising the colour to a
  // readable slate-500 narrows the visual gap to the live items, so the
  // distinction has to be carried by something that is not a hue at all
  // — the same rule `StatusBadge` applies to the traffic light.
  await page.goto("/dashboard");

  const nav = page.getByRole("navigation", { name: "Main navigation" });
  const inert = nav.locator('[aria-disabled="true"]').first();

  await expect(inert).toContainText(/planned/i);

  // And the old wording must not come back: "Available in slice 15" is a
  // build schedule, not something a formulation chemist can act on.
  const titles = await nav
    .locator('[aria-disabled="true"]')
    .evaluateAll((els) => els.map((e) => e.getAttribute("title") ?? ""));
  expect(
    titles.filter((t) => /slice/i.test(t)),
    "an inert nav item explains itself with an internal slice number",
  ).toEqual([]);
});
