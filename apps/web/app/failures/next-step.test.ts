/**
 * What the investigation queue says a row needs next.
 *
 * 🔴 IT IS ORDERED, AND THE ORDER IS THE ONLY THING THAT CAN BE WRONG.
 *
 * More than one condition is true at once on a real investigation: an accepted
 * root cause AND three open actions is the normal state of work in progress.
 * A first-match-wins rule has exactly one failure mode — announcing the wrong
 * one — and it is invisible on screen, because every answer it gives is a true
 * statement about the row. "Root cause accepted" over four open actions reads
 * as finished work.
 *
 * So each case below pins a row where at least two branches are satisfiable.
 * A test that only ever fed it one true condition would pass against any
 * ordering.
 *
 * ⚠️ NOTHING HERE IS A JUDGEMENT. Each string restates a count the server
 * returned. `nextStep` must never decide whether an investigation is going
 * well — §10 keeps disposition on the server, and this is a queue label.
 */
import { describe, expect, it } from "vitest";

import type { FailureSummary } from "@/lib/api/failures";

import { nextStep } from "./page";

/** A row with nothing going on, to be overridden per case. */
function row(overrides: Partial<FailureSummary> = {}): FailureSummary {
  return {
    id: "11111111-1111-1111-1111-111111111111",
    failure_code: "FL-0001",
    title: "Adhesion loss after 24h cure",
    severity: "major",
    status: "open",
    project_id: "22222222-2222-2222-2222-222222222222",
    test_id: null,
    formula_version_id: null,
    opened_at: "2026-08-27T10:00:00Z",
    closed_at: null,
    hypothesis_count: 0,
    has_root_cause: false,
    open_actions: 0,
    ...overrides,
  };
}

describe("nextStep", () => {
  it("says a closed investigation is closed, whatever else is true of it", () => {
    // 🔴 THE ROW THAT PROVES THE ORDER. Closed, WITH two open actions and an
    // accepted root cause — so three branches match and only one is right.
    // A rule that checked `open_actions` first would tell a lead that a closed
    // investigation still needs work.
    expect(
      nextStep(
        row({
          status: "closed",
          closed_at: "2026-08-28T09:00:00Z",
          open_actions: 2,
          has_root_cause: true,
          hypothesis_count: 3,
        }),
      ),
    ).toBe("Closed");
  });

  it("puts open actions ahead of an accepted root cause", () => {
    // The case the ordering exists for. Both are true; the actions are the
    // work. Saying "root cause accepted" here would read as done.
    expect(nextStep(row({ has_root_cause: true, hypothesis_count: 4, open_actions: 3 }))).toBe(
      "3 corrective actions open",
    );
  });

  it("counts one action in the singular", () => {
    expect(nextStep(row({ open_actions: 1 }))).toBe("1 corrective action open");
  });

  it("reports an accepted root cause with no actions left", () => {
    expect(nextStep(row({ has_root_cause: true, hypothesis_count: 2 }))).toBe(
      "Root cause accepted — no open actions",
    );
  });

  it("says so when nothing has been proposed", () => {
    expect(nextStep(row())).toBe("No hypothesis yet");
  });

  it("reports hypotheses with none accepted, in the singular and the plural", () => {
    expect(nextStep(row({ hypothesis_count: 1 }))).toBe("1 hypothesis, none accepted");
    expect(nextStep(row({ hypothesis_count: 5 }))).toBe("5 hypotheses, none accepted");
  });

  it("🔴 never claims a root cause from a hypothesis count alone", () => {
    // `has_root_cause` was a `count(*)` in the service until 2026-08-27, and a
    // screen deriving "accepted" from `hypothesis_count > 0` would be the same
    // mistake one layer up: four proposals are not an accepted cause, and
    // §7 turns on the difference.
    expect(nextStep(row({ hypothesis_count: 4, has_root_cause: false }))).not.toContain(
      "Root cause accepted",
    );
  });
});
