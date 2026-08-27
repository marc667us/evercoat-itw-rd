/**
 * Every theme is measured, not chosen by eye.
 *
 * 🔴 THIS PROJECT HAS ALREADY SHIPPED AN ILLEGIBLE SURFACE AND PASSED A11Y.
 *
 * The sidebar's unbuilt items rendered at **1.48:1** against white — seventeen
 * of twenty-six entries, two thirds of the primary navigation — and axe-core
 * reported zero violations, because `aria-disabled` silences its own
 * `color-contrast` rule. It was found by measuring the rendered colour, not by
 * a scanner.
 *
 * Adding four more palettes multiplies that risk by four, and the e2e
 * accessibility sweep runs against the DEFAULT theme only: a dark theme could
 * be unreadable and every existing test would stay green. So the ratios are
 * computed here, from the same constants the application paints with.
 *
 * ⚠️ IT ASSERTS THE TOKENS THAT CARRY TEXT, AND SAYS WHICH ARE EXEMPT. Not
 * every step is text: `slate-200`/`300` are borders, and `slate-400` is used
 * only for decoration and for disabled controls, which WCAG 1.4.3 exempts and
 * which this codebase deliberately does not rely on to convey state.
 */
import { describe, expect, it } from "vitest";

import {
  CSS_VARIABLES,
  PALETTES,
  STATUS_VARIABLES,
  THEMES,
  contrast,
  luminance,
  resolvePalette,
} from "./theme";

/** The steps this application actually uses for TEXT, with their usage counts. */
const TEXT_STEPS = [
  ["slate500", 142], // muted labels
  ["slate600", 247], // body text — the most used colour in the product
  ["slate700", 110],
  ["slate800", 39],
  ["slate900", 166], // headings
] as const;

describe("theme palettes", () => {
  it("offers exactly five options", () => {
    // The count is a requirement, not an accident of the list.
    expect(THEMES).toHaveLength(5);
    expect(THEMES.map((t) => t.id)).toEqual(["system", "light", "dark", "contrast", "paper"]);
  });

  it("🔴 every text step clears WCAG AA on its own surface", () => {
    const failures: string[] = [];

    for (const [name, palette] of Object.entries(PALETTES)) {
      for (const [step] of TEXT_STEPS) {
        const ratio = contrast(palette[step], palette.white);
        if (ratio < 4.5) {
          failures.push(`${name}.${step} on surface: ${ratio.toFixed(2)}:1`);
        }
      }
    }

    expect(failures, "text below 4.5:1 is not readable by the people this rule exists for").toEqual(
      [],
    );
  });

  it("🔴 and the primary button's label clears AA on the button", () => {
    // `bg-slate-900` with `text-white` is the primary control, 17 call sites.
    // It is the one pairing that is NOT text-on-surface, so a palette can pass
    // every assertion above and still render an unreadable button — which is
    // exactly what happens if a theme darkens the ramp uniformly instead of
    // reversing it.
    const failures: string[] = [];

    for (const [name, palette] of Object.entries(PALETTES)) {
      const ratio = contrast(palette.white, palette.slate900);
      if (ratio < 4.5) {
        failures.push(`${name}: label on primary button ${ratio.toFixed(2)}:1`);
      }
    }

    expect(failures).toEqual([]);
  });

  it("🔴 the traffic-light colours stay readable on every surface", () => {
    // 🔴 THIS TEST REFUSED THE FIRST VERSION OF THE PALETTES, WHICH IS WHY IT
    // EXISTS. §10's four colours are validated for a WHITE surface, and the
    // first draft kept them fixed across all five themes on the argument that
    // re-tinting would invalidate the deltaE measurement. On the dark surface
    // they measured 3.56, 2.76, 3.63 and 2.25 — the traffic light would have
    // been the least readable thing on the screen, on the theme most likely to
    // be used at the end of a long day, and the e2e accessibility sweep runs
    // against the default theme only, so nothing else would have caught it.
    //
    // Each palette now carries its own set, and each is checked against its own
    // surface.
    const failures: string[] = [];
    for (const [themeName, palette] of Object.entries(PALETTES)) {
      for (const [statusName, colour] of Object.entries(palette.status)) {
        const ratio = contrast(colour, palette.white);
        if (ratio < 4.5) {
          failures.push(`${statusName} on ${themeName}: ${ratio.toFixed(2)}:1`);
        }
      }
    }

    expect(
      failures,
      "a status colour below 4.5:1 makes the traffic light unreadable — and §10 " +
        "already forbids relying on colour alone, so this is the text failing too",
    ).toEqual([]);
  });

  it("🔴 `invalid` shares the fail hue in every theme, because it is the same state", () => {
    // ADR-015 routes invalid to RED: the domain has THREE display states, and a
    // fourth hue would imply a fourth. Easy to break by hand when copying a
    // palette, and invisible until somebody invalidates a test.
    for (const [name, palette] of Object.entries(PALETTES)) {
      expect(palette.status.invalid, `${name} gave invalid its own hue`).toBe(palette.status.fail);
    }
  });

  it("high contrast means what it says: every text step clears 7:1", () => {
    const palette = PALETTES.contrast;
    for (const [step] of TEXT_STEPS) {
      const ratio = contrast(palette[step], palette.white);
      expect(ratio, `contrast.${step} is ${ratio.toFixed(2)}:1`).toBeGreaterThanOrEqual(7);
    }
  });

  it("🔴 the ramp is monotonic in every theme", () => {
    // A ramp that reverses direction mid-way renders a "lighter" step darker
    // than a "darker" one, and every hierarchy built on it inverts locally —
    // a heading quieter than the label above it. Cheap to get wrong by hand
    // and invisible until somebody looks at the right screen.
    for (const [name, palette] of Object.entries(PALETTES)) {
      const steps = [
        palette.slate50,
        palette.slate100,
        palette.slate200,
        palette.slate300,
        palette.slate400,
        palette.slate500,
        palette.slate600,
        palette.slate700,
        palette.slate800,
        palette.slate900,
      ].map(luminance);

      const descending = steps.every((value, i) => i === 0 || value <= (steps[i - 1] ?? 1));
      const ascending = steps.every((value, i) => i === 0 || value >= (steps[i - 1] ?? 0));

      expect(descending || ascending, `${name}'s ramp changes direction`).toBe(true);
    }
  });

  it("system resolves to a real palette in both directions", () => {
    expect(resolvePalette("system", false)).toBe(PALETTES.light);
    expect(resolvePalette("system", true)).toBe(PALETTES.dark);
    // And a named theme ignores the system preference entirely — choosing dark
    // must not flip back to light because the laptop is in light mode.
    expect(resolvePalette("paper", true)).toBe(PALETTES.paper);
  });

  it("names a CSS variable for every palette entry", () => {
    // The provider writes these onto `<html>`; a palette key with no variable
    // would simply never be applied, and the step would silently keep the
    // previous theme's value.
    const keys = Object.keys(PALETTES.light)
      .filter((key) => key !== "status")
      .sort();
    expect(Object.keys(CSS_VARIABLES).sort()).toEqual(keys);
    expect(Object.keys(STATUS_VARIABLES).sort()).toEqual(
      Object.keys(PALETTES.light.status).sort(),
    );
  });
});
