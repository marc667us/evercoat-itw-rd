"""Material safety and compliance lookup.

Concept Note §11 — *"MSD should assist users in locating and understanding
controlled safety and compliance information"* — with these examples:

    "Show the current SDS for this resin."
    "Which components in this formula are restricted?"
    "Are any material safety documents missing?"
    "Which formulas contain Material RM-104?"

and one hard limit, stated in the same section:

    "However, MSD should not replace formal Compliance/QA review. Safety
     and regulatory decisions should remain controlled through the
     appropriate Compliance or Quality workflow."

🔴 THIS TOOL REPORTS RECORD STATE. IT DOES NOT ASSESS HAZARD.

The distinction is the whole design. "RM-104 is `restricted`, the reason
on file is X, and its SDS is on file / is missing" are facts read out of
columns. "RM-104 is safe to use at 4%" is a compliance determination, and
nothing here produces one — not from `hazard_summary`, not from an SDS,
not from a model.

That is not squeamishness. A chemist who asks an assistant whether a
material is safe and gets a confident sentence has been given a
regulatory opinion by a text generator, and the founder's own document
forbids exactly that. So the answers are counts, statuses and stated
absences, and the absence of a document is reported as the ACTIONABLE
fact it is.

Every query runs on the caller's own RLS-scoped session, like every other
tool here.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

__all__ = ["formula_safety", "formulas_containing", "material_safety"]


def material_safety(
    session: Session, *, organization_id: uuid.UUID, query: str, limit: int = 5
) -> list[dict[str, Any]]:
    """Safety-record state for materials matching `query`.

    Matches on code or name, so "the resin" finds nothing and "RM-104" or
    "polyester resin" finds something — which is honest. A fuzzy matcher
    that guessed which resin was meant would be answering a safety
    question about a material the asker did not name.
    """
    rows = session.execute(
        text(
            """
            SELECT m.material_code, m.name, m.category, m.status,
                   m.restriction_reason, m.hazard_summary, m.requires_sds,
                   (SELECT count(*) FROM materials.usable_documents d
                     WHERE d.material_id = m.id
                       AND d.organization_id = m.organization_id
                       AND d.document_type = 'SDS') AS sds_count,
                   (SELECT max(d.issued_on) FROM materials.usable_documents d
                     WHERE d.material_id = m.id
                       AND d.organization_id = m.organization_id
                       AND d.document_type = 'SDS') AS sds_issued_on
            FROM materials.materials m
            WHERE m.organization_id = :org
              AND (m.material_code ILIKE :q OR m.name ILIKE :q)
            ORDER BY m.material_code
            LIMIT :limit
            """
        ),
        {"org": organization_id, "q": f"%{query.strip()}%", "limit": limit},
    ).mappings()
    return [dict(r) for r in rows]


def formula_safety(
    session: Session, *, organization_id: uuid.UUID, version_id: uuid.UUID
) -> list[dict[str, Any]]:
    """Every component of a formula version, with its safety-record state.

    Answers *"which components in this formula are restricted?"* and *"are
    any material safety documents missing?"* over one version.

    🔴 IT RETURNS EVERY COMPONENT, NOT JUST THE PROBLEM ONES.

    Returning only the restricted ones would make "no rows" mean two
    different things — nothing is restricted, or the formula has no
    components the caller can see — and those must never look the same in
    a safety answer. The caller decides what to highlight; the tool
    reports the set.
    """
    rows = session.execute(
        text(
            """
            SELECT m.material_code, m.name, m.status, m.restriction_reason,
                   m.requires_sds, c.percentage,
                   (SELECT count(*) FROM materials.usable_documents d
                     WHERE d.material_id = m.id
                       AND d.organization_id = m.organization_id
                       AND d.document_type = 'SDS') AS sds_count
            FROM formulations.formula_components c
            JOIN materials.materials m
              ON m.id = c.material_id AND m.organization_id = c.organization_id
            WHERE c.formula_version_id = :vid AND c.organization_id = :org
            ORDER BY c.display_order, m.material_code
            """
        ),
        {"vid": version_id, "org": organization_id},
    ).mappings()
    return [dict(r) for r in rows]


def formulas_containing(
    session: Session, *, organization_id: uuid.UUID, material_query: str, limit: int = 20
) -> list[dict[str, Any]]:
    """Which formula versions use a material — Concept Note §11's fourth question.

    🔴 THIS COULD NOT BE ANSWERED BY THE RECORD SEARCH, AND LOOKED AS IF
    IT COULD.

    `retrieve_for_question` matches a formula on its own CODE and NAME. So
    *"which formulas contain Material RM-104"* searched formula names for
    the string "RM-104", found nothing, and would have answered "I found
    no records you have access to" — a confident, wrong "no" about a
    safety question, which is the worst possible direction for this
    particular error.

    Answering it needs the component join, which is what this is.

    It is a safety question in practice, not a curiosity: it is the one
    asked when a material is restricted, an SDS expires, or a supplier
    recalls a lot, and the answer decides which work stops.
    """
    rows = session.execute(
        text(
            """
            SELECT f.formula_code, f.name AS formula_name,
                   v.version_code, v.status AS version_status,
                   m.material_code, c.percentage
            FROM formulations.formula_components c
            JOIN materials.materials m
              ON m.id = c.material_id AND m.organization_id = c.organization_id
            JOIN formulations.formula_versions v
              ON v.id = c.formula_version_id AND v.organization_id = c.organization_id
            JOIN formulations.formulas f
              ON f.id = v.formula_id AND f.organization_id = v.organization_id
            WHERE c.organization_id = :org
              AND (m.material_code ILIKE :q OR m.name ILIKE :q)
            ORDER BY f.formula_code, v.version_code
            LIMIT :limit
            """
        ),
        {"org": organization_id, "q": f"%{material_query.strip()}%", "limit": limit},
    ).mappings()
    return [dict(r) for r in rows]
