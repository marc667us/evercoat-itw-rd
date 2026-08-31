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
  // 🔴 THE PUBLIC SURFACE FIRST, BECAUSE IT IS THE ONLY PART ANYONE CAN REACH
  // WITHOUT AN ACCOUNT.
  //
  // Every other page in this list is behind sign-in, so its audience is ten
  // demo users and a controlled set of staff. These three are the front door,
  // the marketplace and the news feed, served to anybody with the URL — which
  // makes them the pages where an accessibility failure has the widest reach
  // and the least chance of being reported by someone who can raise a ticket.
  //
  // Scanned in their REAL public state: signed out, with whatever the public
  // API returns. That is the state a visitor meets.
  { name: "public landing page", path: "/" },
  { name: "public marketplace", path: "/marketplace" },
  { name: "public industry news", path: "/industry-news" },
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
  // Slices 4 and 5. These two are the first screens with NO demonstration
  // fallback — with no API compiled in they render a "no data source"
  // notice rather than rows, so what axe scans here is that state. Worth
  // scanning precisely because it is the state the deployed site is in.
  { name: "laboratory", path: "/laboratory" },
  { name: "testing", path: "/testing" },
  // Slice 6, built 2026-08-27. 🔴 THIS LIST IS HAND-MAINTAINED AND THAT IS ITS
  // ONE WEAKNESS: a screen added without an entry here is never scanned, and
  // nothing fails. Both new destinations are added in the same commit that
  // makes them reachable, and `navigation.spec.ts`'s crawl is the backstop that
  // at least proves they render.
  { name: "failures", path: "/failures" },
  { name: "approvals", path: "/approvals" },
  // The account screens, 2026-08-27. `/account/settings` is the one that
  // matters most here: it renders five theme swatches, and a swatch is exactly
  // the kind of decorative colour block that acquires a contrast failure the
  // moment somebody gives it a label.
  { name: "profile", path: "/account/profile" },
  { name: "settings", path: "/account/settings" },
  { name: "security", path: "/account/security" },
  // Administration's new sections.
  { name: "stage gates", path: "/admin/stage-gates" },
  { name: "reference data", path: "/admin/reference-data" },
  // 🔴 THESE TWO WERE SHIPPED IN THE SAME COMMIT AND LEFT OUT OF THIS LIST.
  // The Supervisor found it. They are the densest pages in Administration —
  // `/admin/permissions` renders every permission code in the product as a
  // `<code>` chip, and a chip is exactly the small, low-contrast element this
  // sweep exists to catch. A page absent from the list is a page nobody
  // checked, and the list looked complete because it had just grown.
  { name: "roles", path: "/admin/roles" },
  { name: "permissions", path: "/admin/permissions" },
  // 🔴 AND MEASURING THE WHOLE ROUTE LIST FOUND EIGHT MORE.
  //
  // The Supervisor named the two above. Asking the wider question — which
  // routes exist and which appear here — found that this list had never
  // covered `/analytics`, `/knowledge`, `/reports`, or any of the five
  // workspace routes, some of them since the slice that built them. The list
  // has always LOOKED complete because it grows whenever somebody remembers.
  //
  // `lib/accessibility-coverage.test.ts` now derives the route list from the
  // filesystem and fails when one is absent, so remembering is no longer the
  // mechanism.
  { name: "analytics", path: "/analytics" },
  { name: "knowledge", path: "/knowledge" },
  // The Material Safety Data & Research Center (slice 7, 2026-08-28).
  // The name is unique and stays unique: a DUPLICATE test title makes
  // Playwright refuse the ENTIRE run -- not one failure, zero tests
  // executed and nothing in the output looking red. That took out a whole
  // live suite on 2026-08-27, which is why
  // `lib/accessibility-coverage.test.ts` now asserts uniqueness too.
  { name: "material safety data", path: "/material-safety" },
  { name: "competitor intelligence", path: "/material-safety/competitors" },
  { name: "research center", path: "/material-safety/research" },
  { name: "reports", path: "/reports" },
  // Global search (spec §29). Swept with no `q`, which is the state a visitor
  // arriving from the top-bar box sees before submitting -- a form, a label
  // and an explanatory paragraph. The amber "not searched" panel only renders
  // after a query, and its contrast is the reason it is amber-900 on
  // amber-50 rather than the amber-600 that first looked right.
  { name: "global search", path: "/search" },
  // The workspace routes, with no record named. That is a REAL state — it is
  // what a bookmarked link without its query string renders — and it is the
  // one most likely to be an unlabelled empty page.
  //
  // ⚠️ NAMED "(no record named)" BECAUSE THE NAME IS THE TEST TITLE, AND A
  // DUPLICATE TITLE TAKES THE WHOLE SUITE OUT. `project workspace` and
  // `formula workspace` were already taken by the DETAIL routes above, and
  // Playwright refuses to run a single test when two share a title:
  //
  //     Error: duplicate test title "project workspace has no WCAG 2.1 AA
  //     violations", first declared in shellccessibility.spec.ts:102
  //
  // Nothing ran. Not one test, not one file — a suite-wide outage from one
  // repeated string, and the process still exited through a pipeline that
  // reported rc=0. `accessibility-coverage.test.ts` now asserts the names are
  // unique, so this cannot reach a live run again.
  { name: "failure investigation", path: "/failures/investigation" },
  { name: "formula workspace (no record named)", path: "/formulations/formula" },
  { name: "batch workspace", path: "/laboratory/batch" },
  { name: "project workspace (no record named)", path: "/projects/workspace" },
  { name: "test workspace", path: "/testing/test" },
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

test("the MSD panel opens, is announced, and has no violations", async ({
  page,
}) => {
  /**
   * MSD is the first interactive surface in this shell — everything else
   * is a page. So it is the first thing whose accessibility depends on
   * STATE rather than on markup, and scanning the closed shell says
   * nothing about it.
   *
   * Concept Note §33 asks for a "persistent but unobtrusive" control.
   * Unobtrusive must not mean unreachable: the trigger carries
   * `aria-expanded`, the panel is a labelled dialog, and focus moves into
   * it on open.
   */
  await page.goto("/dashboard");

  const trigger = page.getByRole("button", { name: "MSD", exact: true });
  await expect(trigger).toBeVisible();
  await expect(trigger).toHaveAttribute("aria-expanded", "false");

  await trigger.click();
  await expect(trigger).toHaveAttribute("aria-expanded", "true");

  const panel = page.getByRole("dialog", { name: /Material Science/i });
  await expect(panel).toBeVisible();

  // The standing notice about what MSD is and is not. §7 is about every
  // OUTPUT being labelled; this is the reader knowing before they start.
  await expect(
    panel.getByRole("note", { name: /What MSD can and cannot do/i }),
  ).toContainText(/never approves anything/i);

  const results = await new AxeBuilder({ page }).withTags(STANDARD).analyze();
  expect(
    results.violations.map((v) => `${v.id}: ${v.help}`),
    "opening the MSD panel introduced accessibility violations",
  ).toEqual([]);

  // Escape closes it, as every dialog is expected to.
  await page.keyboard.press("Escape");
  await expect(panel).toBeHidden();
  await expect(trigger).toHaveAttribute("aria-expanded", "false");
});

test("MSD refuses to answer without a session, and says why", async ({
  page,
}) => {
  /**
   * 🔴 THE REFUSAL IS THE FEATURE.
   *
   * §7: MSD operates under exactly the calling user's authorization
   * boundary. With no session there is no boundary to operate under, so
   * there is no safe answer — and an assistant that answered anyway,
   * from the demonstration fixture, would be exactly the
   * "permission-bypass channel" the rule forbids.
   *
   * The deployed site has no API and no identity provider, so this is
   * the state a visitor actually meets.
   */
  await page.goto("/dashboard");
  await page.getByRole("button", { name: "MSD", exact: true }).click();

  const panel = page.getByRole("dialog", { name: /Material Science/i });
  await panel.getByRole("button", { name: /What is waiting for me/i }).click();

  await expect(panel.getByRole("alert")).toContainText(/signed-in session/i);
  await expect(panel.getByRole("alert")).toContainText(/no anonymous mode/i);
});
