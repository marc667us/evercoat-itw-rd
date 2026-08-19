"""Messaging, notifications, and promotion into controlled records.

**Most of these routes carry no permission dependency, deliberately** --
the same reasoning as My Work. There are no `message.*` or
`notification.*` permissions in the catalogue, and inventing them here
would produce exactly the defect this project has now caught five times:
a permission nobody holds, gating a feature nobody can then use.

That is not a gap. Messaging is governed by something stronger than a
grant: **RLS and channel membership**. A restricted project's channel is
not returned to a non-member by the database, so there is nothing for a
permission check to add. `promote_message` is the exception -- it creates
a controlled record, so it requires `project.edit`.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.security import Principal, get_db, get_principal, require_permission
from app.core.tenancy import CrossTenantReferenceError
from app.domains.messaging.service import (
    ChannelInput,
    MessageInput,
    MessagingError,
    MessagingNotFoundError,
    create_channel,
    list_channels,
    list_messages,
    mark_notification_read,
    my_notifications,
    post_message,
    promote_message,
    thread_for_record,
)

router = APIRouter()

__all__ = ["router"]


class ChannelCreate(BaseModel):
    channel_type: str = Field(pattern="^(project|direct|technical_thread|announcement)$")
    name: str | None = Field(default=None, max_length=200)
    project_id: uuid.UUID | None = None
    entity_type: str | None = Field(default=None, max_length=50)
    entity_id: uuid.UUID | None = None
    member_ids: list[uuid.UUID] = Field(default_factory=list, max_length=50)


class ThreadOpen(BaseModel):
    """Open (or find) the discussion thread attached to one record."""

    entity_type: str = Field(max_length=50)
    entity_id: uuid.UUID
    project_id: uuid.UUID


class MessagePost(BaseModel):
    # 4000 characters, not unbounded. A message is a message; a 2MB paste
    # belongs in an attachment, where it can be versioned and scanned.
    body: str = Field(min_length=1, max_length=4000)
    reply_to_id: uuid.UUID | None = None


class MessagePromote(BaseModel):
    task_type: str = Field(max_length=50)
    title: str = Field(min_length=1, max_length=200)
    assigned_user_id: uuid.UUID | None = None


@router.get("/channels", summary="Channels this user can see")
def get_channels(
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_db),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[dict[str, Any]]:
    return list_channels(
        session,
        organization_id=principal.organization_id,
        actor_id=principal.user_id,
        limit=limit,
    )


@router.post("/channels", status_code=status.HTTP_201_CREATED, summary="Open a channel")
def post_channel(
    payload: ChannelCreate,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        result = create_channel(
            session,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
            spec=ChannelInput(
                channel_type=payload.channel_type,
                name=payload.name,
                project_id=payload.project_id,
                entity_type=payload.entity_type,
                entity_id=payload.entity_id,
                member_ids=tuple(payload.member_ids),
            ),
        )
    except MessagingNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except (MessagingError, CrossTenantReferenceError) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    session.commit()
    return result


@router.post("/threads", summary="The discussion thread for a record, opening one if needed")
def open_thread(
    payload: ThreadOpen,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """Idempotent.

    Every "discuss this" button can call it without checking first, which
    is the only way a record ends up with one thread rather than six.
    """
    try:
        result = thread_for_record(
            session,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
            entity_type=payload.entity_type,
            entity_id=payload.entity_id,
            project_id=payload.project_id,
        )
    except MessagingNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except (MessagingError, CrossTenantReferenceError) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    session.commit()
    return result


@router.get("/channels/{channel_id}/messages", summary="A channel's messages")
def get_messages(
    channel_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_db),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[dict[str, Any]]:
    return list_messages(
        session,
        channel_id=channel_id,
        organization_id=principal.organization_id,
        limit=limit,
    )


@router.post(
    "/channels/{channel_id}/messages",
    status_code=status.HTTP_201_CREATED,
    summary="Post a message, resolving #references and @mentions",
)
def post_channel_message(
    channel_id: uuid.UUID,
    payload: MessagePost,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        result = post_message(
            session,
            channel_id=channel_id,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
            spec=MessageInput(body=payload.body, reply_to_id=payload.reply_to_id),
        )
    except MessagingNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except (MessagingError, CrossTenantReferenceError) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    session.commit()
    return result


@router.post(
    "/messages/{message_id}/promote",
    status_code=status.HTTP_201_CREATED,
    summary="Promote a message into a controlled record (a task)",
)
def post_promotion(
    message_id: uuid.UUID,
    payload: MessagePromote,
    principal: Principal = Depends(require_permission("project.edit")),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """The only route here that requires a permission.

    Section 7: informal chat never becomes authoritative knowledge
    automatically. This route is the explicit human act that the rule
    demands, and it is the only one in this module that writes a
    controlled record -- which is exactly why it is the only one gated.
    """
    try:
        result = promote_message(
            session,
            message_id=message_id,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
            task_type=payload.task_type,
            title=payload.title,
            assigned_user_id=payload.assigned_user_id,
        )
    except MessagingNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except (MessagingError, CrossTenantReferenceError) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    session.commit()
    return result


@router.get("/notifications", summary="This user's notifications")
def get_notifications(
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_db),
    unread_only: bool = Query(default=False),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[dict[str, Any]]:
    return my_notifications(
        session,
        organization_id=principal.organization_id,
        recipient_id=principal.user_id,
        unread_only=unread_only,
        limit=limit,
    )


@router.post("/notifications/{notification_id}/read", summary="Mark one as read")
def post_notification_read(
    notification_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """`recipient_id` comes from the token, never the request.

    A caller therefore cannot mark somebody else's notification read and
    hide it, silently and permanently, from the person who needed to act.
    """
    try:
        result = mark_notification_read(
            session,
            notification_id=notification_id,
            organization_id=principal.organization_id,
            recipient_id=principal.user_id,
        )
    except MessagingNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    session.commit()
    return result
