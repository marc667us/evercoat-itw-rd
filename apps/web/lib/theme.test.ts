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
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import tailwindConfig from "../tailwind.config";
import {
  ACCENT_NAMES,
  ACCENT_STEPS,
  CSS_VARIABLES,
  PALETTES,
  STATUS_VARIABLES,
  THEMES,
  THEME_STORAGE_KEY,
  accentVariable,
  contrast,
  luminance,
  paletteVariables,
  prePaintScript,
  resolvePalette,
  type AccentName,
  type Palette,
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
  it("offers exactly six options", () => {
    // The count is a requirement, not an accident of the list.
    //
    // Six since 2026-08-30: `patriot` was added on the owner's instruction.
    // Changed deliberately rather than loosened — an assertion relaxed to
    // `toBeGreaterThan` would stop noticing a theme added by accident, and
    // this list is offered to users in this order.
    expect(THEMES).toHaveLength(6);
    expect(THEMES.map((t) => t.id)).toEqual([
      "system",
      "light",
      "dark",
      "contrast",
      "paper",
      "patriot",
    ]);
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
        palette.slate950,
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
      .filter((key) => key !== "status" && key !== "accents")
      .sort();
    expect(Object.keys(CSS_VARIABLES).sort()).toEqual(keys);
    expect(Object.keys(STATUS_VARIABLES).sort()).toEqual(
      Object.keys(PALETTES.light.status).sort(),
    );
  });
});

/* -------------------------------------------------------------------------- */
/* The pairs that actually appear together                                     */
/* -------------------------------------------------------------------------- */

/**
 * 🔴 THE CONTRAST TEST ABOVE MEASURED THE WRONG THING, AND SHIPPED A 1.65:1
 * BADGE.
 *
 * It checks every status colour against `palette.white` — the page. A
 * `StatusBadge` does not sit on the page: it sits on `bg-emerald-50`, and while
 * the status colours moved with the theme the accent ramps did not, so on dark
 * the pass badge was lightened text on a ground that had stayed light. Measured
 * afterwards: **1.65:1**. Codex found it.
 *
 * So this reads the SOURCE and measures what the source pairs. A class string
 * naming both a background and a foreground is an element whose two colours
 * will be seen together; there is no judgement here about which pairs matter,
 * which is the point — a hand-written list of pairs is the hand-copied list
 * this project has already been caught by twice.
 */

/** Every `.tsx` under the given root. */
function sources(root: string, found: string[] = []): string[] {
  for (const entry of readdirSync(root, { withFileTypes: true })) {
    const path = join(root, entry.name);
    if (entry.isDirectory()) sources(path, found);
    else if (entry.name.endsWith(".tsx")) found.push(path);
  }
  return found;
}

/** The palette value a Tailwind colour utility resolves to, or null if it is not a colour. */
function resolve(token: string, palette: Palette): string | null {
  const status = /^(?:bg|text|border)-status-(pass|fail|conditional|invalid|neutral)$/.exec(token);
  if (status !== null) return palette.status[status[1] as keyof typeof palette.status];

  if (/^(?:bg|text|border)-white$/.test(token)) return palette.white;

  const slate = /^(?:bg|text|border)-slate-(50|100|200|300|400|500|600|700|800|900|950)$/.exec(
    token,
  );
  if (slate !== null) return palette[`slate${slate[1] as string}` as keyof Palette] as string;

  const accent = new RegExp(
    "^(?:bg|text|border)-(" + ACCENT_NAMES.join("|") + ")-(" + ACCENT_STEPS.join("|") + ")$",
  ).exec(token);
  if (accent !== null) {
    return palette.accents[accent[1] as (typeof ACCENT_NAMES)[number]][
      accent[2] as (typeof ACCENT_STEPS)[number]
    ];
  }

  return null;
}

interface Pairing {
  readonly file: string;
  readonly background: string;
  readonly foreground: string;
}

/** Class strings in the source that name a background AND a foreground. */
function pairings(): Pairing[] {
  const found: Pairing[] = [];
  const roots = [join(__dirname, "..", "app"), join(__dirname, "..", "components")];

  for (const root of roots) {
    for (const file of sources(root)) {
      const text = readFileSync(file, "utf8");
      // Runs of class names between quotes. Deliberately crude: a run that
      // happens to contain a background and a foreground is exactly the thing
      // being looked for.
      //
      // ⚠️ AND A FALSE POSITIVE IS NOT FREE. An earlier version of this
      // comment said one "costs one measurement" — it does not: a spurious
      // pair below 4.5:1 lands in `failures` and reds the suite over a
      // pairing nobody renders. The Supervisor found the comment, which is
      // the version of this that matters, because it is what would let the
      // next reader wave a real failure through as harmless.
      for (const literal of text.match(/"[^"\n]{0,400}"/g) ?? []) {
        const tokens = literal.slice(1, -1).split(/\s+/);
        const background = tokens.find((token) => token.startsWith("bg-"));
        if (background === undefined) continue;
        for (const token of tokens) {
          if (!token.startsWith("text-") && !token.startsWith("border-")) continue;
          found.push({ file: file.replace(/\\/g, "/"), background, foreground: token });
        }
      }
    }
  }
  return found;
}

describe("the colours that appear together", () => {
  it("finds real pairings to measure", () => {
    // 🔴 A SCANNER THAT FINDS NOTHING PASSES EVERYTHING. This is the guard that
    // stops the test below from going green because a regex stopped matching.
    const measurable = pairings().filter(
      (pair) =>
        resolve(pair.background, PALETTES.light) !== null &&
        resolve(pair.foreground, PALETTES.light) !== null,
    );
    expect(measurable.length).toBeGreaterThan(40);
  });

  it("🔴 text stays readable on the ground it is actually painted on, in every theme", () => {
    const failures: string[] = [];

    for (const [name, palette] of Object.entries(PALETTES)) {
      for (const pair of pairings()) {
        if (!pair.foreground.startsWith("text-")) continue;
        const background = resolve(pair.background, palette);
        const foreground = resolve(pair.foreground, palette);
        if (background === null || foreground === null) continue;

        const ratio = contrast(foreground, background);
        if (ratio < 4.5) {
          failures.push(
            `${name}: ${pair.foreground} on ${pair.background} = ${ratio.toFixed(2)}:1`,
          );
        }
      }
    }

    expect([...new Set(failures)].sort()).toEqual([]);
  });

  it("🔴 no theme makes a border LESS visible than the shipped default does", () => {
    // 🔴 THE ABSOLUTE THRESHOLD WAS THE WRONG MEASUREMENT, AND IT FAILED THE
    // SHIPPED DESIGN.
    //
    // Written as "every border clears 1.35:1" this refused the LIGHT theme:
    // `border-slate-200` on `bg-white` is 1.23:1, and that is Tailwind's own
    // pairing, used across the entire product, accepted long before themes
    // existed. A guard that refuses the accepted default is not finding a
    // defect; it is a second opinion about a decision already made.
    //
    // What a THEME can be held to is that it does not make things worse. So
    // each pair is measured against the same pair on light, which is the
    // property this change could actually break.
    const failures: string[] = [];

    for (const [name, palette] of Object.entries(PALETTES)) {
      if (name === "light") continue;
      for (const pair of pairings()) {
        if (!pair.foreground.startsWith("border-")) continue;
        const background = resolve(pair.background, palette);
        const foreground = resolve(pair.foreground, palette);
        if (background === null || foreground === null) continue;

        const reference = contrast(
          resolve(pair.foreground, PALETTES.light) as string,
          resolve(pair.background, PALETTES.light) as string,
        );
        // An edge the default deliberately does not draw -- `border-slate-900`
        // on `bg-slate-900`, the primary button -- has nothing to preserve.
        if (reference < 1.05) continue;

        // Capped at WCAG 1.4.11's non-text threshold: once a border clears
        // 3:1 it is visible, and holding a 17:1 pairing to 14.5:1 is arithmetic
        // rather than legibility. Below 3:1 -- which is where every alert box
        // border in this product sits -- the theme must not erode it.
        const required = Math.min(reference * 0.85, 3);
        const ratio = contrast(foreground, background);
        if (ratio < required) {
          failures.push(
            `${name}: ${pair.foreground} on ${pair.background} = ${ratio.toFixed(2)}:1 ` +
              `against ${reference.toFixed(2)}:1 on light`,
          );
        }
      }
    }

    expect([...new Set(failures)].sort()).toEqual([]);
  });
});

/* -------------------------------------------------------------------------- */
/* One producer                                                                */
/* -------------------------------------------------------------------------- */

describe("tailwind resolves through the palette and nothing else", () => {
  /** Every `rgb(var(--x, R G B) / <alpha-value>)` in the built config. */
  function configTokens(): Map<string, string> {
    const found = new Map<string, string>();
    const walk = (value: unknown): void => {
      if (typeof value === "string") {
        const match = /^rgb\(var\((--[a-z0-9-]+),\s*([0-9 ]+)\)\s*\/\s*<alpha-value>\)$/.exec(value);
        if (match !== null) found.set(match[1] as string, (match[2] as string).trim());
        return;
      }
      if (value !== null && typeof value === "object") {
        Object.values(value as Record<string, unknown>).forEach(walk);
      }
    };
    walk(tailwindConfig.theme?.extend?.colors);
    return found;
  }

  it("🔴 every themed colour in the config falls back to the LIGHT palette", () => {
    // `tailwind.config.ts` used to CLAIM this test existed while it did not,
    // over 60 hand-copied triples. The config now imports the palette, so there
    // is nothing to drift — and this measures the RESOLVED config rather than
    // trusting that, so re-hardcoding a value is caught rather than assumed
    // impossible.
    const light = paletteVariables(PALETTES.light);
    const drifted: string[] = [];

    for (const [variable, fallback] of configTokens()) {
      if (light[variable] !== fallback) {
        drifted.push(`${variable}: config ${fallback} vs palette ${light[variable] ?? "absent"}`);
      }
    }

    expect(drifted).toEqual([]);
  });

  it("🔴 every variable a theme sets is reachable from a Tailwind class", () => {
    // The other direction, and the one that caught `slate-950`: a variable the
    // provider writes that no utility reads is a colour that never moves — and
    // Tailwind DEEP-MERGES a partial scale, so the missing step silently keeps
    // its built-in literal instead of failing.
    const inConfig = new Set(configTokens().keys());
    const missing = Object.keys(paletteVariables(PALETTES.light)).filter(
      (variable) => !inConfig.has(variable),
    );

    expect(missing).toEqual([]);
  });

  it("names a CSS variable for every accent step", () => {
    const variables = paletteVariables(PALETTES.light);
    for (const name of ACCENT_NAMES) {
      for (const step of ACCENT_STEPS) {
        expect(variables[accentVariable(name, step)]).toBe(PALETTES.light.accents[name][step]);
      }
    }
  });

  it("🔴 no themed palette leaves an accent ramp at Tailwind's own values", () => {
    // The half-theme, stated as an assertion.
    for (const [name, palette] of Object.entries(PALETTES)) {
      if (name === "light") continue;
      const unchanged = ACCENT_NAMES.filter((hue) =>
        ACCENT_STEPS.every(
          (step) => palette.accents[hue][step] === PALETTES.light.accents[hue][step],
        ),
      );
      expect(unchanged, `${name} left these ramps at the light values`).toEqual([]);
    }
  });
});

describe("the pre-paint script", () => {
  const script = prePaintScript();

  it("reads the same storage key the application writes", () => {
    expect(script).toContain(JSON.stringify(THEME_STORAGE_KEY));
  });

  it("🔴 carries every variable the React provider sets", () => {
    // A property in one and not the other is a colour that changes at
    // hydration — the same flash, arriving later and harder to see.
    for (const variable of Object.keys(paletteVariables(PALETTES.dark))) {
      expect(script).toContain(variable);
    }
  });

  it("carries every palette, and the dark one is really dark", () => {
    const payload = /var P=(\{.*?\}),K=/.exec(script);
    expect(payload).not.toBeNull();
    const palettes = JSON.parse((payload as RegExpExecArray)[1] as string) as Record<
      string,
      Record<string, string>
    >;
    // 🔴 DERIVED FROM `PALETTES`, NOT A LIST TYPED OUT HERE.
    //
    // It used to name the four literally, and that is why `patriot` could be
    // added to THEMES while the pre-paint script did not carry it — this test
    // would have gone on passing over a theme that flashed the default on
    // every load, because the script applies the palette BEFORE React
    // hydrates and a missing one simply does nothing.
    //
    // The type system caught it first (`PALETTES` is an exhaustive Record over
    // ThemeId), which is the better guard. This is the second one, and it now
    // compares against the source of truth instead of a copy.
    expect(Object.keys(palettes).sort()).toEqual(Object.keys(PALETTES).sort());
    expect(palettes["dark"]?.[CSS_VARIABLES.white]).toBe(PALETTES.dark.white);
  });

  it("is one self-contained expression that cannot throw out of the document", () => {
    // It runs before anything else exists. `localStorage` throws outright in
    // some private windows, and an exception here would be an unstyled page.
    expect(script.startsWith("(function(){try{")).toBe(true);
    expect(script.endsWith("}catch(e){}})();")).toBe(true);
  });
});

describe("the grounds an alert sits on", () => {
  it("🔴 every accent ground is visible against its own page", () => {
    // 🔴 THE PAPER THEME ERASED THEM AND NOTHING NOTICED.
    //
    // `warmed()` mixed each accent `50` 55% into the paper surface. Both are
    // near-white and the surface is the DARKER of the two, so every alert fill
    // landed on the page's own luminance: red 1.007:1, orange 1.004:1 — a
    // two-in-255 difference in one channel. A red notice and an amber one
    // became identical by fill. The Supervisor measured it; no test could,
    // because every assertion here compared text to a ground and none compared
    // the ground to the page.
    //
    // 1.02 is deliberately a floor and not a target: `bg-red-50` on white is
    // only 1.12:1 and always has been. What this refuses is a fill that is not
    // there at all.
    const failures: string[] = [];

    for (const [name, palette] of Object.entries(PALETTES)) {
      for (const hue of ACCENT_NAMES) {
        const ratio = contrast(palette.accents[hue]["50"], palette.white);
        if (ratio < 1.02) {
          failures.push(`${name}: bg-${hue}-50 on the page = ${ratio.toFixed(3)}:1`);
        }
      }
    }

    expect(
      failures.sort(),
      "an alert fill this close to the page is not a fill — the notice loses " +
        "its shape and two different kinds of message become the same colour",
    ).toEqual([]);
  });

  it("🔴 the status colours clear AA on the grounds they are painted on, not only on the page", () => {
    // The pairing that broke twice: `StatusBadge` puts `text-status-pass` on
    // `bg-emerald-50`, `text-status-fail` on `bg-red-50`,
    // `text-status-conditional` on `bg-amber-50`. Measuring status against
    // `palette.white` said all three were fine while they were 1.65, 2.53 and
    // 1.61 on dark, and 4.08/4.82/4.09 on paper.
    const ON: ReadonlyArray<readonly [keyof typeof PALETTES.light.status, AccentName]> = [
      ["pass", "emerald"],
      ["fail", "red"],
      ["conditional", "amber"],
      ["invalid", "red"],
    ];
    const failures: string[] = [];

    for (const [name, palette] of Object.entries(PALETTES)) {
      for (const [status, hue] of ON) {
        const ratio = contrast(palette.status[status], palette.accents[hue]["50"]);
        if (ratio < 4.5) {
          failures.push(`${name}: status-${status} on bg-${hue}-50 = ${ratio.toFixed(2)}:1`);
        }
      }
    }

    expect(failures.sort()).toEqual([]);
  });
});

describe("the ramps cover what the product paints with", () => {
  /** Every colour utility in the source, whatever hue it names. */
  function colourUtilities(): Map<string, string[]> {
    const found = new Map<string, string[]>();
    const roots = [join(__dirname, "..", "app"), join(__dirname, "..", "components")];
    const pattern =
      /\b(?:bg|text|border|ring|fill|divide|placeholder|decoration|outline|accent|caret|from|via|to)-([a-z]+)-(\d{2,3})\b/g;

    for (const root of roots) {
      for (const file of sources(root)) {
        const text = readFileSync(file, "utf8");
        for (const match of text.matchAll(pattern)) {
          const key = `${match[1] as string}-${match[2] as string}`;
          const where = found.get(key) ?? [];
          where.push(file.replace(/\\/g, "/").split("/apps/web/")[1] ?? file);
          found.set(key, where);
        }
      }
    }
    return found;
  }

  it("finds the utilities it is meant to be checking", () => {
    // The guard on the guard: a regex that stops matching turns the assertion
    // below into a test that proves nothing.
    expect(colourUtilities().size).toBeGreaterThan(15);
  });

  it("🔴 no component paints with a hue or step no palette defines", () => {
    // 🔴 THE FILE'S OWN THESIS HAD NO REGRESSION GUARD. `theme.ts` says "a
    // partial theme is a theme with a lie in its header" and then defines the
    // ramps as two hand-written lists. The moment somebody writes
    // `text-red-600` or `bg-blue-50`, Tailwind's deep merge keeps the literal —
    // the half-theme returns — AND `resolve()` above returns null, so the
    // pairing scan silently steps past it. Two mechanisms failing in the same
    // direction, quietly. The Supervisor found that nothing asserted it.
    const known = new Set<string>();
    for (const hue of ACCENT_NAMES) {
      for (const step of ACCENT_STEPS) known.add(`${hue}-${step}`);
    }
    for (const step of ["50", "100", "200", "300", "400", "500", "600", "700", "800", "900", "950"]) {
      known.add(`slate-${step}`);
    }

    const unthemed = [...colourUtilities().entries()]
      .filter(([token]) => !known.has(token))
      .map(([token, where]) => `${token} (${[...new Set(where)].sort().join(", ")})`);

    expect(
      unthemed.sort(),
      "these resolve to Tailwind's own literal on every theme, because a " +
        "colour scale given only some steps is DEEP-MERGED rather than " +
        "replaced. Add the hue to ACCENT_NAMES or the step to ACCENT_STEPS in " +
        "lib/theme.ts, or use a step the palette already defines",
    ).toEqual([]);
  });
});

describe("the pairings a parent and a child make", () => {
  /**
   * 🔴 THE LITERAL-SCOPED SCAN MISSES THE COMMONEST SHAPE IN THIS PRODUCT.
   *
   * `pairings()` above only pairs a `bg-` with a foreground found in the SAME
   * quoted string. That catches `StatusBadge`, whose whole pairing is one
   * literal — and misses a parent `bg-red-50` with `text-status-fail` on a
   * child, and misses the two halves of a `[…].join(" ")`. The Supervisor
   * named two live examples: `formula-detail.tsx` and `project-detail.tsx`,
   * both status-colour-on-accent-ground, both invisible to it.
   *
   * This pairs, WITHIN ONE FILE, every accent ground against every status and
   * accent foreground that file also names. It is deliberately coarser: a file
   * that uses `bg-amber-50` somewhere and `text-red-900` elsewhere will be
   * measured as though they met. That is acceptable here because both are
   * foreground-on-tint pairings the themes must keep readable anyway — and it
   * is NOT acceptable in the literal-scoped test above, where a false positive
   * would fail a suite over a pairing nobody renders.
   */
  function fileScoped(): { file: string; ground: string; ink: string }[] {
    const found: { file: string; ground: string; ink: string }[] = [];
    const roots = [join(__dirname, "..", "app"), join(__dirname, "..", "components")];
    const groundPattern = new RegExp(`\\bbg-(${ACCENT_NAMES.join("|")})-50\\b`, "g");
    const inkPattern = new RegExp(
      `\\btext-(?:status-(?:pass|fail|conditional|invalid|neutral)|(?:${ACCENT_NAMES.join("|")})-(?:700|800|900))\\b`,
      "g",
    );

    for (const root of roots) {
      for (const file of sources(root)) {
        const text = readFileSync(file, "utf8");
        const grounds = [...new Set([...text.matchAll(groundPattern)].map((m) => m[0] as string))];
        if (grounds.length === 0) continue;
        const inks = [...new Set([...text.matchAll(inkPattern)].map((m) => m[0] as string))];
        for (const ground of grounds) {
          const hue = ground.slice("bg-".length, -"-50".length);
          for (const ink of inks) {
            // ⚠️ SAME HUE, OR A STATUS INK. The first version paired every
            // ground in a file with every ink in it, and immediately reported
            // `text-amber-700` on `bg-purple-50` — a pairing no component
            // renders, reddening a suite over nothing. A status colour really
            // does go on all three grounds (`StatusBadge`), and an accent ink
            // really does go on its own; a red ink on a purple fill does not.
            if (!ink.startsWith(`text-${hue}-`) && !ink.startsWith("text-status-")) continue;
            found.push({ file: file.replace(/\\/g, "/"), ground, ink });
          }
        }
      }
    }
    return found;
  }

  it("finds the parent/child pairings the literal scan cannot see", () => {
    expect(fileScoped().length).toBeGreaterThan(10);
  });

  it("🔴 a foreground on an accent ground clears AA wherever the two share a file", () => {
    const failures: string[] = [];

    for (const [name, palette] of Object.entries(PALETTES)) {
      for (const pair of fileScoped()) {
        const background = resolve(pair.ground, palette);
        const foreground = resolve(pair.ink, palette);
        if (background === null || foreground === null) continue;

        const ratio = contrast(foreground, background);
        if (ratio < 4.5) {
          failures.push(`${name}: ${pair.ink} on ${pair.ground} = ${ratio.toFixed(2)}:1`);
        }
      }
    }

    expect([...new Set(failures)].sort()).toEqual([]);
  });
});
