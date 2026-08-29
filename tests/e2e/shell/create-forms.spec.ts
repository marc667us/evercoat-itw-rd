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
const USERNAME_FIELD = "#username, input[name='username']";
const PASSWORD_FIELD = "#password, input[name='password']";

/** Short, and unique per run. */
function runId(): string {
  return Math.random().toString(36).slice(2, 8).toUpperCase();
}

async function signIn(page: Page): Promise<void> {
  await page.goto("/");
  const signInButton = page.getByRole("button", { name: "Sign in" });
  await expect(signInButton).toBeVisible({ timeout: 30_000 });
  await signInButton.click();
  await page.locator(USERNAME_FIELD).fill(USERNAME, { timeout: 60_000 });
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
    await signIn(page);
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
    await page.getByRole("button", { name: "Raise task" }).click();

    await expect(page.getByRole("status")).toContainText("Task raised", { timeout: 30_000 });
  });

  test("create: the test form will not let a sample be chosen before a batch", async ({
    page,
  }) => {
    test.skip(PASSWORD === "", "TEST_KEYCLOAK_PASSWORD is not set — NOT verified");
    await signIn(page);
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
    await signIn(page);
    await openFromSidebar(page, "Materials", /\/materials/);

    // `lead.demo` HOLDS `material.create`, so the control is here. This asserts
    // the shell renders the openable form rather than the refusal — the other
    // direction is covered by the permission tests, and asserting only the
    // refusal would pass against a component that never renders a form at all.
    await expect(page.getByRole("button", { name: "New material" })).toBeEnabled();
  });
});
