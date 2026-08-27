/**
 * I79 — the sidebar offers only what the signed-in caller may actually use.
 *
 * 🔴 WHY THIS EXISTS WHEN THREE OTHER LAYERS ARE ALREADY TESTED.
 *
 * Migration 045 is verified against the database, `/api/me` is verified with a
 * real token, and `effectiveNavPermissions` is unit-tested in isolation. Every
 * layer is proven and the COMPOSITION was not — which is precisely the shape
 * this project keeps being caught by. On 2026-08-24 the live suite read
 * 713 / 0 / 0 while browser sign-in returned 404, because every test drove a
 * path no human uses.
 *
 * So this drives the real one: a laboratory technician signs in through the
 * real identity provider and looks at the menu they are offered.
 *
 * 🔴 IT ASSERTS BOTH DIRECTIONS, AND THE SECOND IS THE IMPORTANT ONE.
 *
 * "Administration is absent" passes just as happily when the sidebar is empty,
 * when the session failed, or when navigation is broken outright. So it also
 * asserts that Laboratory IS offered. `tech.demo` holds `batch.view` (which
 * Laboratory requires) and not `admin.users` (which Administration requires),
 * measured against the seeded realm on 2026-08-25: 11 permissions, against 38
 * for `lead.demo`.
 *
 * A test that can only ever prove absence is a test that a broken feature
 * passes.
 *
 * 🔴 THE PASSWORD IS NEVER HARD-CODED. This repository is public.
 */

import { expect, test } from "@playwright/test";

const PASSWORD = process.env.TEST_KEYCLOAK_PASSWORD ?? "";

/**
 * Deliberately NOT `TEST_SIGNIN_USER`. That variable selects who drives the
 * sign-in round trip and defaults to `lead.demo`, who holds 38 permissions
 * and would see very nearly the whole menu either way — so this test would
 * pass against the unfixed code. The point of this file is a caller whose
 * permissions differ visibly from the full map.
 */
const TECHNICIAN = process.env.TEST_RESTRICTED_USER ?? "tech.demo";

const USERNAME_FIELD = "#username, input[name='username']";
const PASSWORD_FIELD = "#password, input[name='password']";

test.describe("the sidebar reflects the caller's permissions", () => {
  test("a laboratory technician is not offered Administration", async ({
    page,
  }) => {
    test.skip(
      PASSWORD === "",
      "TEST_KEYCLOAK_PASSWORD is not set — permission gating was NOT verified",
    );

    await page.goto("/");

    const signIn = page.getByRole("button", { name: "Sign in" });
    await expect(
      signIn,
      "no Sign in button — the deployment may have no identity provider compiled in",
    ).toBeVisible();
    await signIn.click();

    await page.waitForURL(/\/realms\/[^/]+\/protocol\/openid-connect\/auth/, {
      timeout: 60_000,
    });
    await expect(
      page.locator(USERNAME_FIELD),
      "no username field — the realm most likely rejected redirect_uri",
    ).toBeVisible({ timeout: 30_000 });

    await page.locator(USERNAME_FIELD).fill(TECHNICIAN);
    await page.locator(PASSWORD_FIELD).fill(PASSWORD);
    await page.locator(PASSWORD_FIELD).press("Enter");

    await page.waitForURL(
      (url) => !/\/realms\/|\/protocol\/openid-connect\//.test(url.pathname),
      { timeout: 60_000 },
    );

    // The session must actually exist before the menu means anything. An
    // anonymous shell legitimately shows the FULL map (that fallback is
    // deliberate — an empty set there makes real pages unreachable), so
    // asserting the menu without first proving a session would be asserting
    // against the wrong branch entirely.
    await expect(
      page.getByLabel("Active organization"),
      "no organization switcher — not signed in, so the sidebar below is the " +
        "anonymous fallback and this test would be measuring nothing",
    ).toBeVisible({ timeout: 60_000 });

    const sidebar = page.getByRole("navigation");

    // 🔴 THE POSITIVE HALF FIRST, so a broken or empty sidebar fails loudly
    // rather than passing the absence check below.
    await expect(
      sidebar.getByRole("link", { name: "Laboratory" }),
      "Laboratory is missing for a technician who holds batch.view — the " +
        "sidebar is filtering on an EMPTY permission set, not on theirs",
    ).toBeVisible({ timeout: 30_000 });

    // And the half that fails against the unfixed code, where every caller
    // was handed ALL_NAV_PERMISSIONS.
    await expect(
      sidebar.getByRole("link", { name: "Administration" }),
      "Administration is offered to a laboratory technician who does not hold " +
        "admin.users — /api/me's permissions are not reaching the sidebar (I79)",
    ).toHaveCount(0);
  });
});

/**
 * The SECOND level — a control inside a page, not a destination in the menu.
 *
 * 🔴 WHY THE SIDEBAR TEST ABOVE WAS NOT ENOUGH.
 *
 * I79 gave the sidebar the caller's permissions on 2026-08-25 and nothing
 * else. Three screens went on offering every control to every role, each with
 * a comment stating the reason: *"`/api/me` returns roles, not permissions."*
 * That reason had expired two days before those words were last true, and the
 * comment kept the screens frozen in the shape it had chosen. So the sidebar
 * was role-scoped and the workspace inside it was not.
 *
 * The knowledge library is the cleanest place to measure that in a browser:
 * `chem.demo` and `lead.demo` BOTH hold `knowledge.view`, so both reach the
 * page and see the same library, and only `lead.demo` holds
 * `knowledge.ingest`. Measured against the deployed demo on 2026-08-27 —
 * `chem.demo` holds `knowledge.promote` and NOT `knowledge.ingest`, so before
 * this change a Chemist was offered a form that could only ever answer 403.
 *
 * 🔴 BOTH DIRECTIONS, IN TWO TESTS. "The Chemist is not offered the form"
 * passes when the page fails to load, when the session dies, and when the
 * filter hides everything from everybody. The second test is what makes the
 * first one mean something.
 */

const CHEMIST = process.env.TEST_CHEMIST_USER ?? "chem.demo";
const LEAD = process.env.TEST_SIGNIN_USER ?? "lead.demo";

/** The ingest control, by its accessible name. */
const INGEST_CONTROL = "Add technical text to the library";

async function signIn(page: import("@playwright/test").Page, username: string) {
  await page.goto("/");

  const signInButton = page.getByRole("button", { name: "Sign in" });
  await expect(
    signInButton,
    "no Sign in button — the deployment may have no identity provider compiled in",
  ).toBeVisible();
  await signInButton.click();

  await page.waitForURL(/\/realms\/[^/]+\/protocol\/openid-connect\/auth/, {
    timeout: 60_000,
  });
  await expect(
    page.locator(USERNAME_FIELD),
    "no username field — the realm most likely rejected redirect_uri",
  ).toBeVisible({ timeout: 30_000 });

  await page.locator(USERNAME_FIELD).fill(username);
  await page.locator(PASSWORD_FIELD).fill(PASSWORD);
  await page.locator(PASSWORD_FIELD).press("Enter");

  await page.waitForURL(
    (url) => !/\/realms\/|\/protocol\/openid-connect\//.test(url.pathname),
    { timeout: 60_000 },
  );

  // 🔴 THE SESSION MUST EXIST BEFORE ANY OF THIS MEANS ANYTHING. An anonymous
  // shell falls back to the module map deliberately, so an assertion made
  // before the switcher appears is an assertion against the wrong branch.
  await expect(
    page.getByLabel("Active organization"),
    `no organization switcher — ${username} is not signed in, so what follows ` +
      "would be measuring the anonymous fallback",
  ).toBeVisible({ timeout: 60_000 });
}

test.describe("a control inside a page is gated too, not just the menu", () => {
  test("a Chemist is not offered the knowledge ingest form", async ({ page }) => {
    test.skip(
      PASSWORD === "",
      "TEST_KEYCLOAK_PASSWORD is not set — permission gating was NOT verified",
    );

    await signIn(page, CHEMIST);
    await page.goto("/knowledge/");

    // 🔴 THE POSITIVE HALF FIRST. `chem.demo` holds `knowledge.view`, so the
    // library itself must be there. Without this, a page that failed to render
    // at all would satisfy the assertion below.
    await expect(
      page.getByRole("heading", { name: "Knowledge library", level: 1 }),
      "the Knowledge Library did not render for a Chemist who holds " +
        "knowledge.view — the page is broken, not gated",
    ).toBeVisible({ timeout: 30_000 });

    await expect(
      page.getByRole("button", { name: INGEST_CONTROL }),
      "the ingest form is offered to a Chemist who does not hold " +
        "knowledge.ingest — the control can only ever answer 403",
    ).toHaveCount(0);
  });

  test("a Lead IS offered the knowledge ingest form", async ({ page }) => {
    test.skip(
      PASSWORD === "",
      "TEST_KEYCLOAK_PASSWORD is not set — permission gating was NOT verified",
    );

    await signIn(page, LEAD);
    await page.goto("/knowledge/");

    await expect(
      page.getByRole("button", { name: INGEST_CONTROL }),
      "the ingest form is HIDDEN from a Lead who holds knowledge.ingest — the " +
        "gate is filtering on an empty set, which hides the control from " +
        "everybody and would make the Chemist test above pass for the wrong reason",
    ).toBeVisible({ timeout: 30_000 });
  });
});
