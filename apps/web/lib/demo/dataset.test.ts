import { describe, expect, it } from "vitest";

import {
  OPPORTUNITIES,
  PROJECTS,
  STAGES,
  TASKS,
  USERS,
  allRequirements,
  projectByCode,
  openOpportunities,
  requirementCounts,
  requirementSetStatus,
  requirementStatus,
  requirementsNeedingAction,
  riskSeverity,
  stageProgress,
  userName,
  type DemoRequirement,
} from "./dataset";

/**
 * These tests guard the DERIVATIONS, not the data.
 *
 * The dataset is demonstration content and will change. What must not
 * change is that an unmeasured requirement never counts as a pass, that
 * every yellow carries a reason, and that the referential links between
 * records actually resolve — a demo whose project links point at nothing
 * is worse than no demo, because it fails in front of a client.
 */

const req = (over: Partial<DemoRequirement>): DemoRequirement => ({
  requirement_code: "REQ-X",
  name: "Test requirement",
  category: "physical",
  target_value: "10",
  minimum_value: "8",
  maximum_value: null,
  canonical_unit: "MPa",
  criticality: "critical",
  verification_method: "laboratory_test",
  test_method_code: "ASTM X",
  measured_value: "9",
  warning_minimum: null,
  warning_maximum: null,
  ...over,
});

describe("requirement status is derived from the measurement", () => {
  // These drive real MEASUREMENTS against real LIMITS. An earlier version
  // of this suite set a stored `result` string and asserted the mapping —
  // which tested that a switch statement worked, not that the status was
  // derived. Codex found the underlying function had the same problem: a
  // record could say `measured_value: null, result: "pass"` and render
  // green. The stored field is gone; these tests are why it cannot return.

  it("reports a measurement below its minimum as RED", () => {
    const d = requirementStatus(req({ minimum_value: "8", measured_value: "6" }));
    expect(d.status).toBe("red");
    expect(d.label).toBe("FAIL");
  });

  it("reports a measurement above its maximum as RED", () => {
    const d = requirementStatus(
      req({ minimum_value: null, maximum_value: "40", measured_value: "47" }),
    );
    expect(d.status).toBe("red");
  });

  it("NEVER counts an unmeasured requirement as a pass", () => {
    // The whole point. An absent measurement is not evidence of success,
    // and a dashboard that treats it as one is the defect CLAUDE.md §10
    // exists to prevent.
    const d = requirementStatus(req({ measured_value: null }));
    expect(d.status).toBe("yellow");
    expect(d.status).not.toBe("green");
    expect(d.label).toBe("NOT MEASURED");
  });

  it("cannot be told it passed — there is no stored status to set", () => {
    // A compile-time guarantee expressed as a runtime one: the only inputs
    // are the measurement and the limits, so no caller can assert a result.
    const d = requirementStatus(req({ measured_value: null, minimum_value: "8" }));
    expect(d.status).toBe("yellow");
  });

  it("flags a pass that sits inside the warning band", () => {
    const d = requirementStatus(
      req({ minimum_value: "6.5", warning_minimum: "7.0", measured_value: "6.8" }),
    );
    expect(d.status).toBe("yellow");
    expect(d.label).toBe("PASS — LOW MARGIN");
    expect(d.reason).toContain("6.5");
  });

  it("passes cleanly when comfortably inside the limits", () => {
    const d = requirementStatus(
      req({ minimum_value: "6.5", warning_minimum: "7.0", measured_value: "9.2" }),
    );
    expect(d.status).toBe("green");
    expect(d.label).toBe("PASS");
  });

  it("judges a TWO-SIDED requirement against the right band", () => {
    // The defect a single shared threshold caused: with both a minimum and
    // a maximum, every reading except exactly the threshold fell inside one
    // side of the band, so everything in tolerance reported LOW MARGIN and
    // the reason cited the wrong limit. Raised by the Supervisor while no
    // record had both limits — latent, and now impossible.
    const twoSided = {
      minimum_value: "1.0",
      maximum_value: "2.0",
      warning_minimum: "1.1",
      warning_maximum: "1.9",
    };
    expect(requirementStatus(req({ ...twoSided, measured_value: "1.5" })).status).toBe(
      "green",
    );
    const low = requirementStatus(req({ ...twoSided, measured_value: "1.05" }));
    expect(low.status).toBe("yellow");
    expect(low.reason).toContain("minimum");
    const high = requirementStatus(req({ ...twoSided, measured_value: "1.95" }));
    expect(high.status).toBe("yellow");
    expect(high.reason).toContain("maximum");
  });

  it("treats a BLANK measurement as unmeasured, not as zero", () => {
    // `Number("")` is 0, so a blank field parsed as a measured zero and,
    // against a maximum-limited requirement, rendered a green PASS for a
    // value nobody recorded. Raised by the Supervisor.
    for (const blank of ["", "   "]) {
      const d = requirementStatus(
        req({ minimum_value: null, maximum_value: "0.5", measured_value: blank }),
      );
      expect(d.status, `blank ${JSON.stringify(blank)} read as a measurement`).toBe(
        "yellow",
      );
      expect(d.status).not.toBe("green");
    }
  });

  it("fails safe on a measurement that is not a number", () => {
    const d = requirementStatus(req({ measured_value: "pending" }));
    expect(d.status).toBe("yellow");
    expect(d.status).not.toBe("green");
  });

  it("gives every YELLOW a reason", () => {
    // §10: "a yellow with no explanation is a defect".
    const yellows = [
      req({ measured_value: null }),
      req({ measured_value: "" }),
      req({ measured_value: "not-a-number" }),
      req({ minimum_value: "6.5", warning_minimum: "7.0", measured_value: "6.8" }),
    ];
    for (const r of yellows) {
      const d = requirementStatus(r);
      expect(d.status).toBe("yellow");
      expect(d.reason, `no reason given for ${r.measured_value}`).toBeTruthy();
    }
  });

  it("states the limit it was judged against when it fails", () => {
    // A bare "FAIL" tells nobody what to do. The reason must carry the
    // number the measurement was compared with.
    const d = requirementStatus(
      req({ minimum_value: null, maximum_value: "40", measured_value: "47" }),
    );
    expect(d.reason).toContain("40");
    expect(d.reason).toContain("47");
  });
});

describe("aggregates", () => {
  it("counts every requirement exactly once", () => {
    const all = allRequirements();
    const c = requirementCounts(all);
    expect(c.green + c.yellow + c.red).toBe(all.length);
  });

  it("orders the attention list with failures first", () => {
    const rows = requirementsNeedingAction();
    const firstYellow = rows.findIndex((r) => r.derived.status === "yellow");
    const lastRed = rows.map((r) => r.derived.status).lastIndexOf("red");
    if (firstYellow !== -1 && lastRed !== -1) {
      expect(lastRed).toBeLessThan(firstYellow);
    }
  });

  it("excludes passing requirements from the attention list", () => {
    for (const row of requirementsNeedingAction()) {
      expect(row.derived.status).not.toBe("green");
    }
  });

  it("derives gate progress from distinct stages, so a rework cannot inflate it", () => {
    // The denominator is the NORMAL path — Failure / Rework is entered only
    // on a critical failure, so counting it would make a healthy project
    // permanently incomplete. Asserted against the flag in the data rather
    // than a hardcoded number.
    const normalPath = STAGES.filter((s) => s.normal_path).length;
    expect(normalPath).toBeLessThan(STAGES.length);
    for (const p of PROJECTS) {
      const { done, total } = stageProgress(p);
      expect(total).toBe(normalPath);
      expect(done).toBeLessThanOrEqual(total);
    }
  });

  it("never exceeds 100% when a stage is completed twice", () => {
    // THE CASE THE DEMO DATA DOES NOT CONTAIN, and therefore the case the
    // previous version of this test could not catch. It counted history
    // ENTRIES, so it passed on data with no repeats while the function it
    // guarded would have reported "9 of 8" on a legitimate rework loop.
    // Codex found the defect; this constructs the input that proves it.
    const base = PROJECTS[0]!;
    const reworked = {
      ...base,
      stage_history: [
        ...STAGES.map((s) => ({
          stage_code: s.stage_code,
          entered_on: "2026-01-01",
          exited_on: "2026-01-02",
          outcome: "complete",
        })),
        // Re-entered and completed a second time — valid, and exactly what
        // the Failure / Rework stage exists to allow.
        {
          stage_code: STAGES[5]!.stage_code,
          entered_on: "2026-02-01",
          exited_on: "2026-02-02",
          outcome: "complete",
        },
      ],
    };

    const { done, total } = stageProgress(reworked);
    const normalPath = STAGES.filter((s) => s.normal_path).length;
    expect(done).toBe(normalPath);
    expect(done).toBeLessThanOrEqual(total);
  });
});

describe("a requirement SET verdict", () => {
  it("NEVER reports an empty set as passed", () => {
    // Three screens fell through to green for an empty requirement set, so
    // a project at the REQUIREMENTS stage — which by definition has none —
    // was badged "ALL REQUIREMENTS PASSED". Absence of evidence rendering
    // as success is the one failure the traffic-light design exists to
    // prevent. Raised by the Supervisor.
    const d = requirementSetStatus([]);
    expect(d.status).toBe("neutral");
    expect(d.status).not.toBe("green");
    expect(d.label).toBe("NO REQUIREMENTS DEFINED");
  });

  it("reports a failure ahead of anything unverified", () => {
    const failing = req({ minimum_value: "8", measured_value: "1" });
    const unverified = req({ measured_value: null });
    expect(requirementSetStatus([failing, unverified]).status).toBe("red");
  });

  it("reports green only when every requirement has passed", () => {
    const passing = req({ minimum_value: "1", measured_value: "9" });
    expect(requirementSetStatus([passing]).status).toBe("green");
    expect(requirementSetStatus([passing, req({ measured_value: null })]).status).toBe(
      "yellow",
    );
  });
});

describe("open opportunities", () => {
  it("counts only what is genuinely still open", () => {
    // `!== "converted"` counted rejected and closed opportunities as open.
    for (const o of openOpportunities()) {
      expect(["proposed", "under_review"]).toContain(o.status);
    }
  });
});

describe("referential integrity of the demonstration dataset", () => {
  it("resolves every project lead, director and member to a real user", () => {
    const usernames = new Set(USERS.map((u) => u.username));
    for (const p of PROJECTS) {
      expect(usernames.has(p.lead), `${p.project_code} lead`).toBe(true);
      expect(usernames.has(p.director), `${p.project_code} director`).toBe(true);
      for (const m of p.members) {
        expect(usernames.has(m.username), `${p.project_code} member`).toBe(true);
      }
      for (const r of p.risks) {
        expect(usernames.has(r.owner), `${r.risk_code} owner`).toBe(true);
      }
    }
  });

  it("resolves every project stage to a configured stage", () => {
    const codes = new Set(STAGES.map((s) => s.stage_code));
    for (const p of PROJECTS) {
      expect(codes.has(p.current_stage), `${p.project_code} current stage`).toBe(true);
      for (const v of p.stage_history) {
        expect(codes.has(v.stage_code), `${p.project_code} history`).toBe(true);
      }
    }
  });

  it("points every task at a project that exists", () => {
    // A task linking to a missing project renders a dead link on My Work.
    for (const t of TASKS) {
      expect(projectByCode(t.project_code), t.title).toBeDefined();
    }
  });

  it("points every converted opportunity at a project that exists", () => {
    // CLAUDE.md §2: no record may become an isolated island. A converted
    // opportunity whose project is missing breaks the first link of the
    // digital thread.
    for (const o of OPPORTUNITIES) {
      if (o.converted_to_project) {
        expect(projectByCode(o.converted_to_project), o.opportunity_code).toBeDefined();
      }
    }
  });

  it("resolves task assignees to real users", () => {
    for (const t of TASKS) {
      expect(userName(t.assigned_to)).not.toBe(t.assigned_to);
    }
  });

  it("uses unique project codes", () => {
    const codes = PROJECTS.map((p) => p.project_code);
    expect(new Set(codes).size).toBe(codes.length);
  });
});

describe("risk severity", () => {
  it("is SEVERE only when both probability and impact are high", () => {
    const base = PROJECTS[0]!.risks[0]!;
    expect(
      riskSeverity({ ...base, probability: "high", impact: "high" }).status,
    ).toBe("red");
    expect(
      riskSeverity({ ...base, probability: "low", impact: "low" }).status,
    ).toBe("neutral");
  });

  it("explains an elevated risk rather than just colouring it", () => {
    const base = PROJECTS[0]!.risks[0]!;
    const d = riskSeverity({ ...base, probability: "high", impact: "low" });
    expect(d.status).toBe("yellow");
    expect(d.reason).toBeTruthy();
  });
});
