import { expect, test } from "@playwright/test";

/**
 * The Research Center in a real browser.
 *
 * 🔴 WHAT THIS PROVES THAT THE PYTHON SUITE CANNOT.
 *
 * `tests/auth/test_research_routes.py` drives all 25 routes and asserts what a
 * client receives. It cannot tell you whether a PERSON can reach any of them.
 * This project has counted twenty-five instances of the same defect wearing
 * three hats — a route with no caller, a permission with no enforcement point,
 * a table with no writer — and the lesson written down after the last one is
 * blunt: **a client function is not a caller. A route is reachable when a
 * person can press something.**
 *
 * So this asserts controls, not requests.
 *
 * ⚠️ EVERY TITLE HERE IS UNIQUE ACROSS THE WHOLE SUITE. A duplicate Playwright
 * test title makes the runner refuse the ENTIRE run — not one test, all of them
 * — and it is not a failure, so nothing in the output looks red. On 2026-08-27
 * that produced a live suite reporting exit 0 having executed nothing.
 */

test.describe("the Research Center is reachable and pressable", () => {
  test("research: the sidebar reaches the Research Center", async ({ page }) => {
    await page.goto("/dashboard/");
    const link = page.getByRole("link", { name: "Research Center", exact: true });
    await expect(link).toBeVisible();
    await link.click();
    await expect(page).toHaveURL(/\/material-safety\/research/);
  });

  test("research: the page names itself and says what it will not invent", async ({
    page,
  }) => {
    await page.goto("/material-safety/research/");
    await expect(
      page.getByRole("heading", { name: "Research Center", level: 1 }),
    ).toBeVisible();
    // The live-only notice, in this screen's OWN words. It was hardcoded once
    // and rendered a paragraph about physical test results on the Knowledge
    // Library — found by reading the page, not by any test.
    await expect(page.getByText(/research findings and experiment proposals/i)).toBeVisible();
  });

  test("research: opening a workspace is a control a person can press", async ({ page }) => {
    await page.goto("/material-safety/research/");
    await expect(
      page.getByRole("heading", { name: "Open a research workspace" }),
    ).toBeVisible();
    await expect(page.getByRole("button", { name: "Open workspace" })).toBeVisible();
    await expect(page.getByLabel("Research question")).toBeVisible();
  });

  test("research: the organization-wide option is offered and explained", async ({ page }) => {
    await page.goto("/material-safety/research/");
    // §1.2 makes `project_id` nullable deliberately, and the screen has to say
    // what the empty option MEANS — "— none —" would read as "not chosen".
    await expect(
      page.getByRole("option", { name: "Organization-wide (no project)" }),
    ).toBeAttached();
    await expect(
      page.getByText(/cannot be sent for\s+approval/i),
    ).toBeVisible();
  });

  test("research: both registers are on the page, not behind a second click", async ({
    page,
  }) => {
    await page.goto("/material-safety/research/");
    await expect(
      page.getByRole("heading", { name: "Findings register" }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Experiment proposals" }),
    ).toBeVisible();
  });

  test("research: the register says approval happens in the approval engine", async ({
    page,
  }) => {
    await page.goto("/material-safety/research/");
    // 🔴 THERE IS NO APPROVE BUTTON HERE, AND THAT IS THE DESIGN. A second
    // approve control would be a second notion of "signed off", which
    // CLAUDE.md §12 forbids. Asserting its ABSENCE is what stops somebody
    // adding one for convenience.
    await expect(page.getByText(/approval happens in Approvals/i)).toBeVisible();
    await expect(
      page.getByRole("button", { name: /^Approve finding$/ }),
    ).toHaveCount(0);
  });
});
