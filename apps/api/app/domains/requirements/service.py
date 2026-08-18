"""Requirements — structured records and the Verification Matrix.

Requirements are structured, never free text, because the structure is
what makes automatic test evaluation possible at all. "Adhesion should be
good" cannot be compared against 5.3 MPa; `minimum_value = 6.000000`,
`canonical_unit = 'MPa'` can.

**The Verification Matrix** maps every requirement to the tests that
verify it and answers the four questions the source names:

    Which requirements have been tested?
    Which have passed?
    Which are pending?
    Which are blocking validation?

Test results arrive in Slice 5. Until then the matrix reports every
requirement as `not_verified` and says so explicitly — it does not
pretend, and it does not omit the column. A matrix that silently drops
the verification dimension until the tests exist is a matrix nobody
notices is empty.

**Approved requirements are immutable.** Changing an approved requirement
in place would retroactively alter what every existing test was measured
against — the same reasoning that makes formula versions immutable. A
change creates a new revision and supersedes the old one.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.audit import AuditEvent, write_audit

__all__ = [
    "RequirementError",
    "RequirementImmutableError",
    "RequirementInvalidError",
    "approve_requirement",
    "create_requirement",
    "revise_requirement",
    "verification_matrix",
]

# Statuses in which the record is fixed evidence rather than a draft.
_IMMUTABLE = {"approved", "locked", "superseded"}


class RequirementError(RuntimeError):
    """Base for refusals that are business rules, not bugs."""


class RequirementImmutableError(RequirementError):
    pass


class RequirementInvalidError(RequirementError):
    pass


@dataclass(frozen=True, slots=True)
class RequirementInput:
    requirement_code: str
    name: str
    category: str = "technical"
    description: str | None = None
    target_value: Decimal | None = None
    minimum_value: Decimal | None = None
    maximum_value: Decimal | None = None
    canonical_unit: str | None = None
    warning_threshold: Decimal | None = None
    criticality: str = "major"
    verification_method: str = "test"
    test_method_code: str | None = None
    source: str | None = None


def _validate(spec: RequirementInput) -> None:
    """Application-side checks that mirror the database constraints.

    Duplicated deliberately. The database constraints are the guarantee;
    these exist to produce a usable message instead of a raw
    integrity-violation traceback. If they ever disagree, the database
    wins and this function is the bug.
    """
    numeric = (spec.target_value, spec.minimum_value, spec.maximum_value)
    if any(v is not None for v in numeric) and not spec.canonical_unit:
        raise RequirementInvalidError(
            "a numeric requirement needs a unit — 'adhesion >= 6' is "
            "ambiguous between MPa and N/mm² by a factor that matters"
        )

    lo, hi, target = spec.minimum_value, spec.maximum_value, spec.target_value
    if lo is not None and hi is not None and lo > hi:
        raise RequirementInvalidError(f"minimum ({lo}) exceeds maximum ({hi}) — unsatisfiable")
    if lo is not None and target is not None and lo > target:
        raise RequirementInvalidError(f"target ({target}) is below minimum ({lo})")
    if hi is not None and target is not None and target > hi:
        raise RequirementInvalidError(f"target ({target}) is above maximum ({hi})")

    if spec.warning_threshold is not None:
        # The warning band sits INSIDE the acceptance range; a threshold
        # outside it can never fire, which is worse than not setting one
        # because it reads as configured.
        if lo is not None and spec.warning_threshold < lo:
            raise RequirementInvalidError(
                f"warning threshold ({spec.warning_threshold}) is below the "
                f"minimum ({lo}) — it could never fire"
            )
        if hi is not None and spec.warning_threshold > hi:
            raise RequirementInvalidError(
                f"warning threshold ({spec.warning_threshold}) is above the "
                f"maximum ({hi}) — it could never fire"
            )


def create_requirement(
    session: Session,
    *,
    project_id: uuid.UUID,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    spec: RequirementInput,
) -> uuid.UUID:
    _validate(spec)

    requirement_id: uuid.UUID = session.execute(
        text(
            """
            INSERT INTO projects.requirements
                (organization_id, project_id, requirement_code, category, name,
                 description, target_value, minimum_value, maximum_value,
                 canonical_unit, warning_threshold, criticality,
                 verification_method, test_method_code, source, created_by)
            VALUES
                (:org, :pid, :code, :category, :name, :description, :target,
                 :minimum, :maximum, :unit, :warn, :criticality,
                 :verification, :method_code, :source, :actor)
            RETURNING id
            """
        ),
        {
            "org": organization_id,
            "pid": project_id,
            "code": spec.requirement_code,
            "category": spec.category,
            "name": spec.name,
            "description": spec.description,
            "target": spec.target_value,
            "minimum": spec.minimum_value,
            "maximum": spec.maximum_value,
            "unit": spec.canonical_unit,
            "warn": spec.warning_threshold,
            "criticality": spec.criticality,
            "verification": spec.verification_method,
            "method_code": spec.test_method_code,
            "source": spec.source,
            "actor": actor_id,
        },
    ).scalar_one()

    write_audit(
        session,
        AuditEvent(
            action="requirement.created",
            entity_type="requirement",
            entity_id=str(requirement_id),
            organization_id=organization_id,
            user_id=actor_id,
            new_state={"code": spec.requirement_code, "criticality": spec.criticality},
            reason="requirement created",
        ),
    )
    return requirement_id


def approve_requirement(
    session: Session,
    *,
    requirement_id: uuid.UUID,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
) -> None:
    """Approve and lock. After this the record is evidence, not a draft."""
    row = (
        session.execute(
            text(
                "SELECT status, requirement_code, created_by FROM projects.requirements "
                "WHERE id = :id"
            ),
            {"id": requirement_id},
        )
        .mappings()
        .one_or_none()
    )

    if row is None:
        raise RequirementError("requirement not found")
    if row["status"] in _IMMUTABLE:
        raise RequirementImmutableError(f"requirement is already {row['status']}")

    session.execute(
        text(
            """
            UPDATE projects.requirements
            SET status = 'approved', approved_by = :actor, approved_at = now(),
                updated_at = now()
            WHERE id = :id
            """
        ),
        {"id": requirement_id, "actor": actor_id},
    )

    write_audit(
        session,
        AuditEvent(
            action="requirement.approved",
            entity_type="requirement",
            entity_id=str(requirement_id),
            organization_id=organization_id,
            user_id=actor_id,
            previous_state={"status": row["status"]},
            new_state={"status": "approved"},
            reason="requirement approved and locked",
        ),
    )


def revise_requirement(
    session: Session,
    *,
    requirement_id: uuid.UUID,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    spec: RequirementInput,
    reason: str,
) -> uuid.UUID:
    """Supersede an approved requirement with a new revision.

    Never an in-place edit. Editing an approved requirement would
    retroactively change what every existing test was measured against —
    a test recorded as passing 'adhesion >= 6.0' would silently become a
    test against 'adhesion >= 7.0', and the pass would be a lie. Same
    reasoning as formula version immutability.
    """
    if not reason or not reason.strip():
        raise RequirementInvalidError("a revision reason is required")

    current = (
        session.execute(
            text(
                "SELECT requirement_code, revision, project_id, status "
                "FROM projects.requirements WHERE id = :id"
            ),
            {"id": requirement_id},
        )
        .mappings()
        .one_or_none()
    )

    if current is None:
        raise RequirementError("requirement not found")

    _validate(spec)

    if spec.requirement_code != current["requirement_code"]:
        raise RequirementInvalidError(
            "a revision keeps the requirement code; a different code is a different requirement"
        )

    session.execute(
        text(
            "UPDATE projects.requirements SET status = 'superseded', "
            "updated_at = now() WHERE id = :id"
        ),
        {"id": requirement_id},
    )

    new_id: uuid.UUID = session.execute(
        text(
            """
            INSERT INTO projects.requirements
                (organization_id, project_id, requirement_code, category, name,
                 description, target_value, minimum_value, maximum_value,
                 canonical_unit, warning_threshold, criticality,
                 verification_method, test_method_code, source, status,
                 revision, created_by)
            VALUES
                (:org, :pid, :code, :category, :name, :description, :target,
                 :minimum, :maximum, :unit, :warn, :criticality, :verification,
                 :method_code, :source, 'draft', :revision, :actor)
            RETURNING id
            """
        ),
        {
            "org": organization_id,
            "pid": current["project_id"],
            "code": spec.requirement_code,
            "category": spec.category,
            "name": spec.name,
            "description": spec.description,
            "target": spec.target_value,
            "minimum": spec.minimum_value,
            "maximum": spec.maximum_value,
            "unit": spec.canonical_unit,
            "warn": spec.warning_threshold,
            "criticality": spec.criticality,
            "verification": spec.verification_method,
            "method_code": spec.test_method_code,
            "source": spec.source,
            "revision": current["revision"] + 1,
            "actor": actor_id,
        },
    ).scalar_one()

    write_audit(
        session,
        AuditEvent(
            action="requirement.revised",
            entity_type="requirement",
            entity_id=str(new_id),
            organization_id=organization_id,
            user_id=actor_id,
            previous_state={"id": str(requirement_id), "revision": current["revision"]},
            new_state={"id": str(new_id), "revision": current["revision"] + 1},
            reason=reason,
        ),
    )
    return new_id


def verification_matrix(
    session: Session, *, project_id: uuid.UUID, organization_id: uuid.UUID
) -> dict[str, Any]:
    """Every requirement against its verification evidence.

    Answers the four questions the source names. Until Slice 5 supplies
    test results, `verification_status` is `not_verified` for every row
    and `tests_available` is False — stated explicitly rather than left
    to look like "nothing has passed yet", which is a different claim.

    `blocking_validation` is the operative column: a critical requirement
    that is not verified is what stops a formula becoming a validation
    candidate.
    """
    rows = (
        session.execute(
            text(
                """
            SELECT id, requirement_code, name, category, criticality,
                   target_value, minimum_value, maximum_value, canonical_unit,
                   warning_threshold, verification_method, test_method_code,
                   status, revision
            FROM projects.requirements
            WHERE project_id = :pid AND organization_id = :org
              AND status <> 'superseded'
            ORDER BY
                CASE criticality
                    WHEN 'critical' THEN 1 WHEN 'major' THEN 2
                    WHEN 'minor' THEN 3 ELSE 4
                END,
                requirement_code
            """
            ),
            {"pid": project_id, "org": organization_id},
        )
        .mappings()
        .all()
    )

    entries = []
    for r in rows:
        # Slice 5 replaces this with a real join onto testing.test_results.
        # It is a named constant rather than a silent NULL so the gap is
        # visible in the payload itself.
        verification_status = "not_verified"
        blocking = r["criticality"] == "critical" and verification_status != "passed"

        entries.append(
            {
                "requirement_id": r["id"],
                "requirement_code": r["requirement_code"],
                "name": r["name"],
                "category": r["category"],
                "criticality": r["criticality"],
                "acceptance": _format_acceptance(r),
                "verification_method": r["verification_method"],
                "test_method_code": r["test_method_code"],
                "requirement_status": r["status"],
                "revision": r["revision"],
                "verification_status": verification_status,
                "latest_result": None,
                "blocking_validation": blocking,
            }
        )

    return {
        "project_id": project_id,
        "requirements": entries,
        "summary": {
            "total": len(entries),
            "verified": 0,
            "not_verified": len(entries),
            "blocking_validation": sum(1 for e in entries if e["blocking_validation"]),
        },
        # Explicit, not implied. Without this a caller cannot distinguish
        # "no requirement has passed" from "we cannot yet tell".
        "tests_available": False,
        "note": (
            "Test results arrive in Slice 5. Every requirement reports "
            "not_verified because no test evidence exists yet, not because "
            "testing has failed."
        ),
    }


def _format_acceptance(r) -> str:  # type: ignore[no-untyped-def]
    """Human-readable acceptance criterion, e.g. '>= 6.0 MPa' or '1.20-1.30 g/cm3'."""
    unit = f" {r['canonical_unit']}" if r["canonical_unit"] else ""
    lo, hi, target = r["minimum_value"], r["maximum_value"], r["target_value"]

    if lo is not None and hi is not None:
        # EN DASH is correct for a range; a hyphen reads as subtraction.
        return f"{_num(lo)}–{_num(hi)}{unit}"  # noqa: RUF001
    if lo is not None:
        return f"≥ {_num(lo)}{unit}"
    if hi is not None:
        return f"≤ {_num(hi)}{unit}"
    if target is not None:
        return f"{_num(target)}{unit}"
    return "qualitative"


def _num(value: Decimal) -> str:
    """Trim trailing zeros without losing significant figures."""
    return f"{value.normalize():f}" if isinstance(value, Decimal) else str(value)
