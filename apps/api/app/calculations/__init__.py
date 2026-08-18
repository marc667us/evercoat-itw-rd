"""Deterministic scientific calculation.

**Pure functions only.** No I/O, no database, no LLM, no framework import.
`CLAUDE.md` rule 2 is that Python owns deterministic scientific
calculation, and that the model may *call* these and *explain* them but
must never perform the arithmetic itself. That rule only means anything if
the functions it points at are reachable and testable without standing up
an application, so nothing in this package may import from `app.domains`,
`app.api` or SQLAlchemy.

**`Decimal`, never `float`.** `CLAUDE.md` §5: floating point on a
controlled formulation percentage is a defect. Every public function here
takes and returns `Decimal`, and rejects `float` at the boundary rather
than silently widening it — a `float` that reaches a formula percentage is
the bug, and accepting it here is where it would be laundered into looking
correct.
"""

from app.calculations.formulation import (
    Component,
    SubmissionBlock,
    binder_to_filler_ratio,
    cost_per_kg,
    normalize_to_100,
    scale_to_batch,
    solids_content,
    stoichiometric_hardener_parts,
    theoretical_density,
    total_percentage,
    validate_for_submission,
    voc_content_g_per_l,
)

__all__ = [
    "Component",
    "SubmissionBlock",
    "binder_to_filler_ratio",
    "cost_per_kg",
    "normalize_to_100",
    "scale_to_batch",
    "solids_content",
    "stoichiometric_hardener_parts",
    "theoretical_density",
    "total_percentage",
    "validate_for_submission",
    "voc_content_g_per_l",
]
