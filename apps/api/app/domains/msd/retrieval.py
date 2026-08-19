"""MSD retrieval -- the authorization boundary, as a mechanism.

🔴 THE RULE THIS MODULE EXISTS FOR

`CLAUDE.md` §7: "MSD operates under EXACTLY the calling user's
authorization boundary. If the user cannot open Formula F100 through the
app, MSD must not retrieve, summarize, infer or expose F100 in chat.
**Filter retrieval before the model sees anything — never filter after
generation.** AI must never become a permission-bypass channel."

WHY FILTERING AFTERWARDS IS THE FAILURE MODE
--------------------------------------------
It is seductive because it appears to work: hand the model everything,
let it write, then redact what the user should not see. What survives
redaction is an answer SHAPED by data the user has no right to — a
summary subtly different because F100 existed, a confidence that came
from another project's formulation, a "similar failures" list whose
similarity was computed over rows outside the boundary. Nothing in the
output names the leak, and no reviewer can detect it.

HOW THE BOUNDARY IS ENFORCED HERE
---------------------------------
There is no privileged reader in this module. Every query runs on the
CALLER'S OWN SESSION, whose RLS GUCs were set from their verified token,
so PostgreSQL applies the same policies that govern the screens they can
open. A restricted project they do not belong to is not filtered out by
this code — it is never returned to it.

That is a deliberate choice over the alternative of a service account
plus explicit `WHERE` clauses. A `WHERE` clause is a check somebody can
forget on the seventh query; RLS is a property of the connection. This
project has already been bitten by the difference — Codex found a formula
INSERT that RLS could not refuse, and the fix was to put the predicate
where it could not be omitted.

WHAT THIS MODULE DOES NOT DO
----------------------------
It does not call a model. `CLAUDE.md` §4 keeps the framework leak inside
`app/agents/graphs/`; this is the retrieval half, and it is deliberately
usable — and testable — with no LLM present at all. The boundary can
therefore be proven without a model in the loop, which is the only way
it could be proven reliably.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

__all__ = [
    "RetrievedRecord",
    "retrieve_for_question",
    "verify_evidence_within_boundary",
]


@dataclass(frozen=True, slots=True)
class RetrievedRecord:
    """One record MSD is allowed to reason over, and where it came from.

    `entity_type` and `entity_id` are carried so the answer can cite it —
    §7 requires MSD answers to carry evidence links to source records —
    and so `ai.msd_evidence` can record exactly what was used.
    """

    entity_type: str
    entity_id: uuid.UUID
    label: str
    excerpt: str


# 🔴 `CAST(:project AS uuid)`, NOT a bare `:project`.
#
# `project_id` is optional, so the parameter is often NULL — and psycopg
# sends an untyped NULL, which leaves PostgreSQL unable to resolve
# `$n IS NULL` against any operator. It fails at PARSE time with
# "could not determine data type of parameter", so the query never runs
# at all rather than running wrongly. The cast is load-bearing; removing
# it breaks every unfiltered retrieval.
#
# The searchable surface, as (entity_type, SQL). Each query selects a
# short human-readable label and an excerpt, and NONE of them carries a
# privilege escalation: they are ordinary reads that RLS filters.
#
# Written out per entity rather than as one dynamic query, because a
# dynamic one would need interpolated table names — and this repository
# has already learned three times that interpolation defended by an
# argument is not a mechanism.
_SOURCES: dict[str, str] = {
    "formula_version": """
        SELECT v.id AS entity_id,
               f.formula_code || ' ' || v.version_code AS label,
               coalesce(v.change_reason, '') || ' ' ||
               coalesce(v.technical_hypothesis, '') || ' ' ||
               coalesce(v.observed_effect, '') AS excerpt
        FROM formulations.formula_versions v
        JOIN formulations.formulas f
          ON f.id = v.formula_id AND f.organization_id = v.organization_id
        WHERE v.organization_id = :org
          AND (CAST(:project AS uuid) IS NULL OR v.project_id = CAST(:project AS uuid))
          AND (
                f.formula_code ILIKE :q OR f.name ILIKE :q
                OR v.version_code ILIKE :q
                OR coalesce(v.change_reason, '') ILIKE :q
                OR coalesce(v.technical_hypothesis, '') ILIKE :q
                OR coalesce(v.observed_effect, '') ILIKE :q
              )
        ORDER BY v.created_at DESC
        LIMIT :limit
    """,
    "material": """
        SELECT m.id AS entity_id,
               m.material_code || ' ' || m.name AS label,
               coalesce(m.description, '') || ' ' || coalesce(m.hazard_summary, '')
                   AS excerpt
        FROM materials.materials m
        WHERE m.organization_id = :org
          AND (
                m.material_code ILIKE :q OR m.name ILIKE :q
                OR coalesce(m.description, '') ILIKE :q
              )
        ORDER BY m.material_code
        LIMIT :limit
    """,
    "test": """
        SELECT t.id AS entity_id,
               t.test_number || ' (' || t.execution_status || ')' AS label,
               coalesce(t.calculated_result, 'not yet computed') || ' ' ||
               coalesce(t.notes, '') AS excerpt
        FROM testing.tests t
        WHERE t.organization_id = :org
          AND (CAST(:project AS uuid) IS NULL OR t.project_id = CAST(:project AS uuid))
          AND (t.test_number ILIKE :q OR coalesce(t.notes, '') ILIKE :q)
        ORDER BY t.created_at DESC
        LIMIT :limit
    """,
    "failure": """
        SELECT f.id AS entity_id,
               f.failure_code || ' ' || f.title AS label,
               coalesce(f.description, '') || ' ' || coalesce(f.closure_summary, '')
                   AS excerpt
        FROM quality.failures f
        WHERE f.organization_id = :org
          AND (CAST(:project AS uuid) IS NULL OR f.project_id = CAST(:project AS uuid))
          AND (
                f.failure_code ILIKE :q OR f.title ILIKE :q
                OR coalesce(f.description, '') ILIKE :q
              )
        ORDER BY f.opened_at DESC
        LIMIT :limit
    """,
    "batch": """
        SELECT b.id AS entity_id,
               b.batch_number || ' (' || b.status || ')' AS label,
               coalesce(b.purpose, '') || ' ' || coalesce(b.notes, '') AS excerpt
        FROM laboratory.batches b
        WHERE b.organization_id = :org
          AND (CAST(:project AS uuid) IS NULL OR b.project_id = CAST(:project AS uuid))
          AND (b.batch_number ILIKE :q OR coalesce(b.purpose, '') ILIKE :q)
        ORDER BY b.created_at DESC
        LIMIT :limit
    """,
}


def retrieve_for_question(
    session: Session,
    *,
    organization_id: uuid.UUID,
    question: str,
    project_id: uuid.UUID | None = None,
    entity_types: tuple[str, ...] | None = None,
    per_source_limit: int = 5,
) -> list[RetrievedRecord]:
    """Everything MSD is permitted to reason over for this question.

    🔴 `session` MUST BE THE CALLER'S OWN SESSION.

    Not a service account, not an unscoped one. Its RLS GUCs were set
    from the caller's verified token, so PostgreSQL returns exactly the
    rows they could open through the application — a restricted project
    they do not belong to is never returned here, rather than being
    filtered out afterwards.

    The signature takes no `user_id` on purpose. A parameter would invite
    a caller to pass somebody else's, and there is no honest reason to
    retrieve as one person on behalf of another.
    """
    if not question.strip():
        return []

    pattern = f"%{question.strip()}%"
    wanted = entity_types or tuple(_SOURCES)

    found: list[RetrievedRecord] = []
    for entity_type in wanted:
        sql = _SOURCES.get(entity_type)
        if sql is None:
            # An unknown source is refused rather than skipped. Skipping
            # would let a typo silently narrow the search and return a
            # confident, incomplete answer.
            raise ValueError(f"'{entity_type}' is not a retrievable source")

        rows = session.execute(
            text(sql),
            {
                "org": organization_id,
                "project": project_id,
                "q": pattern,
                "limit": per_source_limit,
            },
        ).mappings()

        found.extend(
            RetrievedRecord(
                entity_type=entity_type,
                entity_id=row["entity_id"],
                label=row["label"],
                excerpt=(row["excerpt"] or "").strip()[:500],
            )
            for row in rows
        )

    return found


def verify_evidence_within_boundary(
    session: Session,
    *,
    organization_id: uuid.UUID,
    turn_id: uuid.UUID,
) -> list[dict[str, Any]]:
    """Which cited records the CURRENT session cannot actually read.

    An empty list means every source of that answer is inside this
    caller's boundary.

    🔴 THIS IS WHY `ai.msd_evidence` EXISTS.

    §7's boundary is a property of retrieval, which makes it correct by
    construction — and unverifiable after the fact unless something wrote
    down what was retrieved. This reads the evidence back and re-checks
    each row against the caller's own RLS view, so "MSD respected the
    boundary" becomes a question with an answer rather than a claim about
    code.

    A non-empty result is not proof of a leak by itself: a record can
    legitimately become unreadable later, when a project is made
    restricted or a membership is revoked. It is a signal that a specific
    answer should be reviewed, which is exactly what an auditor wants.
    """
    cited = session.execute(
        text(
            """
            SELECT entity_type, entity_id, excerpt
            FROM ai.msd_evidence
            WHERE turn_id = :turn AND organization_id = :org
            """
        ),
        {"turn": turn_id, "org": organization_id},
    ).mappings()

    unreadable: list[dict[str, Any]] = []
    for row in cited:
        readable = _is_readable(
            session,
            entity_type=row["entity_type"],
            entity_id=row["entity_id"],
            organization_id=organization_id,
        )
        if not readable:
            unreadable.append(
                {
                    "entity_type": row["entity_type"],
                    "entity_id": row["entity_id"],
                    "note": (
                        "this answer cited a record the current session cannot read; "
                        "review whether the boundary held when it was written"
                    ),
                }
            )
    return unreadable


# Which table answers "can this session see it?" for each cited type.
# Existence under RLS IS the readability check: the policies are the
# same ones every screen is subject to.
_READABILITY: dict[str, str] = {
    "formula_version": (
        "SELECT 1 FROM formulations.formula_versions WHERE id = :id AND organization_id = :org"
    ),
    "material": "SELECT 1 FROM materials.materials WHERE id = :id AND organization_id = :org",
    "test": "SELECT 1 FROM testing.tests WHERE id = :id AND organization_id = :org",
    "failure": "SELECT 1 FROM quality.failures WHERE id = :id AND organization_id = :org",
    "batch": "SELECT 1 FROM laboratory.batches WHERE id = :id AND organization_id = :org",
    "project": "SELECT 1 FROM projects.projects WHERE id = :id AND organization_id = :org",
    "requirement": "SELECT 1 FROM projects.requirements WHERE id = :id AND organization_id = :org",
}


def _is_readable(
    session: Session, *, entity_type: str, entity_id: uuid.UUID, organization_id: uuid.UUID
) -> bool:
    sql = _READABILITY.get(entity_type)
    if sql is None:
        # An unrecognised type is reported as NOT readable, deliberately.
        # Treating the unknown as fine is how a check ends up passing over
        # exactly the cases nobody thought about.
        return False
    return session.execute(text(sql), {"id": entity_id, "org": organization_id}).first() is not None
