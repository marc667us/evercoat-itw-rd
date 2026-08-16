/**
 * Chart palette and theme tokens.
 *
 * Every value here was run through the palette validator rather than
 * chosen by eye. The measurements are recorded because they are the
 * reason for the rules, not decoration.
 *
 * SERIES COLOURS — validated all-pairs, light and dark:
 *   light  #2a78d6 #eb6834 #1baf7a
 *          worst CVD ΔE 9.2 (deutan), worst normal-vision ΔE 24.0
 *   dark   #3987e5 #d95926 #199e70
 *          worst CVD ΔE 9.4 (deutan), worst normal-vision ΔE 20.9
 *
 * The cap at THREE is deliberate. Adding a fourth hue puts yellow beside
 * orange, which fails the all-pairs floors. Scatter, bubble and small
 * multiples compare every series against every other, so they get three
 * and no more; a fourth series folds into "Other" or becomes a facet.
 * Line and stacked-bar charts only ever place *adjacent* series together
 * and may use the extended list.
 *
 * STATUS COLOURS ARE NOT A PALETTE, and must never be relied on alone.
 * Measured on the light surface, pass-green vs fail-red is **ΔE 4.2 under
 * deuteranopia**. Roughly 8% of men cannot tell them apart by hue at all.
 * A traffic light encoded only in colour is, for those readers, no
 * information whatsoever — which is precisely why CLAUDE.md §10 requires
 * colour + icon + text everywhere, and why the chart layer enforces the
 * same rule rather than trusting each caller.
 */

export type ThemeMode = "light" | "dark";

/** Categorical series, in fixed slot order. Never cycled, never reordered. */
export const SERIES = {
  light: ["#2a78d6", "#eb6834", "#1baf7a"] as const,
  dark: ["#3987e5", "#d95926", "#199e70"] as const,
};

/**
 * Extended slots for adjacent-only forms (lines, stacked bars).
 * Validated on the adjacent pairlist: worst CVD ΔE 9.1 light / 8.4 dark.
 * Do NOT use these for scatter or small multiples — see above.
 */
export const SERIES_EXTENDED = {
  light: [
    "#2a78d6", "#eb6834", "#1baf7a", "#eda100",
    "#e87ba4", "#008300", "#4a3aa7", "#e34948",
  ] as const,
  dark: [
    "#3987e5", "#d95926", "#199e70", "#c98500",
    "#d55181", "#008300", "#9085e9", "#e66767",
  ] as const,
};

/**
 * Traffic light. Fixed, never themed, never used for a data series.
 *
 * `invalid` deliberately shares the `fail` hue: the source defines THREE
 * states, and ADR-015 routes an invalid result to RED. Inventing a
 * fourth colour would imply a fourth state that the domain does not
 * have — and the extra hue failed the lightness band anyway (L 0.396).
 * Invalid is distinguished by its label, which is the honest channel.
 */
export const STATUS = {
  pass: "#15803d",
  fail: "#b91c1c",
  conditional: "#a16207",
  invalid: "#b91c1c",
  neutral: "#52514e",
} as const;

/** Icon per status. Never optional — this is the CVD-safe channel. */
export const STATUS_ICON = {
  pass: "✓",
  fail: "✕",
  conditional: "!",
  invalid: "✕",
  neutral: "•",
} as const;

export const CHROME = {
  light: {
    surface: "#fcfcfb",
    textPrimary: "#0b0b0b",
    textSecondary: "#52514e",
    muted: "#898781",
    grid: "#e1e0d9",
    axis: "#c3c2b7",
  },
  dark: {
    surface: "#1a1a19",
    textPrimary: "#ffffff",
    textSecondary: "#c3c2b7",
    muted: "#898781",
    grid: "#2c2c2a",
    axis: "#383835",
  },
} as const;

/**
 * Sequential ramp for magnitude — heat maps, DOE response surfaces.
 * One hue, light to dark. Never a rainbow: a rainbow ramp implies
 * category boundaries where the data has none, and reverses perceived
 * order for CVD readers.
 */
export const SEQUENTIAL_BLUE = [
  "#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef",
  "#6da7ec", "#5598e7", "#3987e5", "#2a78d6",
  "#256abf", "#1c5cab", "#184f95", "#104281", "#0d366b",
] as const;

/**
 * Diverging pair for polarity — lab-vs-pilot deviation, actual-vs-
 * predicted residuals. Warm and cool poles with a NEUTRAL GRAY midpoint;
 * a hue at the midpoint would read as a third category rather than as
 * "no difference".
 */
export const DIVERGING = {
  negative: "#d03b3b",
  midpoint: { light: "#f0efec", dark: "#383835" },
  positive: "#2a78d6",
} as const;

/** Base ECharts options. Recessive chrome; the data carries the emphasis. */
export function baseOption(mode: ThemeMode) {
  const c = CHROME[mode];
  return {
    backgroundColor: "transparent",
    textStyle: {
      fontFamily: 'system-ui, -apple-system, "Segoe UI", sans-serif',
      color: c.textSecondary,
    },
    grid: { top: 32, right: 16, bottom: 32, left: 56, containLabel: true },
    xAxis: {
      axisLine: { lineStyle: { color: c.axis } },
      axisTick: { show: false },
      axisLabel: { color: c.muted, fontSize: 11 },
      splitLine: { show: false },
    },
    yAxis: {
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: c.muted, fontSize: 11 },
      // Hairline grid only, and only on the value axis. Grid on both
      // axes turns the plot into graph paper and competes with the data.
      splitLine: { lineStyle: { color: c.grid, width: 1 } },
    },
    tooltip: {
      trigger: "axis",
      backgroundColor: c.surface,
      borderColor: c.axis,
      borderWidth: 1,
      textStyle: { color: c.textPrimary, fontSize: 12 },
    },
    legend: {
      textStyle: { color: c.textSecondary, fontSize: 11 },
      icon: "roundRect",
      itemWidth: 10,
      itemHeight: 10,
      top: 0,
    },
    animationDuration: 200,
  };
}
