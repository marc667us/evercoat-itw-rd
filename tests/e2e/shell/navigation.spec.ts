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
    // The trailing slash is optional on purpose. The standalone build
    // serves `/dashboard`; the static export sets `trailingSlash` (so that
    // it writes directory indexes, which every static host serves) and
    // therefore lands on `/dashboard/`. Both are the same destination, and
    // anchoring on `$` without the `\/?` made this test assert a build mode
    // rather than the behaviour it is named after.
    await expect(page).toHaveURL(/\/dashboard\/?$/);
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

  test("every figure is unmistakably labelled as demonstration data", async ({ page }) => {
    // Rule 3 of the seven non-negotiables: predictions must never render as
    // confirmed results, and §10 that a dashboard of invented KPIs is
    // indistinguishable from a working one at a glance.
    //
    // This test used to assert "No data yet" was on screen, because the
    // dashboard had nothing on it. It now carries real figures derived from
    // the demonstration dataset, so the SAME rule is enforced differently:
    // the figures may exist, but the standing notice that they are
    // synthetic must exist too, and must be reachable by assistive
    // technology rather than being a faint line of grey text.
    await page.goto("/dashboard");
    const notice = page.getByRole("note", { name: /demonstration data/i });
    await expect(notice).toBeVisible();
    await expect(notice).toContainText(/synthetic/i);
  });

  test("the demonstration notice is on every page, not just the dashboard", async ({
    page,
  }) => {
    // A notice that appears on the landing page and nowhere else is worse
    // than none: a viewer who navigates once will believe the rest is real.
    for (const path of [
      "/dashboard", "/projects", "/my-work", "/pipeline", "/innovation",
      "/materials", "/suppliers", "/formulations", "/formulations/FRM-014",
    ]) {
      await page.goto(path);
      await expect(
        page.getByRole("note", { name: /demonstration data/i }),
        `no demonstration notice on ${path}`,
      ).toBeVisible();
    }
  });
});

test.describe("navigation gating", () => {
  test("an unbuilt destination is inert, not a dead link", async ({ page }) => {
    await page.goto("/dashboard");
    const nav = page.getByRole("navigation", { name: "Main navigation" });

    // "Laboratory" is slice 4. Its page does not exist. It must be present
    // (so the structure is legible) and NOT navigable (so it cannot 404).
    //
    // This named "My Work" until Slice 2 built it, then "Formulations"
    // until Slice 3 built it. The example has to be a destination that is
    // genuinely still unbuilt, or the assertion says nothing — and moving
    // it each slice is the cost of the assertion continuing to mean
    // something.
    const item = nav.getByText("Laboratory", { exact: true });
    await expect(item).toBeVisible();

    const inert = nav.locator('[aria-disabled="true"]', { hasText: "Laboratory" });
    await expect(inert).toHaveCount(1);

    // The decisive assertion: no anchor points at it.
    await expect(nav.locator('a[href^="/laboratory"]')).toHaveCount(0);
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

  test("every enabled sidebar link reaches a real page", async ({ page }) => {
    // WHAT REPLACED WHAT, AND WHY, STATED PLAINLY.
    //
    // This test used to assert that Administration was ABSENT, because the
    // layout passed an empty permission set. That is no longer true: the
    // demonstration shell passes ALL_NAV_PERMISSIONS so a client can see
    // the whole module map. The old test's own comment anticipated exactly
    // this and asked the right question — was the filter made permissive?
    // Yes, deliberately, and only in the shell's presentation layer.
    //
    // That is safe here for one specific reason: `visibleNavigation` is
    // covered exhaustively by lib/navigation.test.ts, including
    // "never leaks an item the user cannot hold", which checks EVERY
    // permissioned item against a principal lacking exactly that
    // permission. Removing the browser-level assertion drops a duplicate,
    // not the coverage.
    //
    // What replaces it is the guarantee this deployment actually needs and
    // that nothing previously checked: no enabled link anywhere in the
    // sidebar leads to a page that does not exist. A dead link in a client
    // demonstration is worse than a greyed-out one.
    await page.goto("/dashboard");
    const nav = page.getByRole("navigation", { name: "Main navigation" });

    const hrefs = await nav
      .locator("a")
      .evaluateAll((els) =>
        els
          .map((e) => (e as HTMLAnchorElement).getAttribute("href"))
          .filter((h): h is string => Boolean(h)),
      );
    expect(hrefs.length, "the sidebar rendered no links at all").toBeGreaterThan(3);

    for (const href of hrefs) {
      const response = await page.goto(href);
      expect(response?.status(), `${href} is a dead link`).toBe(200);
    }
  });

  test("no page contains a dead internal link", async ({ page }) => {
    // The sidebar check above is not enough, and Codex said so: the
    // Administration header advertised /admin/roles, /admin/permissions and
    // five more as live links into pages that do not exist, and a
    // sidebar-only crawl walked straight past them.
    //
    // This visits every route a viewer can reach and follows EVERY internal
    // anchor on it. In a client demonstration a dead link is the single most
    // visible possible failure, so it is worth the extra seconds.
    const seen = new Set<string>();
    const pages = [
      "/dashboard", "/projects", "/my-work", "/pipeline", "/innovation", "/admin",
      "/materials", "/suppliers", "/formulations", "/formulations/FRM-014",
    ];

    for (const path of pages) {
      await page.goto(path);
      const hrefs = await page
        .locator("a[href^='/']")
        .evaluateAll((els) =>
          els
            .map((e) => (e as HTMLAnchorElement).getAttribute("href"))
            .filter((h): h is string => Boolean(h)),
        );

      for (const href of hrefs) {
        if (seen.has(href)) continue;
        seen.add(href);

        // A SAME-DOCUMENT FRAGMENT IS NOT A NAVIGATION.
        //
        // `page.goto("/x#y")` while already on /x resolves without a network
        // request, so `response` is null and `.status()` is undefined — the
        // first version reported "#composition is a dead link" about a link
        // that works perfectly. The right question for a fragment is not
        // "what status did it return" but "does the target element exist",
        // because an anchor pointing at a missing id is the actual defect.
        const [pathPart, fragment] = href.split("#");

        const response = await page.goto(pathPart || path);
        expect(
          response?.status(),
          `${href}, linked from ${path}, is a dead link`,
        ).toBe(200);

        if (fragment) {
          await expect(
            page.locator(`#${fragment}`),
            `${href}, linked from ${path}, points at an element that does not exist`,
          ).toHaveCount(1);
        }

        await page.goto(path);
      }
    }

    expect(seen.size, "no internal links were crawled at all").toBeGreaterThan(5);
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
    // `/laboratory` is slice 4: no page exists. It must 404 rather than
    // render an empty shell that looks like a working screen with no data.
    //
    // This named `/my-work` until Slice 2 built it and `/formulations`
    // until Slice 3 built it.
    const response = await page.goto("/laboratory");
    expect(response?.status()).toBe(404);
  });
});
