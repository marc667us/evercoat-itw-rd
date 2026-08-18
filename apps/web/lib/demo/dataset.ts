/**
 * The demo dataset, and the derivations over it.
 *
 * WHY THIS EXISTS. `apps/web` makes no API calls, and the deployed site is
 * a static export with no server behind it. Without this, every screen in
 * the product is an empty state — which is what the deployed shell was:
 * a correct deployment of nothing anyone could evaluate.
 *
 * WHAT IT IS NOT. It is not a mock layer that pretends to be an API, and
 * it is not a fixture that only tests see. It is a **build-time dataset**
 * baked into the export, so a client can open the URL and walk the real
 * navigation over coherent records.
 *
 * 🔴 EVERY RECORD IS SYNTHETIC. `CLAUDE.md` rule 3 is that predictions
 * must never be mistaken for measurements, and §10 that a dashboard of
 * invented figures is indistinguishable from a working one at a glance.
 * That cuts both ways here: demo data is legitimate, but only if it is
 * impossible to mistake for real R&D records. Hence `<DemoBanner />` on
 * every page and `DEMO_NOTICE` below — not a footnote, a standing label.
 *
 * ONE SOURCE. `demo-data.json` is read by BOTH this module and
 * `scripts/seed.py`, which loads the same records into PostgreSQL. A
 * TypeScript copy and a Python copy kept in step by hand is the exact
 * defect this repository keeps hitting.
 *
 * SHAPES MIRROR THE REAL API (`app/api/projects.py`, `tasks.py`,
 * `opportunities.py`). When the API is wired in, the data source changes
 * and the components do not.
 */

import raw from "./demo-data.json";

import type { DisplayStatus } from "@/components/ui/status-badge";

// Deliberately does NOT begin with "Demonstration data" — the banner
// renders that as its own bold prefix, and having it here too produced
// "DEMONSTRATION DATA — Demonstration data — ..." on every page. Caught by
// looking at the rendered page, which is the only way that class of defect
// is ever caught.
export const DEMO_NOTICE =
  "every project, requirement, measurement and person shown here is " +
  "synthetic. Nothing on this site is a real R&D record.";

// ---------------------------------------------------------------- types

export interface DemoUser {
  readonly username: string;
  readonly display_name: string;
  readonly role: string;
}

export interface DemoStage {
  readonly stage_code: string;
  readonly name: string;
  readonly sequence: number;
  readonly entry_criteria: string | null;
  readonly required_deliverables: string | null;
  readonly responsible_role: string | null;
  readonly requires_approval: boolean;
  readonly approval_role: string | null;
}

export interface DemoOpportunity {
  readonly opportunity_code: string;
  readonly title: string;
  readonly market_need: string | null;
  readonly product_family: string | null;
  readonly target_application: string | null;
  readonly technical_concept: string | null;
  readonly priority: string;
  readonly status: string;
  readonly decision: string | null;
  readonly rationale: string | null;
  readonly converted_to_project: string | null;
}

export interface DemoStageVisit {
  readonly stage_code: string;
  readonly entered_on: string;
  readonly exited_on: string | null;
  readonly outcome: string;
}

export interface DemoMember {
  readonly username: string;
  readonly project_role: string;
  readonly status: string;
}

export interface DemoMilestone {
  readonly name: string;
  readonly planned_date: string;
  readonly actual_date: string | null;
  readonly status: string;
}

export interface DemoRisk {
  readonly risk_code: string;
  readonly title: string;
  readonly probability: string;
  readonly impact: string;
  readonly category: string;
  readonly status: string;
  readonly mitigation: string | null;
  readonly owner: string;
}

export interface DemoRequirement {
  readonly requirement_code: string;
  readonly name: string;
  readonly category: string;
  readonly target_value: string | null;
  readonly minimum_value: string | null;
  readonly maximum_value: string | null;
  readonly canonical_unit: string | null;
  readonly criticality: string;
  readonly verification_method: string;
  readonly test_method_code: string | null;
  readonly measured_value: string | null;
  /**
   * The value on the failing side of which a pass is reported as a LOW
   * MARGIN pass. Compared below the limit for a minimum, above it for a
   * maximum. Null means no warning band is configured.
   */
  readonly warning_threshold: string | null;
}

export interface DemoProject {
  readonly project_code: string;
  readonly name: string;
  readonly product_family: string | null;
  readonly status: string;
  readonly priority: string;
  readonly confidentiality: string;
  readonly current_stage: string;
  readonly target_release_date: string | null;
  readonly description: string;
  readonly technical_objective: string;
  readonly commercial_objective: string;
  readonly lead: string;
  readonly director: string;
  readonly stage_history: readonly DemoStageVisit[];
  readonly members: readonly DemoMember[];
  readonly milestones: readonly DemoMilestone[];
  readonly risks: readonly DemoRisk[];
  readonly requirements: readonly DemoRequirement[];
}

export interface DemoTask {
  readonly task_type: string;
  readonly title: string;
  readonly project_code: string;
  readonly priority: string;
  readonly status: string;
  readonly assigned_to: string;
  readonly due_date: string;
  readonly required_action: string;
}

interface DemoDataset {
  readonly organization: { readonly name: string; readonly note: string };
  readonly users: readonly DemoUser[];
  readonly stages: readonly DemoStage[];
  readonly opportunities: readonly DemoOpportunity[];
  readonly projects: readonly DemoProject[];
  readonly tasks: readonly DemoTask[];
}

// The JSON carries a `_README` array that is documentation, not data. It is
// dropped here rather than typed, so no consumer can accidentally render it.
const data = raw as unknown as DemoDataset;

export const ORGANIZATION = data.organization;
export const USERS: readonly DemoUser[] = data.users;
export const STAGES: readonly DemoStage[] = [...data.stages].sort(
  (a, b) => a.sequence - b.sequence,
);
export const OPPORTUNITIES: readonly DemoOpportunity[] = data.opportunities;
export const PROJECTS: readonly DemoProject[] = data.projects;
export const TASKS: readonly DemoTask[] = data.tasks;

// ---------------------------------------------------------------- lookups

export function userName(username: string): string {
  return USERS.find((u) => u.username === username)?.display_name ?? username;
}

export function stageName(code: string): string {
  return STAGES.find((s) => s.stage_code === code)?.name ?? code;
}

export function projectByCode(code: string): DemoProject | undefined {
  return PROJECTS.find((p) => p.project_code === code);
}

export function tasksForProject(code: string): readonly DemoTask[] {
  return TASKS.filter((t) => t.project_code === code);
}

// ---------------------------------------------------- derived presentation

export interface Derived {
  readonly status: DisplayStatus;
  readonly label: string;
  /** Required whenever the status is yellow — see below. */
  readonly reason?: string;
}

/**
 * Requirement verification status, DERIVED FROM THE MEASUREMENT.
 *
 * `CLAUDE.md` §10: the state is computed by an ORDERED algorithm where the
 * first match wins, and it is never a field a user picks.
 *
 * 🔴 THIS USED TO READ A STORED `result` STRING and call itself derived.
 * Codex caught it. The docstring claimed an absent measurement could never
 * read as a pass, while `{ measured_value: null, result: "pass" }` rendered
 * green — the invariant was an assertion in a comment, not a mechanism, and
 * the two could disagree silently. The stored column has been removed from
 * the dataset entirely, so there is no longer anything to disagree with.
 *
 * The order, first match wins:
 *
 *   1. no measurement            → YELLOW, unverified. Never a pass.
 *   2. outside a stated limit    → RED
 *   3. inside the warning band   → YELLOW, and says by how much
 *   4. otherwise                 → GREEN
 *
 * Every YELLOW carries a reason. §10: "a yellow with no explanation is a
 * defect" — a colour that does not say what to do next is decoration.
 */
export function requirementStatus(r: DemoRequirement): Derived {
  const unit = r.canonical_unit ? ` ${r.canonical_unit}` : "";

  // 1. An absent measurement is not evidence of anything.
  if (r.measured_value === null) {
    return {
      status: "yellow",
      label: "NOT MEASURED",
      reason: "No measurement recorded yet — this requirement is unverified.",
    };
  }

  const measured = Number(r.measured_value);
  if (!Number.isFinite(measured)) {
    // Fails safe. An unparseable measurement is not a pass.
    return {
      status: "yellow",
      label: "UNREADABLE MEASUREMENT",
      reason: `Recorded value ${r.measured_value} is not a number.`,
    };
  }

  const min = r.minimum_value === null ? null : Number(r.minimum_value);
  const max = r.maximum_value === null ? null : Number(r.maximum_value);
  const warn = r.warning_threshold === null ? null : Number(r.warning_threshold);

  // 2. Outside a stated limit.
  if (min !== null && measured < min) {
    return {
      status: "red",
      label: "FAIL",
      reason: `Measured ${measured}${unit} against a minimum of ${min}${unit}.`,
    };
  }
  if (max !== null && measured > max) {
    return {
      status: "red",
      label: "FAIL",
      reason: `Measured ${measured}${unit} against a maximum of ${max}${unit}.`,
    };
  }

  // 3. Inside the warning band — a pass, but one worth stating.
  if (warn !== null) {
    const nearMinimum = min !== null && measured < warn;
    const nearMaximum = max !== null && measured > warn;
    if (nearMinimum || nearMaximum) {
      return {
        status: "yellow",
        label: "PASS — LOW MARGIN",
        reason: `Measured ${measured}${unit} against a ${
          nearMinimum ? `minimum of ${min}` : `maximum of ${max}`
        }${unit} — inside tolerance but past the warning threshold of ${warn}${unit}.`,
      };
    }
  }

  // 4. A pass, with no qualification needed.
  return { status: "green", label: "PASS" };
}

export function milestoneStatus(m: DemoMilestone): Derived {
  if (m.status === "complete") return { status: "green", label: "COMPLETE" };
  if (m.status === "in_progress")
    return {
      status: "yellow",
      label: "IN PROGRESS",
      reason: `Planned for ${m.planned_date}; not yet complete.`,
    };
  return {
    status: "neutral",
    label: "NOT STARTED",
  };
}

/**
 * Risk severity from probability x impact.
 *
 * Deliberately a small explicit table rather than a numeric score. A
 * 1–25 score invites false precision on two three-point judgements, and
 * nobody can say what the difference between 11 and 12 means.
 */
export function riskSeverity(r: DemoRisk): Derived {
  const high = r.impact === "high";
  const likely = r.probability === "high";
  if (high && likely) return { status: "red", label: "SEVERE" };
  if (high || likely)
    return {
      status: "yellow",
      label: "ELEVATED",
      reason: `${r.probability} probability, ${r.impact} impact — ${
        r.status === "open" ? "no mitigation in progress yet" : "mitigation in progress"
      }.`,
    };
  return { status: "neutral", label: "MODERATE" };
}

// ------------------------------------------------------------- aggregates

export interface RequirementCounts {
  green: number;
  yellow: number;
  red: number;
}

export function requirementCounts(
  reqs: readonly DemoRequirement[],
): RequirementCounts {
  const counts: RequirementCounts = { green: 0, yellow: 0, red: 0 };
  for (const r of reqs) {
    const s = requirementStatus(r).status;
    if (s === "green") counts.green += 1;
    else if (s === "red") counts.red += 1;
    else counts.yellow += 1;
  }
  return counts;
}

export function allRequirements(): readonly DemoRequirement[] {
  return PROJECTS.flatMap((p) => p.requirements);
}

/**
 * Progress through the stage gate, as a fraction.
 *
 * Derived from the project's own stage HISTORY rather than from its
 * current stage alone. `CLAUDE.md` §5 requires stage history to be
 * preserved rather than a `current_stage` field merely being updated, and
 * a progress figure computed from history is the visible consequence of
 * that: it survives a project moving backwards into Failure / Rework,
 * which a naive "index of current stage" reading would report as progress.
 */
export function stageProgress(p: DemoProject): { done: number; total: number } {
  // DISTINCT stage codes, not history entries. A rework loop legitimately
  // re-enters and re-completes a stage, and counting visits would report
  // "9 of 8 complete" — a progress figure above 100%, from data that is
  // perfectly valid. Raised by Codex.
  const completed = new Set(
    p.stage_history.filter((v) => v.outcome === "complete").map((v) => v.stage_code),
  );
  return { done: completed.size, total: STAGES.length };
}

/** Requirements needing action across every project, worst first. */
export function requirementsNeedingAction(): {
  project: DemoProject;
  requirement: DemoRequirement;
  derived: Derived;
}[] {
  const rows = PROJECTS.flatMap((project) =>
    project.requirements.map((requirement) => ({
      project,
      requirement,
      derived: requirementStatus(requirement),
    })),
  ).filter((row) => row.derived.status !== "green");

  // Red before yellow. A list that interleaves them buries the failures.
  //
  // Keyed by DisplayStatus rather than `string`, so the table is exhaustive
  // by construction: adding a status to DisplayStatus fails to compile here
  // instead of silently sorting the new state to the top under
  // noUncheckedIndexedAccess.
  const rank: Record<DisplayStatus, number> = {
    red: 0,
    yellow: 1,
    neutral: 2,
    green: 3,
  };
  return rows.sort((a, b) => rank[a.derived.status] - rank[b.derived.status]);
}

export function openTasks(): readonly DemoTask[] {
  return TASKS.filter((t) => t.status !== "complete");
}
