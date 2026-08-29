import { expect, test, type Page } from "@playwright/test";

/**
 * The Research Center in a real browser, SIGNED IN.
 *
 * 🔴 WHAT THIS PROVES THAT THE PYTHON SUITE CANNOT.
 *
 * `tests/auth/test_research_routes.py` drives all 26 routes and asserts what a
 * client receives. It cannot tell you whether a PERSON can reach any of them.
 * This project has counted twenty-five instances of the same defect wearing
 * three hats — a route with no caller, a permission with no enforcement point,
 * a table with no writer — and the lesson written down after the last one is
 * blunt: **a client function is not a caller. A route is reachable when a
 * person can press something.**
 *
 * 🔴 AND THE FIRST TWO VERSIONS OF THIS FILE MEASURED NOTHING.
 *
 * Version one asserted the forms unconditionally, and CI failed on four tests
 * that were describing the wrong environment: the `shell` project runs against
 * a build with no session, and every `LiveOnlyPage` then renders a notice
 * instead of its content, because it refuses to invent data.
 *
 * Version two made those four SKIP when the notice was present. They skipped in
 * CI — and then skipped **on the live site too**, because a production build
 * compiles out the session seam the E2E suite otherwise uses. Four assertions
 * that could never run anywhere: *a gate on an unused path is decoration*, and
 * the live suite's own report said so — `1020 passed / 0 failed / 4 skipped`,
 * with the note "a skip is not a pass".
 *
 * So they now SIGN IN, through the real identity provider, exactly as
 * `sign-in.spec.ts` does. They skip only where there are no credentials, which
 * is an honest "not measurable here" rather than a hidden hole, and the live
 * suite exports `TEST_KEYCLOAK_PASSWORD` so live is where they run.
 *
 * ⚠️ EVERY TITLE HERE IS UNIQUE ACROSS THE WHOLE SUITE. A duplicate Playwright
 * test title makes the runner refuse the ENTIRE run — not one test, all of them
 * — and it is not a failure, so nothing in the output looks red. On 2026-08-27
 * that produced a live suite reporting exit 0 having executed nothing.
 *
 * 🔴 THE PASSWORD IS NEVER HARD-CODED. This repository is public.
 */

const PASSWORD = process.env.TEST_KEYCLOAK_PASSWORD ?? "";
const USERNAME = process.env.TEST_SIGNIN_USER ?? "lead.demo";

/** The realm's own login form, whatever theme it is wearing. */
const USERNAME_FIELD = "#username, input[name='username']";
const PASSWORD_FIELD = "#password, input[name='password']";

/**
 * Sign in for real, then land on the Research Center.
 *
 * Deliberately a copy of `sign-in.spec.ts`'s steps rather than an import: that
 * file's test IS the assertion that the round trip works, and a shared helper
 * would let a change there silently redefine what this file measures. Here the
 * sign-in is a PRECONDITION — if it breaks, `sign-in.spec.ts` is the test that
 * should name it.
 */
async function signInAndOpenResearch(page: Page): Promise<void> {
  await page.goto("/");
  const signIn = page.getByRole("button", { name: "Sign in" });
  await expect(signIn).toBeVisible({ timeout: 30_000 });
  await signIn.click();

  await page.locator(USERNAME_FIELD).fill(USERNAME, { timeout: 60_000 });
  await page.locator(PASSWORD_FIELD).fill(PASSWORD);
  await page.locator(PASSWORD_FIELD).press("Enter");

  await expect(page.getByRole("button", { name: "Sign in" })).toBeHidden({
    timeout: 60_000,
  });
  // 🔴 AND THE ORGANIZATION MUST HAVE RESOLVED. `useCredentials` reports
  // "unavailable" until `session.status === "authenticated"`, so asserting only
  // that the Sign in button vanished lands on the page mid-exchange.
  await expect(page.getByLabel("Active organization")).toBeVisible({ timeout: 30_000 });

  // 🔴 CLICK THE LINK; DO NOT `page.goto`. A full navigation drops the
  // client-side session and the screen renders its "no API" notice again --
  // which is exactly how the previous version of this helper failed, with a
  // message blaming the bundle for something the test itself had done. This is
  // also the path a person takes.
  await page.getByRole("link", { name: "Research Center", exact: true }).click();
  await expect(page).toHaveURL(/\/material-safety\/research/);

  // 🔴 AND THE PAGE MUST NOT BE SHOWING ITS "no data" NOTICE. Without this the
  // assertions below would fail with "element not found", which reads like a
  // missing control rather than a missing session — the diagnosis that cost
  // this file two rewrites.
  await expect(
    page.getByText(/No research data can be shown until this build is pointed at an API/i),
    "signed in, but the Research Center still reports no API — the session did " +
      "not reach the client, or the bundle carries the wrong API base",
  ).toHaveCount(0);
}

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

  test("research: signed in, opening a workspace is a control a person can press", async ({
    page,
  }) => {
    test.skip(PASSWORD === "", "TEST_KEYCLOAK_PASSWORD is not set — NOT verified");
    await signInAndOpenResearch(page);
    await expect(
      page.getByRole("heading", { name: "Open a research workspace" }),
    ).toBeVisible();
    await expect(page.getByRole("button", { name: "Open workspace" })).toBeVisible();
    await expect(page.getByLabel("Research question")).toBeVisible();
  });

  test("research: signed in, the organization-wide option is offered and explained", async ({
    page,
  }) => {
    test.skip(PASSWORD === "", "TEST_KEYCLOAK_PASSWORD is not set — NOT verified");
    await signInAndOpenResearch(page);
    // §1.2 makes `project_id` nullable deliberately, and the screen has to say
    // what the empty option MEANS — "— none —" would read as "not chosen".
    await expect(
      page.getByRole("option", { name: "Organization-wide (no project)" }),
    ).toBeAttached();
    await expect(page.getByText(/cannot be sent for\s+approval/i)).toBeVisible();
  });

  test("research: signed in, both registers are on the page, not behind a second click", async ({
    page,
  }) => {
    test.skip(PASSWORD === "", "TEST_KEYCLOAK_PASSWORD is not set — NOT verified");
    await signInAndOpenResearch(page);
    await expect(page.getByRole("heading", { name: "Findings register" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Experiment proposals" })).toBeVisible();
  });

  test("research: signed in, the register says approval happens in the approval engine", async ({
    page,
  }) => {
    test.skip(PASSWORD === "", "TEST_KEYCLOAK_PASSWORD is not set — NOT verified");
    await signInAndOpenResearch(page);
    // 🔴 THERE IS NO APPROVE BUTTON HERE, AND THAT IS THE DESIGN. A second
    // approve control would be a second notion of "signed off", which
    // CLAUDE.md §12 forbids. Asserting its ABSENCE is what stops somebody
    // adding one for convenience.
    await expect(page.getByText(/approval happens in Approvals/i)).toBeVisible();
    await expect(page.getByRole("button", { name: /^Approve finding$/ })).toHaveCount(0);
  });
});
