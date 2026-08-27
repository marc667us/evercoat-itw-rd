import type { Config } from "tailwindcss";

import {
  ACCENT_NAMES,
  ACCENT_STEPS,
  CSS_VARIABLES,
  PALETTES,
  STATUS_VARIABLES,
  accentVariable,
} from "./lib/theme";

/**
 * 🔴 THE PALETTE RESOLVES THROUGH CSS VARIABLES, WHICH IS WHAT MAKES THEMES
 * POSSIBLE WITHOUT EDITING 900 CALL SITES.
 *
 * Measured across `app/` and `components/`: this application draws from
 * `white`, `slate-50…950`, the four traffic-light tokens, and seven accent
 * ramps — `text-slate-600` alone appears 247 times, `text-slate-900` 166,
 * `bg-white` 67, and the accents another 129 between them. Every one of those
 * resolves here, so redefining the variables on `<html>` re-themes the whole
 * product and no component knows a theme exists.
 *
 * ⚠️ EVERY VARIABLE CARRIES ITS LIGHT VALUE AS A FALLBACK, and that is not
 * belt-and-braces. This is a STATIC EXPORT: the HTML is served before any
 * script runs. A pre-paint script in `app/layout.tsx` now sets the properties
 * before first paint, but it is a script — with JavaScript disabled, or if it
 * throws, there would be no custom properties at all and every colour would
 * resolve to nothing. The fallbacks ARE the light theme, which is also the
 * default.
 *
 * 🔴 `white` IS REDEFINED AND THAT IS DELIBERATE. `bg-white` is the card
 * surface and `text-white` is the primary button's label; on a dark theme both
 * have to move or the surface stays white and the label disappears. It is named
 * `--surface` rather than `--white` because on the dark palette it is not
 * white — a variable called `--white` holding `15 23 42` is the kind of name
 * that survives into a bug report.
 *
 * 🔴 THE FALLBACKS ARE IMPORTED, NOT COPIED, AND THAT IS THE POINT.
 *
 * The first version wrote every triple out by hand under a comment claiming
 * *"`theme.test.ts` asserts the fallbacks below match the LIGHT palette"* — a
 * drift guard that did not exist. The Supervisor found it. Two literals in two
 * files cannot be type-checked into agreement, and a test that compares them is
 * strictly worse than not having two: this file now reads `PALETTES.light`, so
 * there is one definition and nothing to drift. `theme.test.ts` still measures
 * the resolved config, so a future hand-written value is caught rather than
 * assumed impossible.
 */
const L = PALETTES.light;

/** `rgb(var(--x, <light value>) / <alpha-value>)`, the one shape used below. */
function token(variable: string, fallback: string): string {
  return `rgb(var(${variable}, ${fallback}) / <alpha-value>)`;
}

const slate = {
  50: token(CSS_VARIABLES.slate50, L.slate50),
  100: token(CSS_VARIABLES.slate100, L.slate100),
  200: token(CSS_VARIABLES.slate200, L.slate200),
  300: token(CSS_VARIABLES.slate300, L.slate300),
  400: token(CSS_VARIABLES.slate400, L.slate400),
  500: token(CSS_VARIABLES.slate500, L.slate500),
  600: token(CSS_VARIABLES.slate600, L.slate600),
  700: token(CSS_VARIABLES.slate700, L.slate700),
  800: token(CSS_VARIABLES.slate800, L.slate800),
  900: token(CSS_VARIABLES.slate900, L.slate900),
  // 🔴 950 IS HERE BECAUSE IT WAS MISSING AND ONE CALL SITE STAYED LITERAL.
  // Tailwind DEEP-MERGES a partial colour scale, so listing 50…900 left
  // `slate-950` resolving to its built-in `#020617` — near-black text on a
  // near-black page under the dark theme, in `components/msd/msd-panel.tsx`.
  // An incomplete scale does not fail; it silently keeps the original. The
  // Supervisor found it, and `theme.test.ts` now asserts the other direction:
  // every variable a theme sets must be reachable from some utility.
  950: token(CSS_VARIABLES.slate950, L.slate950),
};

/**
 * The accent ramps, generated from the same list the palettes are built from.
 *
 * Written by hand this is 49 entries, each a chance to pair `--rose-300` with
 * `rose.200` — and nothing would notice until one border went the wrong colour
 * on one theme.
 */
const accents = Object.fromEntries(
  ACCENT_NAMES.map((name) => [
    name,
    Object.fromEntries(
      ACCENT_STEPS.map((step) => [step, token(accentVariable(name, step), L.accents[name][step])]),
    ),
  ]),
);

export default {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./features/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        white: token(CSS_VARIABLES.white, L.white),
        slate,
        ...accents,
        // Traffic-light tokens. Named by MEANING, not by colour, so a
        // component cannot render "green" for a result that is only
        // technically passing but not yet approved (CLAUDE.md §10).
        // Validated, not chosen by eye. Measured on the light surface,
        // pass vs fail is deltaE 4.2 under deuteranopia -- roughly 8% of
        // men cannot tell them apart by hue. That is the measurement
        // behind CLAUDE.md 10's colour + icon + text rule, and why
        // components take domain state rather than a colour prop.
        //
        // `invalid` shares the fail hue deliberately: the domain has
        // THREE states and ADR-015 routes invalid to RED. A fourth hue
        // would imply a fourth state, and the darker red tried first
        // failed the lightness band at L 0.396.
        //
        // 🔴 THESE MOVE WITH THE SURFACE NOW, AND THE TEST IS WHY. Held fixed
        // across all five themes they measured 3.56, 2.76, 3.63 and 2.25 on the
        // dark surface -- below AA, on the traffic light, on the theme most
        // likely to be used late in the day. The dark set keeps the same hues
        // with lightness raised; the fallbacks here are the validated light set.
        status: {
          pass: token(STATUS_VARIABLES.pass, L.status.pass),
          fail: token(STATUS_VARIABLES.fail, L.status.fail),
          conditional: token(STATUS_VARIABLES.conditional, L.status.conditional),
          invalid: token(STATUS_VARIABLES.invalid, L.status.invalid),
          neutral: token(STATUS_VARIABLES.neutral, L.status.neutral),
        },
      },
    },
  },
  plugins: [],
} satisfies Config;
