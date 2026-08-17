import { expect, test } from "@playwright/test";

/**
 * The application shell, in a real browser.
 *
 * Everything asserted here was previously only asserted by reading code
 * or by unit-testing a pure function. `TODO.md` carried "no human has yet
 * *seen* the full sidebar" as an open item; these are the assertions that
 * close it without a human having to look every time.
 *
 * The navigation gating is the substantive part. `lib/navigation.ts` sets
 * `CURRENT_SLICE = 1`, and `app/layout.tsx` passes a DELIBERATELY EMPTY
 * permission set — deliberately empty rather than permissive, because a
 * shell that shows everything by default makes the RBAC filter look like
 * it works when it has never been exercised.
 *
 * Two different mechanisms therefore hide two different things, and
 * conflating them is easy:
 *
 *   permission filter  removes an item ENTIRELY (it is not in the DOM)
 *   slice gating       renders it INERT — present, visible, not a link
 *
 * The second is the one that matters for a shipped product: an unbuilt
 * destination must not be clickable, because a dead link in the shell
 * reads as a broken product rather than as an unfinished slice.
 */

test.describe("application shell", () => {
  test("the root path redirects into the dashboard", async ({ page }) => {
    // Asserted in a browser because `redirect()` in a server component is
    // not something reading the file proves — it proves the intent.
    await page.goto("/");
    await expect(page).toHaveURL(/\/dashboard$/);
    await expect(page.getByRole("heading", { name: "Dashboard", level: 1 })).toBeVisible();
  });

  test("the shell renders its landmarks", async ({ page }) => {
    await page.goto("/dashboard");

    await expect(page.getByRole("navigation", { name: "Main navigation" })).toBeVisible();
    await expect(page.getByRole("main")).toBeVisible();
    await expect(page.getByText("EvercoatITWRD", { exact: true })).toBeVisible();
  });

  test("the document title carries the product name", async ({ page }) => {
    // The identity strings in CLAUDE.md §1 are fixed. "ITERDRD" and any
    // generic R&D name are explicitly forbidden, so this is a contract,
    // not cosmetics.
    await page.goto("/dashboard");
    await expect(page).toHaveTitle(/EvercoatITWRD APP/);
    await expect(page).not.toHaveTitle(/ITERDRD/i);
  });

  test("the dashboard shows no fabricated figures", async ({ page }) => {
    // Rule 3 of the seven non-negotiables: predictions must never render
    // as confirmed results. A placeholder dashboard of invented KPIs is
    // the same failure in a smaller costume — indistinguishable from a
    // working one at a glance.
    await page.goto("/dashboard");
    await expect(page.getByText(/No data yet/i)).toBeVisible();
  });
});

test.describe("navigation gating", () => {
  test("an unbuilt destination is inert, not a dead link", async ({ page }) => {
    await page.goto("/dashboard");
    const nav = page.getByRole("navigation", { name: "Main navigation" });

    // "My Work" is slice 2. Its API exists; its page does not. It must be
    // present (so the structure is legible) and NOT navigable (so it
    // cannot 404).
    const myWork = nav.getByText("My Work", { exact: true });
    await expect(myWork).toBeVisible();

    const inert = nav.locator('[aria-disabled="true"]', { hasText: "My Work" });
    await expect(inert).toHaveCount(1);

    // The decisive assertion: no anchor points at it.
    await expect(nav.locator('a[href="/my-work"]')).toHaveCount(0);
  });

  test("every unbuilt item is inert and every built item is a link", async ({ page }) => {
    await page.goto("/dashboard");
    const nav = page.getByRole("navigation", { name: "Main navigation" });

    // Whatever the shell renders, the invariant is absolute: an anchor in
    // the sidebar must never be disabled, and a disabled entry must never
    // be an anchor. Written as a property over the rendered DOM rather
    // than a fixed list, so it keeps holding as CURRENT_SLICE advances.
    const anchors = nav.locator("a");
    const anchorCount = await anchors.count();
    expect(anchorCount).toBeGreaterThan(0);

    for (let i = 0; i < anchorCount; i += 1) {
      const anchor = anchors.nth(i);
      await expect(anchor).not.toHaveAttribute("aria-disabled", "true");
      const href = await anchor.getAttribute("href");
      expect(href, "a sidebar anchor with no href is a dead control").toBeTruthy();
    }

    const disabled = nav.locator('[aria-disabled="true"]');
    for (let i = 0; i < (await disabled.count()); i += 1) {
      await expect(disabled.nth(i)).toHaveJSProperty("tagName", "SPAN");
    }
  });

  test("a permission-gated item is absent entirely, not merely disabled", async ({ page }) => {
    await page.goto("/dashboard");
    const nav = page.getByRole("navigation", { name: "Main navigation" });

    // Administration requires `admin.users`. The layout supplies no
    // permissions, so it must be filtered out of the DOM completely —
    // this is the filter behaving correctly, NOT a missing feature.
    //
    // Recorded explicitly because `/admin` DOES exist and is reachable by
    // URL: if this ever starts failing because the item appeared, the
    // question to ask is whether real permissions were wired in (fine) or
    // whether the filter was made permissive (not fine).
    await expect(nav.getByText("Administration", { exact: true })).toHaveCount(0);
    await expect(nav.locator('a[href="/admin"]')).toHaveCount(0);

    // Groups whose every item is permission-gated are dropped, so nobody
    // stares at a heading with nothing under it.
    await expect(nav.getByRole("heading", { name: "Development" })).toHaveCount(0);
    await expect(nav.getByRole("heading", { name: "Resources" })).toHaveCount(0);
  });

  test("the sidebar collapses and reports its state assistively", async ({ page }) => {
    await page.goto("/dashboard");
    const nav = page.getByRole("navigation", { name: "Main navigation" });
    const toggle = page.getByRole("button", { name: /Collapse|»/ });

    await expect(toggle).toHaveAttribute("aria-expanded", "true");
    await expect(nav).toHaveAttribute("data-collapsed", "false");

    await toggle.click();

    await expect(toggle).toHaveAttribute("aria-expanded", "false");
    await expect(nav).toHaveAttribute("data-collapsed", "true");

    // Collapsed hides labels visually but must keep them in the
    // accessibility tree — a screen-reader user does not get a narrower
    // application just because a sighted user reclaimed 176px.
    await expect(nav.getByText("Dashboard", { exact: true })).toBeAttached();
  });
});

test.describe("routes that exist are reachable", () => {
  // Administration is filtered out of the sidebar but the route is built
  // and ships in Slice 1. Reaching it by URL proves the page renders;
  // its data tables stay empty until authentication is wired.
  test("the administration page renders", async ({ page }) => {
    const response = await page.goto("/admin");
    expect(response?.status()).toBe(200);
    await expect(page.getByRole("main")).toBeVisible();
  });

  test("an unbuilt route is not silently served", async ({ page }) => {
    // `/my-work` has an API but no page. It must 404 rather than render
    // an empty shell that looks like a working screen with no data.
    const response = await page.goto("/my-work");
    expect(response?.status()).toBe(404);
  });
});
