"""Administration — section 2: stage-gate configuration.

ADR-021: **a configuration value referenced anywhere must have an
Administration screen in the same slice or earlier.** Slice 2's pipeline
reads `workflow.stage_definitions` on every transition -- the stage list,
the entry criteria, `requires_approval` and `approval_role` all come from
these rows. Without this router those rows exist only because a seed
script inserted them, which is the exact failure Administration §1 was
built to stop: *ask of every configuration value, which production path
writes it?*

Three rules make this router different from ordinary CRUD.

**Stages are retired, never deleted.** A deleted stage definition orphans
every `workflow.project_stages` row that references it, and those rows
are the project's history. `is_active = false` removes it from the
pipeline going forward while leaving what already happened intact -- the
same reason CLAUDE.md §5 forbids cascade-deleting R&D history.

**Sequence is unique per organization and reordering is one statement.**
`stage_definitions_org_seq_key` means a naive "set A to 2, set B to 3"
collides mid-way through. Reordering is therefore a single UPDATE ... FROM
against the whole set, which the constraint checks once at statement end.

**`requires_approval` cannot be set without `approval_role`.** The
`stage_definitions_approval_complete` CHECK enforces it; it is validated
here too so the caller gets a message naming the field rather than a
constraint name. A gate that requires approval from nobody in particular
is a gate that never opens.
"""

from __future__ import annotations

import uuid
from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import text
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.audit import AuditEvent, write_audit
from app.core.db import guarded_write
from app.core.logging import log_audit
from app.core.security import Principal, get_db, require_permission

router = APIRouter()

__all__ = ["router"]


class StageDefinitionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    stage_code: str
    name: str
    sequence: int
    entry_criteria: str | None
    required_deliverables: str | None
    exit_criteria: str | None
    responsible_role: str | None
    requires_approval: bool
    approval_role: str | None
    is_active: bool
    # How many projects have ever been in this stage. Shown beside the
    # retire control so an administrator can see what they are about to
    # remove from the pipeline before they do it.
    projects_visited: int


class StageDefinitionWrite(BaseModel):
    stage_code: str = Field(min_length=1, max_length=50, pattern="^[A-Z0-9_]+$")
    name: str = Field(min_length=1, max_length=100)
    sequence: int = Field(ge=1, le=999)
    entry_criteria: str | None = None
    required_deliverables: str | None = None
    exit_criteria: str | None = None
    responsible_role: str | None = None
    requires_approval: bool = False
    approval_role: str | None = None

    @model_validator(mode="after")
    def _approval_needs_an_approver(self) -> StageDefinitionWrite:
        """Mirror of the stage_definitions_approval_complete CHECK.

        Validated here as well as in the database so the caller is told
        which field is wrong. The constraint stays because this validator
        only guards the HTTP path -- a migration or a later module
        reaching the table directly is governed by the database.
        """
        if self.requires_approval and not self.approval_role:
            raise ValueError(
                "approval_role is required when requires_approval is true: "
                "a gate that requires approval from nobody never opens"
            )
        return self


class StageReorder(BaseModel):
    # The complete ordered list of stage ids. Partial reorders are not
    # accepted: the unique constraint on (organization_id, sequence)
    # means a partial list can only be applied by guessing what the
    # caller intended for the rest.
    ordered_stage_ids: list[uuid.UUID] = Field(min_length=1)


class StageActivation(BaseModel):
    is_active: bool
    reason: str = Field(min_length=3, max_length=500)


@router.get("/stage-gates", response_model=list[StageDefinitionRead], tags=["admin"])
def list_stage_definitions(
    include_inactive: bool = True,
    principal: Principal = Depends(require_permission("admin.stage_gates")),
    session: Session = Depends(get_db),
) -> list[StageDefinitionRead]:
    """The configured pipeline.

    Inactive stages are included by default. An administration screen that
    hides retired configuration cannot explain why a project's history
    mentions a stage that appears nowhere in the list.
    """
    rows = session.execute(
        text(
            """
            SELECT sd.id, sd.stage_code, sd.name, sd.sequence, sd.entry_criteria,
                   sd.required_deliverables, sd.exit_criteria, sd.responsible_role,
                   sd.requires_approval, sd.approval_role, sd.is_active,
                   (SELECT COUNT(DISTINCT ps.project_id)
                      FROM workflow.project_stages ps
                     WHERE ps.stage_definition_id = sd.id) AS projects_visited
            FROM workflow.stage_definitions sd
            WHERE sd.organization_id = :org
              AND (:include_inactive OR sd.is_active)
            ORDER BY sd.sequence
            """
        ),
        {"org": principal.organization_id, "include_inactive": include_inactive},
    ).mappings()
    return [StageDefinitionRead(**r) for r in rows]


@router.post(
    "/stage-gates",
    response_model=StageDefinitionRead,
    status_code=status.HTTP_201_CREATED,
    tags=["admin"],
)
def create_stage_definition(
    payload: StageDefinitionWrite,
    principal: Principal = Depends(require_permission("admin.stage_gates")),
    session: Session = Depends(get_db),
) -> StageDefinitionRead:
    """Add a stage to the pipeline."""
    try:
        with guarded_write(session):
            row = (
                session.execute(
                    text(
                        """
                    INSERT INTO workflow.stage_definitions
                        (organization_id, stage_code, name, sequence, entry_criteria,
                         required_deliverables, exit_criteria, responsible_role,
                         requires_approval, approval_role)
                    VALUES (:org, :code, :name, :seq, :entry, :deliverables, :exit,
                            :responsible, :requires_approval, :approval_role)
                    RETURNING id, stage_code, name, sequence, entry_criteria,
                              required_deliverables, exit_criteria, responsible_role,
                              requires_approval, approval_role, is_active,
                              0 AS projects_visited
                    """
                    ),
                    {
                        "org": principal.organization_id,
                        "code": payload.stage_code,
                        "name": payload.name,
                        "seq": payload.sequence,
                        "entry": payload.entry_criteria,
                        "deliverables": payload.required_deliverables,
                        "exit": payload.exit_criteria,
                        "responsible": payload.responsible_role,
                        "requires_approval": payload.requires_approval,
                        "approval_role": payload.approval_role,
                    },
                )
                .mappings()
                .one()
            )
    except IntegrityError as exc:
        # Both unique constraints land here. The message names which,
        # because "duplicate key" alone sends an administrator hunting
        # through a list for a clash they cannot see.
        detail = (
            f"stage code {payload.stage_code} already exists"
            if "org_code" in str(exc.orig)
            else f"sequence {payload.sequence} is already taken by another stage"
        )
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail) from exc

    write_audit(
        session,
        AuditEvent(
            action="admin.stage_gate_created",
            entity_type="stage_definition",
            entity_id=str(row["id"]),
            organization_id=principal.organization_id,
            user_id=principal.user_id,
            new_state={
                "stage_code": payload.stage_code,
                "sequence": payload.sequence,
                "requires_approval": payload.requires_approval,
                "approval_role": payload.approval_role,
            },
            reason="stage gate configured",
        ),
    )
    log_audit("stage_gate_created", stage_code=payload.stage_code)
    return StageDefinitionRead(**row)


@router.put("/stage-gates/{stage_id}", response_model=StageDefinitionRead, tags=["admin"])
def update_stage_definition(
    stage_id: uuid.UUID,
    payload: StageDefinitionWrite,
    principal: Principal = Depends(require_permission("admin.stage_gates")),
    session: Session = Depends(get_db),
) -> StageDefinitionRead:
    """Edit a stage.

    `stage_code` is editable, and that is a considered decision rather
    than an oversight: `projects.current_stage` stores the code, so a
    rename must carry through. The UPDATE below does both in one
    transaction. Leaving them to drift would make the denormalised column
    point at a stage that no longer exists under that name -- the
    two-literals-in-two-places failure, in a place a type-checker cannot
    see.
    """
    before = (
        session.execute(
            text(
                """
            SELECT stage_code, name, sequence, requires_approval, approval_role
            FROM workflow.stage_definitions
            WHERE id = :sid AND organization_id = :org
            """
            ),
            {"sid": stage_id, "org": principal.organization_id},
        )
        .mappings()
        .one_or_none()
    )
    if before is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="stage not found")

    try:
        with guarded_write(session):
            row = (
                session.execute(
                    text(
                        """
                    UPDATE workflow.stage_definitions
                    SET stage_code = :code, name = :name, sequence = :seq,
                        entry_criteria = :entry, required_deliverables = :deliverables,
                        exit_criteria = :exit, responsible_role = :responsible,
                        requires_approval = :requires_approval,
                        approval_role = :approval_role
                    WHERE id = :sid AND organization_id = :org
                    RETURNING id, stage_code, name, sequence, entry_criteria,
                              required_deliverables, exit_criteria, responsible_role,
                              requires_approval, approval_role, is_active,
                              (SELECT COUNT(DISTINCT ps.project_id)
                                 FROM workflow.project_stages ps
                                WHERE ps.stage_definition_id = :sid) AS projects_visited
                    """
                    ),
                    {
                        "sid": stage_id,
                        "org": principal.organization_id,
                        "code": payload.stage_code,
                        "name": payload.name,
                        "seq": payload.sequence,
                        "entry": payload.entry_criteria,
                        "deliverables": payload.required_deliverables,
                        "exit": payload.exit_criteria,
                        "responsible": payload.responsible_role,
                        "requires_approval": payload.requires_approval,
                        "approval_role": payload.approval_role,
                    },
                )
                .mappings()
                .one()
            )
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="stage code or sequence is already taken by another stage",
        ) from exc

    # Carry a rename through to the denormalised column, in the same
    # transaction as the rename itself.
    if before["stage_code"] != payload.stage_code:
        session.execute(
            text(
                """
                UPDATE projects.projects
                SET current_stage = :new, updated_at = now()
                WHERE organization_id = :org AND current_stage = :old
                """
            ),
            {
                "org": principal.organization_id,
                "old": before["stage_code"],
                "new": payload.stage_code,
            },
        )

    write_audit(
        session,
        AuditEvent(
            action="admin.stage_gate_updated",
            entity_type="stage_definition",
            entity_id=str(stage_id),
            organization_id=principal.organization_id,
            user_id=principal.user_id,
            previous_state=dict(before),
            new_state={
                "stage_code": payload.stage_code,
                "name": payload.name,
                "sequence": payload.sequence,
                "requires_approval": payload.requires_approval,
                "approval_role": payload.approval_role,
            },
            reason="stage gate reconfigured",
        ),
    )
    return StageDefinitionRead(**row)


@router.patch(
    "/stage-gates/{stage_id}/activation",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["admin"],
)
def set_stage_activation(
    stage_id: uuid.UUID,
    payload: StageActivation,
    principal: Principal = Depends(require_permission("admin.stage_gates")),
    session: Session = Depends(get_db),
) -> None:
    """Retire or restore a stage. **There is no delete.**

    Deleting a stage definition would orphan every `project_stages` row
    that references it, and those rows are the project history CLAUDE.md
    §5 forbids destroying. Retiring removes it from the pipeline going
    forward and leaves what already happened intact.

    Retiring a stage that projects are currently sitting in is refused.
    Those projects would be parked in a stage the pipeline no longer
    contains, with no configured transition out -- reachable only by a
    forced override, which is not a state an administrator should be able
    to create by accident.
    """
    # The "no active projects in this stage" test is INSIDE the UPDATE.
    #
    # Counted first and updated afterwards, a project can enter the stage
    # between the two statements and end up parked in a retired stage with
    # no configured way out -- the exact state this guard exists to
    # prevent (Codex C7). NOT EXISTS in the WHERE clause makes the check
    # and the write one atomic decision.
    updated = session.execute(
        text(
            """
            UPDATE workflow.stage_definitions sd
            SET is_active = :active
            WHERE sd.id = :sid
              AND sd.organization_id = :org
              AND (
                    :active
                 OR NOT EXISTS (
                        SELECT 1 FROM workflow.project_stages ps
                        WHERE ps.stage_definition_id = sd.id
                          AND ps.organization_id = sd.organization_id
                          AND ps.status = 'active'
                    )
              )
            RETURNING stage_code
            """
        ),
        {"sid": stage_id, "org": principal.organization_id, "active": payload.is_active},
    ).scalar_one_or_none()

    if updated is None:
        # Diagnose only. Distinguishing "no such stage" from "still
        # occupied" needs a second look, and by now the write has already
        # been decided either way.
        occupied = session.execute(
            text(
                """
                SELECT COUNT(DISTINCT ps.project_id)
                FROM workflow.project_stages ps
                WHERE ps.stage_definition_id = :sid
                  AND ps.organization_id = :org
                  AND ps.status = 'active'
                """
            ),
            {"sid": stage_id, "org": principal.organization_id},
        ).scalar_one()
        if int(occupied) > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"{occupied} project(s) are currently in this stage; "
                    "move them on before retiring it"
                ),
            )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="stage not found")

    write_audit(
        session,
        AuditEvent(
            action="admin.stage_gate_activation_changed",
            entity_type="stage_definition",
            entity_id=str(stage_id),
            organization_id=principal.organization_id,
            user_id=principal.user_id,
            previous_state={"is_active": not payload.is_active},
            new_state={"is_active": payload.is_active},
            reason=payload.reason,
        ),
    )
    log_audit("stage_gate_activation", stage_code=updated, is_active=payload.is_active)


@router.post("/stage-gates/reorder", status_code=status.HTTP_204_NO_CONTENT, tags=["admin"])
def reorder_stage_definitions(
    payload: StageReorder,
    principal: Principal = Depends(require_permission("admin.stage_gates")),
    session: Session = Depends(get_db),
) -> None:
    """Renumber the whole pipeline in one deferred transaction.

    `stage_definitions_org_seq_key` is UNIQUE (organization_id,
    sequence), so any reorder passes through intermediate states where two
    stages briefly hold the same sequence.

    An earlier version of this comment claimed a single
    `UPDATE ... FROM unnest(...)` avoided that "because a non-deferrable
    unique constraint is checked once at statement end". That was false,
    and the tests in `test_slice2_stage_gates.py` establish the actual
    three-way behaviour:

      * **non-deferrable** -- checked per ROW as each row is updated. The
        single statement fails in exactly the same place a row-by-row
        loop does. This is what broke.
      * **DEFERRABLE INITIALLY IMMEDIATE** -- enforced by a constraint
        trigger that fires at end of STATEMENT. Intermediate duplicates
        inside one statement are fine; the final state must be unique.
        This is what migration 009 configured, and it is all the reorder
        needs.
      * **DEFERRABLE + SET CONSTRAINTS DEFERRED** -- checked at COMMIT.
        Deliberately NOT used: a violation would then surface after this
        function has returned, past its error handling, as a 500 instead
        of a 409.

    Ordinary single-row writes are unaffected -- for a one-row statement,
    "end of statement" is immediate, and a duplicate sequence is still
    refused at the statement that causes it.

    The endpoint takes the complete ordered list rather than a move
    instruction because a partial list can only be applied by guessing
    what the caller intended for the rest.
    """
    expected = session.execute(
        text(
            """
            SELECT COUNT(*) FROM workflow.stage_definitions
            WHERE organization_id = :org
            """
        ),
        {"org": principal.organization_id},
    ).scalar_one()

    if len(payload.ordered_stage_ids) != int(expected):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"the reorder must list every stage: got "
                f"{len(payload.ordered_stage_ids)}, expected {expected}"
            ),
        )
    if len(set(payload.ordered_stage_ids)) != len(payload.ordered_stage_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="the reorder lists the same stage more than once",
        )

    # No SET CONSTRAINTS here, deliberately -- see the docstring. The
    # constraint being DEFERRABLE is already enough to move the check to
    # statement end. Deferring further, to COMMIT, would push a violation
    # past this function's error handling and turn a 409 into a 500.
    # `Session.execute` is typed as returning `Result`, which has no
    # `rowcount` — that lives on `CursorResult`, which is what a DML
    # statement actually returns at runtime. The cast records that, rather
    # than the alternative of counting the rows again in a second query,
    # which would reintroduce exactly the read-then-write gap the count is
    # here to close.
    result = cast(
        "CursorResult[Any]",
        session.execute(
            text(
                """
                UPDATE workflow.stage_definitions sd
                SET sequence = ordering.position
                FROM (
                    SELECT id, ordinality AS position
                    FROM unnest(CAST(:ids AS UUID[])) WITH ORDINALITY AS t(id, ordinality)
                ) AS ordering
                WHERE sd.id = ordering.id
                  AND sd.organization_id = :org
                """
            ),
            {"ids": [str(i) for i in payload.ordered_stage_ids], "org": principal.organization_id},
        ),
    )
    updated = result.rowcount

    if updated != len(payload.ordered_stage_ids):
        # One or more ids belong to another organization, or do not
        # exist. Refusing the whole reorder is the only safe answer: a
        # partial renumber leaves the pipeline in an order nobody chose.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="the reorder names a stage that does not belong to this organization",
        )

    write_audit(
        session,
        AuditEvent(
            action="admin.stage_gates_reordered",
            entity_type="stage_definition",
            entity_id=str(principal.organization_id),
            organization_id=principal.organization_id,
            user_id=principal.user_id,
            new_state={"order": [str(i) for i in payload.ordered_stage_ids]},
            reason="pipeline reordered",
        ),
    )
    log_audit("stage_gates_reordered", count=len(payload.ordered_stage_ids))
