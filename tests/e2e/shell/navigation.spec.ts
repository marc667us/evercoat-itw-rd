import { expect, test } from "@playwright/test";

// The SINGLE SOURCE OF TRUTH for what is built, imported rather than
// restated. `lib/navigation.ts` is self-contained data with no imports of
// its own, so it costs nothing to reuse here — and reusing it is what
// stops this file drifting out of step with the sidebar it asserts on.
import { NAVIGATION, isAvailable } from "../../../apps/web/lib/navigation";

/** Every destination the sidebar renders as inert, derived not named. */
const UNAVAILABLE_ITEMS = NAVIGATION.flatMap((group) =>
  group.items.filter((item) => !isAvailable(item)),
);

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
  test("the root path is the public landing page and does NOT redirect", async ({ page }) => {
    // 🔴 THIS TEST IS THE INVERSE OF THE ONE IT REPLACES, DELIBERATELY.
    //
    // It used to read "the root path redirects into the dashboard" and assert
    // `/dashboard`. That was a real assertion about real behaviour, and the
    // behaviour changed on purpose: the owner specified `/` as a PUBLIC
    // landing page carrying sign-in, the competitor marketplace and the
    // industry news feed. So the assertion is inverted rather than deleted --
    // deleting it would leave the front door with no browser coverage at all,
    // and "it redirects" and "it renders" are both things only a browser can
    // prove.
    //
    // ⚠️ The landing preference did NOT disappear with the redirect. Its
    // reader moved to sign-in, where `auth-provider` substitutes
    // `readLanding()` for a `returnTo` of `/`. That is covered by
    // `apps/web/lib/auth/return-to.test.ts`, because it happens in a redirect
    // flow this suite cannot complete without a live Keycloak.
    await page.goto("/");

    // Still `/` after the app has had time to run any client-side effect. A
    // bare `toHaveURL` immediately after `goto` would also pass against a
    // redirect that had simply not fired yet.
    await expect(
      page.getByRole("heading", { level: 1, name: /Global competitor products/i }),
    ).toBeVisible({ timeout: 30_000 });
    await expect(page).toHaveURL(/\/$/);

    // The two public surfaces the owner asked for, and the way in.
    await expect(
      page.getByRole("heading", { name: "Global Competitor Product Marketplace" }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Global Competitor Industry News Feed" }),
    ).toBeVisible();
    await expect(page.getByRole("button", { name: "Sign in" })).toBeVisible();
  });

  test("the shell renders its landmarks", async ({ page }) => {
    await page.goto("/dashboard");

    await expect(
      page.getByRole("navigation", { name: "Main navigation" }),
    ).toBeVisible();
    await expect(page.getByRole("main")).toBeVisible();
    await expect(
      page.getByText("EvercoatITWRD", { exact: true }),
    ).toBeVisible();
  });

  test("the document title carries the product name", async ({ page }) => {
    // The identity strings in CLAUDE.md §1 are fixed. "ITERDRD" and any
    // generic R&D name are explicitly forbidden, so this is a contract,
    // not cosmetics.
    await page.goto("/dashboard");
    await expect(page).toHaveTitle(/EvercoatITWRD APP/);
    await expect(page).not.toHaveTitle(/ITERDRD/i);
  });

  test("every figure is unmistakably labelled as demonstration data", async ({
    page,
  }) => {
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

  test("the demonstration notice is on every page that shows demonstration data", async ({
    page,
  }) => {
    // A notice that appears on the landing page and nowhere else is worse
    // than none: a viewer who navigates once will believe the rest is real.
    for (const path of [
      "/dashboard",
      "/projects",
      "/my-work",
      "/pipeline",
      "/materials",
      "/suppliers",
      "/formulations",
      "/formulations/FRM-014",
    ]) {
      await page.goto(path);
      await expect(
        page.getByRole("note", { name: /demonstration data/i }),
        `no demonstration notice on ${path}`,
      ).toBeVisible();
    }
  });

  /**
   * 🔴 THE OTHER DIRECTION, BECAUSE THE LIST ABOVE USED TO CARRY `/innovation`.
   *
   * `/innovation` rendered a static array from `lib/demo/dataset` until it was
   * wired to the opportunities API, at which point it stopped having a
   * demonstration notice — correctly, because it no longer has demonstration
   * data — and the test above went red on a screen that had just been fixed.
   *
   * The lesson is the one recorded on `an unbuilt destination is inert` below:
   * a hand-kept list of screens breaks every time a screen changes category.
   * Deleting the path would have left it untested, so it moved here and the
   * assertion inverted. A live-only screen must carry a data-source note —
   * "Live data" or "No data source" — and must NOT claim demonstration data.
   * Both halves matter: without the first, a page that rendered no banner at
   * all would pass.
   */
  test("a live-only page says which, and never claims demonstration data", async ({
    page,
  }) => {
    for (const path of ["/innovation"]) {
      await page.goto(path);
      await expect(
        page.getByRole("note", { name: /(data source|no data source) notice/i }),
        `no data-source notice at all on ${path}`,
      ).toBeVisible();
      await expect(
        page.getByRole("note", { name: /demonstration data/i }),
        `${path} is live-only and must not claim demonstration data`,
      ).toHaveCount(0);
    }
  });
});

test.describe("navigation gating", () => {
  test("an unbuilt destination is inert, not a dead link", async ({ page }) => {
    await page.goto("/dashboard");
    const nav = page.getByRole("navigation", { name: "Main navigation" });

    // 🔴 DERIVED FROM THE NAV MODEL, NOT NAMED.
    //
    // This asserted on "Laboratory" and broke the moment Laboratory was
    // built — as it had already broken for "My Work" at Slice 2 and
    // "Formulations" at Slice 3. The old comment treated re-editing it
    // every slice as the price of the assertion. It is not: it is the
    // same "two literals in two files" trap this repository keeps
    // finding, and `lib/navigation.test.ts` had ALREADY rejected exactly
    // this approach in its own comment — *"naming a specific item means
    // editing this test every slice, and a test edited every slice is a
    // test nobody reads."* That lesson had been learned in the unit
    // suite and not carried across to this one.
    //
    // So the example comes from the single source of truth. The
    // assertion is now the INVARIANT — every unavailable destination is
    // inert and none is navigable — which is what was meant all along
    // and never needs touching again.
    const unbuilt = UNAVAILABLE_ITEMS;
    expect(
      unbuilt.length,
      "every destination is built, so there is nothing left to gate — delete this test",
    ).toBeGreaterThan(0);

    for (const item of unbuilt) {
      const inert = nav.locator('[aria-disabled="true"]', {
        hasText: item.label,
      });
      await expect(inert, `${item.label} should be inert`).toHaveCount(1);

      // The decisive assertion: no anchor points at it.
      await expect(
        nav.locator(`a[href^="${item.href}"]`),
        `${item.label} is unbuilt but the sidebar links to ${item.href}`,
      ).toHaveCount(0);
    }
  });

  test("every unbuilt item is inert and every built item is a link", async ({
    page,
  }) => {
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
      expect(
        href,
        "a sidebar anchor with no href is a dead control",
      ).toBeTruthy();
    }

    const disabled = nav.locator('[aria-disabled="true"]');
    for (let i = 0; i < (await disabled.count()); i += 1) {
      await expect(disabled.nth(i)).toHaveJSProperty("tagName", "SPAN");
    }
  });

  test("every enabled sidebar link reaches a real page", async ({ page }) => {
    // 🔴 A CRAWL DOES NOT FIT THE SUITE-WIDE 60s BUDGET, AND FOR TWO REASONS
    // THAT ONLY APPEAR OUTSIDE A PRE-BUILT SITE.
    //
    // This test and `no page contains a dead internal link` below are the only
    // two that perform DOZENS of navigations rather than one or two. The 60s
    // default in `playwright.config.ts` was set against a STATIC EXPORT, where
    // every route is already built and a navigation is a file read.
    //
    // Measured 2026-08-23, both failing on `Test timeout of 60000ms exceeded`:
    //   * against a Next DEV server, every route compiles on first visit —
    //     seconds each, and the crawl visits each one exactly once, so it pays
    //     the compile cost on every single hop;
    //   * through the demonstration TUNNEL, each page load measured 1.3–2.7s
    //     of round trip on top of that.
    //
    // Neither is a defect in the application, and both were briefly read as
    // one: the failure surfaced as `page.goto: net::ERR_ABORTED` inside the
    // crawl loop, which looks exactly like a dead link. `test.slow()` triples
    // the budget to 180s, which is what this test's actual work costs.
    //
    // ⚠️ It does NOT paper over a slow application. If a SINGLE navigation
    // ever takes 60s the other twenty-odd tests in this file fail first, and
    // they still carry the default budget.
    test.slow();

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
    expect(
      hrefs.length,
      "the sidebar rendered no links at all",
    ).toBeGreaterThan(3);

    for (const href of hrefs) {
      const response = await page.goto(href);
      expect(response?.status(), `${href} is a dead link`).toBe(200);
    }
  });

  test("no page contains a dead internal link", async ({ page }) => {
    // 🔴 THE HEAVIEST TEST IN THE SUITE, AND `test.slow()` WAS NOT ENOUGH.
    //
    // It follows EVERY internal anchor on ten pages, where the sidebar crawl
    // above follows one link per sidebar entry. `test.slow()` tripled the
    // budget to 180s and it STILL timed out against the demonstration tunnel.
    //
    // Measured 2026-08-23 rather than guessed at:
    //   * ten crawled pages carry 157 anchors, deduplicated to roughly
    //     thirty-five distinct destinations (the sidebar repeats on each);
    //   * a bare HTML fetch through the tunnel costs ~1.2s, measured three
    //     times: 1.309s / 1.193s / 1.148s;
    //   * but Playwright navigates with `waitUntil: "load"`, so each hop also
    //     pulls JS chunks and CSS — several times the HTML cost.
    //
    // Thirty-five browser navigations at that cost lands just past 180s, which
    // is exactly the marginal overrun observed. 600s is that measurement with
    // headroom, not a number picked to make a red test green.
    //
    // ⚠️ THE COST IS THE TUNNEL, NOT THE APPLICATION. Against the static
    // export that actually deploys, this crawl finishes in about two minutes;
    // both crawls together ran in 3.5m against a local dev server. If this
    // test ever fails on a FAST origin, that is a real defect and the budget
    // is not the reason.
    //
    // Kept in the live profile deliberately. A dead link is the most visible
    // possible failure in a client demonstration, and dropping the crawl from
    // the deployed run to save minutes would remove the coverage exactly where
    // it matters most.
    test.setTimeout(600_000);

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
      "/dashboard",
      "/projects",
      "/my-work",
      "/pipeline",
      "/innovation",
      "/admin",
      "/materials",
      "/suppliers",
      "/formulations",
      "/formulations/FRM-014",
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

    expect(seen.size, "no internal links were crawled at all").toBeGreaterThan(
      5,
    );
  });

  test("the sidebar collapses and reports its state assistively", async ({
    page,
  }) => {
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
    // Derived, for the reason given on the gating test above: this named
    // `/my-work` until Slice 2 built it, `/formulations` until Slice 3,
    // and `/laboratory` until Slice 4 — breaking each time.
    //
    // An unbuilt route must 404 rather than render an empty shell that
    // looks like a working screen with no data. That is the same rule
    // `RecordLink` follows: a dead link reads as a missing RECORD, not as
    // an unbuilt screen.
    const [first] = UNAVAILABLE_ITEMS;
    expect(first, "every destination is built — delete this test").toBeTruthy();

    const response = await page.goto(first.href);
    expect(
      response?.status(),
      `${first.href} is not built, so it must 404 rather than serve a shell`,
    ).toBe(404);
  });
});

test.describe("the Intelligence group is reachable, not merely declared", () => {
  // 🔴 THE THING THIS CATCHES IS A ROUTE WITH NO CALLER.
  //
  // `GET /api/analysis/reports/test-results` shipped on 2026-08-25 and gave
  // `report.generate` its first enforcement point anywhere. Nothing in the
  // browser reached it: Reports sat at slice 20 in `navigation.ts` and
  // rendered inert, so the endpoint existed, was tested, and no person could
  // press anything that called it. This project found 23 endpoints in that
  // condition on 08-24; this was the twenty-fourth, one day old.
  //
  // `analytics.view` and `analytics.portfolio` were the same defect turned on
  // the permission catalogue: held by nine and two of the ten seeded roles,
  // read by no line of application code.
  //
  // ⚠️ THE GENERIC CRAWL ABOVE IS NOT ENOUGH ON ITS OWN. "every enabled
  // sidebar link reaches a real page" asserts a 200, which an empty shell
  // also returns. These assert the screens actually rendered themselves.

  for (const [id, path, heading] of [
    ["analytics", "/analytics", "Analytics"],
    ["reports", "/reports", "Reports"],
  ] as const) {
    test(`${heading} is an enabled link and the page renders`, async ({ page }) => {
      const item = NAVIGATION.flatMap((g) => g.items).find((i) => i.id === id);
      expect(item, `the ${id} navigation item has gone`).toBeDefined();
      expect(
        isAvailable(item!),
        `${heading} is still gated as unbuilt, so its API has no browser caller`,
      ).toBe(true);

      const response = await page.goto(path);
      expect(response?.status(), `${path} is a dead link`).toBe(200);
      await expect(page.getByRole("heading", { name: heading, level: 1 })).toBeVisible();
      await expect(page.getByRole("main")).toBeVisible();
    });
  }

  test("neither Intelligence screen invents a figure when it has no data", async ({ page }) => {
    // 🔴 THE 2026-08-19 INCIDENT, ASSERTED RATHER THAN REMEMBERED: a failed
    // `/api/me` became DEMONSTRATION DATA on a screen that looked fine.
    //
    // Both of these are `LiveOnly` — real numbers or an honest statement of
    // their absence — and neither has a demonstration fixture, deliberately.
    // A fabricated "9 tests GREEN" is a safety claim about physical
    // measurements that were never made, which is materially worse than a
    // fabricated supplier row.
    //
    // Without a session the shell renders the "no data source" notice. What
    // must NOT appear is a number presented as a count of real test outcomes.
    for (const path of ["/analytics", "/reports"]) {
      await page.goto(path);
      const main = page.getByRole("main");
      await expect(main).toBeVisible();

      const notice = page.getByTestId("no-data-source");
      const banner = page.getByRole("note", { name: "Data source notice" });
      const explained = (await notice.count()) > 0 || (await banner.count()) > 0;
      expect(
        explained,
        `${path} rendered without saying where its figures came from`,
      ).toBe(true);
    }
  });
});
