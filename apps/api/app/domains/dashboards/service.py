"""The four role dashboards. TODO I4.

Chemist, Engineer, Lead, Director — the panels the source names for each
(`ITWRD App.txt` L7187-7261), answered from source records.

═══════════════════════════════════════════════════════════════════════════
THE FOUR RULES THESE ARE BUILT TO
═══════════════════════════════════════════════════════════════════════════

**1. EVERY RECORD PANEL CARRIES ITS SOURCE RECORD'S ID.** §2: "Dashboards
must drill down to real source records." A tile showing "7 failed tests" that
a chemist cannot click is a number they then have to go and find by hand,
which is worse than no tile — it tells them there is a problem and not which
one.

🔴 THREE PANELS ARE FACETS, NOT RECORDS, AND SAY SO. `pipeline_status`,
`rd_portfolio` and `innovation_pipeline` are GROUPED COUNTS — "how many
projects at each stage" has no single source record to point at. They carry no
`id` and cannot, which is a different thing from having forgotten one. An
earlier version of this paragraph claimed *every* row carried an id while
three panels did not, which is exactly the overclaiming comment this codebase
keeps finding in its own source. Raised by Codex.

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

from app.domains.approvals.service import pending_steps_for

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
# `pending_steps_for` defaults to 100 and the dashboard used to take that
# silently, so a Lead with 140 actionable steps was shown "100" with nothing
# saying so. Named here and reported through `truncated`. Raised by the
# Supervisor.
_APPROVAL_LIMIT = 100

_NOT_YET: dict[str, str] = {
    "doe_experiments": "DOE arrives in Slice 12 (pyDOE3, runs linked to formula and batch).",
    "pilot_projects": "Pilot and Scale-Up arrive in Slice 16.",
    "scale_up": "Pilot and Scale-Up arrive in Slice 16.",
    "qualification_tasks": "Qualification and Release arrive in Slice 18.",
    "pilot_qualification_pipeline": "Pilot arrives in Slice 16, Qualification in Slice 18.",
    # §27 asks the Engineer dashboard for "Safety-related Process Issues".
    # There is no process-deviation record in this product: `quality.failures`
    # is a FORMULA failing a test, not a process going wrong on a line, and
    # reading safety alerts under §27's name would answer a different question
    # while looking like an answer to this one. Named as absent rather than
    # approximated — "nothing to report" and "does not exist" are opposite
    # statements about the business, which is what `_unavailable` is for.
    "safety_process_issues": (
        "There is no process-deviation record yet. quality.failures is a formula "
        "failing a test, not a process issue; this arrives with Production."
    ),
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
    return {
        "available": False,
        "reason": _NOT_YET[panel],
        "rows": [],
        "count": 0,
        "truncated": False,
    }


def _panel(rows: list[dict[str, Any]], *, truncated_at: int | None = None) -> dict[str, Any]:
    """A panel that was answered.

    `truncated_at` is stated rather than hidden: a count that silently caps is
    a count Rule 2 cannot rely on, and "100" where the true answer is 140
    understates a backlog with nothing to say it did. Raised by the
    Supervisor.
    """
    return {
        "available": True,
        "reason": None,
        "rows": rows,
        "count": len(rows),
        "truncated": truncated_at is not None and len(rows) >= truncated_at,
    }


def _forbidden(permission: str) -> dict[str, Any]:
    """🔴 A THIRD STATE: THE PANEL EXISTS AND THIS CALLER MAY NOT ACT ON IT.

    Raised by the Supervisor, and it is the same mistake as `_unavailable`
    exists to prevent, one layer along. A permission-gated panel that returned
    an empty list was byte-identical to a genuinely empty queue — so a
    technician opening the engineer view was told there are no open process
    deviations while there were twelve.

    "Nothing to report", "not built yet" and "not yours to act on" are three
    different statements and a screen cannot infer which from an empty list.
    """
    return {
        "available": False,
        "reason": f"requires the {permission} permission",
        "rows": [],
        "count": 0,
        "truncated": False,
    }


def _rows(session: Session, sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    return [dict(r) for r in session.execute(text(sql), params).mappings()]


# ---------------------------------------------------------------------------
# Chemist — formulation activity and technical experimentation (§57)
# ---------------------------------------------------------------------------


def chemist_dashboard(
    session: Session,
    *,
    user_id: uuid.UUID,
    organization_id: uuid.UUID,
    held_permissions: frozenset[str] = frozenset(),
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

    # Lab work IN FLIGHT on MY formulas -- the chemist did not run the batch,
    # so scoping this by who created the BATCH would show them nothing.
    #
    # ⚠️ THIS IS A BATCH-STATE PANEL AND THE NAME OVERSELLS IT (Codex finding
    # 8). It answers "what of mine is in the lab right now", not "which
    # results are outstanding" -- a draft batch with no tests appears, and a
    # COMPLETED batch whose test has not been run does not. Answering the
    # narrower question needs a test-state join that would double this
    # panel's cost, and the broader one is what a chemist checking on their
    # own work actually wants. Stated rather than quietly approximated.
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
    #
    # THE LEFT JOIN AND ITS NULL BEHAVIOUR ARE DELIBERATE, and Codex was right
    # to ask. A failed test with NO investigation gives `fl.id IS NULL`, the
    # correlated NOT EXISTS is trivially true, and the row is INCLUDED with a
    # null `failure_id`. That is the intent: a RED result nobody opened an
    # investigation for is the MOST actionable row on this panel, and an inner
    # join would have hidden precisely it.
    #
    # It cannot fan out: migration 029 added a partial unique index on
    # `(organization_id, test_id)`, so at most one investigation names a test.
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
          -- An INVALID measurement is not a failure to answer -- a
          -- calibration breach makes the number untrustworthy, not the
          -- formula wrong. And a test that has been SUPERSEDED by a retest
          -- has been answered by that retest, which writes no
          -- `formula_version_drivers` row and so would otherwise leave the
          -- original here forever. Both raised by the Supervisor: without
          -- them this drifts from "what needs a chemist today" back into
          -- "everything that has ever gone wrong".
          AND t.validity_status <> 'invalid'
          AND NOT EXISTS (
                SELECT 1 FROM testing.tests retest
                WHERE retest.supersedes_test_id = t.id
                  AND retest.organization_id = t.organization_id
          )
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
        -- 🔴 ONE ROW PER VERSION (Codex finding 6). `DISTINCT` including
        -- `t.test_number` meant two approved confirmation tests on one
        -- version produced TWO candidates, and the panel counted a single
        -- formula twice. The actionable entity is the version.
        SELECT v.id, v.version_code, f.formula_code, v.project_id,
               count(*) AS confirming_tests
        FROM testing.tests t
        JOIN laboratory.samples s ON s.id = t.sample_id
        JOIN laboratory.batches b ON b.id = s.batch_id
        JOIN formulations.formula_versions v ON v.id = b.formula_version_id
        JOIN formulations.formulas f ON f.id = v.formula_id
        WHERE t.organization_id = :org
          AND v.created_by = :uid
          AND t.test_purpose = 'confirmation'
          -- 🔴 `final_confirmed`, WHICH IS WHAT THE COMMENT ALWAYS CLAIMED.
          -- This read `approval_state = 'approved'`, and DATA_MODEL.md makes
          -- those DIFFERENT states: `final_confirmed` moves false->true only
          -- FROM approved, requires `test.confirm`, and is never reachable
          -- from `conditionally_approved`. So an approved-but-unconfirmed
          -- test was listed as a validation candidate -- the query
          -- re-deriving an answer beside the stored one, which is the exact
          -- thing the comment said it avoided. Raised by the Supervisor.
          AND t.final_confirmed
          AND t.calculated_result = 'pass'
        GROUP BY v.id, v.version_code, f.formula_code, v.project_id
        ORDER BY v.version_code
        """,
        p,
    )

    # -----------------------------------------------------------------
    # §27's four chemist widgets (Phase 5).
    #
    # 🔴 EVERY ONE READS A TABLE THAT EXISTS AND HAS A WRITER. §27 lists what a
    # chemist wants to see; it does not license inventing a query for a subject
    # nobody built. Where that happens the panel is `_unavailable` with a
    # reason — see `safety_process_issues` on the engineer view.
    #
    # ⚠️ AND THEY ARE PERMISSION-GATED. RLS already scopes every row to what
    # this caller can reach, so the gate is not what keeps the data safe; it is
    # what stops the screen offering a queue the person cannot act on, which is
    # the distinction `_forbidden` exists to draw.
    # -----------------------------------------------------------------
    safety_reviews = (
        _rows(
            session,
            """
            SELECT r.id AS route_id, r.entity_id AS review_id, r.project_id,
                   r.opened_at, sr.reason, sv.material_id,
                   m.material_code, m.name AS material_name
              FROM workflow.approval_routes r
              JOIN safety.safety_reviews sr ON sr.id = r.entity_id
                                           AND sr.organization_id = r.organization_id
              JOIN safety.sds_versions sv   ON sv.id = sr.sds_version_id
                                           AND sv.organization_id = sr.organization_id
              JOIN materials.materials m    ON m.id = sv.material_id
                                           AND m.organization_id = sv.organization_id
             WHERE r.organization_id = :org
               AND r.entity_type = 'safety_review'
               AND r.status = 'open'
             ORDER BY r.opened_at
             LIMIT 50
            """,
            p,
        )
        if "compliance.review_sds" in held_permissions
        else None
    )

    investigations = (
        _rows(
            session,
            """
            SELECT i.id, i.investigation_code, i.title, i.status, i.project_id,
                   i.created_at,
                   (SELECT count(*) FROM research.findings f
                     WHERE f.investigation_id = i.id
                       AND f.organization_id = i.organization_id) AS finding_count
              FROM research.investigations i
             WHERE i.organization_id = :org
               AND i.owner_user_id = :uid
               AND i.status = 'active'
             ORDER BY i.created_at DESC
             LIMIT 50
            """,
            p,
        )
        if "research.view" in held_permissions
        else None
    )

    # 🔴 `proposed` ONLY, WHICH IS THE WIDGET'S WHOLE VALUE. §20 makes a
    # proposal inert until a chemist decides. Listing accepted ones would turn a
    # decision queue into a history — rule 2's defect precisely.
    proposals = (
        _rows(
            session,
            """
            SELECT x.id, x.proposal_code, x.objective, x.confidence, x.created_at,
                   x.project_id, i.investigation_code
              FROM research.experiment_proposals x
              JOIN research.investigations i ON i.id = x.investigation_id
                                            AND i.organization_id = x.organization_id
             WHERE x.organization_id = :org
               AND x.status = 'proposed'
             ORDER BY x.created_at
             LIMIT 50
            """,
            p,
        )
        if "research.view" in held_permissions
        else None
    )

    # 🔴 GATED ON `material.view`, AND IT WAS NOT (Codex P1).
    #
    # `GET /api/material-safety/alerts` requires `material.view`. This panel
    # returned the same rows to anybody who could load a dashboard — a SOFTER
    # DOOR to the same data than the endpoint that owns it, which is the I104
    # shape. RLS still scoped the rows, so the leak was bounded; the defect is
    # that authorization was decided in two places and one of them said yes.
    #
    # ⚠️ AND THE `_forbidden` MATTERS AS MUCH AS THE GATE. Without it a caller
    # lacking the permission saw an EMPTY actionable queue — "no safety alerts"
    # — which is a false all-clear rather than a refusal.
    material_alerts = (
        _rows(
            session,
            """
            SELECT a.id, a.severity, a.change_summary, a.created_at, a.project_id,
                   a.material_id, m.material_code, m.name AS material_name
              FROM safety.safety_alerts a
              -- LEFT, because 054 gave the alert TYPED targets rather than a
              -- polymorphic pointer: it may name a formula version or a batch
              -- instead of a material, and an inner join would drop exactly
              -- those.
              LEFT JOIN materials.materials m ON m.id = a.material_id
                                            AND m.organization_id = a.organization_id
             WHERE a.organization_id = :org
               AND a.acknowledged_at IS NULL
             -- 🔴 SEVERITY FIRST, THEN RECENCY. Ordering by time alone put a
             -- fresh `informational` above an older `critical` (Codex P2) --
             -- the lead and director panels already did this and the chemist's
             -- did not, which is the drift a shared vocabulary invites.
             ORDER BY CASE a.severity
                        WHEN 'critical' THEN 0 WHEN 'high' THEN 1 ELSE 2 END,
                      a.created_at DESC
             LIMIT 50
            """,
            p,
        )
        if "material.view" in held_permissions
        else None
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
            "safety_reviews_required": (
                _panel(safety_reviews, truncated_at=50)
                if safety_reviews is not None
                else _forbidden("compliance.review_sds")
            ),
            "research_investigations": (
                _panel(investigations, truncated_at=50)
                if investigations is not None
                else _forbidden("research.view")
            ),
            "experiment_proposals": (
                _panel(proposals, truncated_at=50)
                if proposals is not None
                else _forbidden("research.view")
            ),
            "material_alerts": (
                _panel(material_alerts, truncated_at=50)
                if material_alerts is not None
                else _forbidden("material.view")
            ),
        },
    }


# ---------------------------------------------------------------------------
# Engineer — test plans, reviews, and what the lab reported wrong
# ---------------------------------------------------------------------------


def engineer_dashboard(
    session: Session,
    *,
    user_id: uuid.UUID,
    organization_id: uuid.UUID,
    held_permissions: frozenset[str] = frozenset(),
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
    # 🔴 THE PERMISSION, NOT JUST THE IDENTITY (Codex finding 3). Excluding
    # the executor is necessary and not sufficient: someone without
    # `test.review` cannot review anything, so listing the work for them
    # inflates a count §11 requires to be of ACTIONABLE items. Visibility is
    # RLS's answer; actionability is this one.
    reviews = (
        _rows(
            session,
            """
            SELECT t.id, t.test_number, t.calculated_result, t.executed_at,
                   t.project_id
            FROM testing.tests t
            WHERE t.organization_id = :org
              AND t.execution_status = 'complete'
              AND t.review_state = 'awaiting_review'
              -- DATA_MODEL.md §3.5 bars the executor from reviewing their own
              -- measurements, so offering it here would be work the service
              -- refuses.
              AND (t.executed_by IS NULL OR t.executed_by <> :uid)
            ORDER BY t.executed_at NULLS LAST
            """,
            p,
        )
        if "test.review" in held_permissions
        else None
    )

    # Process deviations still open. `resolved_at IS NULL` is the whole
    # filter: a resolved deviation is a record, not an action.
    #
    # 🔴 `batch.execute` OR `batch.complete` -- THE PERMISSIONS THAT EXIST.
    #
    # The first version gated this on `batch.review`, WHICH IS NOT A
    # PERMISSION IN THIS SYSTEM. `core.permissions` holds batch.view, .create,
    # .execute, .complete and .reject -- so no user could ever hold it and the
    # panel returned EMPTY FOR EVERYONE, FOREVER, while reporting itself
    # available. That is precisely the failure mode this module's docstring
    # says it exists to catch, and it survived because the test supplied the
    # phantom permission to itself. Raised by the Supervisor.
    #
    # These two are what `POST /batches/{id}/deviations` requires -- the
    # person at the bench or the one reviewing -- so the panel now offers work
    # to exactly the people who can act on it.
    deviations = (
        _rows(
            session,
            """
        SELECT d.id, d.description, d.severity, d.raised_at,
               b.batch_number, d.batch_id, d.project_id
        FROM laboratory.batch_deviations d
        JOIN laboratory.batches b ON b.id = d.batch_id
        WHERE d.organization_id = :org AND d.resolved_at IS NULL
        ORDER BY
                CASE d.severity WHEN 'critical' THEN 0 WHEN 'major' THEN 1
                     WHEN 'minor' THEN 2 ELSE -1 END,
                d.raised_at
            """,
            p,
        )
        if held_permissions & {"batch.execute", "batch.complete"}
        else None
    )

    # -----------------------------------------------------------------
    # §27's engineer widgets (Phase 5).
    #
    # 🔴 "Research-linked tests" IS A REAL JOIN, NOT A LABEL. A test is
    # research-linked when an evidence card CITES it — `research.evidence`
    # carries a typed `test_id` for exactly this. Anything looser (a test in a
    # project that also has an investigation) would put unrelated work under a
    # heading that claims a connection.
    # -----------------------------------------------------------------
    # 🔴 BOTH PERMISSIONS, AND `research.view` ALONE WAS A BYPASS (Codex P1).
    #
    # The panel returns test numbers, execution state, calculated results and
    # execution times — `testing.tests` rows, whose own routes require
    # `test.view`. Gating on `research.view` alone let a research-only caller
    # read testing data through the dashboard. The panel is the INTERSECTION of
    # two modules, so it needs the permission of both.
    #
    # 🔴 AND `SELECT DISTINCT` DID NOT DO WHAT IT LOOKED LIKE (Codex P2). The
    # select list carried the investigation and the stance, so a test cited by
    # two investigations — or twice with different stances — produced two
    # "distinct" rows and INFLATED an actionable count. §11 says these counts
    # are of items needing action, so a double-counted test is a wrong answer,
    # not a cosmetic one. Aggregated per TEST instead, with the citations
    # collected: one row per test, and the panel can still say who cited it.
    research_tests = (
        _rows(
            session,
            """
            SELECT t.id, t.test_number, t.calculated_result, t.execution_status,
                   t.project_id, t.executed_at,
                   count(*) AS citation_count,
                   array_agg(DISTINCT i.investigation_code) AS investigation_codes,
                   array_agg(DISTINCT e.stance) AS stances
              FROM research.evidence e
              JOIN testing.tests t          ON t.id = e.test_id
                                           AND t.organization_id = e.organization_id
              JOIN research.investigations i ON i.id = e.investigation_id
                                           AND i.organization_id = e.organization_id
             WHERE e.organization_id = :org
               AND e.test_id IS NOT NULL
             GROUP BY t.id, t.test_number, t.calculated_result, t.execution_status,
                      t.project_id, t.executed_at
             ORDER BY t.executed_at DESC NULLS LAST
             LIMIT 50
            """,
            p,
        )
        if {"research.view", "test.view"} <= held_permissions
        else None
    )

    # A benchmark names one of OUR formula versions beside a competitor's
    # measured value. Gated on `test.view` because that is what the competitor
    # benchmark ROUTE is gated on — the dashboard must not be a softer door to
    # the same rows than the endpoint that owns them.
    benchmarks = (
        _rows(
            session,
            """
            SELECT b.id, b.attribute, b.competitor_value, b.our_value,
                   b.gap_summary, b.project_id, b.created_at,
                   cp.manufacturer, cp.product_name, v.version_code
              FROM competitors.benchmarks b
              JOIN competitors.products cp ON cp.id = b.competitor_product_id
                                          AND cp.organization_id = b.organization_id
              LEFT JOIN formulations.formula_versions v
                     ON v.id = b.formula_version_id
                    AND v.organization_id = b.organization_id
             WHERE b.organization_id = :org
             ORDER BY b.created_at DESC
             LIMIT 50
            """,
            p,
        )
        if "test.view" in held_permissions
        else None
    )

    return {
        "role": "engineer",
        "panels": {
            "pending_test_plans": _panel(planned),
            "engineering_reviews": (
                _panel(reviews) if reviews is not None else _forbidden("test.review")
            ),
            "pilot_projects": _unavailable("pilot_projects"),
            "scale_up": _unavailable("scale_up"),
            "process_deviations": (
                _panel(deviations)
                if deviations is not None
                else _forbidden("batch.execute or batch.complete")
            ),
            "qualification_tasks": _unavailable("qualification_tasks"),
            # §27's three engineer widgets (Phase 5).
            "research_linked_tests": (
                _panel(research_tests, truncated_at=50)
                if research_tests is not None
                else _forbidden("research.view and test.view")
            ),
            # 🔴 NOT APPROXIMATED. See `_NOT_YET["safety_process_issues"]`.
            "safety_process_issues": _unavailable("safety_process_issues"),
            "benchmark_investigations": (
                _panel(benchmarks, truncated_at=50)
                if benchmarks is not None
                else _forbidden("test.view")
            ),
        },
    }


# ---------------------------------------------------------------------------
# Lead — the projects they are answerable for
# ---------------------------------------------------------------------------


def lead_dashboard(
    session: Session,
    *,
    user_id: uuid.UUID,
    organization_id: uuid.UUID,
    held_permissions: frozenset[str] = frozenset(),
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
            CASE p.priority WHEN 'critical' THEN 0 WHEN 'high' THEN 1
                            WHEN 'medium' THEN 2 WHEN 'low' THEN 3
                            -- An unknown or NULL priority sorts FIRST, not
                            -- last: a value the vocabulary does not contain
                            -- is a data defect, and burying it at the bottom
                            -- with the low-priority work is how it stays
                            -- unnoticed. Raised by Codex.
                            ELSE -1 END,
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

    # 🔴 ONE ROW PER PROJECT, NOT PER BLOCKER (Codex finding 5).
    #
    # The first version UNION ALL'd risks and milestones, so a project with
    # three risks and two overdue milestones produced FIVE rows and a panel
    # named "blocked projects" reported `count: 5` for ONE blocked project.
    # The single-record tests could never have caught it.
    #
    # The reasons are aggregated onto the project instead, so the panel still
    # says WHY -- a tile reading "3 blocked" that does not say what is
    # stopping them sends somebody to open three projects and read them.
    blocked = _rows(
        session,
        """
        WITH blockers AS (
            SELECT p.id, p.project_code, p.name, 'high-impact risk' AS blocked_by,
                   r.title AS detail
            FROM projects.projects p
            JOIN projects.risks r
              ON r.project_id = p.id AND r.organization_id = p.organization_id
            WHERE p.organization_id = :org AND p.lead_user_id = :uid
              AND r.status IN ('open', 'mitigating') AND r.impact = 'high'
            UNION ALL
            SELECT p.id, p.project_code, p.name, 'overdue milestone' AS blocked_by,
                   m.name AS detail
            FROM projects.projects p
            JOIN projects.milestones m
              ON m.project_id = p.id AND m.organization_id = p.organization_id
            WHERE p.organization_id = :org AND p.lead_user_id = :uid
              AND m.status IN ('planned', 'in_progress')
              AND m.planned_date < CURRENT_DATE
        )
        SELECT id, project_code, name,
               count(*)                             AS blocker_count,
               array_agg(DISTINCT blocked_by)       AS blocked_by,
               array_agg(detail ORDER BY detail)    AS reasons
        FROM blockers
        GROUP BY id, project_code, name
        ORDER BY project_code
        """,
        p,
    )

    # 🔴 FINDINGS 1 AND 2 (Codex): THIS WAS BOTH UNAUTHORIZED AND DUPLICATED.
    #
    # It re-implemented the engine's sequencing rules and filtered on
    # `p.lead_user_id = :uid` -- which is not a permission. So it showed a
    # lead every open step INCLUDING ones they cannot decide (a QA rung is not
    # theirs), and showed an authorized non-lead NOTHING. §6: authorization is
    # on permissions, never on a role or a column that stands in for one.
    #
    # And re-implementing reachability guarantees eventual divergence: the
    # engine's rule changed twice in one day this session -- once for returned
    # rungs, once for escalation -- and a copy would have silently disagreed
    # with `decide_step` in both directions.
    #
    # `pending_steps_for` is the engine's own read-only queue and answers
    # exactly this question. It is a READ, so calling it from a dashboard does
    # not couple a view to something that writes.
    approvals = [
        dict(step)
        for step in pending_steps_for(
            session,
            organization_id=organization_id,
            held_permissions=held_permissions,
            limit=_APPROVAL_LIMIT,
        )
    ]

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
            CASE r.impact WHEN 'high' THEN 0 WHEN 'medium' THEN 1
                 WHEN 'low' THEN 2 ELSE -1 END
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

    # 🔴 A LEAD CAN SEE A RESTRICTED PROJECT AND NOT ITS CONTENTS, AND THE
    # PANELS WOULD REPORT THAT AS "NOTHING WRONG".
    #
    # Migration 006 gives `projects.projects` a lead exception
    # (`lead_user_id = core.current_user_id()`). The CHILD tables have no such
    # clause -- `projects.risks` and `projects.milestones` are
    # `confidentiality = 'normal' OR core.is_project_member(p.id)`, and
    # `is_project_member` reads `project_members` alone. So a Lead NAMED on a
    # restricted project but not carrying a membership row -- a state
    # migration 006's own commentary says occurs -- sees the project in
    # `assigned_projects` and ZERO risks, ZERO milestones and ZERO blockers.
    #
    # The panel would affirmatively report the project as unblocked and
    # risk-free, which is worse than saying nothing: it is a false all-clear
    # on the one screen a Lead uses to find what is going wrong.
    #
    # It cannot be fixed from here -- widening the query would not widen RLS,
    # and it should not. So the condition is DETECTED and reported. Raised by
    # the Supervisor.
    unreadable = _rows(
        session,
        """
        SELECT p.id, p.project_code, p.name
        FROM projects.projects p
        WHERE p.organization_id = :org
          AND p.lead_user_id = :uid
          AND p.confidentiality <> 'normal'
          AND NOT EXISTS (
                SELECT 1 FROM projects.project_members pm
                WHERE pm.project_id = p.id
                  AND pm.organization_id = p.organization_id
                  AND pm.user_id = :uid
                  AND pm.status = 'active'
          )
        ORDER BY p.project_code
        """,
        p,
    )

    # -----------------------------------------------------------------
    # §27's lead widgets (Phase 5).
    #
    # ⚠️ THESE INHERIT THE `incomplete_visibility` CAVEAT ABOVE, and that is
    # why it is stated at the top level rather than per panel: a lead who leads
    # a restricted project they are not a MEMBER of cannot see its research
    # either. RLS decides, so these panels are short rather than wrong — and
    # the caveat is what stops a short panel reading as an empty queue.
    # -----------------------------------------------------------------
    research_pipeline = (
        _rows(
            session,
            """
            SELECT i.id, i.investigation_code, i.title, i.status, i.project_id,
                   i.owner_user_id, i.created_at,
                   (SELECT count(*) FROM research.findings f
                     WHERE f.investigation_id = i.id
                       AND f.organization_id = i.organization_id) AS finding_count,
                   (SELECT count(*) FROM research.experiment_proposals x
                     WHERE x.investigation_id = i.id
                       AND x.organization_id = i.organization_id) AS proposal_count
              FROM research.investigations i
             WHERE i.organization_id = :org
               AND i.status = 'active'
             ORDER BY i.created_at DESC
             LIMIT 50
            """,
            p,
        )
        if "research.view" in held_permissions
        else None
    )

    # 🔴 THE VOCABULARY IS `critical | high | informational`, MEASURED.
    #
    # The first version of this filtered on `severity = 'high'` on the
    # assumption that severities run low/medium/high — and would therefore have
    # EXCLUDED every `critical` alert from a panel headed "Critical Safety
    # Alerts", which is the worst possible direction for that mistake. The
    # CHECK constraint said otherwise and a test caught it.
    #
    # `informational` is left out deliberately: a panel headed critical that
    # lists everything teaches a lead to ignore it, which is worse than not
    # having the panel at all.
    # 🔴 GATED, for the reason the chemist's panel is. Codex P1.
    critical_alerts = (
        _rows(
            session,
            """
            SELECT a.id, a.severity, a.change_summary, a.created_at, a.project_id,
                   a.material_id, m.material_code, m.name AS material_name
              FROM safety.safety_alerts a
              LEFT JOIN materials.materials m ON m.id = a.material_id
                                            AND m.organization_id = a.organization_id
             WHERE a.organization_id = :org
               AND a.severity IN ('critical', 'high')
               AND a.acknowledged_at IS NULL
             ORDER BY CASE a.severity WHEN 'critical' THEN 0 ELSE 1 END,
                      a.created_at DESC
             LIMIT 50
            """,
            p,
        )
        if "material.view" in held_permissions
        else None
    )

    gaps = (
        _rows(
            session,
            """
            SELECT g.id, g.description, g.impact, g.created_at,
                   i.investigation_code, i.project_id
              FROM research.knowledge_gaps g
              JOIN research.investigations i ON i.id = g.investigation_id
                                            AND i.organization_id = g.organization_id
             WHERE g.organization_id = :org
               AND g.status = 'open'
             ORDER BY CASE g.impact WHEN 'high' THEN 0 WHEN 'moderate' THEN 1
                                    ELSE 2 END,
                      g.created_at
             LIMIT 50
            """,
            p,
        )
        if "research.view" in held_permissions
        else None
    )

    proposal_queue = (
        _rows(
            session,
            """
            SELECT x.id, x.proposal_code, x.objective, x.confidence, x.created_at,
                   x.project_id, i.investigation_code
              FROM research.experiment_proposals x
              JOIN research.investigations i ON i.id = x.investigation_id
                                            AND i.organization_id = x.organization_id
             WHERE x.organization_id = :org
               AND x.status = 'proposed'
             ORDER BY x.created_at
             LIMIT 50
            """,
            p,
        )
        if "research.view" in held_permissions
        else None
    )

    return {
        "role": "lead",
        # Named at the top level rather than buried in a panel: it qualifies
        # EVERY panel below it, and a caveat attached to one of six would be
        # read as applying only to that one.
        "incomplete_visibility": [
            {
                **row,
                "reason": (
                    "you lead this restricted project but are not a member of it, so "
                    "its risks, milestones and blockers are not visible to you. The "
                    "panels below EXCLUDE them - they are not empty."
                ),
            }
            for row in unreadable
        ],
        "panels": {
            "assigned_projects": _panel(projects),
            "pipeline_status": _panel(pipeline),
            "blocked_projects": _panel(blocked),
            "pending_approvals": _panel(approvals, truncated_at=_APPROVAL_LIMIT),
            "risks": _panel(risks),
            "milestones": _panel(milestones),
            # §27's four lead widgets (Phase 5).
            "research_pipeline": (
                _panel(research_pipeline, truncated_at=50)
                if research_pipeline is not None
                else _forbidden("research.view")
            ),
            "critical_safety_alerts": (
                _panel(critical_alerts, truncated_at=50)
                if critical_alerts is not None
                else _forbidden("material.view")
            ),
            "knowledge_gaps": (
                _panel(gaps, truncated_at=50) if gaps is not None else _forbidden("research.view")
            ),
            "experiment_proposal_queue": (
                _panel(proposal_queue, truncated_at=50)
                if proposal_queue is not None
                else _forbidden("research.view")
            ),
        },
    }


# ---------------------------------------------------------------------------
# Director — the portfolio, not a project
# ---------------------------------------------------------------------------


def director_dashboard(
    session: Session,
    *,
    user_id: uuid.UUID,
    organization_id: uuid.UUID,
    held_permissions: frozenset[str] = frozenset(),
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

    # 🔴 `opportunity.view`, BECAUSE RLS DOES NOT GUARD THIS TABLE THE WAY THE
    # ROUTE DOCSTRING ASSUMED. `innovation.opportunities` carries an
    # ORGANIZATION-ONLY policy -- no project predicate, no confidentiality --
    # while `/api/opportunities` guards the same rows with
    # `require_permission("opportunity.view")`.
    #
    # So the dashboard's `project.view` floor was a way around that guard: a
    # laboratory_technician calling `/api/dashboards/director` received every
    # unannounced opportunity in the company, including the Director's whole
    # decision queue. Raised by the Supervisor, and the route's own reasoning
    # ("RLS decides what the caller sees") was FALSE for org-scoped tables.
    innovation = (
        _rows(
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
        if "opportunity.view" in held_permissions
        else None
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
    # And the DECISION queue needs the DECIDING permission (Supervisor finding
    # 8): every other queue in this module is gated on actionability, and a
    # Lead reading the director view was getting a list of decisions only a
    # Director can make.
    awaiting = (
        _rows(
            session,
            """
        SELECT o.id, o.opportunity_code, o.title, o.priority, o.status,
               o.created_at
        FROM innovation.opportunities o
        WHERE o.organization_id = :org
          -- 🔴 `awaiting_decision` ONLY (Codex finding 4). `feasibility`
          -- means somebody is still doing the work, and `on_hold` is the
          -- explicit statement that a decision is NOT being asked for. Both
          -- were in the first version, which turned a Director's decision
          -- queue into a list of everything not yet finished.
          AND o.status = 'awaiting_decision'
        ORDER BY
                CASE o.priority WHEN 'critical' THEN 0 WHEN 'high' THEN 1
                     WHEN 'medium' THEN 2 WHEN 'low' THEN 3 ELSE -1 END,
                o.created_at
            """,
            p,
        )
        if "opportunity.decide" in held_permissions
        else None
    )

    # -----------------------------------------------------------------
    # §27's director widgets (Phase 5).
    # -----------------------------------------------------------------
    # 🔴 GATED ON BOTH, AND IT WAS GATED ON NEITHER (Codex P1).
    #
    # The panel lists competitor products — `material.view` on their own routes
    # — and counts their BENCHMARKS, which `GET /api/competitors/{id}/benchmarks`
    # gates on `test.view`. Ungated, the director dashboard was a softer door to
    # both. Requiring the intersection is right for a panel that shows the
    # intersection; a director holds both, and anybody who does not should be
    # refused rather than shown a partial answer with no way to know it.
    competitors = (
        _rows(
            session,
            """
            SELECT cp.id, cp.manufacturer, cp.product_name, cp.market_segment,
                   cp.project_id, cp.created_at,
                   (SELECT count(*) FROM competitors.composition_evidence ce
                     WHERE ce.competitor_product_id = cp.id
                       AND ce.organization_id = cp.organization_id) AS evidence_count,
                   (SELECT count(*) FROM competitors.benchmarks b
                     WHERE b.competitor_product_id = cp.id
                       AND b.organization_id = cp.organization_id) AS benchmark_count
              FROM competitors.products cp
             WHERE cp.organization_id = :org
             ORDER BY cp.created_at DESC
             LIMIT 50
            """,
            p,
        )
        if {"material.view", "test.view"} <= held_permissions
        else None
    )

    technology = (
        _rows(
            session,
            """
            SELECT o.id, o.opportunity_code, o.title, o.status, o.priority,
                   o.product_family, o.target_application, o.created_at
              FROM innovation.opportunities o
             WHERE o.organization_id = :org
               AND o.technical_concept IS NOT NULL
             ORDER BY o.created_at DESC
             LIMIT 50
            """,
            p,
        )
        if "opportunity.view" in held_permissions
        else None
    )

    # 🔴 THE SAME DEFINITION OF "CRITICAL" AS THE LEAD'S PANEL, deliberately:
    # `critical` or `high`, unacknowledged. Two roles reading one answer, not
    # two definitions that can drift into disagreeing about which alerts
    # matter. Restricted to alerts that name a MATERIAL, because the panel is
    # material risks — an alert about a formula version belongs elsewhere.
    # 🔴 GATED, like its two siblings. Codex P1.
    material_risks = (
        _rows(
            session,
            """
            SELECT a.id, a.severity, a.change_summary, a.created_at, a.project_id,
                   a.material_id, m.material_code, m.name AS material_name
              FROM safety.safety_alerts a
              JOIN materials.materials m ON m.id = a.material_id
                                        AND m.organization_id = a.organization_id
             WHERE a.organization_id = :org
               AND a.severity IN ('critical', 'high')
               AND a.acknowledged_at IS NULL
             ORDER BY CASE a.severity WHEN 'critical' THEN 0 ELSE 1 END,
                      a.created_at DESC
             LIMIT 50
            """,
            p,
        )
        if "material.view" in held_permissions
        else None
    )

    research_portfolio = (
        _rows(
            session,
            """
            SELECT i.status,
                   count(*) AS investigations,
                   count(*) FILTER (WHERE i.project_id IS NULL) AS organization_wide,
                   (SELECT count(*) FROM research.findings f
                     WHERE f.organization_id = i.organization_id) AS findings_total,
                   (SELECT count(*) FROM research.experiment_proposals x
                     WHERE x.organization_id = i.organization_id
                       AND x.status = 'accepted') AS proposals_accepted
              FROM research.investigations i
             WHERE i.organization_id = :org
             GROUP BY i.status, i.organization_id
             ORDER BY i.status
            """,
            p,
        )
        if "research.view" in held_permissions
        else None
    )

    return {
        "role": "director",
        "panels": {
            "rd_portfolio": _panel(portfolio),
            "innovation_pipeline": (
                _panel(innovation) if innovation is not None else _forbidden("opportunity.view")
            ),
            "critical_risks": _panel(critical_risks),
            "projects_awaiting_approval": (
                _panel(awaiting) if awaiting is not None else _forbidden("opportunity.decide")
            ),
            "pilot_qualification_pipeline": _unavailable("pilot_qualification_pipeline"),
            "products_awaiting_release": _unavailable("products_awaiting_release"),
            # §27's four director widgets (Phase 5).
            "competitor_intelligence": (
                _panel(competitors, truncated_at=50)
                if competitors is not None
                else _forbidden("material.view and test.view")
            ),
            # 🔴 `technology_opportunities` IS `innovation_pipeline` FILTERED,
            # NOT A SECOND SOURCE. §27 asks the director for both; answering
            # them from two different tables would let the same portfolio give
            # two counts, which is the "two literals" defect wearing a
            # dashboard. Same rows, decided ones only.
            "technology_opportunities": (
                _panel(technology, truncated_at=50)
                if technology is not None
                else _forbidden("opportunity.view")
            ),
            "critical_material_risks": (
                _panel(material_risks, truncated_at=50)
                if material_risks is not None
                else _forbidden("material.view")
            ),
            "research_portfolio": (
                _panel(research_portfolio, truncated_at=50)
                if research_portfolio is not None
                else _forbidden("research.view")
            ),
        },
    }


ROLE_DASHBOARDS = {
    "chemist": chemist_dashboard,
    "engineer": engineer_dashboard,
    "lead": lead_dashboard,
    "director": director_dashboard,
}
