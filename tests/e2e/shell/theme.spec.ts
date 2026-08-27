/**
 * The themes actually repaint the application, in a real browser.
 *
 * 🔴 `theme.test.ts` PROVES THE PALETTES ARE READABLE. IT CANNOT PROVE THEY ARE
 * APPLIED.
 *
 * That test computes contrast ratios from constants — it would pass unchanged
 * if the provider never ran, if `tailwind.config` still emitted literal colours,
 * or if the custom properties were written to the wrong element. Every one of
 * those leaves a Settings screen whose radio buttons move and whose application
 * stays white, which is exactly the shape this project keeps finding: a layer
 * proven in isolation and a composition nobody checked.
 *
 * So this reads the COMPUTED style out of the document after choosing a theme.
 *
 * ⚠️ IT ASSERTS THE PAGE BACKGROUND, NOT ONLY THE VARIABLE. Setting
 * `--slate-50` proves the provider wrote it; the body's background proves
 * Tailwind's `bg-slate-50` resolves through it. The second is the one that
 * would fail if the config regressed to literals, and it is the one a person
 * would actually notice.
 */

import { expect, test } from "@playwright/test";

/** Choose a theme the way the Settings screen does, then reload. */
async function choose(page: import("@playwright/test").Page, theme: string) {
  await page.goto("/dashboard/");
  await page.evaluate((value) => window.localStorage.setItem("evercoat.theme", value), theme);
  await page.reload({ waitUntil: "load" });
  // The provider applies on mount; without this the first read races hydration.
  await expect(page.locator("html")).toHaveAttribute("data-theme", theme, { timeout: 15_000 });
}

async function painted(page: import("@playwright/test").Page) {
  return page.evaluate(() => {
    const root = getComputedStyle(document.documentElement);
    return {
      surface: root.getPropertyValue("--surface").trim(),
      body: getComputedStyle(document.body).backgroundColor,
      colorScheme: root.colorScheme,
    };
  });
}

test.describe("themes", () => {
  test("dark repaints the page and tells the browser it is dark", async ({ page }) => {
    await choose(page, "dark");
    const result = await painted(page);

    expect(result.surface, "the provider did not write the palette").toBe("15 23 42");
    // 🔴 THE ONE THAT CATCHES A CONFIG REGRESSION. `bg-slate-50` must resolve
    // THROUGH the variable; if Tailwind emitted a literal, this stays the light
    // value while the variable above is perfectly correct.
    expect(result.body, "bg-slate-50 is not resolving through the variable").toBe(
      "rgb(30, 41, 59)",
    );
    // Without `color-scheme` the browser paints scrollbars, form controls and
    // the overscroll band light — beside a data grid, on every page.
    expect(result.colorScheme).toBe("dark");
  });

  test("paper and high contrast are distinct surfaces, not a tinted dark", async ({ page }) => {
    await choose(page, "paper");
    const paper = await painted(page);
    expect(paper.surface).toBe("250 246 238");
    expect(paper.colorScheme).toBe("light");

    await choose(page, "contrast");
    const contrast = await painted(page);
    expect(contrast.surface).toBe("255 255 255");

    // 🔴 BOTH DIRECTIONS. "Dark is dark" passes against a provider that applies
    // one palette and ignores the rest; this fails unless each theme is
    // genuinely its own.
    expect(paper.body).not.toBe(contrast.body);
  });

  test("the choice survives a reload, which is the whole point of storing it", async ({
    page,
  }) => {
    await choose(page, "dark");
    await page.goto("/testing/");
    // A different screen, no re-selection: the preference is read on mount
    // wherever the reader lands.
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
    expect((await painted(page)).surface).toBe("15 23 42");
  });

  test("🔴 the default build is unchanged when nothing has been chosen", async ({ page }) => {
    // The regression that matters most: themes must not alter the application
    // for anybody who never opens Settings. `system` resolves against the test
    // browser's own preference, which Playwright leaves light.
    await page.goto("/dashboard/");
    await expect(page.locator("html")).toHaveAttribute("data-theme", "system", {
      timeout: 15_000,
    });

    const result = await painted(page);
    expect(result.surface).toBe("255 255 255");
    expect(result.body).toBe("rgb(248, 250, 252)");
  });
});

test.describe("before the first paint", () => {
  /**
   * 🔴 THE THEME WAS APPLIED BY REACT, SO EVERY LOAD FLASHED WHITE.
   *
   * `ThemeProvider` runs in an effect — after hydration, and therefore after
   * the browser has already painted a document whose only colours are the
   * light fallbacks in `tailwind.config`. A reader who had chosen dark got a
   * full white page and then their theme. Both reviewers found it, and every
   * test above passed over it, because all of them read the computed style
   * once the application is running.
   *
   * This asserts the state of the document BEFORE any React has executed.
   */
  test("the palette is set before React runs, not after", async ({ page }) => {
    await page.goto("/dashboard/");
    await page.evaluate(() => window.localStorage.setItem("evercoat.theme", "dark"));

    // Stop the page as early as a browser will let us: `domcontentloaded`
    // fires once the head scripts have run and before the React bundle has
    // hydrated. If the dark palette is only applied by the provider, the
    // variable is empty at this moment.
    await page.goto("/dashboard/", { waitUntil: "domcontentloaded" });

    const surface = await page.evaluate(() =>
      getComputedStyle(document.documentElement).getPropertyValue("--surface").trim(),
    );

    expect(
      surface,
      "the dark surface was not set at DOMContentLoaded, so the first frame " +
        "is painted with the light fallbacks and the page flashes white",
    ).toBe("15 23 42");
  });

  test("an unreadable preference still paints, rather than leaving no colours", async ({
    page,
  }) => {
    // The pre-paint script runs before anything else exists and swallows
    // everything on purpose. A stored value from a version of this application
    // that offered a theme no longer in the list must resolve to the default,
    // not to an unstyled document.
    await page.goto("/dashboard/");
    await page.evaluate(() => window.localStorage.setItem("evercoat.theme", "midnight-1998"));
    await page.reload({ waitUntil: "load" });

    const surface = await page.evaluate(() =>
      getComputedStyle(document.documentElement).getPropertyValue("--surface").trim(),
    );
    expect(surface).toBe("255 255 255");
  });
});

test.describe("where the application opens", () => {
  /**
   * 🔴 THE PREFERENCE HAD NO READER, AND THE SCREEN SAID IT WORKED.
   *
   * `readLanding()` was written by Settings, validated on the way back out,
   * and consulted by nothing: `app/page.tsx` redirected to a hard-coded
   * `/dashboard`. Both reviewers found it — it is this project's own rule
   * about a setting with no enforcement point, arriving from the user's side
   * of the screen.
   */
  test("the front door opens on the chosen screen", async ({ page }) => {
    await page.goto("/dashboard/");
    await page.evaluate(() => window.localStorage.setItem("evercoat.landing", "/testing"));

    await page.goto("/");
    await expect(page).toHaveURL(/\/testing\/?$/, { timeout: 15_000 });
  });

  test("and on the dashboard when nothing has been chosen", async ({ page }) => {
    // The default must be unchanged for anybody who never opens Settings.
    await page.goto("/");
    await expect(page).toHaveURL(/\/dashboard\/?$/, { timeout: 15_000 });
  });

  test("a stored screen that no longer exists falls back rather than 404s", async ({ page }) => {
    await page.goto("/dashboard/");
    await page.evaluate(() => window.localStorage.setItem("evercoat.landing", "/formulations"));
    // `/formulations` is a real page but NOT one of the three offered, so it is
    // not a valid stored value — `isLandingScreen` refuses it and the default
    // applies. A preference read that accepted any path would be an open
    // redirect with a friendly name.
    await page.goto("/");
    await expect(page).toHaveURL(/\/dashboard\/?$/, { timeout: 15_000 });
  });
});
