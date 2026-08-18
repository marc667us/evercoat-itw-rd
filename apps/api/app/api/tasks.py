"""My Work — the task inbox.

**These routes carry no permission dependency, and that is deliberate.**
Every other route in this application sits behind `require_permission`.
My Work does not, because it returns only the caller's own tasks and the
unclaimed tasks addressed to roles the caller actually holds. There is no
permission to check: the query is scoped by `principal.user_id` and
`principal.roles`, both of which come from a signature-verified token and
a database lookup, never from the request.

Requiring a permission here would mean a user could be locked out of
their own inbox by an administrator forgetting a grant -- work would pile
up addressed to somebody who cannot see it, and nothing would report the
condition.

The one exception is :func:`create_task`, which addresses work to
*other* people and therefore needs `project.edit`.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.security import (
    Principal,
    get_db,
    get_principal,
    require_permission,
    require_project_member,
)
from app.core.tenancy import CrossTenantReferenceError
from app.domains.tasks.service import (
    TaskInput,
    TaskNotFoundError,
    TaskStateError,
    claim_task,
    complete_task,
    create_task,
    my_work,
    my_work_counts,
    project_tasks,
    reassign_task,
)

router = APIRouter()

__all__ = ["router"]


class TaskCreate(BaseModel):
    task_type: str = Field(min_length=1, max_length=50)
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    priority: str = Field(default="medium", pattern="^(low|medium|high|critical)$")
    assigned_user_id: uuid.UUID | None = None
    assigned_role: str | None = None
    project_id: uuid.UUID | None = None
    due_date: date | None = None
    required_action: str | None = None
    entity_type: str | None = None
    entity_id: uuid.UUID | None = None


class TaskComplete(BaseModel):
    outcome_note: str | None = None


class TaskReassign(BaseModel):
    to_user_id: uuid.UUID
    # Required, not optional. "Why is this suddenly mine" is the first
    # question the new assignee asks.
    reason: str = Field(min_length=3, max_length=500)


def _refuse(exc: Exception) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


def _bad_reference(exc: CrossTenantReferenceError) -> HTTPException:
    """400, not 403 or 404.

    The caller named a user who is not a member of this organization. 403
    would imply the id is real and merely off-limits; 404 would imply it
    is not real. Both leak. 400 says only that the payload was wrong,
    which is all the caller is entitled to know.
    """
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("", tags=["my-work"])
def list_my_work(
    include_done: bool = Query(default=False),
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """The caller's inbox, most urgent first."""
    return my_work(
        session,
        user_id=principal.user_id,
        organization_id=principal.organization_id,
        role_codes=principal.roles,
        include_done=include_done,
    )


@router.get("/counts", tags=["my-work"])
def get_my_work_counts(
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_db),
) -> dict[str, int]:
    """Sidebar badge numbers.

    Actionable items only (CLAUDE.md §11). Built from the same predicate
    as the list above, so the badge and the inbox can never disagree.
    """
    return my_work_counts(
        session,
        user_id=principal.user_id,
        organization_id=principal.organization_id,
        role_codes=principal.roles,
    )


@router.post("", status_code=status.HTTP_201_CREATED, tags=["my-work"])
def post_task(
    payload: TaskCreate,
    principal: Principal = Depends(require_permission("project.edit")),
    session: Session = Depends(get_db),
) -> dict[str, str]:
    """Raise a task. Addresses work to another person or role."""
    try:
        task_id = create_task(
            session,
            data=TaskInput(
                task_type=payload.task_type,
                title=payload.title,
                description=payload.description,
                priority=payload.priority,
                assigned_user_id=payload.assigned_user_id,
                assigned_role=payload.assigned_role,
                project_id=payload.project_id,
                due_date=payload.due_date,
                source_event="manual",
                entity_type=payload.entity_type,
                entity_id=payload.entity_id,
                required_action=payload.required_action,
            ),
            actor_id=principal.user_id,
            organization_id=principal.organization_id,
        )
    except CrossTenantReferenceError as exc:
        raise _bad_reference(exc) from exc
    except TaskStateError as exc:
        raise _refuse(exc) from exc
    return {"id": str(task_id)}


@router.post("/{task_id}/claim", status_code=status.HTTP_204_NO_CONTENT, tags=["my-work"])
def post_claim(
    task_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_db),
) -> None:
    """Take a role-addressed task.

    No permission check: the service refuses any task not addressed to a
    role the caller holds, which is a stronger condition than any
    permission grant could express.
    """
    try:
        claim_task(
            session,
            task_id=task_id,
            user_id=principal.user_id,
            organization_id=principal.organization_id,
            role_codes=principal.roles,
        )
    except TaskStateError as exc:
        raise _refuse(exc) from exc


@router.post("/{task_id}/complete", status_code=status.HTTP_204_NO_CONTENT, tags=["my-work"])
def post_complete(
    task_id: uuid.UUID,
    payload: TaskComplete,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_db),
) -> None:
    """Mark the caller's own task done. The service refuses anyone else's."""
    try:
        complete_task(
            session,
            task_id=task_id,
            actor_id=principal.user_id,
            organization_id=principal.organization_id,
            outcome_note=payload.outcome_note,
        )
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except TaskStateError as exc:
        raise _refuse(exc) from exc


@router.post("/{task_id}/reassign", status_code=status.HTTP_204_NO_CONTENT, tags=["my-work"])
def post_reassign(
    task_id: uuid.UUID,
    payload: TaskReassign,
    principal: Principal = Depends(require_permission("project.edit")),
    session: Session = Depends(get_db),
) -> None:
    """Delegate a task. Requires the authority to direct someone else's work."""
    try:
        reassign_task(
            session,
            task_id=task_id,
            to_user_id=payload.to_user_id,
            actor_id=principal.user_id,
            organization_id=principal.organization_id,
            reason=payload.reason,
        )
    except CrossTenantReferenceError as exc:
        raise _bad_reference(exc) from exc
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except TaskStateError as exc:
        raise _refuse(exc) from exc


@router.get("/project/{project_id}", tags=["my-work"])
def list_project_tasks(
    project_id: uuid.UUID,
    principal: Principal = Depends(require_permission("project.view")),
    _scope: Principal = Depends(require_project_member("project_id")),
    session: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """Everything outstanding on a project, not just the caller's share.

    Both dependencies, as everywhere: `project.view` asks whether this
    person may ever read a project, `require_project_member` asks whether
    they may read *this* one.
    """
    return project_tasks(session, project_id=project_id, organization_id=principal.organization_id)
