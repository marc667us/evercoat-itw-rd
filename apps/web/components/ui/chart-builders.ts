/**
 * Option builders for the recurring chart forms.
 *
 * Builders rather than raw options at each call site, so the domain rules
 * are applied once. The source names these charts repeatedly across five
 * separate passes; they will be built dozens of times, and "remember to
 * label the segments" is not a control.
 */

import { CHROME, SEQUENTIAL_BLUE, SERIES, STATUS, STATUS_ICON, type ThemeMode } from "./chart-theme";

export interface TrafficLightCounts {
  green: number;
  yellow: number;
  red: number;
}

/**
 * Test traffic-light distribution.
 *
 * The measurement that shapes this: pass-green against fail-red is
 * **ΔE 4.2 under deuteranopia**. For roughly 8% of men these two
 * segments are the same colour. A pie or a bare stacked bar showing
 * "68% / 21% / 11%" in green/yellow/red therefore conveys *nothing* to
 * those readers about which slice is which.
 *
 * So every segment carries its icon and its label inside the mark, and
 * the count is written out. Colour becomes the fastest channel for
 * readers who have it, and a redundant one for readers who do not —
 * which is the only defensible way to use it here.
 *
 * A horizontal stacked bar rather than a pie: proportions of a whole are
 * read more accurately along a common baseline than by angle, and the
 * labels have somewhere to sit.
 */
export function trafficLightOption(counts: TrafficLightCounts, mode: ThemeMode = "light") {
  const total = counts.green + counts.yellow + counts.red;
  const c = CHROME[mode];

  const segments = [
    { key: "green", label: "Successful", value: counts.green, color: STATUS.pass, icon: STATUS_ICON.pass },
    { key: "yellow", label: "Conditional", value: counts.yellow, color: STATUS.conditional, icon: STATUS_ICON.conditional },
    { key: "red", label: "Failed", value: counts.red, color: STATUS.fail, icon: STATUS_ICON.fail },
  ].filter((s) => s.value > 0);

  return {
    grid: { top: 8, right: 8, bottom: 8, left: 8, containLabel: false },
    xAxis: { type: "value", max: total, show: false },
    yAxis: { type: "category", data: [""], show: false },
    legend: { show: false },
    tooltip: {
      trigger: "item",
      formatter: (p: { seriesName: string; value: number }) =>
        `${p.seriesName}: ${p.value} of ${total} (${((p.value / total) * 100).toFixed(0)}%)`,
    },
    series: segments.map((s) => ({
      name: `${s.icon} ${s.label}`,
      type: "bar",
      stack: "status",
      barWidth: 40,
      itemStyle: {
        color: s.color,
        // 2px surface gap between segments, so adjacent fills stay
        // distinguishable without relying on the hue boundary.
        borderColor: c.surface,
        borderWidth: 2,
      },
      label: {
        show: true,
        position: "inside",
        // Icon AND text AND count inside the mark. This is the line that
        // makes the chart readable at ΔE 4.2.
        formatter: () => `${s.icon} ${s.label}\n${s.value}`,
        color: "#ffffff",
        fontSize: 11,
        lineHeight: 14,
        fontWeight: 500,
      },
      data: [s.value],
    })),
  };
}

/**
 * Failure Pareto — frequency descending, with a cumulative line.
 *
 * A Pareto is the one place a second axis is genuinely conventional, and
 * ChartWrapper forbids it anyway. The cumulative series is therefore
 * expressed as a percentage of the same total and plotted on the single
 * value axis, so both series share one scale honestly.
 */
export function failureParetoOption(
  categories: { label: string; count: number }[],
  mode: ThemeMode = "light",
) {
  const sorted = [...categories].sort((a, b) => b.count - a.count);
  const total = sorted.reduce((sum, c) => sum + c.count, 0) || 1;

  let running = 0;
  const cumulative = sorted.map((c) => {
    running += c.count;
    return Number(((running / total) * 100).toFixed(1));
  });

  return {
    xAxis: {
      type: "category",
      data: sorted.map((c) => c.label),
      axisLabel: { interval: 0, rotate: sorted.length > 6 ? 30 : 0 },
    },
    yAxis: { type: "value", max: 100, axisLabel: { formatter: "{value}%" } },
    legend: { show: true },
    series: [
      {
        name: "Share of failures",
        type: "bar",
        data: sorted.map((c) => Number(((c.count / total) * 100).toFixed(1))),
        itemStyle: { color: SERIES[mode][0], borderRadius: [4, 4, 0, 0] },
      },
      {
        name: "Cumulative",
        type: "line",
        data: cumulative,
        smooth: false,
        lineStyle: { width: 2, color: SERIES[mode][1] },
        itemStyle: { color: SERIES[mode][1] },
        symbolSize: 8,
      },
    ],
  };
}

/**
 * Requirement heat map — formulas against requirements.
 *
 * A single-hue sequential ramp, never a rainbow: a rainbow implies
 * category boundaries the data does not have and inverts perceived order
 * for CVD readers. Pass/fail cells additionally carry a glyph, because
 * this grid is read to find the failures.
 */
export function requirementHeatmapOption(
  formulas: string[],
  requirements: string[],
  cells: { x: number; y: number; value: number; passed: boolean }[],
) {
  return {
    xAxis: { type: "category", data: formulas, splitArea: { show: true } },
    yAxis: { type: "category", data: requirements, splitArea: { show: true } },
    visualMap: {
      min: 0,
      max: 100,
      calculable: true,
      orient: "horizontal",
      left: "center",
      bottom: 0,
      inRange: { color: [...SEQUENTIAL_BLUE] },
      textStyle: { fontSize: 10 },
    },
    series: [
      {
        type: "heatmap",
        data: cells.map((c) => [c.x, c.y, c.value]),
        label: {
          show: true,
          formatter: (p: { data: [number, number, number] }) => {
            const cell = cells.find((c) => c.x === p.data[0] && c.y === p.data[1]);
            // Glyph plus value: the grid exists to locate failures, and
            // a failure that is only a slightly different blue is not
            // located.
            return cell ? `${cell.passed ? "✓" : "✕"} ${p.data[2]}` : "";
          },
          fontSize: 10,
        },
        itemStyle: { borderColor: "#fcfcfb", borderWidth: 2 },
      },
    ],
  };
}
