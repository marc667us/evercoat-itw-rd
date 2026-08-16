/**
 * Chart builder contract tests.
 *
 * These assert the accessibility rules that are easy to regress and
 * impossible to notice: a segment that loses its label still renders
 * perfectly, looks fine to the author, and silently becomes unreadable
 * for a deuteranopic reader.
 */

import { describe, expect, it } from "vitest";

import { failureParetoOption, trafficLightOption } from "./chart-builders";
import { SERIES, STATUS } from "./chart-theme";

describe("traffic light", () => {
  const counts = { green: 68, yellow: 21, red: 11 };

  it("labels every segment with icon AND text AND count", () => {
    // The rule that makes it readable at CVD deltaE 4.2 between the
    // green and red segments.
    const option = trafficLightOption(counts);
    for (const series of option.series) {
      const label = series.label.formatter();
      expect(label).toMatch(/[✓!✕]/);
      expect(label).toMatch(/Successful|Conditional|Failed/);
      expect(label).toMatch(/\d/);
    }
  });

  it("names each series with its icon, so the tooltip is not colour-only", () => {
    const option = trafficLightOption(counts);
    const names = option.series.map((s) => s.name);
    expect(names).toEqual(["✓ Successful", "! Conditional", "✕ Failed"]);
  });

  it("omits zero-count segments rather than drawing a sliver", () => {
    const option = trafficLightOption({ green: 5, yellow: 0, red: 0 });
    expect(option.series).toHaveLength(1);
  });

  it("puts a surface-coloured gap between adjacent fills", () => {
    const option = trafficLightOption(counts);
    for (const s of option.series) {
      expect(s.itemStyle.borderWidth).toBe(2);
    }
  });

  it("uses the fixed status palette, never a series colour", () => {
    const option = trafficLightOption(counts);
    const colors = option.series.map((s) => s.itemStyle.color);
    expect(colors).toEqual([STATUS.pass, STATUS.conditional, STATUS.fail]);
    for (const c of colors) {
      expect(SERIES.light).not.toContain(c);
    }
  });
});

describe("failure pareto", () => {
  const data = [
    { label: "Adhesion", count: 23 },
    { label: "Pinholing", count: 28 },
    { label: "Sag", count: 17 },
  ];

  it("sorts descending — that is what makes it a Pareto", () => {
    const option = failureParetoOption(data);
    expect(option.xAxis.data).toEqual(["Pinholing", "Adhesion", "Sag"]);
  });

  it("expresses cumulative on the SAME scale, not a second axis", () => {
    // ChartWrapper throws on a dual axis; the builder must not need one.
    const option = failureParetoOption(data);
    expect(Array.isArray(option.yAxis)).toBe(false);
    expect(option.yAxis.max).toBe(100);
    const cumulative = option.series[1]!.data as number[];
    expect(cumulative.at(-1)).toBeCloseTo(100, 1);
  });

  it("keeps cumulative monotonically non-decreasing", () => {
    const option = failureParetoOption(data);
    const c = option.series[1]!.data as number[];
    for (let i = 1; i < c.length; i++) {
      expect(c[i]!).toBeGreaterThanOrEqual(c[i - 1]!);
    }
  });

  it("does not divide by zero on an empty set", () => {
    const option = failureParetoOption([]);
    expect(option.series[1]!.data).toEqual([]);
  });
});
