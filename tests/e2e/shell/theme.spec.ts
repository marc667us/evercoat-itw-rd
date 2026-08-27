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
