"""Messaging, smart linking, and the NotificationService.

**A conversation about a record is part of that record's thread.** The
digital thread's rule — "no major technical record may become an isolated
data island" — applies to discussion too: a decision argued out in a chat
window that links to nothing is exactly the island the rule forbids. So
`#FRM-014` in a message body becomes a real row in
`messaging.message_links`, and "what has been said about this formula?"
is a query rather than a search.

🔴 TWO RULES THAT SHAPE EVERYTHING BELOW

**Informal chat never becomes authoritative knowledge automatically.**
§7. `promote_message` is the only path from a message to a controlled
record, it requires an explicit human act, and it creates a TASK rather
than a conclusion — somebody still has to do the work and sign for it.
Nothing here promotes anything on its own.

**A notification must not disclose what the recipient cannot see.**
Mentioning somebody in a restricted project's channel would otherwise
send them a notification naming a project they have no access to — the
notification itself becomes the leak, and no amount of care in the
channel's RLS prevents it. So a mention only notifies a user who can
already reach that channel, and the mention link is still recorded either
way: the message said what it said.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.audit import AuditEvent, write_audit
from app.core.tenancy import require_active_member

__all__ = [
    "ChannelInput",
    "MessageInput",
    "MessagingError",
    "MessagingNotFoundError",
    "MessagingStateError",
    "create_channel",
    "list_channels",
    "list_messages",
    "mark_notification_read",
    "my_notifications",
    "notify",
    "post_message",
    "promote_message",
    "thread_for_record",
]

# `#FRM-014`, `#LB-2026-0007`, `#T-2026-0041`. Deliberately narrow: an
# uppercase prefix, a hyphen, then alphanumerics and hyphens. A looser
# pattern would turn every `#1` and every hex colour in a message into a
# failed lookup, and a message full of unresolved links reads as broken.
_REFERENCE = re.compile(r"#([A-Z]{1,6}-[A-Za-z0-9-]{2,40})")

# `@username`. Resolved against `core.users.email`'s local part, because
# that is the only handle this schema has today; a display name is not
# unique and cannot be a mention target.
_MENTION = re.compile(r"@([a-zA-Z0-9._-]{2,60})")

# Which code prefixes resolve against which table. Written out rather
# than derived, because a dynamic version would need interpolated table
# names -- and interpolation defended by an argument has already been the
# wrong answer three times in this repository.
_RESOLVERS: dict[str, tuple[str, str]] = {
    "formula_version": (
        "version_code",
        """
        SELECT v.id FROM formulations.formula_versions v
        WHERE v.organization_id = :org AND v.version_code = :code
        """,
    ),
    "batch": (
        "batch_number",
        """
        SELECT b.id FROM laboratory.batches b
        WHERE b.organization_id = :org AND b.batch_number = :code
        """,
    ),
    "test": (
        "test_number",
        """
        SELECT t.id FROM testing.tests t
        WHERE t.organization_id = :org AND t.test_number = :code
        """,
    ),
    "failure": (
        "failure_code",
        """
        SELECT f.id FROM quality.failures f
        WHERE f.organization_id = :org AND f.failure_code = :code
        """,
    ),
    "material": (
        "material_code",
        """
        SELECT m.id FROM materials.materials m
        WHERE m.organization_id = :org AND m.material_code = :code
        """,
    ),
}


class MessagingError(RuntimeError):
    """Base for refusals that are business rules, not bugs."""


class MessagingNotFoundError(MessagingError):
    pass


class MessagingStateError(MessagingError):
    pass


@dataclass(frozen=True, slots=True)
class ChannelInput:
    channel_type: str
    name: str | None = None
    project_id: uuid.UUID | None = None
    entity_type: str | None = None
    entity_id: uuid.UUID | None = None
    member_ids: tuple[uuid.UUID, ...] = ()


@dataclass(frozen=True, slots=True)
class MessageInput:
    body: str
    reply_to_id: uuid.UUID | None = None


# ---------------------------------------------------------------------------
# Channels
# ---------------------------------------------------------------------------


def create_channel(
    session: Session,
    *,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    spec: ChannelInput,
) -> dict[str, Any]:
    """Open a channel.

    A PROJECT channel is created through the project, so RLS applies that
    project's confidentiality to the conversation from the first message.
    The author must be able to see the project to open a channel on it —
    the same predicate the policy uses, applied in the INSERT for the
    reason `create_formula` needed it: WITH CHECK is organization-only,
    so naming a restricted project would otherwise succeed and merely
    become invisible.
    """
    require_active_member(
        session, user_id=actor_id, organization_id=organization_id, role_description="author"
    )

    if spec.channel_type == "project" and spec.project_id is None:
        raise MessagingError(
            "a project channel must name its project; without one, RLS cannot apply "
            "that project's confidentiality to the conversation"
        )

    if spec.project_id is not None:
        channel_id = session.execute(
            text(
                """
                INSERT INTO messaging.channels
                    (organization_id, project_id, channel_type, name, entity_type,
                     entity_id, created_by)
                SELECT :org, p.id, :ctype, :name, :etype, :eid, :actor
                FROM projects.projects p
                WHERE p.id = :pid AND p.organization_id = :org
                  AND (p.confidentiality = 'normal' OR core.is_project_member(p.id))
                RETURNING id
                """
            ),
            {
                "org": organization_id,
                "pid": spec.project_id,
                "ctype": spec.channel_type,
                "name": spec.name,
                "etype": spec.entity_type,
                "eid": spec.entity_id,
                "actor": actor_id,
            },
        ).scalar_one_or_none()
        if channel_id is None:
            raise MessagingNotFoundError("no such project in this organization")
    else:
        channel_id = session.execute(
            text(
                """
                INSERT INTO messaging.channels
                    (organization_id, channel_type, name, entity_type, entity_id,
                     created_by)
                VALUES (:org, :ctype, :name, :etype, :eid, :actor)
                RETURNING id
                """
            ),
            {
                "org": organization_id,
                "ctype": spec.channel_type,
                "name": spec.name,
                "etype": spec.entity_type,
                "eid": spec.entity_id,
                "actor": actor_id,
            },
        ).scalar_one()

    # The author is always a member. A channel its creator is not in is a
    # channel that vanishes from their own list the moment they make it.
    for member in {actor_id, *spec.member_ids}:
        require_active_member(
            session, user_id=member, organization_id=organization_id, role_description="member"
        )
        session.execute(
            text(
                """
                INSERT INTO messaging.channel_members
                    (organization_id, channel_id, user_id)
                VALUES (:org, :cid, :uid)
                ON CONFLICT (channel_id, user_id) DO NOTHING
                """
            ),
            {"org": organization_id, "cid": channel_id, "uid": member},
        )

    write_audit(
        session,
        AuditEvent(
            action="channel.created",
            entity_type="channel",
            entity_id=str(channel_id),
            organization_id=organization_id,
            user_id=actor_id,
            new_state={"channel_type": spec.channel_type, "name": spec.name},
            reason="channel opened",
        ),
    )
    return {"id": channel_id, "channel_type": spec.channel_type}


def thread_for_record(
    session: Session,
    *,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    entity_type: str,
    entity_id: uuid.UUID,
    project_id: uuid.UUID,
) -> dict[str, Any]:
    """The technical thread for a record, opening one if it has none.

    Idempotent on purpose. Every screen that offers "discuss this" would
    otherwise create a new thread per click, and a record with six threads
    has no discussion at all — it has six fragments nobody reads together.
    """
    existing = (
        session.execute(
            text(
                """
                SELECT id, channel_type FROM messaging.channels
                WHERE organization_id = :org AND entity_type = :etype
                  AND entity_id = :eid AND channel_type = 'technical_thread'
                  AND NOT is_archived
                """
            ),
            {"org": organization_id, "etype": entity_type, "eid": entity_id},
        )
        .mappings()
        .one_or_none()
    )
    if existing is not None:
        return dict(existing)

    return create_channel(
        session,
        organization_id=organization_id,
        actor_id=actor_id,
        spec=ChannelInput(
            channel_type="technical_thread",
            name=f"Discussion: {entity_type}",
            project_id=project_id,
            entity_type=entity_type,
            entity_id=entity_id,
        ),
    )


def list_channels(
    session: Session, *, organization_id: uuid.UUID, actor_id: uuid.UUID, limit: int = 100
) -> list[dict[str, Any]]:
    """Channels this caller can see.

    RLS excludes restricted projects they are not in; membership narrows
    it further for direct messages, which are not project-scoped and
    therefore have nothing else to hide behind.
    """
    rows = session.execute(
        text(
            """
            SELECT c.id, c.channel_type, c.name, c.project_id, c.entity_type,
                   c.entity_id, c.created_at,
                   (SELECT count(*) FROM messaging.messages m
                     WHERE m.channel_id = c.id AND NOT m.is_deleted) AS message_count
            FROM messaging.channels c
            WHERE c.organization_id = :org
              AND NOT c.is_archived
              AND (
                    c.channel_type <> 'direct'
                    OR EXISTS (
                        SELECT 1 FROM messaging.channel_members cm
                        WHERE cm.channel_id = c.id AND cm.user_id = :actor
                    )
                  )
            ORDER BY c.created_at DESC
            LIMIT :limit
            """
        ),
        {"org": organization_id, "actor": actor_id, "limit": limit},
    ).mappings()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------


def post_message(
    session: Session,
    *,
    channel_id: uuid.UUID,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    spec: MessageInput,
) -> dict[str, Any]:
    """Post a message, resolving its `#references` and `@mentions`.

    **Links are resolved at WRITE time and stored.** Resolving on read
    would mean a message rendering differently after the record it names
    is renamed or retired, and a conversation must say what it said when
    it was written.

    **Resolution runs in the author's session**, so a reference to a
    record they cannot see simply does not resolve — it stays as text.
    That is deliberate: an unresolvable reference is a broken link, and
    the alternative is a link whose existence confirms that a record with
    that code exists somewhere the author cannot look.
    """
    channel = (
        session.execute(
            text(
                """
                SELECT id, project_id, channel_type FROM messaging.channels
                WHERE id = :cid AND organization_id = :org AND NOT is_archived
                """
            ),
            {"cid": channel_id, "org": organization_id},
        )
        .mappings()
        .one_or_none()
    )
    if channel is None:
        raise MessagingNotFoundError("no such channel in this organization")

    message_id: uuid.UUID = session.execute(
        text(
            """
            INSERT INTO messaging.messages
                (organization_id, channel_id, body, reply_to_id, author_id)
            VALUES (:org, :cid, :body, :reply, :actor)
            RETURNING id
            """
        ),
        {
            "org": organization_id,
            "cid": channel_id,
            "body": spec.body,
            "reply": spec.reply_to_id,
            "actor": actor_id,
        },
    ).scalar_one()

    links = _resolve_references(
        session, organization_id=organization_id, message_id=message_id, body=spec.body
    )
    mentions = _resolve_mentions(
        session,
        organization_id=organization_id,
        message_id=message_id,
        channel_id=channel_id,
        body=spec.body,
        actor_id=actor_id,
    )

    return {
        "id": message_id,
        "links": links,
        "mentions": mentions,
    }


def _resolve_references(
    session: Session, *, organization_id: uuid.UUID, message_id: uuid.UUID, body: str
) -> list[dict[str, Any]]:
    """Turn `#FRM-014` into a row pointing at the real record.

    Tries every resolver for each code, because the prefixes are a
    convention rather than a guarantee — a deployment may issue
    `T-2026-0041` for a test and `T-...` for something else later, and a
    resolver keyed on the prefix alone would then point at the wrong
    table with complete confidence.
    """
    found: list[dict[str, Any]] = []
    for code in dict.fromkeys(_REFERENCE.findall(body)):
        for entity_type, (_column, sql) in _RESOLVERS.items():
            entity_id = session.execute(
                text(sql), {"org": organization_id, "code": code}
            ).scalar_one_or_none()
            if entity_id is None:
                continue

            session.execute(
                text(
                    """
                    INSERT INTO messaging.message_links
                        (organization_id, message_id, link_type, entity_type,
                         entity_id, label)
                    VALUES (:org, :mid, 'record', :etype, :eid, :label)
                    """
                ),
                {
                    "org": organization_id,
                    "mid": message_id,
                    "etype": entity_type,
                    "eid": entity_id,
                    "label": code,
                },
            )
            found.append({"code": code, "entity_type": entity_type, "entity_id": entity_id})
            break

    return found


def _resolve_mentions(
    session: Session,
    *,
    organization_id: uuid.UUID,
    message_id: uuid.UUID,
    channel_id: uuid.UUID,
    body: str,
    actor_id: uuid.UUID,
) -> list[dict[str, Any]]:
    """Record @mentions, and notify only those who can see the channel.

    🔴 THE NOTIFICATION IS THE LEAK, IF YOU LET IT BE.

    Mentioning somebody in a restricted project's channel would otherwise
    send them a notification naming a project they have no access to. The
    channel's RLS protects the MESSAGES and does nothing about a
    notification row addressed to an outsider — so membership is checked
    before notifying.

    The mention LINK is recorded either way. The message said what it
    said, and editing history to match permissions would be a worse lie
    than an unresolved handle.
    """
    notified: list[dict[str, Any]] = []
    for handle in dict.fromkeys(_MENTION.findall(body)):
        user = (
            session.execute(
                text(
                    """
                    SELECT u.id, u.display_name
                    FROM core.users u
                    JOIN core.organization_members m
                      ON m.user_id = u.id AND m.organization_id = :org
                     AND m.status = 'active'
                    WHERE split_part(u.email, '@', 1) = :handle
                    """
                ),
                {"org": organization_id, "handle": handle},
            )
            .mappings()
            .one_or_none()
        )
        if user is None:
            continue

        session.execute(
            text(
                """
                INSERT INTO messaging.message_links
                    (organization_id, message_id, link_type, mentioned_user_id, label)
                VALUES (:org, :mid, 'mention', :uid, :label)
                """
            ),
            {"org": organization_id, "mid": message_id, "uid": user["id"], "label": handle},
        )

        # Can the RECIPIENT reach this channel?
        #
        # 🔴 THE ANSWER CANNOT BE BORROWED FROM RLS HERE.
        #
        # This query runs in the AUTHOR's session, so RLS answers "can the
        # author see it?" -- and the author demonstrably can, because they
        # just posted in it. Reusing `list_channels`'s predicate would
        # therefore return true for every project channel including a
        # restricted one, and the notification would name a project the
        # recipient has no access to. The leak would be the notification
        # itself, in the one place the channel's own RLS cannot reach.
        #
        # So the recipient's access is evaluated EXPLICITLY, against the
        # same two facts the project policy uses: confidentiality, and
        # membership.
        reachable = session.execute(
            text(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM messaging.channels c
                    LEFT JOIN projects.projects p
                      ON p.id = c.project_id AND p.organization_id = c.organization_id
                    WHERE c.id = :cid AND c.organization_id = :org
                      -- A direct message reaches only its own members.
                      AND (
                            c.channel_type <> 'direct'
                            OR EXISTS (
                                SELECT 1 FROM messaging.channel_members cm
                                WHERE cm.channel_id = c.id AND cm.user_id = :uid
                            )
                          )
                      -- A project channel reaches only people who can see
                      -- the project. `p.confidentiality` is NULL for a
                      -- channel with no project, which is why the
                      -- IS NULL arm comes first rather than relying on a
                      -- NULL comparison to behave.
                      AND (
                            c.project_id IS NULL
                            OR p.confidentiality = 'normal'
                            OR EXISTS (
                                SELECT 1 FROM projects.project_members pm
                                WHERE pm.project_id = c.project_id
                                  AND pm.organization_id = c.organization_id
                                  AND pm.user_id = :uid
                                  AND pm.status = 'active'
                            )
                          )
                )
                """
            ),
            {"cid": channel_id, "org": organization_id, "uid": user["id"]},
        ).scalar_one()

        if reachable and user["id"] != actor_id:
            notify(
                session,
                organization_id=organization_id,
                recipient_id=user["id"],
                notification_type="message.mention",
                title="You were mentioned",
                body=body[:200],
                entity_type="message",
                entity_id=message_id,
                is_actionable=True,
            )
            notified.append({"handle": handle, "user_id": user["id"], "notified": True})
        else:
            # Recorded, deliberately, so the behaviour is inspectable
            # rather than a silent no-op somebody later mistakes for a bug.
            notified.append({"handle": handle, "user_id": user["id"], "notified": False})

    return notified


def list_messages(
    session: Session,
    *,
    channel_id: uuid.UUID,
    organization_id: uuid.UUID,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """A channel's messages, oldest first, with their links.

    Withdrawn messages come back with their body replaced rather than
    omitted: a conversation with holes in it cannot be read, and a reply
    to a message that has vanished is unintelligible.
    """
    rows = [
        dict(r)
        for r in session.execute(
            text(
                """
                SELECT m.id, m.body, m.author_id, m.posted_at, m.edited_at,
                       m.is_deleted, m.reply_to_id, u.display_name AS author_name
                FROM messaging.messages m
                JOIN core.users u ON u.id = m.author_id
                WHERE m.channel_id = :cid AND m.organization_id = :org
                ORDER BY m.posted_at
                LIMIT :limit
                """
            ),
            {"cid": channel_id, "org": organization_id, "limit": limit},
        ).mappings()
    ]

    if not rows:
        return []

    links = session.execute(
        text(
            """
            SELECT l.message_id, l.link_type, l.entity_type, l.entity_id,
                   l.mentioned_user_id, l.label
            FROM messaging.message_links l
            JOIN messaging.messages m
              ON m.id = l.message_id AND m.organization_id = l.organization_id
            WHERE m.channel_id = :cid AND l.organization_id = :org
            """
        ),
        {"cid": channel_id, "org": organization_id},
    ).mappings()

    by_message: dict[uuid.UUID, list[dict[str, Any]]] = {}
    for link in links:
        by_message.setdefault(link["message_id"], []).append(dict(link))

    for row in rows:
        row["links"] = by_message.get(row["id"], [])
        if row["is_deleted"]:
            row["body"] = "(this message was withdrawn)"

    return rows


def promote_message(
    session: Session,
    *,
    message_id: uuid.UUID,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    task_type: str,
    title: str,
    assigned_user_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """Turn a message into a controlled record — a TASK.

    🔴 §7: "Informal chat never becomes authoritative knowledge
    automatically. Conclusions become controlled records only by explicit
    human promotion."

    This is that explicit act, and it deliberately creates a task rather
    than a decision or a conclusion: somebody still has to do the work and
    sign for it. A path from "somebody said so in chat" straight to a
    technical decision is the thing the rule forbids.

    The promotion is recorded as a link back to the message, so the task
    can always answer "where did this come from?" — which is the digital
    thread's rule applied to the conversation itself.
    """
    message = (
        session.execute(
            text(
                """
                SELECT m.id, m.body, c.project_id
                FROM messaging.messages m
                JOIN messaging.channels c
                  ON c.id = m.channel_id AND c.organization_id = m.organization_id
                WHERE m.id = :mid AND m.organization_id = :org
                """
            ),
            {"mid": message_id, "org": organization_id},
        )
        .mappings()
        .one_or_none()
    )
    if message is None:
        raise MessagingNotFoundError("no such message in this organization")

    if assigned_user_id is not None:
        require_active_member(
            session,
            user_id=assigned_user_id,
            organization_id=organization_id,
            role_description="assignee",
        )

    try:
        task_id: uuid.UUID = session.execute(
            text(
                """
                INSERT INTO workflow.tasks
                    (organization_id, project_id, task_type, title, description,
                     assigned_user_id, assigned_role, source_event, entity_type,
                     entity_id, created_by)
                VALUES (:org, :pid, :ttype, :title, :description, :assignee,
                        CASE WHEN :assignee IS NULL THEN 'product_development_lead' END,
                        'message.promoted', 'message', :mid, :actor)
                RETURNING id
                """
            ),
            {
                "org": organization_id,
                "pid": message["project_id"],
                "ttype": task_type,
                "title": title,
                "description": message["body"][:2000],
                "assignee": assigned_user_id,
                "mid": message_id,
                "actor": actor_id,
            },
        ).scalar_one()
    except IntegrityError as exc:
        session.rollback()
        raise MessagingError(str(exc.orig)) from exc

    session.execute(
        text(
            """
            INSERT INTO messaging.message_links
                (organization_id, message_id, link_type, entity_type, entity_id, label)
            VALUES (:org, :mid, 'promotion', 'task', :tid, :label)
            """
        ),
        {"org": organization_id, "mid": message_id, "tid": task_id, "label": title[:100]},
    )

    write_audit(
        session,
        AuditEvent(
            action="message.promoted",
            entity_type="task",
            entity_id=str(task_id),
            organization_id=organization_id,
            user_id=actor_id,
            new_state={"task_type": task_type, "from_message": str(message_id)},
            reason=f"promoted from a message: {title}",
        ),
    )
    return {"task_id": task_id, "message_id": message_id}


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------


def notify(
    session: Session,
    *,
    organization_id: uuid.UUID,
    recipient_id: uuid.UUID,
    notification_type: str,
    title: str,
    body: str | None = None,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    is_actionable: bool = False,
) -> uuid.UUID:
    """Write one notification.

    THE single writer, in the same sense as one approval engine: every
    module calls this rather than growing its own table. `is_actionable`
    separates "you must do something" from "this happened", because §11
    requires a badge to count items needing action and that distinction
    has to exist in the data or every count is a total.
    """
    return session.execute(  # type: ignore[no-any-return]
        text(
            """
            INSERT INTO messaging.notifications
                (organization_id, recipient_id, notification_type, title, body,
                 entity_type, entity_id, is_actionable)
            VALUES (:org, :recipient, :ntype, :title, :body, :etype, :eid, :actionable)
            RETURNING id
            """
        ),
        {
            "org": organization_id,
            "recipient": recipient_id,
            "ntype": notification_type,
            "title": title,
            "body": body,
            "etype": entity_type,
            "eid": entity_id,
            "actionable": is_actionable,
        },
    ).scalar_one()


def my_notifications(
    session: Session,
    *,
    organization_id: uuid.UUID,
    recipient_id: uuid.UUID,
    unread_only: bool = False,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """This caller's notifications.

    Scoped by `recipient_id` in the predicate rather than by RLS, because
    notifications are organization-scoped rows: without this clause every
    colleague's notifications would be readable. RLS answers "which
    tenant"; this answers "whose".
    """
    rows = session.execute(
        text(
            """
            SELECT id, notification_type, title, body, entity_type, entity_id,
                   is_actionable, read_at, created_at
            FROM messaging.notifications
            WHERE organization_id = :org AND recipient_id = :recipient
              AND (:unread_only = FALSE OR read_at IS NULL)
            ORDER BY created_at DESC
            LIMIT :limit
            """
        ),
        {
            "org": organization_id,
            "recipient": recipient_id,
            "unread_only": unread_only,
            "limit": limit,
        },
    ).mappings()
    return [dict(r) for r in rows]


def mark_notification_read(
    session: Session,
    *,
    notification_id: uuid.UUID,
    organization_id: uuid.UUID,
    recipient_id: uuid.UUID,
) -> dict[str, Any]:
    """Mark one as read.

    `recipient_id` is in the WHERE clause, so a caller cannot mark
    somebody else's notification read — which would hide it from the
    person who needed it, silently and permanently.
    """
    row = (
        session.execute(
            text(
                """
                UPDATE messaging.notifications
                SET read_at = now()
                WHERE id = :nid AND organization_id = :org
                  AND recipient_id = :recipient AND read_at IS NULL
                RETURNING id, read_at
                """
            ),
            {"nid": notification_id, "org": organization_id, "recipient": recipient_id},
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise MessagingNotFoundError("no such unread notification for this recipient")
    return dict(row)
