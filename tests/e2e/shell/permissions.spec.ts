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
