/**
 * Themes — five options, and the palettes behind them.
 *
 * 🔴 WHY THIS WORKS WITHOUT TOUCHING A SINGLE COMPONENT.
 *
 * Measured across `app/` and `components/`, this application draws from a small
 * palette: `white` and `slate-50…950` as background, text and border, the four
 * traffic-light tokens, and seven accent ramps used for notices and alert boxes.
 * `text-slate-600` alone appears 247 times.
 *
 * So the themes redefine THE SCALES rather than the call sites. `tailwind.config`
 * resolves each step to a CSS custom property, a theme sets those properties on
 * `<html>`, and every existing `bg-white` / `text-slate-600` / `bg-red-50`
 * follows. No component knows a theme exists.
 *
 * 🔴 AND THE FIRST VERSION OF THAT SENTENCE WAS FALSE FOR 129 CALL SITES.
 *
 * It said "no component knows a theme exists — which is also why a component
 * cannot opt out of one and quietly stay light", over a file that themed only
 * `white` and `slate-50…900`. Everything else stayed literal: every
 * `bg-red-50` alert box, every `border-amber-300`, `slate-950`, and — worst —
 * `StatusBadge`, whose `bg-emerald-50` ground stayed light while its
 * `text-status-pass` had just been LIGHTENED for a dark surface. Measured on
 * the badge's own ground rather than on the page: **1.65:1 for pass, 2.53:1 for
 * fail, 1.61:1 for conditional.** The contrast test did not see it because it
 * measured status colours against `palette.white`, which is not what a badge
 * sits on. Both reviewers found it independently.
 *
 * A partial theme is a theme with a lie in its header. Every ramp the product
 * actually paints with is now themed, and `theme.test.ts` measures the PAIRS
 * that appear together in the source rather than text-on-surface alone.
 *
 * ⚠️ THIS IS NOT `packages/design-tokens`, AND MUST NOT BE MISTAKEN FOR IT.
 * Extension slice E5 builds a real token layer — primitive → semantic →
 * component, exported to a Tailwind preset, with Storybook and per-story
 * axe-core. This is the interim: the ramps, remapped. When E5 lands, these
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

/* -------------------------------------------------------------------------- */
/* The accent ramps                                                            */
/* -------------------------------------------------------------------------- */

/**
 * The seven hues this product paints with beyond slate, measured from source.
 *
 * Not "the ones Tailwind ships" — the ones actually used. `red` and `amber`
 * carry alerts and warnings, `emerald` carries the pass badge, and `purple`,
 * `sky`, `rose` and `orange` distinguish record kinds in the knowledge and MSD
 * surfaces. A hue nothing uses would be a variable set on every page load for
 * nothing.
 */
export const ACCENT_NAMES = ["red", "amber", "emerald", "purple", "sky", "rose", "orange"] as const;
export type AccentName = (typeof ACCENT_NAMES)[number];

/**
 * The steps used, in lightness order.
 *
 * 🔴 THESE ARE THE STEPS THE SOURCE NAMES, NOT A TIDY SUBSET. `border-amber-400`
 * appears once and `text-red-800` twice; dropping either would mean two call
 * sites silently keeping Tailwind's literal value while the rest of their own
 * ramp moved — which is the half-theme this whole change exists to end.
 */
export const ACCENT_STEPS = ["50", "200", "300", "400", "700", "800", "900"] as const;
export type AccentStep = (typeof ACCENT_STEPS)[number];

export type Accent = Readonly<Record<AccentStep, string>>;
export type Accents = Readonly<Record<AccentName, Accent>>;

/** Tailwind's own values for every step this product uses. The default must not move. */
const ACCENTS_ON_LIGHT: Accents = {
  red: {
    "50": "254 242 242",
    "200": "254 202 202",
    "300": "252 165 165",
    "400": "248 113 113",
    "700": "185 28 28",
    "800": "153 27 27",
    "900": "127 29 29",
  },
  amber: {
    "50": "255 251 235",
    "200": "253 230 138",
    "300": "252 211 77",
    "400": "251 191 36",
    "700": "180 83 9",
    "800": "146 64 14",
    "900": "120 53 15",
  },
  emerald: {
    "50": "236 253 245",
    "200": "167 243 208",
    "300": "110 231 183",
    "400": "52 211 153",
    "700": "4 120 87",
    "800": "6 95 70",
    "900": "6 78 59",
  },
  purple: {
    "50": "250 245 255",
    "200": "233 213 255",
    "300": "216 180 254",
    "400": "192 132 252",
    "700": "126 34 206",
    "800": "107 33 168",
    "900": "88 28 135",
  },
  sky: {
    "50": "240 249 255",
    "200": "186 230 253",
    "300": "125 211 252",
    "400": "56 189 248",
    "700": "3 105 161",
    "800": "7 89 133",
    "900": "12 74 110",
  },
  rose: {
    "50": "255 241 242",
    "200": "254 205 211",
    "300": "253 164 175",
    "400": "251 113 133",
    "700": "190 18 60",
    "800": "159 18 57",
    "900": "136 19 55",
  },
  orange: {
    "50": "255 247 237",
    "200": "254 215 170",
    "300": "253 186 116",
    "400": "251 146 60",
    "700": "194 65 12",
    "800": "154 52 18",
    "900": "124 45 18",
  },
};

/**
 * The two steps beyond the ones the product names, per hue.
 *
 * 🔴 THE REVERSAL NEEDED MORE ROOM THAN THE PRODUCT'S OWN STEPS GAVE IT, AND
 * THE PAIRING TEST IS WHAT SAID SO.
 *
 * Reversing `50…900` onto itself put the dark alert ground at the hue's `900`,
 * and `text-status-fail` on that ground measured **3.62:1** — below AA, on the
 * fail badge, which is the single element in this product that most has to be
 * read correctly. That is the same defect Codex found one layer down, caught
 * this time by measurement rather than by a reviewer.
 *
 * `950` is dark enough to hold light text and `100` is light enough to be it,
 * and both are values Tailwind already ships for that hue — so the dark theme
 * still invents no colour.
 */
const ACCENT_ENDS: Readonly<Record<AccentName, { readonly "100": string; readonly "950": string }>> =
  {
    red: { "100": "254 226 226", "950": "69 10 10" },
    amber: { "100": "254 243 199", "950": "69 26 3" },
    emerald: { "100": "209 250 229", "950": "2 44 34" },
    purple: { "100": "243 232 255", "950": "59 7 100" },
    sky: { "100": "224 242 254", "950": "8 47 73" },
    rose: { "100": "255 228 230", "950": "76 5 25" },
    orange: { "100": "255 237 213", "950": "67 20 7" },
  };

/**
 * The dark accent set: each ramp REVERSED within its own hue.
 *
 * 🔴 A REVERSAL RATHER THAN A RE-TINT, FOR THE SAME REASON THE SLATE RAMP IS
 * REVERSED. `bg-red-50` is the ground an alert sits on and `text-red-900` is
 * its text; on a dark surface the ground has to become the dark end and the
 * text the light end, or the box stays a white rectangle on a dark page. Every
 * pairing in the source is (light step, dark step) of one hue, so swapping the
 * ends keeps every pair readable while moving the box onto the page.
 *
 * `400` is the axis of the reversal and stays where it is.
 */
function reversed(name: AccentName): Accent {
  const accent = ACCENTS_ON_LIGHT[name];
  const ends = ACCENT_ENDS[name];
  return {
    "50": ends["950"],
    "200": accent["900"],
    "300": accent["800"],
    "400": accent["400"],
    "700": accent["300"],
    "800": accent["200"],
    "900": ends["100"],
  };
}

/** Mix two `R G B` triples in sRGB space. `t = 0` is `a`, `t = 1` is `b`. */
function mix(a: string, b: string, t: number): string {
  const left = a.split(/\s+/).map(Number);
  const right = b.split(/\s+/).map(Number);
  return [0, 1, 2]
    .map((i) => Math.round((left[i] ?? 0) * (1 - t) + (right[i] ?? 0) * t))
    .join(" ");
}

const BLACK = "0 0 0";

/**
 * High contrast: the grounds stay pale, the text and borders go much darker.
 *
 * The hue is kept because it is doing work — a red notice and an amber one are
 * different kinds of message, and this theme exists for low vision, not for
 * monochrome. What changes is separation.
 */
function hardened(name: AccentName): Accent {
  const accent = ACCENTS_ON_LIGHT[name];
  return {
    "50": accent["50"],
    "200": mix(accent["200"], BLACK, 0.3),
    "300": mix(accent["300"], BLACK, 0.4),
    "400": mix(accent["400"], BLACK, 0.45),
    "700": mix(accent["700"], BLACK, 0.35),
    "800": mix(accent["800"], BLACK, 0.4),
    "900": mix(accent["900"], BLACK, 0.45),
  };
}

const PAPER_SURFACE = "250 246 238";

/**
 * Paper: the grounds warmed toward the page, the text left alone.
 *
 * A `bg-red-50` box on a warm page is the one thing that gives this theme away
 * if it is not adjusted — a cool white-pink rectangle on cream reads as a
 * rendering fault. The ink steps are already dark enough on a light ground and
 * moving them would cost contrast for nothing.
 */
function warmed(name: AccentName): Accent {
  const accent = ACCENTS_ON_LIGHT[name];
  return {
    "50": mix(accent["50"], PAPER_SURFACE, 0.55),
    "200": mix(accent["200"], PAPER_SURFACE, 0.3),
    "300": mix(accent["300"], PAPER_SURFACE, 0.2),
    "400": accent["400"],
    "700": accent["700"],
    "800": accent["800"],
    "900": accent["900"],
  };
}

function mapAccents(transform: (name: AccentName) => Accent): Accents {
  return Object.fromEntries(ACCENT_NAMES.map((name) => [name, transform(name)])) as Accents;
}

/** The slate ramp, the surface and the accents, as `R G B` triples for `rgb()`. */
export interface Palette {
  readonly status: StatusColours;
  readonly accents: Accents;
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
  /**
   * ⚠️ `slate-950` IS ONE CALL SITE AND IT WAS MISSED BY THE FIRST VERSION.
   *
   * `components/msd/msd-panel.tsx` uses it, and a deep merge of Tailwind's own
   * slate scale kept `#020617` there while every other step became a variable —
   * so on the dark theme that one element stayed near-black on a near-black
   * page. The Supervisor found it. One call site is still a call site.
   */
  readonly slate950: string;
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
 * `theme.test.ts` asserts `tailwind.config.ts`'s fallbacks still match it.
 */
const LIGHT: Palette = {
  status: STATUS_ON_LIGHT,
  accents: ACCENTS_ON_LIGHT,
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
  slate950: "2 6 23",
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
  accents: mapAccents(reversed),
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
  // Past the end of the reversed ramp, and therefore lighter than `slate900`.
  // Anything else breaks the monotonicity the whole hierarchy is built on.
  slate950: "255 255 255",
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
  accents: mapAccents(hardened),
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
  slate950: "0 0 0",
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
  accents: mapAccents(warmed),
  white: PAPER_SURFACE,
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
  slate950: "18 15 10",
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
 * and inside the pre-paint script in `app/layout.tsx`, which has no React.
 */
export function resolvePalette(theme: ThemeId, prefersDark: boolean): Palette {
  if (theme === "system") {
    return prefersDark ? DARK : LIGHT;
  }
  return PALETTES[theme];
}

/** The CSS custom-property name for each slate/surface entry. */
export const CSS_VARIABLES: Readonly<
  Record<Exclude<keyof Palette, "status" | "accents">, string>
> = {
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
  slate950: "--slate-950",
};

/** The CSS custom-property name for each status colour. */
export const STATUS_VARIABLES: Readonly<Record<keyof StatusColours, string>> = {
  pass: "--status-pass",
  fail: "--status-fail",
  conditional: "--status-conditional",
  invalid: "--status-invalid",
  neutral: "--status-neutral",
};

/**
 * The CSS custom-property name for one accent step.
 *
 * A function rather than a table because the names are mechanical — 49 hand
 * written entries would be 49 chances to write `--rose-300` beside `rose.200`,
 * and nothing would notice until a border went the wrong colour on one theme.
 */
export function accentVariable(name: AccentName, step: AccentStep): string {
  return `--${name}-${step}`;
}

/**
 * Every custom property a theme sets, as `name → value`.
 *
 * 🔴 ONE PRODUCER, TWO CONSUMERS. The React provider applies this after
 * hydration and the pre-paint script in `app/layout.tsx` applies it before
 * first paint. They must set exactly the same properties or the page changes
 * colour when React arrives — so they call this, and neither owns a list.
 */
export function paletteVariables(palette: Palette): Record<string, string> {
  const variables: Record<string, string> = {};

  for (const [key, variable] of Object.entries(CSS_VARIABLES)) {
    variables[variable] = palette[key as keyof typeof CSS_VARIABLES];
  }
  for (const [key, variable] of Object.entries(STATUS_VARIABLES)) {
    variables[variable] = palette.status[key as keyof StatusColours];
  }
  for (const name of ACCENT_NAMES) {
    for (const step of ACCENT_STEPS) {
      variables[accentVariable(name, step)] = palette.accents[name][step];
    }
  }

  return variables;
}

/* -------------------------------------------------------------------------- */
/* Before first paint                                                          */
/* -------------------------------------------------------------------------- */

/**
 * Where the chosen theme is kept.
 *
 * 🔴 IN THIS FILE RATHER THAN IN `lib/preferences.ts`, WHICH READS IT.
 * `preferences.ts` is a `"use client"` module, and the pre-paint script is
 * built by the SERVER component `app/layout.tsx`. A server component importing
 * a constant across a client boundary is a build-time reference rather than a
 * string, so the key would have had to be written out a second time — and a
 * pre-paint script reading `"evercoat.theme"` while the application wrote
 * `"evercoat.themes"` would flash the default forever and pass every test.
 */
export const THEME_STORAGE_KEY = "evercoat.theme";

/**
 * The script that themes the page BEFORE the browser paints it.
 *
 * 🔴 WITHOUT THIS, EVERY LOAD FLASHES WHITE. Both reviewers found it. The
 * fallbacks in `tailwind.config` are the LIGHT palette by design — they have to
 * be, or a page with no JavaScript would render colourless — so a reader who
 * has chosen dark got a full white page, then their theme when React hydrated.
 * On a static export served from a CDN that gap is the whole first impression,
 * and it is worst on the theme chosen by people most sensitive to a bright
 * screen.
 *
 * ⚠️ IT IS BUILT FROM `paletteVariables`, NOT FROM A SECOND LIST. The provider
 * and this script must set exactly the same properties; if they diverge the
 * page changes colour at hydration, which is the same flash in a subtler form.
 *
 * ⚠️ AND IT SWALLOWS EVERYTHING. This runs before the application exists, with
 * `localStorage` unavailable in a locked-down profile and throwing outright in
 * some private windows. A theme that cannot be read is not an error worth
 * having; it is the default. Nothing here may be allowed to stop the page.
 */
export function prePaintScript(): string {
  const palettes = Object.fromEntries(
    Object.entries(PALETTES).map(([id, palette]) => [id, paletteVariables(palette)]),
  );

  return (
    `(function(){try{` +
    `var P=${JSON.stringify(palettes)},K=${JSON.stringify(THEME_STORAGE_KEY)},t=null;` +
    `try{t=window.localStorage.getItem(K)}catch(e){}` +
    // An unknown id -- a theme a previous version of this application offered
    // -- resolves to the default rather than to nothing.
    `if(t!=="light"&&t!=="dark"&&t!=="contrast"&&t!=="paper")t="system";` +
    `var d=window.matchMedia("(prefers-color-scheme: dark)").matches;` +
    `var p=P[t==="system"?(d?"dark":"light"):t],r=document.documentElement;` +
    `for(var k in p)r.style.setProperty(k,p[k]);` +
    `r.dataset.theme=t;` +
    // `color-scheme` too, or the scrollbar and the overscroll band stay light
    // on a dark page -- and on this product the scrollbar sits beside a data
    // grid on most screens.
    `r.style.colorScheme=(t==="dark"||(t==="system"&&d))?"dark":"light";` +
    `}catch(e){}})();`
  );
}

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
