"""The formulation equations, as a tool MSD may call.

Concept Note §17 draws the line this module sits on:

    "Scientific calculation engine calculates. MSD interprets and
     communicates."

and rule 2 of the seven non-negotiables makes it a rule rather than a
preference:

    "Python owns deterministic scientific calculation. The LLM may CALL
     calculation tools and EXPLAIN results; it must never perform the
     arithmetic."

🔴 SO THIS DELEGATES. IT COMPUTES NOTHING.

`evaluate_version` already runs every equation — total percentage,
theoretical density, binder-to-filler, solids content, VOC content, cost
— through `app/calculations/formulation.py`, with Hypothesis tests behind
it. A second implementation here would be a second answer to "what is
this formula's density", and the two would disagree the first time either
changed. The `pending_work` tool had exactly that defect this morning.

🔴 COST IS A PERMISSION, AND MSD IS NOT AN EXCEPTION.

`evaluate_version(include_cost=...)` is decided by the ROUTE from
`formula.view_cost`, and the key is ABSENT rather than null when the
caller lacks it — a null would read as "no cost data exists", which is a
different and false statement. MSD passes the same permission through, so
asking the assistant is not a way around a permission that governs the
screen. That is §7's "AI must never become a permission-bypass channel",
applied to a field rather than to a record.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.domains.formulations.service import compare_versions, evaluate_version

__all__ = ["compare_formulas", "formula_figures"]


def formula_figures(
    session: Session,
    *,
    organization_id: uuid.UUID,
    version_id: uuid.UUID,
    include_cost: bool,
) -> dict[str, Any]:
    """Every derived property of a formula version, and its submission blocks.

    The result's shape is deliberately preserved from the engine: each
    property is either a value or a STATED REASON it could not be
    computed — "density unknown for: RM-FIL-07" — never a null and never
    a zero. MSD must carry that sentence through to the reader rather
    than reporting a blank, because a blank reads as "calculated, and it
    came out empty".

    `include_cost` comes from the caller's `formula.view_cost`.
    """
    return evaluate_version(
        session,
        version_id=version_id,
        organization_id=organization_id,
        include_cost=include_cost,
    )


def compare_formulas(
    session: Session,
    *,
    organization_id: uuid.UUID,
    left_version_id: uuid.UUID,
    right_version_id: uuid.UUID,
    include_cost: bool,
) -> dict[str, Any]:
    """Two versions, side by side — Concept Note §9.

    🔴 IT DELEGATES, AND IT DOES NOT SUBTRACT.

    `compare_versions` returns each component as a PAIR of percentages
    rather than a delta, and says why in its own docstring: *"The
    percentage-point delta on a component is a SUBTRACTION OF TWO
    PERCENTAGES and is therefore arithmetic -- so it is not done here."*
    Two such conversions were already caught inside React components on
    this project.

    MSD is the last place that rule should be relaxed. The composition
    renders "12.5000 -> 9.0000", never "-3.5", so nothing in the assistant
    computes a number a chemist might quote.

    `include_cost` is the caller's `formula.view_cost`, threaded from the
    verified principal exactly as `formula_figures` does.
    """
    return compare_versions(
        session,
        left_version_id=left_version_id,
        right_version_id=right_version_id,
        organization_id=organization_id,
        include_cost=include_cost,
    )
