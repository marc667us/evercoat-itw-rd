"""Project dashboard and context bar.

CLAUDE.md §11 states what every major page must answer:

    Where am I in the process?  What is the current status?
    What changed?  What requires action?  What evidence supports this?

This module is deliberately shaped to those five questions rather than to
whatever the UI happened to need first. :func:`project_dashboard` returns
one key per question, so a missing answer is a missing key rather than a
panel somebody forgot to add.

**Every count drills down.** CLAUDE.md §2 requires dashboards to reach
real source records, so the aggregates here ship with the identifiers
needed to open what they counted. A KPI tile showing "4 overdue" that
cannot say *which* four is a number the user has to go and re-derive by
hand, which means they stop reading the tile.

**Nothing here is a status decision.** The traffic-light derivation
(CLAUDE.md §10) is a Slice 5 concern and belongs in one place. This
module reports stored statuses and counts; it must never grow its own
green/yellow/red logic, because a second implementation of that algorithm
is a second answer to a safety-critical question.
"""

from __future__ import annotations

import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session

__all__ = ["project_context", "project_dashboard"]


def project_context(
    session: Session, *, project_id: uuid.UUID, organization_id: uuid.UUID
) -> dict | None:
    """The context bar: who and what, on every page inside a project.

    Returns None when the project is not visible to the caller. The
    caller turns that into a 404 -- deliberately the same answer as "does
    not exist", because a project code is itself confidential information
    (CLAUDE.md §6, and the reason PermissionDenied does not distinguish
    either).
    """
    row = (
        session.execute(
            text(
                """
            SELECT p.id, p.project_code, p.name, p.status, p.priority,
                   p.current_stage, p.confidentiality, p.product_family,
                   p.start_date, p.target_release_date, p.authorized_at,
                   lead.display_name     AS lead_name,
                   director.display_name AS director_name,
                   o.opportunity_code,
                   sd.name     AS current_stage_name,
                   sd.sequence AS current_stage_sequence,
                   (SELECT COUNT(*) FROM workflow.stage_definitions s
                     WHERE s.organization_id = p.organization_id AND s.is_active)
                       AS total_stages
            FROM projects.projects p
            LEFT JOIN core.users lead     ON lead.id = p.lead_user_id
            LEFT JOIN core.users director ON director.id = p.director_user_id
            LEFT JOIN innovation.opportunities o
                   ON o.id = p.opportunity_id AND o.organization_id = p.organization_id
            LEFT JOIN workflow.stage_definitions sd
                   ON sd.stage_code = p.current_stage
                  AND sd.organization_id = p.organization_id
            WHERE p.id = :pid AND p.organization_id = :org
            """
            ),
            {"pid": project_id, "org": organization_id},
        )
        .mappings()
        .one_or_none()
    )
    return dict(row) if row is not None else None


def project_dashboard(
    session: Session, *, project_id: uuid.UUID, organization_id: uuid.UUID
) -> dict:
    """The five questions, answered from source records.

    Each query is separate rather than one wide join. A single join across
    requirements, tasks, milestones and risks multiplies rows against each
    other and silently inflates every count -- the classic fan-out that
    makes a dashboard confidently wrong. Four small indexed queries are
    both correct and, on the indexes migration 003 creates, cheaper.

    ``organization_id`` is filtered explicitly in every one. RLS is the
    backstop, never the scoping mechanism.
    """
    params = {"pid": project_id, "org": organization_id}

    # --- What is the current status? -----------------------------------
    requirements = (
        session.execute(
            text(
                """
            -- The buckets PARTITION the six statuses -- every row lands in
            -- exactly one of live/settled/retired, so total is their sum
            -- and a tile showing parts that do not add up to the whole is
            -- impossible. Counting only 'approved', 'draft' and
            -- 'superseded' silently dropped under_review, locked and
            -- withdrawn.
            SELECT COUNT(*)                                              AS total,
                   -- 'locked' is stronger than approved, not weaker.
                   COUNT(*) FILTER (WHERE status IN ('approved','locked'))
                       AS settled,
                   COUNT(*) FILTER (WHERE status IN ('draft','under_review'))
                       AS live,
                   -- Retired requirements are history, not outstanding
                   -- work. Counting them as unapproved raises an alarm
                   -- about requirements somebody deliberately closed.
                   COUNT(*) FILTER (WHERE status IN ('superseded','withdrawn'))
                       AS retired,
                   COUNT(*) FILTER (WHERE criticality = 'critical')      AS critical,
                   COUNT(*) FILTER (WHERE criticality = 'critical'
                                      AND status IN ('draft','under_review'))
                       AS critical_unapproved
            FROM projects.requirements
            WHERE project_id = :pid AND organization_id = :org
            """
            ),
            params,
        )
        .mappings()
        .one()
    )

    # --- What requires action? -----------------------------------------
    tasks = (
        session.execute(
            text(
                """
            SELECT COUNT(*) FILTER (WHERE status IN ('open','in_progress'))  AS open,
                   COUNT(*) FILTER (WHERE status = 'blocked')                AS blocked,
                   COUNT(*) FILTER (WHERE status IN ('open','in_progress')
                                      AND due_date IS NOT NULL
                                      AND due_date < CURRENT_DATE)           AS overdue,
                   COUNT(*) FILTER (WHERE status IN ('open','in_progress')
                                      AND priority = 'critical')             AS critical
            FROM workflow.tasks
            WHERE project_id = :pid AND organization_id = :org
            """
            ),
            params,
        )
        .mappings()
        .one()
    )

    # Drill-down for the "requires action" tile. Capped, and the cap is
    # visible to the caller as `open`/`overdue` above -- a truncated list
    # presented as the whole list is how "we fixed everything on the
    # dashboard" becomes untrue.
    action_items = session.execute(
        text(
            """
            SELECT t.id, t.title, t.priority, t.status, t.due_date,
                   t.required_action, u.display_name AS assignee
            FROM workflow.tasks t
            LEFT JOIN core.users u ON u.id = t.assigned_user_id
            WHERE t.project_id = :pid AND t.organization_id = :org
              AND t.status IN ('open','in_progress','blocked')
            ORDER BY
                (t.due_date IS NOT NULL AND t.due_date < CURRENT_DATE) DESC,
                CASE t.priority WHEN 'critical' THEN 1 WHEN 'high' THEN 2
                                WHEN 'medium' THEN 3 ELSE 4 END,
                t.due_date NULLS LAST
            LIMIT 10
            """
        ),
        params,
    ).mappings()

    milestones = (
        session.execute(
            text(
                """
            SELECT COUNT(*)                                        AS total,
                   COUNT(*) FILTER (WHERE status = 'met')          AS met,
                   COUNT(*) FILTER (WHERE status = 'missed')       AS missed,
                   COUNT(*) FILTER (WHERE status IN ('planned','in_progress')
                                      AND planned_date < CURRENT_DATE) AS overdue
            FROM projects.milestones
            WHERE project_id = :pid AND organization_id = :org
            """
            ),
            params,
        )
        .mappings()
        .one()
    )

    risks = (
        session.execute(
            text(
                """
            SELECT COUNT(*) FILTER (WHERE status IN ('open','mitigating')) AS open,
                   COUNT(*) FILTER (WHERE status IN ('open','mitigating')
                                      AND probability = 'high'
                                      AND impact = 'high')                 AS high_high,
                   COUNT(*) FILTER (WHERE status = 'realised')             AS realised
            FROM projects.risks
            WHERE project_id = :pid AND organization_id = :org
            """
            ),
            params,
        )
        .mappings()
        .one()
    )

    # --- What changed? --------------------------------------------------
    # From the append-only transition log, not from an updated_at column.
    # updated_at answers "when was this row last touched"; the log answers
    # "what happened and who did it", which is the actual question.
    recent = session.execute(
        text(
            """
            -- EVERY join carries organization_id, not just the outer
            -- WHERE. A top-level `t.organization_id = :org` scopes the
            -- transition row and says nothing about the rows joined to
            -- it: referential integrity bypasses RLS, so before migration
            -- 010 a tenant-A transition could name a tenant-B
            -- from_stage_id and this query would have rendered another
            -- tenant's stage_code on this tenant's dashboard (Codex C8).
            --
            -- Migration 010 added the missing composite FK, which makes
            -- that unrepresentable. These predicates stay anyway: a
            -- constraint added in one migration can be dropped in
            -- another, and a query that is only correct because of a
            -- constraint elsewhere is a query nobody can verify locally.
            SELECT t.transitioned_at AS at, t.reason, u.display_name AS actor,
                   fsd.stage_code AS from_stage, tsd.stage_code AS to_stage
            FROM workflow.stage_transitions t
            JOIN core.users u ON u.id = t.transitioned_by
            LEFT JOIN workflow.project_stages fps
                   ON fps.id = t.from_stage_id
                  AND fps.organization_id = t.organization_id
            LEFT JOIN workflow.stage_definitions fsd
                   ON fsd.id = fps.stage_definition_id
                  AND fsd.organization_id = fps.organization_id
            JOIN workflow.project_stages tps
                   ON tps.id = t.to_stage_id
                  AND tps.organization_id = t.organization_id
            JOIN workflow.stage_definitions tsd
                   ON tsd.id = tps.stage_definition_id
                  AND tsd.organization_id = tps.organization_id
            WHERE t.project_id = :pid AND t.organization_id = :org
            ORDER BY t.transitioned_at DESC
            LIMIT 5
            """
        ),
        params,
    ).mappings()

    return {
        # Where am I in the process? -- the pipeline itself is served by
        # pipeline.project_pipeline(); the context bar carries the
        # position so a page can show it without a second round trip.
        "context": project_context(session, project_id=project_id, organization_id=organization_id),
        # What is the current status?
        "requirements": {k: int(v) for k, v in requirements.items()},
        "milestones": {k: int(v) for k, v in milestones.items()},
        "risks": {k: int(v) for k, v in risks.items()},
        # What requires action?
        "tasks": {k: int(v) for k, v in tasks.items()},
        "action_items": [dict(r) for r in action_items],
        # What changed?
        "recent_transitions": [dict(r) for r in recent],
    }
