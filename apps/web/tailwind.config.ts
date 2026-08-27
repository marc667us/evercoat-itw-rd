import type { Config } from "tailwindcss";

/**
 * 🔴 THE PALETTE RESOLVES THROUGH CSS VARIABLES, WHICH IS WHAT MAKES THEMES
 * POSSIBLE WITHOUT EDITING 900 CALL SITES.
 *
 * Measured across `app/` and `components/`: this application draws almost
 * entirely from `white` and `slate-50…900` — `text-slate-600` alone appears 247
 * times, `text-slate-900` 166, `bg-white` 67. Every one of those resolves here,
 * so redefining the variables on `<html>` re-themes the whole product and no
 * component knows a theme exists.
 *
 * ⚠️ EVERY VARIABLE CARRIES ITS LIGHT VALUE AS A FALLBACK, and that is not
 * belt-and-braces. This is a STATIC EXPORT: the HTML is served before any script
 * runs, so between first paint and hydration there are no custom properties set
 * at all. Without the fallback every colour would resolve to nothing and the
 * first frame would be unreadable — text with no colour on a background with
 * none. The fallbacks ARE the light theme, which is also the default.
 *
 * 🔴 `white` IS REDEFINED AND THAT IS DELIBERATE. `bg-white` is the card
 * surface and `text-white` is the primary button's label; on a dark theme both
 * have to move or the surface stays white and the label disappears. It is named
 * `--surface` rather than `--white` because on the dark palette it is not
 * white — a variable called `--white` holding `15 23 42` is the kind of name
 * that survives into a bug report.
 *
 * `theme.test.ts` asserts the fallbacks below match the LIGHT palette in
 * `lib/theme.ts`, so the two cannot drift.
 */
const surface = "rgb(var(--surface, 255 255 255) / <alpha-value>)";

const slate = {
  50: "rgb(var(--slate-50, 248 250 252) / <alpha-value>)",
  100: "rgb(var(--slate-100, 241 245 249) / <alpha-value>)",
  200: "rgb(var(--slate-200, 226 232 240) / <alpha-value>)",
  300: "rgb(var(--slate-300, 203 213 225) / <alpha-value>)",
  400: "rgb(var(--slate-400, 148 163 184) / <alpha-value>)",
  500: "rgb(var(--slate-500, 100 116 139) / <alpha-value>)",
  600: "rgb(var(--slate-600, 71 85 105) / <alpha-value>)",
  700: "rgb(var(--slate-700, 51 65 85) / <alpha-value>)",
  800: "rgb(var(--slate-800, 30 41 59) / <alpha-value>)",
  900: "rgb(var(--slate-900, 15 23 42) / <alpha-value>)",
};

export default {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./features/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        white: surface,
        slate,
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
          pass: "rgb(var(--status-pass, 21 128 61) / <alpha-value>)",
          fail: "rgb(var(--status-fail, 185 28 28) / <alpha-value>)",
          conditional: "rgb(var(--status-conditional, 161 98 7) / <alpha-value>)",
          invalid: "rgb(var(--status-invalid, 185 28 28) / <alpha-value>)",
          neutral: "rgb(var(--status-neutral, 82 81 78) / <alpha-value>)",
        },
      },
    },
  },
  plugins: [],
} satisfies Config;
