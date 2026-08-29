import { expect, test, type Page } from "@playwright/test";

/**
 * The create forms, driven the way a person drives them.
 *
 * 🔴 A FORM THAT RENDERS IS NOT A FORM THAT WORKS.
 *
 * `typecheck` proves the props line up and vitest proves the client parses a
 * response. Neither presses the button. This project has shipped a control that
 * 422'd on every use (`document` offered with no picker), a route with a client
 * function and no caller, and a whole dashboard that rendered nothing — none of
 * which any green suite noticed, because each was correct at the layer its
 * tests looked at.
 *
 * So these SUBMIT, against the real API, and assert the record came back.
 *
 * ⚠️ THEY SKIP WITHOUT CREDENTIALS, which is honest rather than hidden: the
 * `shell` project in CI has no session, every `LiveOnlyPage` renders its notice
 * instead of content, and a form cannot be pressed. `live-suite.sh` exports
 * `TEST_KEYCLOAK_PASSWORD`, so live is where these run — and a skip there is a
 * gap to chase, not a pass.
 *
 * 🔴 EVERY RECORD IS SUFFIXED WITH A RUN ID. These COMMIT, against the
 * demonstration tenant, and a fixed code would collide on the second run and
 * report a unique-constraint refusal as a broken form.
 */

const PASSWORD = process.env.TEST_KEYCLOAK_PASSWORD ?? "";
const USERNAME = process.env.TEST_SIGNIN_USER ?? "lead.demo";

/**
 * 🔴 THE FORM YOU ARE TESTING DECIDES WHO SIGNS IN, AND THIS FILE GOT THAT
 * WRONG FOR THREE OF ITS SIX TESTS.
 *
 * Every test signed in as `lead.demo` and the file said so nowhere. Measured
 * against the seeded realm on 2026-08-29, `product_development_lead` holds
 * `project.create` and `project.edit` and does NOT hold `material.create`
 * (procurement and the chemist do) or `test.plan` (the engineer does). So the
 * material tests clicked a "New material" button that is correctly absent, and
 * the plan-a-test one clicked a form that is correctly not offered — three
 * failures against a product that was behaving exactly as designed.
 *
 * One of them even carried the comment *"`lead.demo` HOLDS `material.create`,
 * so the control is here"*, which was simply false. A comment asserting a rule
 * that does not exist, in a test written to catch exactly that class of thing.
 *
 * `scripts/keycloak-bootstrap.sh` seeds ONE USER PER ROLE against a single
 * `KC_USER_PASSWORD`, so the fix is to name the holder rather than to weaken
 * the assertion.
 */
const AS = {
  /** `project.create`, `project.edit`. */
  lead: "lead.demo",
  /** `material.create`. So does `proc.demo`. */
  chemist: "chem.demo",
  /** `test.plan`, and only this role. */
  engineer: "eng.demo",
} as const;
const USERNAME_FIELD = "#username, input[name='username']";
const PASSWORD_FIELD = "#password, input[name='password']";

/** Short, and unique per run. */
function runId(): string {
  return Math.random().toString(36).slice(2, 8).toUpperCase();
}

async function signIn(page: Page, as: string = USERNAME): Promise<void> {
  await page.goto("/");
  const signInButton = page.getByRole("button", { name: "Sign in" });
  await expect(signInButton).toBeVisible({ timeout: 30_000 });
  await signInButton.click();
  await page.locator(USERNAME_FIELD).fill(as, { timeout: 60_000 });
  await page.locator(PASSWORD_FIELD).fill(PASSWORD);
  await page.locator(PASSWORD_FIELD).press("Enter");
  await expect(page.getByRole("button", { name: "Sign in" })).toBeHidden({ timeout: 60_000 });
  await expect(page.getByLabel("Active organization")).toBeVisible({ timeout: 30_000 });
}

/**
 * Reach a page by CLICKING the sidebar, never `page.goto`.
 *
 * 🔴 A FULL NAVIGATION DROPS THE CLIENT-SIDE SESSION, and the screen then
 * renders its "no API" notice — which reads as a missing control and cost two
 * rewrites of the research spec before it was understood.
 */
async function openFromSidebar(page: Page, linkName: string, urlPattern: RegExp) {
  await page.getByRole("link", { name: linkName, exact: true }).click();
  await expect(page).toHaveURL(urlPattern);
}

test.describe("the create forms actually create", () => {
  test("create: a material can be created from the materials page", async ({ page }) => {
    test.skip(PASSWORD === "", "TEST_KEYCLOAK_PASSWORD is not set — NOT verified");
    const id = runId();
    // The chemist, not the lead: `material.create` is held by the chemist and
    // procurement. See `AS`.
    await signIn(page, AS.chemist);
    await openFromSidebar(page, "Materials", /\/materials/);

    await page.getByRole("button", { name: "New material" }).click();
    await page.getByLabel("Material code").fill(`E2E-${id}`);
    await page.getByLabel("Name", { exact: true }).fill(`End-to-end resin ${id}`);
    await page.getByLabel("Category").fill("Resin");
    await page.getByLabel("Density (g/cm³)").fill("1.0900");
    await page.getByRole("button", { name: "Create material" }).click();

    // 🔴 THE SERVER'S OWN CODE COMES BACK. Asserting only that no error
    // appeared would pass against a form that silently did nothing.
    await expect(page.getByRole("status")).toContainText(`E2E-${id} created`, {
      timeout: 30_000,
    });
  });

  test("create: a project can be created and says which confidentiality it has", async ({
    page,
  }) => {
    test.skip(PASSWORD === "", "TEST_KEYCLOAK_PASSWORD is not set — NOT verified");
    const id = runId();
    await signIn(page);
    await openFromSidebar(page, "Projects", /\/projects/);

    await page.getByRole("button", { name: "New project" }).click();
    await page.getByLabel("Project code").fill(`E2E-P-${id}`);
    await page.getByLabel("Name", { exact: true }).fill(`End-to-end project ${id}`);
    // The consequence of `restricted` must be on the screen, not folded away.
    await expect(page.getByText(/visible only to its members/i)).toBeVisible();
    await page.getByRole("button", { name: "Create project" }).click();

    await expect(page.getByRole("status")).toContainText(`E2E-P-${id} created`, {
      timeout: 30_000,
    });
  });

  test("create: raising a task reports that it was raised", async ({ page }) => {
    test.skip(PASSWORD === "", "TEST_KEYCLOAK_PASSWORD is not set — NOT verified");
    const id = runId();
    await signIn(page);
    await openFromSidebar(page, "My Work", /\/my-work/);

    await page.getByRole("button", { name: "Raise a task" }).click();
    await page.getByLabel("Title").fill(`End-to-end task ${id}`);
    // 🔴 A TASK NEEDS AN OWNER, AND THIS TEST PROVED THE FORM COULD NOT GIVE IT
    // ONE. `create_task` refuses a task with neither an assigned user nor an
    // assigned role, and the form carried no assignee control at all — so it
    // returned 409 on every press and this assertion never saw a status. The
    // control exists now, and choosing from it is part of the flow.
    await page.getByLabel("Assign to").selectOption("laboratory_technician");
    await page.getByRole("button", { name: "Raise task" }).click();

    await expect(page.getByRole("status")).toContainText("Task raised", { timeout: 30_000 });
  });

  test("create: the test form will not let a sample be chosen before a batch", async ({
    page,
  }) => {
    test.skip(PASSWORD === "", "TEST_KEYCLOAK_PASSWORD is not set — NOT verified");
    // `test.plan` belongs to the engineer alone. See `AS`.
    await signIn(page, AS.engineer);
    await openFromSidebar(page, "Testing", /\/testing/);

    await page.getByRole("button", { name: "Plan a test" }).click();
    // 🔴 THE ORDER IS THE POINT. §2 runs Batch → Sample → Test, and the sample
    // select is disabled until a batch is chosen — with a label that SAYS so
    // rather than presenting an empty dropdown that looks broken.
    const sample = page.getByLabel("Sample");
    await expect(sample).toBeDisabled();
    await expect(sample).toContainText("Choose a batch first");
  });

  test("create: a form the caller cannot submit says so instead of appearing", async ({
    page,
  }) => {
    test.skip(PASSWORD === "", "TEST_KEYCLOAK_PASSWORD is not set — NOT verified");
    // 🔴 BOTH DIRECTIONS, AND THIS TEST ASSERTED THE WRONG ONE.
    //
    // It signed in as `lead.demo` and asserted the "New material" control was
    // ENABLED, on a stated premise — "`lead.demo` HOLDS `material.create`" —
    // that is false. So it failed against a product doing the right thing, and
    // in the direction that matters least: asserting only that a control
    // APPEARS would pass against a screen that offers everything to everyone,
    // which is the defect twelve controls on this application had last week.
    //
    // The holder sees it; the non-holder does not. Either alone is satisfiable
    // by a component that ignores permissions entirely.
    await signIn(page, AS.chemist);
    await openFromSidebar(page, "Materials", /\/materials/);
    await expect(page.getByRole("button", { name: "New material" })).toBeEnabled();
  });

  test("create: the same form is refused to a caller who does not hold it", async ({
    page,
  }) => {
    test.skip(PASSWORD === "", "TEST_KEYCLOAK_PASSWORD is not set — NOT verified");
    // `product_development_lead` does not hold `material.create`. The control
    // must be absent, and the screen must SAY so rather than simply omitting it
    // — a missing button and a broken page look identical.
    await signIn(page, AS.lead);
    await openFromSidebar(page, "Materials", /\/materials/);

    await expect(page.getByRole("button", { name: "New material" })).toHaveCount(0);
    // The exact sentence `CreateForm` renders, not a guess at it. Written from
    // the component rather than from memory -- the first attempt asserted "do
    // not have permission" and the screen says "do not hold".
    await expect(
      page.getByText(/which your roles do not hold/i).first(),
    ).toBeVisible({ timeout: 30_000 });
  });
});
