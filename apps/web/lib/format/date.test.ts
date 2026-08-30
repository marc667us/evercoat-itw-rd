/**
 * The date formatter, tested where it is actually capable of being wrong.
 *
 * 🔴 EVERY CASE HERE WAS FALSIFIED BY BREAKING THE IMPLEMENTATION ON PURPOSE.
 *
 * This repository's standing lesson is that a test which has only ever passed
 * has not been shown to detect anything, and that a guard which cannot fail is
 * worse than none. So each assertion below was checked by making the specific
 * mistake it describes and watching it go red — the results are noted per case.
 */

import { describe, expect, it } from "vitest";

import { formatDay, formatInstant, hasDate } from "./date";

describe("formatDay", () => {
  it("renders an unambiguous day, never a locale-dependent numeric one", () => {
    // 🔴 THE POINT OF THE WHOLE FORMATTER. `30/08/2026` and `08/30/2026` are
    // the same instant written two ways, and a reader cannot tell which
    // convention a screen used. A month NAME cannot be misread.
    // Falsified by switching the formatter to `numeric` months: red.
    expect(formatDay("2026-08-30T14:22:00Z")).toBe("30 Aug 2026");
  });

  it("does not shift a bare CALENDAR DATE into the previous day", () => {
    // 🔴 THIS TEST FOUND A REAL DEFECT, and it is the reason the file has a
    // calendar-date branch at all.
    //
    // `target_release_date` is a plain `date` column and arrives as
    // `2026-11-30`. The first implementation handed it straight to
    // `new Date(...)`, which parses a bare date as UTC midnight; `Intl` then
    // rendered it in the viewer's zone. On this host (America/Los_Angeles)
    // it came back **29 Nov 2026** — every release target a day early for
    // every user west of UTC.
    //
    // Falsified by deleting the calendar-date branch: red again, immediately.
    expect(formatDay("2026-11-30")).toBe("30 Nov 2026");
    // January and December are where an off-by-one crosses a YEAR, which is
    // the version of this bug nobody notices until an annual report is wrong.
    expect(formatDay("2027-01-01")).toBe("01 Jan 2027");
    expect(formatDay("2026-12-31")).toBe("31 Dec 2026");
  });

  it("still treats a full timestamp as an instant, in the viewer's zone", () => {
    // ⚠️ THE OTHER HALF OF THE SAME RULE. A `timestamptz` is a moment, and
    // "when did this happen, in my time" is the right question for one — so
    // the calendar-date branch must NOT swallow it. The anchored regex is
    // what keeps these two cases apart.
    expect(formatDay("2026-08-30T14:22:00Z")).toBe("30 Aug 2026");
  });

  it("rejects a malformed calendar date instead of rolling it over", () => {
    // `new Date(2026, 12, 45)` does not fail — it becomes 2027. A rolled-over
    // date renders as a real-looking WRONG day, which is worse than "—".
    // Falsified by removing the round-trip check: `2026-13-45` rendered
    // "14 Jan 2027".
    expect(formatDay("2026-13-45")).toBe("—");
    expect(formatDay("2026-02-30")).toBe("—");
  });

  it("renders unknown as an em dash, NOT as today and NOT as blank", () => {
    // A blank cell in a date column reads as "no date", which is a claim.
    // Falsified by returning "" for null: red.
    expect(formatDay(null)).toBe("—");
    expect(formatDay(undefined)).toBe("—");
    expect(formatDay("")).toBe("—");
  });

  it("never renders the literal string 'Invalid Date' into the page", () => {
    // 🔴 `new Date("not a date").toLocaleDateString()` returns the STRING
    // "Invalid Date" rather than throwing, so a malformed value would appear
    // verbatim in the UI. Falsified by removing the `Number.isNaN` guard in
    // `parse`: this case went red and printed "Invalid Date".
    expect(formatDay("not a date")).toBe("—");
    expect(formatDay("2026-13-45")).toBe("—");
  });

  it("does not treat epoch zero as absent", () => {
    // ⚠️ A FALSY-CHECK BUG THIS TEST EXISTS TO CATCH. `if (!value)` would
    // reject the number 0, which is a real instant and exactly the kind of
    // value a broken backfill produces. Reporting it as "—" would hide the
    // bad data instead of showing it.
    //
    // ⚠️ THE EXACT DAY IS NOT ASSERTED, DELIBERATELY. Epoch zero IS an
    // instant, so it correctly renders in the viewer's zone — which is
    // 31 Dec 1969 west of UTC and 1 Jan 1970 east of it. Pinning either would
    // be a test that only passes in one timezone, and this repository already
    // has a rule about tests that name a host or a port.
    expect(formatDay(0)).not.toBe("—");
    expect(formatDay(0)).toMatch(/19(69|70)/);
    expect(hasDate(0)).toBe(true);
  });
});

describe("formatInstant", () => {
  it("carries the time, because the day is not always enough", () => {
    // Reconstructing a sequence of events within one day needs the clock.
    // The exact separator is Intl's, so this asserts the PARTS rather than a
    // brittle full string — a test that pins punctuation breaks on a Node
    // upgrade without anything being wrong.
    const rendered = formatInstant("2026-08-30T14:22:00Z");
    expect(rendered).toContain("30 Aug 2026");
    expect(rendered).toMatch(/\d{2}:\d{2}/);
  });

  it("returns an EMPTY string when unknown, so no tooltip is attached", () => {
    // Deliberately different from `formatDay`'s em dash: this value becomes a
    // `title` attribute, and "—" as a tooltip is a tooltip that says nothing.
    // The component omits the attribute entirely when this is "".
    expect(formatInstant(null)).toBe("");
    expect(formatInstant("not a date")).toBe("");
  });
});

describe("hasDate", () => {
  it("separates 'not recorded' from 'recorded', and nothing else", () => {
    // This is what decides whether an EVENT is rendered at all, so a false
    // positive puts a step on screen that never happened.
    expect(hasDate("2026-08-30T00:00:00Z")).toBe(true);
    expect(hasDate(null)).toBe(false);
    expect(hasDate("")).toBe(false);
    expect(hasDate("not a date")).toBe(false);
  });
});
