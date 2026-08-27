/**
 * Themes — five options, and the palettes behind them.
 *
 * 🔴 WHY THIS WORKS WITHOUT TOUCHING A SINGLE COMPONENT.
 *
 * Measured across `app/` and `components/`, this application draws from a very
 * small palette: `white` and `slate-50…900` as background, text and border,
 * plus the four traffic-light tokens. `text-slate-600` alone appears 247 times.
 *
 * So the themes redefine THE SCALE rather than the call sites. `tailwind.config`
 * resolves each slate step to a CSS custom property, a theme sets those
 * properties on `<html>`, and every existing `bg-white` / `text-slate-600` /
 * `border-slate-200` follows. No component knows a theme exists — which is also
 * why a component cannot opt out of one and quietly stay light.
 *
 * ⚠️ THIS IS NOT `packages/design-tokens`, AND MUST NOT BE MISTAKEN FOR IT.
 * Extension slice E5 builds a real token layer — primitive → semantic →
 * component, exported to a Tailwind preset, with Storybook and per-story
 * axe-core. This is the interim: one ramp, remapped. When E5 lands, these
 * palettes become token sets and this file goes away.
 *
 * 🔴 THE STATUS COLOURS NEEDED A SECOND SET, AND THE TEST IS WHAT FOUND OUT.
 *
 * The first version of this file kept §10's four traffic-light colours fixed
 * across all five themes, arguing that they are validated by measurement — pass
 * vs fail is deltaE 4.2 under deuteranopia — and that re-tinting them would
 * invalidate that. `theme.test.ts` was written to check the claim rather than
 * rest on it, and refused it immediately:
 *
 *     pass on dark: 3.56:1     fail on dark: 2.76:1
 *     conditional on dark: 3.63:1   neutral on dark: 2.25:1
 *
 * Those four are chosen for a WHITE surface. On the dark surface they are below
 * AA — the traffic light would have been the least readable thing on the
 * screen, on the theme most likely to be used at the end of a long day, and the
 * existing accessibility sweep would never have seen it because it runs against
 * the default theme only.
 *
 * So there are two sets: the validated light-surface one, unchanged, and a
 * dark-surface one at the SAME HUES with lightness raised (measured: 10.25,
 * 6.45, 10.69 and 6.97 against the dark surface).
 *
 * ⚠️ AND THE deltaE MEASUREMENT HAS NOT BEEN REDONE FOR THE DARK SET. It was
 * made for the light one. The hues are preserved, so the separation should hold
 * — "should" is not "measured", and this is written down rather than assumed.
 * What carries the weight meanwhile is §10's actual rule, which has never been
 * colour: every status renders colour + icon + TEXT, so a reader who cannot
 * separate the hues still reads the word.
 */

/**
 * §10's four traffic-light colours, for one surface.
 *
 * Named by MEANING and not by colour, exactly as `tailwind.config` has them —
 * so a component cannot ask for "green" for a result that is only technically
 * passing and not yet approved.
 */
export interface StatusColours {
  readonly pass: string;
  readonly fail: string;
  readonly conditional: string;
  readonly invalid: string;
  readonly neutral: string;
}

/**
 * The validated light-surface set, unchanged from `tailwind.config`.
 *
 * `invalid` shares the fail hue deliberately: the domain has THREE states and
 * ADR-015 routes invalid to RED. A fourth hue would imply a fourth state.
 */
const STATUS_ON_LIGHT: StatusColours = {
  pass: "21 128 61",
  fail: "185 28 28",
  conditional: "161 98 7",
  invalid: "185 28 28",
  neutral: "82 81 78",
};

/** The same hues, lifted for a dark surface. Ratios measured, not estimated. */
const STATUS_ON_DARK: StatusColours = {
  pass: "74 222 128",
  fail: "248 113 113",
  conditional: "251 191 36",
  invalid: "248 113 113",
  neutral: "161 161 170",
};

/** The slate ramp plus the surface, as `R G B` triples for `rgb()`. */
export interface Palette {
  readonly status: StatusColours;
  readonly white: string;
  readonly slate50: string;
  readonly slate100: string;
  readonly slate200: string;
  readonly slate300: string;
  readonly slate400: string;
  readonly slate500: string;
  readonly slate600: string;
  readonly slate700: string;
  readonly slate800: string;
  readonly slate900: string;
}

export interface Theme {
  readonly id: ThemeId;
  readonly label: string;
  /** One line a person can choose by, not a restatement of the name. */
  readonly description: string;
  /**
   * The palette, or null for `system`, which resolves to `light` or `dark`
   * from `prefers-color-scheme` and therefore has no palette of its own.
   */
  readonly palette: Palette | null;
}

export type ThemeId = "system" | "light" | "dark" | "contrast" | "paper";

/**
 * The default. Identical to Tailwind's own slate, so an application with no
 * stored preference looks exactly as it did before themes existed — and
 * `theme.test.ts` asserts `globals.css`'s `:root` block still matches it.
 */
const LIGHT: Palette = {
  status: STATUS_ON_LIGHT,
  white: "255 255 255",
  slate50: "248 250 252",
  slate100: "241 245 249",
  slate200: "226 232 240",
  slate300: "203 213 225",
  slate400: "148 163 184",
  slate500: "100 116 139",
  slate600: "71 85 105",
  slate700: "51 65 85",
  slate800: "30 41 59",
  slate900: "15 23 42",
};

/**
 * The ramp reversed, not merely darkened.
 *
 * 🔴 `bg-slate-900` IS THE PRIMARY BUTTON AND `text-white` IS ITS LABEL.
 * Inverting the scale turns that button light with dark text, which is correct
 * — a primary control has to stay the most prominent thing on the surface, and
 * on a dark page that means light. The alternative, darkening every step
 * uniformly, leaves the button invisible against the page.
 */
const DARK: Palette = {
  status: STATUS_ON_DARK,
  white: "15 23 42",
  slate50: "30 41 59",
  slate100: "38 50 68",
  slate200: "51 65 85",
  slate300: "71 85 105",
  slate400: "100 116 139",
  slate500: "148 163 184",
  slate600: "203 213 225",
  slate700: "226 232 240",
  slate800: "241 245 249",
  slate900: "248 250 252",
};

/**
 * Maximum separation, for low vision and for glare.
 *
 * Every text step clears 7:1 on the surface rather than the 4.5:1 WCAG AA asks
 * for — measured in `theme.test.ts`, not estimated. `slate-300` is the border
 * step and is the only one held at the AA threshold, because a border is not
 * text.
 */
const CONTRAST: Palette = {
  status: STATUS_ON_LIGHT,
  white: "255 255 255",
  slate50: "242 242 242",
  slate100: "212 212 212",
  slate200: "148 148 148",
  slate300: "118 118 118",
  slate400: "89 89 89",
  slate500: "51 51 51",
  slate600: "26 26 26",
  slate700: "17 17 17",
  slate800: "10 10 10",
  slate900: "0 0 0",
};

/**
 * Warm and low-glare, for reading long technical text on a bright bench.
 *
 * Not a decorative choice: this application is used beside a screen full of
 * white laboratory surfaces, and a pure-white page next to that is the one
 * complaint a paper-like theme actually answers.
 */
const PAPER: Palette = {
  status: STATUS_ON_LIGHT,
  white: "250 246 238",
  slate50: "243 237 225",
  slate100: "235 227 212",
  slate200: "221 211 192",
  slate300: "201 189 166",
  slate400: "140 128 106",
  slate500: "99 88 71",
  slate600: "74 65 52",
  slate700: "58 50 40",
  slate800: "40 34 27",
  slate900: "28 24 18",
};

/**
 * The five, in the order they are offered.
 *
 * `system` first because it is the answer most people want and the only one
 * that keeps following the machine after it is chosen.
 */
export const THEMES: readonly Theme[] = [
  {
    id: "system",
    label: "Match my system",
    description: "Follows the light or dark setting of this computer, and keeps following it.",
    palette: null,
  },
  {
    id: "light",
    label: "Light",
    description: "The default. Neutral grey on white, for a bright room.",
    palette: LIGHT,
  },
  {
    id: "dark",
    label: "Dark",
    description: "The same layout on a dark surface, for a dim room or a long session.",
    palette: DARK,
  },
  {
    id: "contrast",
    label: "High contrast",
    description: "Maximum separation between text and surface. Every text step clears 7:1.",
    palette: CONTRAST,
  },
  {
    id: "paper",
    label: "Paper",
    description: "Warm and low-glare, for reading long technical text under bench lighting.",
    palette: PAPER,
  },
];

export const DEFAULT_THEME: ThemeId = "system";

/** The palettes a theme can actually resolve to. Exported for the contrast test. */
export const PALETTES: Readonly<Record<Exclude<ThemeId, "system">, Palette>> = {
  light: LIGHT,
  dark: DARK,
  contrast: CONTRAST,
  paper: PAPER,
};

export function isThemeId(value: string): value is ThemeId {
  return THEMES.some((theme) => theme.id === value);
}

/**
 * Which palette a chosen theme actually paints with.
 *
 * `system` is not a palette. It resolves against `prefers-color-scheme` at the
 * moment it is asked, which is why this takes the answer rather than reading
 * `matchMedia` itself — the same function then works in a test, on the server,
 * and inside the pre-paint script that has no React.
 */
export function resolvePalette(theme: ThemeId, prefersDark: boolean): Palette {
  if (theme === "system") {
    return prefersDark ? DARK : LIGHT;
  }
  return PALETTES[theme];
}

/** The CSS custom-property name for each palette entry. */
export const CSS_VARIABLES: Readonly<Record<Exclude<keyof Palette, "status">, string>> = {
  white: "--surface",
  slate50: "--slate-50",
  slate100: "--slate-100",
  slate200: "--slate-200",
  slate300: "--slate-300",
  slate400: "--slate-400",
  slate500: "--slate-500",
  slate600: "--slate-600",
  slate700: "--slate-700",
  slate800: "--slate-800",
  slate900: "--slate-900",
};

/** The CSS custom-property name for each status colour. */
export const STATUS_VARIABLES: Readonly<Record<keyof StatusColours, string>> = {
  pass: "--status-pass",
  fail: "--status-fail",
  conditional: "--status-conditional",
  invalid: "--status-invalid",
  neutral: "--status-neutral",
};

/* -------------------------------------------------------------------------- */
/* Contrast                                                                    */
/* -------------------------------------------------------------------------- */

/**
 * WCAG relative luminance of an `R G B` triple.
 *
 * 🔴 COMPUTED, NOT EYEBALLED. This project has already shipped a sidebar at
 * 1.48:1 under a comment claiming it was legible, and axe-core could not see it
 * because `aria-disabled` silences the contrast rule. A palette chosen by eye
 * is the same mistake with four times the surface area, so every theme's ratios
 * are asserted in `theme.test.ts`.
 */
export function luminance(triple: string): number {
  const channels = triple.split(/\s+/).map((value) => {
    const srgb = Number(value) / 255;
    return srgb <= 0.03928 ? srgb / 12.92 : ((srgb + 0.055) / 1.055) ** 2.4;
  });
  const [r, g, b] = channels;
  if (r === undefined || g === undefined || b === undefined) {
    throw new Error(`not an "R G B" triple: ${triple}`);
  }
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

/** WCAG contrast ratio between two `R G B` triples. */
export function contrast(a: string, b: string): number {
  const first = luminance(a);
  const second = luminance(b);
  const lighter = Math.max(first, second);
  const darker = Math.min(first, second);
  return (lighter + 0.05) / (darker + 0.05);
}
