"""The four role dashboards. TODO I4.

Chemist, Engineer, Lead, Director — the panels the source names for each
(`ITWRD App.txt` L7187-7261), answered from source records.

═══════════════════════════════════════════════════════════════════════════
THE FOUR RULES THESE ARE BUILT TO
═══════════════════════════════════════════════════════════════════════════

**1. EVERY ROW CARRIES ITS SOURCE RECORD'S ID.** §2: "Dashboards must drill
down to real source records." A tile showing "7 failed tests" that a chemist
cannot click is a number they then have to go and find by hand, which is
worse than no tile — it tells them there is a problem and not which one. Every
panel returns rows with an `id` and the human-readable code beside it.

**2. COUNTS ARE OF ACTIONABLE ITEMS, NOT OF ROWS.** §11 says so about the
sidebar and it is the same discipline here. "Pending approvals: 12" that
includes nine somebody else must sign is a number nobody can act on.

**3. A PANEL THAT CANNOT BE ANSWERED SAYS SO.** Several panels the source
names — DOE runs, pilot activity, scale-up, qualification tasks, products
awaiting release — need engines from Slices 12-18 that do not exist. Those
panels are returned with `available: false` and the reason, NOT omitted and
NOT filled with something plausible.

🔴 An omitted panel reads as "nothing to report", which is a false statement
about the business. This codebase has been bitten by exactly that: a
demonstration dataset rendering as real data on every screen, and an empty
requirement set rendering "ALL REQUIREMENTS PASSED". Absence must be visible.

**4. SEPARATE QUERIES, NEVER ONE WIDE JOIN.** `projects/dashboard.py` says
why and it applies unchanged: a join across tests, batches and failures
multiplies rows against each other and silently inflates every count. That
fan-out is how a dashboard becomes confidently wrong.

═══════════════════════════════════════════════════════════════════════════
WHAT "MINE" MEANS, AND WHY IT IS NOT THE SAME QUESTION AS "VISIBLE"
═══════════════════════════════════════════════════════════════════════════

Each dashboard is scoped to the caller — their formulas, their reviews, their
projects. That is a RELEVANCE filter, not a security one: RLS and the project
predicate decide what the caller may see, and every query here filters
`organization_id` explicitly on top of that.

Confusing the two would be a real defect in both directions — a dashboard that
relied on "mine" for safety would leak the moment somebody widened it, and one
that relied on RLS for relevance would show a Director every row in the
company.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

__all__ = [
    "ROLE_DASHBOARDS",
    "chemist_dashboard",
    "director_dashboard",
    "engineer_dashboard",
    "lead_dashboard",
]

# Panels the source names that cannot be answered yet, and the slice that
# would answer them. Written out so a screen can say "not built" rather than
# "none", and so this list is the one place that has to change when a slice
# lands. `IMPLEMENTATION_PLAN.md` section I is the schedule these cite.
_NOT_YET: dict[str, str] = {
    "doe_experiments": "DOE arrives in Slice 12 (pyDOE3, runs linked to formula and batch).",
    "pilot_projects": "Pilot and Scale-Up arrive in Slice 16.",
    "scale_up": "Pilot and Scale-Up arrive in Slice 16.",
    "qualification_tasks": "Qualification and Release arrive in Slice 18.",
    "pilot_qualification_pipeline": "Pilot arrives in Slice 16, Qualification in Slice 18.",
    "products_awaiting_release": (
        "Product release arrives in Slice 18; there is no released-product record yet."
    ),
}


def _unavailable(panel: str) -> dict[str, Any]:
    """A panel that cannot be answered, saying so in the data.

    `available: false` rather than an empty list, because a screen cannot tell
    those apart and a reader certainly cannot: "no DOE experiments" and "DOE
    does not exist yet" are opposite statements about the business.
    """
    return {"available": False, "reason": _NOT_YET[panel], "rows": [], "count": 0}


def _panel(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {"available": True, "reason": None, "rows": rows, "count": len(rows)}


def _rows(session: Session, sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    return [dict(r) for r in session.execute(text(sql), params).mappings()]


# ---------------------------------------------------------------------------
# Chemist — formulation activity and technical experimentation (§57)
# ---------------------------------------------------------------------------


def chemist_dashboard(
    session: Session, *, user_id: uuid.UUID, organization_id: uuid.UUID
) -> dict[str, Any]:
    """My formulations, my results, and what came back failed."""
    p = {"uid": user_id, "org": organization_id}

    active = _rows(
        session,
        """
        SELECT v.id, v.version_code, v.status, v.version_number,
               f.formula_code, f.name AS formula_name,
               pr.project_code, v.project_id, v.updated_at
        FROM formulations.formula_versions v
        JOIN formulations.formulas f  ON f.id = v.formula_id
        JOIN projects.projects pr     ON pr.id = v.project_id
        WHERE v.organization_id = :org
          AND v.created_by = :uid
          -- ACTIVE, not "all mine". A released or superseded version is
          -- history; putting it here would bury the three drafts somebody
          -- is actually working on under a career's worth of finished work.
          AND v.status IN ('draft', 'submitted', 'approved')
        ORDER BY v.updated_at DESC
        """,
        p,
    )

    # Lab work in flight on MY formulas -- the chemist did not run the batch,
    # so scoping this by who created the BATCH would show them nothing.
    pending_lab = _rows(
        session,
        """
        SELECT b.id, b.batch_number, b.status, b.created_at,
               v.version_code, b.project_id
        FROM laboratory.batches b
        JOIN formulations.formula_versions v ON v.id = b.formula_version_id
        WHERE b.organization_id = :org
          AND v.created_by = :uid
          -- 'draft', not 'planned'. Vocabulary is draft|authorized|
          -- in_progress|completed|accepted|rejected|cancelled.
          AND b.status IN ('draft', 'authorized', 'in_progress')
        ORDER BY b.created_at
        """,
        p,
    )

    # 🔴 FAILED, AND NOT YET ANSWERED. A failure with a revision already
    # recorded against it is being dealt with; leaving it here would make the
    # panel a list of everything that has ever gone wrong rather than a list
    # of what needs a chemist today (rule 2).
    failed = _rows(
        session,
        """
        SELECT t.id, t.test_number, t.calculated_result, t.executed_at,
               t.project_id, fl.id AS failure_id, fl.failure_code
        FROM testing.tests t
        JOIN laboratory.samples s ON s.id = t.sample_id
        JOIN laboratory.batches b ON b.id = s.batch_id
        JOIN formulations.formula_versions v ON v.id = b.formula_version_id
        LEFT JOIN quality.failures fl
               ON fl.test_id = t.id AND fl.organization_id = t.organization_id
        WHERE t.organization_id = :org
          AND v.created_by = :uid
          AND t.calculated_result = 'fail'
          AND NOT EXISTS (
                SELECT 1 FROM formulations.formula_version_drivers d
                WHERE d.failure_id = fl.id
          )
        ORDER BY t.executed_at DESC NULLS LAST
        """,
        p,
    )

    # Reformulations: versions that exist BECAUSE something failed. §29's
    # question with its answer attached.
    reformulations = _rows(
        session,
        """
        SELECT v.id, v.version_code, v.status, v.change_reason,
               parent.version_code AS parent_version_code,
               fl.failure_code, v.project_id
        FROM formulations.formula_versions v
        JOIN formulations.formula_version_drivers d
          ON d.formula_version_id = v.id AND d.driver_type = 'failure'
        JOIN quality.failures fl ON fl.id = d.failure_id
        LEFT JOIN formulations.formula_versions parent
          ON parent.id = v.parent_version_id
        WHERE v.organization_id = :org AND v.created_by = :uid
        ORDER BY v.created_at DESC
        """,
        p,
    )

    # A validation candidate is a version whose CONFIRMATION test is finally
    # GREEN -- approved, not merely passing. `final_confirmed` is the stored
    # axis §10 reserves for exactly that, so this reads the system's own
    # answer instead of re-deriving one beside it.
    candidates = _rows(
        session,
        """
        SELECT DISTINCT v.id, v.version_code, f.formula_code, v.project_id,
               t.test_number
        FROM testing.tests t
        JOIN laboratory.samples s ON s.id = t.sample_id
        JOIN laboratory.batches b ON b.id = s.batch_id
        JOIN formulations.formula_versions v ON v.id = b.formula_version_id
        JOIN formulations.formulas f ON f.id = v.formula_id
        WHERE t.organization_id = :org
          AND v.created_by = :uid
          AND t.test_purpose = 'confirmation'
          AND t.approval_state = 'approved'
          AND t.calculated_result = 'pass'
        ORDER BY v.version_code
        """,
        p,
    )

    return {
        "role": "chemist",
        "panels": {
            "my_active_formulations": _panel(active),
            "pending_lab_results": _panel(pending_lab),
            "failed_tests": _panel(failed),
            "reformulations": _panel(reformulations),
            "doe_experiments": _unavailable("doe_experiments"),
            "validation_candidates": _panel(candidates),
        },
    }


# ---------------------------------------------------------------------------
# Engineer — test plans, reviews, and what the lab reported wrong
# ---------------------------------------------------------------------------


def engineer_dashboard(
    session: Session, *, user_id: uuid.UUID, organization_id: uuid.UUID
) -> dict[str, Any]:
    """Tests waiting to be run, results waiting to be reviewed."""
    p = {"uid": user_id, "org": organization_id}

    planned = _rows(
        session,
        """
        SELECT t.id, t.test_number, t.planned_for, t.test_purpose,
               t.authority_level, t.project_id, m.name AS method_name
        FROM testing.tests t
        JOIN testing.test_methods m ON m.id = t.method_id
        WHERE t.organization_id = :org
          AND t.created_by = :uid
          AND t.execution_status = 'not_started'
        ORDER BY t.planned_for NULLS LAST, t.created_at
        """,
        p,
    )

    # 🔴 REVIEWS THIS PERSON CAN ACTUALLY DO. A test is excluded when the
    # caller EXECUTED it -- DATA_MODEL.md §3.5 bars the executor from
    # reviewing their own measurements, so listing it here would offer work
    # the service will refuse. Rule 2: a count nobody can act on is noise.
    reviews = _rows(
        session,
        """
        SELECT t.id, t.test_number, t.calculated_result, t.executed_at,
               t.project_id
        FROM testing.tests t
        WHERE t.organization_id = :org
          AND t.execution_status = 'complete'
          AND t.review_state = 'awaiting_review'
          AND (t.executed_by IS NULL OR t.executed_by <> :uid)
        ORDER BY t.executed_at NULLS LAST
        """,
        p,
    )

    # Process deviations still open. `resolved_at IS NULL` is the whole
    # filter: a resolved deviation is a record, not an action.
    deviations = _rows(
        session,
        """
        SELECT d.id, d.description, d.severity, d.raised_at,
               b.batch_number, d.batch_id, d.project_id
        FROM laboratory.batch_deviations d
        JOIN laboratory.batches b ON b.id = d.batch_id
        WHERE d.organization_id = :org AND d.resolved_at IS NULL
        ORDER BY
            CASE d.severity WHEN 'critical' THEN 0 WHEN 'major' THEN 1 ELSE 2 END,
            d.raised_at
        """,
        p,
    )

    return {
        "role": "engineer",
        "panels": {
            "pending_test_plans": _panel(planned),
            "engineering_reviews": _panel(reviews),
            "pilot_projects": _unavailable("pilot_projects"),
            "scale_up": _unavailable("scale_up"),
            "process_deviations": _panel(deviations),
            "qualification_tasks": _unavailable("qualification_tasks"),
        },
    }


# ---------------------------------------------------------------------------
# Lead — the projects they are answerable for
# ---------------------------------------------------------------------------


def lead_dashboard(
    session: Session, *, user_id: uuid.UUID, organization_id: uuid.UUID
) -> dict[str, Any]:
    """Assigned projects, what is stuck, and what is waiting on a signature."""
    p = {"uid": user_id, "org": organization_id}

    projects = _rows(
        session,
        """
        SELECT p.id, p.project_code, p.name, p.status, p.current_stage,
               p.priority, p.target_release_date
        FROM projects.projects p
        WHERE p.organization_id = :org AND p.lead_user_id = :uid
        ORDER BY
            CASE p.priority WHEN 'critical' THEN 0 WHEN 'high' THEN 1 ELSE 2 END,
            p.target_release_date NULLS LAST
        """,
        p,
    )

    pipeline = _rows(
        session,
        """
        SELECT p.current_stage, count(*) AS projects
        FROM projects.projects p
        WHERE p.organization_id = :org AND p.lead_user_id = :uid
        GROUP BY p.current_stage
        ORDER BY p.current_stage
        """,
        p,
    )

    # BLOCKED means something is stopping it, and the panel says WHICH thing:
    # an open critical risk, or a milestone whose date has gone. A tile that
    # says "3 blocked" without saying why sends somebody to open three
    # projects and read them.
    blocked = _rows(
        session,
        """
        SELECT p.id, p.project_code, p.name, 'high-impact risk' AS blocked_by,
               r.title AS detail
        FROM projects.projects p
        JOIN projects.risks r
          ON r.project_id = p.id AND r.organization_id = p.organization_id
        WHERE p.organization_id = :org AND p.lead_user_id = :uid
          -- 🔴 `impact` is low|medium|high. There is NO 'critical' -- that
          -- vocabulary belongs to `criticality` on requirements and to
          -- `priority` on projects. Filtering on 'critical' here would have
          -- matched NOTHING and the panel would have read "no blocked
          -- projects" forever, which is the worst possible way to be wrong.
          AND r.status IN ('open', 'mitigating') AND r.impact = 'high'
        UNION ALL
        SELECT p.id, p.project_code, p.name, 'overdue milestone' AS blocked_by,
               m.name AS detail
        FROM projects.projects p
        JOIN projects.milestones m
          ON m.project_id = p.id AND m.organization_id = p.organization_id
        WHERE p.organization_id = :org AND p.lead_user_id = :uid
          -- 'met' and 'missed' are the CLOSED states (migration 003's
          -- vocabulary is planned|in_progress|met|missed|cancelled). There is
          -- no 'complete'; the first draft of this file invented one, which
          -- would have made every milestone look overdue.
          AND m.status IN ('planned', 'in_progress')
          AND m.planned_date < CURRENT_DATE
        ORDER BY project_code
        """,
        p,
    )

    # 🔴 APPROVALS THIS PERSON MUST SIGN, not every open route. The step's
    # own permission decides, and an earlier mandatory rung that has not
    # ADVANCED means this rung's turn has not come -- the same predicate the
    # engine enforces, so the dashboard cannot offer work `decide_step` would
    # refuse. Duplicated here rather than shared because a dashboard must
    # never call an engine that writes.
    approvals = _rows(
        session,
        """
        SELECT s.id AS step_id, s.step_label, s.permission_required,
               r.id AS route_id, r.entity_type, r.entity_id, r.template_code,
               r.project_id, r.opened_at
        FROM workflow.approval_route_steps s
        JOIN workflow.approval_routes r
          ON r.id = s.route_id AND r.organization_id = s.organization_id
        JOIN projects.projects p
          ON p.id = r.project_id AND p.organization_id = r.organization_id
        WHERE s.organization_id = :org
          AND r.status = 'open'
          AND s.decision IS NULL
          AND p.lead_user_id = :uid
          AND NOT EXISTS (
                SELECT 1 FROM workflow.approval_route_steps earlier
                WHERE earlier.route_id = s.route_id
                  AND earlier.parallel_group < s.parallel_group
                  AND earlier.is_mandatory
                  AND (
                        earlier.decision IS NULL
                        OR earlier.decision NOT IN
                             ('approve', 'approve_with_condition', 'escalate')
                  )
          )
        ORDER BY r.opened_at
        """,
        p,
    )

    risks = _rows(
        session,
        """
        SELECT r.id, r.risk_code, r.title, r.probability, r.impact, r.status,
               r.project_id
        FROM projects.risks r
        JOIN projects.projects p
          ON p.id = r.project_id AND p.organization_id = r.organization_id
        WHERE r.organization_id = :org AND p.lead_user_id = :uid
          -- 'mitigating' is still OPEN work: somebody is acting on it and it
          -- is not closed. Excluding it would hide the risks being actively
          -- worked, which are the ones a lead most needs to see.
          AND r.status IN ('open', 'mitigating')
        ORDER BY
            CASE r.impact WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END
        """,
        p,
    )

    milestones = _rows(
        session,
        """
        SELECT m.id, m.name, m.planned_date, m.status, m.project_id
        FROM projects.milestones m
        JOIN projects.projects p
          ON p.id = m.project_id AND p.organization_id = m.organization_id
        WHERE m.organization_id = :org AND p.lead_user_id = :uid
          -- planned|in_progress are the OPEN states; met|missed|cancelled
          -- are closed. There is no 'complete'.
          AND m.status IN ('planned', 'in_progress')
        ORDER BY m.planned_date NULLS LAST
        """,
        p,
    )

    return {
        "role": "lead",
        "panels": {
            "assigned_projects": _panel(projects),
            "pipeline_status": _panel(pipeline),
            "blocked_projects": _panel(blocked),
            "pending_approvals": _panel(approvals),
            "risks": _panel(risks),
            "milestones": _panel(milestones),
        },
    }


# ---------------------------------------------------------------------------
# Director — the portfolio, not a project
# ---------------------------------------------------------------------------


def director_dashboard(
    session: Session, *, user_id: uuid.UUID, organization_id: uuid.UUID
) -> dict[str, Any]:
    """Portfolio oversight.

    🔴 THE ONLY DASHBOARD NOT SCOPED TO "MINE", and deliberately: a Director's
    job is the portfolio, and a view of only the projects they personally
    lead is the one view that cannot do it. Scope is the ORGANIZATION, with
    RLS and the project-confidentiality predicate still deciding what is
    visible — a Director is not exempt from a restricted project they are not
    on, and nothing here overrides that.
    """
    p = {"uid": user_id, "org": organization_id}

    portfolio = _rows(
        session,
        """
        SELECT p.current_stage,
               count(*) AS projects,
               count(*) FILTER (WHERE p.priority IN ('critical', 'high'))
                   AS high_priority
        FROM projects.projects p
        WHERE p.organization_id = :org AND p.status = 'active'
        GROUP BY p.current_stage
        ORDER BY p.current_stage
        """,
        p,
    )

    innovation = _rows(
        session,
        """
        SELECT o.status, count(*) AS opportunities
        FROM innovation.opportunities o
        WHERE o.organization_id = :org
        GROUP BY o.status
        ORDER BY o.status
        """,
        p,
    )

    critical_risks = _rows(
        session,
        """
        SELECT r.id, r.risk_code, r.title, r.impact, r.probability,
               r.project_id, p.project_code
        FROM projects.risks r
        JOIN projects.projects p
          ON p.id = r.project_id AND p.organization_id = r.organization_id
        WHERE r.organization_id = :org
          AND r.status IN ('open', 'mitigating') AND r.impact = 'high'
        ORDER BY r.created_at
        """,
        p,
    )

    # "Projects awaiting approval" is the INNOVATION gate: an opportunity
    # submitted and waiting on a decision is a project that does not exist
    # yet, which is precisely what a Director is being asked to authorise.
    awaiting = _rows(
        session,
        """
        SELECT o.id, o.opportunity_code, o.title, o.priority, o.status,
               o.created_at
        FROM innovation.opportunities o
        WHERE o.organization_id = :org
          AND o.status IN ('awaiting_decision', 'feasibility', 'on_hold')
        ORDER BY
            CASE o.priority WHEN 'critical' THEN 0 WHEN 'high' THEN 1 ELSE 2 END,
            o.created_at
        """,
        p,
    )

    return {
        "role": "director",
        "panels": {
            "rd_portfolio": _panel(portfolio),
            "innovation_pipeline": _panel(innovation),
            "critical_risks": _panel(critical_risks),
            "projects_awaiting_approval": _panel(awaiting),
            "pilot_qualification_pipeline": _unavailable("pilot_qualification_pipeline"),
            "products_awaiting_release": _unavailable("products_awaiting_release"),
        },
    }


ROLE_DASHBOARDS = {
    "chemist": chemist_dashboard,
    "engineer": engineer_dashboard,
    "lead": lead_dashboard,
    "director": director_dashboard,
}
