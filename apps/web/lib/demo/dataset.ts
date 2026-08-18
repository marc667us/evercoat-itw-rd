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
 * ONE SOURCE, FOR WHAT IS ACTUALLY SHARED. `demo-data.json` is read by
 * this module and by `scripts/seed.py` — but the seeder consumes only
 * `users` and `stages`. Projects, requirements, milestones, risks,
 * opportunities and tasks are NOT seeded into PostgreSQL; they exist for
 * the static demonstration alone.
 *
 * Stated precisely because the earlier wording here claimed the seeder
 * "loads the same records", which would lead a reader to expect /projects
 * to work against the API after running it. The shared part is real and
 * worth having — users and pipeline stages were previously duplicated as
 * Python literals — but it is not the whole file. Raised by the Supervisor.
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
  /**
   * False for stages entered only by exception — Failure / Rework. Counting
   * them in a progress denominator makes a healthy project permanently
   * incomplete.
   */
  readonly normal_path: boolean;
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
   * Warning bands, ONE PER LIMIT.
   *
   * A single shared threshold cannot describe a two-sided requirement: with
   * both a minimum and a maximum, every reading except exactly the
   * threshold falls inside one side of the band, so everything in tolerance
   * reports LOW MARGIN and the reason cites the wrong limit. Raised by the
   * Supervisor while no record had both limits — latent, but the type and
   * the seeder both permitted it.
   */
  readonly warning_minimum: string | null;
  readonly warning_maximum: string | null;
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
  readonly suppliers: readonly DemoSupplier[];
  readonly materials: readonly DemoMaterial[];
  readonly formulas: readonly DemoFormula[];
  /** Documentation inside the data file. Typed so it can be ignored safely. */
  readonly _README?: readonly string[];
  readonly organization: { readonly name: string; readonly note: string };
  readonly users: readonly DemoUser[];
  readonly stages: readonly DemoStage[];
  readonly opportunities: readonly DemoOpportunity[];
  readonly projects: readonly DemoProject[];
  readonly tasks: readonly DemoTask[];
}

// A DIRECT cast, not `as unknown as`.
//
// Routing through `unknown` disabled all structural checking, not just the
// `_README` field the old comment described: a renamed or missing JSON key
// compiled clean and surfaced at runtime as NaN or a crash on
// `undefined.map`. `_README` is typed as optional above, so the direct cast
// is accepted AND TypeScript still rejects a requirement missing
// `warning_minimum` or a project missing `risks`. Raised by the Supervisor.
const data = raw as DemoDataset;

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

  // `Number("")` is 0, not NaN. A blank measurement therefore parses as a
  // measured zero and, against a maximum-limited requirement, renders a
  // GREEN PASS for a value nobody recorded — the precise invariant the
  // docstring above claims to make impossible. An empty string is the
  // likeliest shape of a blank field once this comes from a form or a
  // database column. Raised by the Supervisor.
  if (r.measured_value.trim() === "") {
    return {
      status: "yellow",
      label: "NOT MEASURED",
      reason: "The measurement field is blank — this requirement is unverified.",
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
  const warnMin = r.warning_minimum === null ? null : Number(r.warning_minimum);
  const warnMax = r.warning_maximum === null ? null : Number(r.warning_maximum);

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

  // 3. Inside a warning band — a pass, but one worth stating.
  //
  // Each limit has its OWN threshold, so a two-sided requirement is judged
  // correctly and the reason always names the limit actually approached.
  if (warnMin !== null && min !== null && measured < warnMin) {
    return {
      status: "yellow",
      label: "PASS — LOW MARGIN",
      reason: `Measured ${measured}${unit} against a minimum of ${min}${unit} — inside tolerance but below the warning threshold of ${warnMin}${unit}.`,
    };
  }
  if (warnMax !== null && max !== null && measured > warnMax) {
    return {
      status: "yellow",
      label: "PASS — LOW MARGIN",
      reason: `Measured ${measured}${unit} against a maximum of ${max}${unit} — inside tolerance but above the warning threshold of ${warnMax}${unit}.`,
    };
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

/**
 * One verification verdict for a whole requirement SET.
 *
 * 🔴 THE EMPTY CASE IS WHY THIS EXISTS. Three screens previously fell
 * through `red > 0` → `yellow > 0` → green, so a project whose requirement
 * set had not been written yet was badged "ALL REQUIREMENTS PASSED" — and
 * a project at the REQUIREMENTS stage is exactly the case that has none.
 * Absence of evidence rendering as success is the single failure the
 * traffic-light design exists to prevent. Raised by the Supervisor.
 */
export function requirementSetStatus(
  reqs: readonly DemoRequirement[],
): Derived {
  if (reqs.length === 0) {
    return {
      status: "neutral",
      label: "NO REQUIREMENTS DEFINED",
    };
  }
  const c = requirementCounts(reqs);
  if (c.red > 0) {
    return { status: "red", label: `${c.red} REQUIREMENT FAILED` };
  }
  if (c.yellow > 0) {
    return {
      status: "yellow",
      label: "IN VERIFICATION",
      reason: `${c.yellow} requirement(s) not yet confirmed.`,
    };
  }
  return { status: "green", label: "ALL REQUIREMENTS PASSED" };
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
  // The denominator is the NORMAL path. Failure / Rework is entered only
  // when a critical test fails, so counting it means a project that goes
  // cleanly through every gate can never report better than "7 of 8" —
  // under-reporting a healthy project as incomplete forever. Raised by the
  // Supervisor. Driven by the data's own `normal_path` flag rather than by
  // a hardcoded stage code.
  const normal = new Set(
    STAGES.filter((s) => s.normal_path).map((s) => s.stage_code),
  );
  const completed = new Set(
    p.stage_history
      .filter((v) => v.outcome === "complete" && normal.has(v.stage_code))
      .map((v) => v.stage_code),
  );
  return { done: completed.size, total: normal.size };
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

/**
 * Whose work "My Work" is.
 *
 * There is no authenticated principal in a static export, and a badge
 * labelled "My Work" that counts the whole organisation's tasks is simply
 * false — §11 requires a count to be items needing action BY THE HOLDER.
 * The demonstration therefore names a viewer explicitly rather than
 * pretending the number is personal. Replaced by the verified principal
 * when Keycloak is wired in. Raised by the Supervisor.
 */
export const DEMO_VIEWER = "lead.demo";

export function tasksAssignedTo(username: string): readonly DemoTask[] {
  return TASKS.filter((t) => t.assigned_to === username && t.status !== "complete");
}

export function openTasks(): readonly DemoTask[] {
  return TASKS.filter((t) => t.status !== "complete");
}

/**
 * Opportunities still awaiting a decision.
 *
 * A POSITIVE filter, not `!== "converted"`. The negative form counted
 * rejected and closed opportunities as open, so the first rejection would
 * silently inflate the dashboard figure while its caption said "proposed or
 * under review". Raised by the Supervisor.
 */
export function openOpportunities(): readonly DemoOpportunity[] {
  return OPPORTUNITIES.filter(
    (o) => o.status === "proposed" || o.status === "under_review",
  );
}

// ------------------------------------------------------- Slice 3 types

export interface DemoSupplier {
  readonly supplier_code: string;
  readonly name: string;
  readonly country: string;
  readonly status: string;
  readonly quality_rating: string;
  readonly note: string;
}

export interface DemoMaterial {
  readonly material_code: string;
  readonly name: string;
  readonly category: string;
  readonly role: string;
  readonly status: string;
  readonly density_g_cm3: string;
  readonly solids_fraction: string;
  readonly voc_fraction: string;
  /**
   * The same values as percentages, computed in PYTHON by
   * `scripts/build_demo_formulations.py`.
   *
   * Present so no component multiplies a fraction by 100 in JavaScript.
   * That is float arithmetic on a controlled percentage, which §5 forbids —
   * and which happened here until Codex caught it.
   */
  readonly solids_percent: string;
  readonly voc_percent: string;
  readonly cost_per_kg: string;
  readonly suppliers: readonly string[];
  readonly note: string;
}

export interface DemoComponent {
  readonly material_code: string;
  readonly percentage: string;
}

export interface DemoSubmissionBlock {
  readonly code: string;
  readonly message: string;
}

export interface DemoDiffRow {
  readonly material_code: string;
  readonly change: string;
  readonly old_percentage: string | null;
  readonly new_percentage: string | null;
  readonly delta: string | null;
  readonly percent_delta: string | null;
}

/**
 * Everything under here was produced by `app.calculations.formulation`
 * at build time, via `scripts/build_demo_formulations.py`.
 *
 * 🔴 NOTHING IN TYPESCRIPT MAY RECOMPUTE ANY OF IT. `CLAUDE.md` rule 2
 * gives deterministic scientific calculation to Python, and a second
 * implementation here — even of something as small as a percentage delta —
 * is that rule broken. These are values to RENDER, not inputs to arithmetic.
 */
export interface DemoComputed {
  readonly total_percentage: string;
  readonly theoretical_density_g_cm3: string;
  readonly binder_to_filler: string;
  readonly solids_percent: string;
  readonly voc_g_per_l: string;
  readonly raw_material_cost_per_kg: string;
  readonly submission_blocks: readonly DemoSubmissionBlock[];
  /**
   * NULL when the version cannot be submitted.
   *
   * A formula outside tolerance has no business producing a weigh-up: the
   * masses would be scaled from a total that is not 100, so a component
   * stated at 36.00% would print as 36.55% of the batch and the two numbers
   * would sit in adjacent columns contradicting each other.
   */
  readonly batch: {
    readonly batch_mass_kg: string;
    readonly masses_kg: Readonly<Record<string, string>>;
  } | null;
  readonly diff_vs_parent: readonly DemoDiffRow[];
}

export interface DemoFormulaVersion {
  readonly version_number: number;
  readonly version_code: string;
  readonly status: string;
  readonly parent_version: string | null;
  readonly created_on: string;
  readonly created_by: string;
  readonly approved_by?: string;
  readonly approved_on?: string;
  readonly change_reason: string;
  readonly technical_hypothesis: string;
  readonly expected_effect: string;
  readonly observed_effect: string | null;
  readonly components: readonly DemoComponent[];
  readonly computed: DemoComputed;
}

export interface DemoFormula {
  readonly formula_code: string;
  readonly name: string;
  readonly project_code: string;
  readonly product_family: string;
  readonly owner: string;
  readonly versions: readonly DemoFormulaVersion[];
}

export const SUPPLIERS: readonly DemoSupplier[] = data.suppliers;
export const MATERIALS: readonly DemoMaterial[] = data.materials;
export const FORMULAS: readonly DemoFormula[] = data.formulas;

export function materialByCode(code: string): DemoMaterial | undefined {
  return MATERIALS.find((m) => m.material_code === code);
}

export function materialName(code: string): string {
  return materialByCode(code)?.name ?? code;
}

export function supplierByCode(code: string): DemoSupplier | undefined {
  return SUPPLIERS.find((s) => s.supplier_code === code);
}

export function formulaByCode(code: string): DemoFormula | undefined {
  return FORMULAS.find((f) => f.formula_code === code);
}

export function materialsFromSupplier(code: string): readonly DemoMaterial[] {
  return MATERIALS.filter((m) => m.suppliers.includes(code));
}

export function formulasForProject(projectCode: string): readonly DemoFormula[] {
  return FORMULAS.filter((f) => f.project_code === projectCode);
}

/**
 * The version a reader should be shown first.
 *
 * The APPROVED one, not simply the highest number. `CLAUDE.md` §8 makes
 * released formulations immutable and revisions additive, so the newest
 * version is frequently an unapproved draft — showing that by default would
 * present an unapproved composition as the formula.
 */
export function currentVersion(f: DemoFormula): DemoFormulaVersion {
  const approved = [...f.versions]
    .filter((v) => v.status === "approved" || v.status === "released")
    .sort((a, b) => b.version_number - a.version_number)[0];
  if (approved) return approved;
  return [...f.versions].sort((a, b) => b.version_number - a.version_number)[0]!;
}

/**
 * Material status, presented. Restricted and obsolete are NOT the same as
 * "unavailable" and must not collapse into one grey pill: a restricted
 * material may be used with an exemption, an obsolete one may not be used
 * at all but still appears in historical batches.
 */
export function materialStatus(m: DemoMaterial): Derived {
  switch (m.status) {
    case "preferred":
      return { status: "green", label: "PREFERRED" };
    case "approved":
      return { status: "green", label: "APPROVED" };
    case "development":
      return {
        status: "yellow",
        label: "IN DEVELOPMENT",
        reason: "Under evaluation — not yet approved for released formulations.",
      };
    case "restricted":
      return {
        status: "red",
        label: "RESTRICTED",
      };
    case "obsolete":
      return { status: "neutral", label: "OBSOLETE" };
    default:
      return { status: "neutral", label: m.status.toUpperCase() };
  }
}

/**
 * Supplier status, presented.
 *
 * Exhaustive with a default, like `materialStatus`. The suppliers page
 * previously rendered a hardcoded yellow "QUALIFIED" for every non-approved
 * state, so the moment a supplier became `suspended` or `disqualified` a
 * blocked source would have been shown as a usable one. Raised by the
 * Supervisor.
 */
export function supplierStatus(s: DemoSupplier): Derived {
  switch (s.status) {
    case "approved":
      return { status: "green", label: "APPROVED" };
    case "qualified":
      return {
        status: "yellow",
        label: "QUALIFIED",
        reason: "Qualified but not yet fully approved for released products.",
      };
    case "suspended":
      return { status: "red", label: "SUSPENDED" };
    case "disqualified":
      return { status: "red", label: "DISQUALIFIED" };
    default:
      return { status: "neutral", label: s.status.toUpperCase() };
  }
}

/**
 * Version status, presented. Shared by the formulations index and the
 * workspace so the two cannot disagree — they did: the index greened only
 * `approved` while the workspace greened `released` too, so a released
 * formula showed a neutral grey badge on one screen and green on the other.
 */
export function versionStatus(v: DemoFormulaVersion): Derived {
  switch (v.status) {
    case "approved":
      return { status: "green", label: "APPROVED" };
    case "released":
      return { status: "green", label: "RELEASED" };
    case "submitted":
      return {
        status: "yellow",
        label: "SUBMITTED",
        reason: "Submitted for approval — not yet approved for laboratory work.",
      };
    case "draft":
      return { status: "neutral", label: "DRAFT" };
    case "superseded":
      return { status: "neutral", label: "SUPERSEDED" };
    default:
      return { status: "neutral", label: v.status.toUpperCase() };
  }
}

/**
 * Whether a version may be submitted, from the blocks the ENGINE returned.
 *
 * Reads `computed.submission_blocks`; it does not re-derive them.
 */
export function submissionStatus(v: DemoFormulaVersion): Derived {
  const blocks = v.computed.submission_blocks;
  if (blocks.length === 0) {
    return { status: "green", label: "SUBMITTABLE" };
  }
  return {
    status: "red",
    label: `${blocks.length} BLOCKER${blocks.length === 1 ? "" : "S"}`,
  };
}
