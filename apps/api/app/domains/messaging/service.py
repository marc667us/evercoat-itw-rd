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
    # 🔴 THE SAME MEMBERSHIP RULE AS THE READ PATH, FOR THE SAME REASON.
    #
    # This lookup already goes through `messaging.channels`, so the
    # project predicate in that table's RLS policy stops a non-member
    # writing into a RESTRICTED project's channel — the row is simply not
    # there for them. A `direct` channel has `project_id IS NULL` and so
    # has no project to hide behind, and the policy lets every org member
    # see the row. Without the clause below, any organization member
    # could post into a private conversation between two other people.
    #
    # `core.current_user_id()` rather than the `actor_id` argument: it is
    # the identity the RLS policies themselves read, so the check and the
    # policies cannot disagree, and a caller cannot widen its own access
    # by passing a different actor than the session is scoped to.
    channel = (
        session.execute(
            text(
                """
                SELECT c.id, c.project_id, c.channel_type
                FROM messaging.channels c
                WHERE c.id = :cid AND c.organization_id = :org
                  AND NOT c.is_archived
                  AND (
                        c.channel_type <> 'direct'
                        OR EXISTS (
                            SELECT 1 FROM messaging.channel_members cm
                            WHERE cm.channel_id = c.id
                              AND cm.user_id = core.current_user_id()
                        )
                      )
                """
            ),
            {"cid": channel_id, "org": organization_id},
        )
        .mappings()
        .one_or_none()
    )
    if channel is None:
        # Deliberately the same answer whether the channel does not exist,
        # is archived, belongs to a project this caller cannot see, or is
        # a direct conversation they are not part of. "You may not see it"
        # and "it is not there" must be indistinguishable, or the error
        # itself confirms that a conversation exists.
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
    """A channel's `limit` MOST RECENT messages, returned oldest-first.

    🔴 THE MOST RECENT, not the first ever posted. This used to order ascending
    with a LIMIT, which pinned every reader to the opening of the conversation:
    past `limit` messages, nothing newly posted could be reached at all and
    there is no cursor parameter to page with. Raised by the Supervisor.
    Within the returned page the order is oldest-first, which is how a
    conversation reads.


    Withdrawn messages come back with their body replaced rather than
    omitted: a conversation with holes in it cannot be read, and a reply
    to a message that has vanished is unintelligible.

    🔴 WHY THIS QUERY JOINS `messaging.channels` WHEN IT SELECTS NO COLUMN
    FROM IT

    It did not, and that was a confidentiality defect. RLS on
    `messaging.channels` carries the project predicate — a channel
    belonging to a `restricted` project is invisible to a non-member. RLS
    on `messaging.messages` carries **only** `organization_id`
    (migration 022's `org_scope` loop). So a query that filtered messages
    by `channel_id` alone and never touched `channels` **bypassed the
    channel's protection entirely**: any authenticated member of the
    organization holding a channel id could read

      * every message in a RESTRICTED project's channel they are not a
        member of, and
      * every message in a DIRECT message between two other people.

    The DM half is the sharper one. The `channels` policy deliberately
    lets any org member see a `direct` channel row and says so in its own
    comment — *"direct messages … are governed by channel membership
    instead"* — and that governance existed in exactly one place,
    `list_channels`'s listing query. Nothing enforced it on the read path
    that actually returns the words.

    Two mechanisms now do:

    1. the JOIN, which subjects every row to the `channels` policy and so
       inherits the project predicate; and
    2. the `channel_members` EXISTS, which supplies the membership rule
       for `direct` channels, where `project_id IS NULL` leaves the
       policy nothing to hide behind.

    The membership test reads `core.current_user_id()` — the same GUC
    every RLS policy reads — rather than an `actor_id` argument, so the
    predicate and the policies cannot come to different answers about who
    is asking. With no context set the GUC is NULL, the EXISTS is false,
    and a direct channel returns nothing: fail closed.

    Migration 025 adds the same rule to the database as an independent
    backstop, because `SECURITY.md` §1 requires that any ONE layer failing
    must not expose data — and this defect was one layer, failing.
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
                -- 🔴 THE JOIN TO `channels` IS THE ACCESS CONTROL, NOT DECORATION.
                JOIN messaging.channels c
                  ON c.id = m.channel_id
                 AND c.organization_id = m.organization_id
                WHERE m.channel_id = :cid AND m.organization_id = :org
                  AND (
                        c.channel_type <> 'direct'
                        OR EXISTS (
                            SELECT 1 FROM messaging.channel_members cm
                            WHERE cm.channel_id = c.id
                              AND cm.user_id = core.current_user_id()
                        )
                      )
                -- 🔴 DESC + LIMIT TAKES THE NEWEST PAGE, THEN PYTHON REVERSES
                -- IT. Ascending with a LIMIT returns the OLDEST `limit` rows,
                -- so once a channel passed 100 messages every message posted
                -- after that was unreachable through this API -- the reader
                -- was pinned to the start of the conversation forever. There
                -- is no offset or cursor parameter to escape with. Raised by
                -- the Supervisor.
                --
                -- `m.id` is a TIEBREAKER, not decoration. An ORDER BY that is
                -- not total is not deterministic: PostgreSQL may return equal
                -- rows in any order, and two messages CAN share a `posted_at`
                -- to the microsecond. Migration 028 changed the default from
                -- `now()` (transaction-start time, identical for every row
                -- written in one transaction) to `clock_timestamp()`, which
                -- makes the order right; this makes it repeatable. Both are
                -- needed -- see 028's header for why neither alone suffices.
                --
                -- Migration 029 adds (channel_id, posted_at DESC, id DESC) to
                -- serve exactly this.
                ORDER BY m.posted_at DESC, m.id DESC
                LIMIT :limit
                """
            ),
            {"cid": channel_id, "org": organization_id, "limit": limit},
        ).mappings()
    ]

    if not rows:
        return []

    # The query took the NEWEST page (see the ORDER BY above); the contract of
    # this function, and what a reader expects, is oldest-first WITHIN that
    # page. Reversed here rather than in SQL because a subquery to re-sort the
    # limited set would defeat the index the LIMIT is using.
    rows.reverse()

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
                  -- The same membership clause as `list_messages` and
                  -- `post_message`. It is not redundant with the RLS
                  -- policy on `messaging.messages`: this is the ONE path
                  -- in this module that had only the database layer, and
                  -- `SECURITY.md` §1 asks for two. It also matters more
                  -- here than anywhere else, because promotion copies the
                  -- message BODY into `workflow.tasks.description`, where
                  -- it is readable by people who were never in the
                  -- conversation. Raised as N2 by the Supervisor.
                  AND (
                        c.channel_type <> 'direct'
                        OR EXISTS (
                            SELECT 1 FROM messaging.channel_members cm
                            WHERE cm.channel_id = c.id
                              AND cm.user_id = core.current_user_id()
                        )
                      )
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
                     entity_id)
                -- `assigned_role` fills in when no user is named, because
                -- `tasks_has_an_owner` requires one of the two: a task
                -- nobody owns is a task nobody does.
                --
                -- There is no `created_by` column on workflow.tasks. An
                -- earlier version of this INSERT named one; the schema was
                -- read, not assumed, and it is not there. The promoter is
                -- recorded in the audit event instead, which is where the
                -- rest of this application looks for "who did this".
                VALUES (:org, :pid, :ttype, :title, :description, :assignee,
                        CASE WHEN CAST(:assignee AS uuid) IS NULL
                             THEN 'product_development_lead' END,
                        'message.promoted', 'message', :mid)
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
            },
        ).scalar_one()
    except IntegrityError as exc:
        # The raw driver message is NOT returned to the caller. It names
        # tables, columns and constraint names, and this path is reachable
        # by anyone who can post a message.
        session.rollback()
        raise MessagingError(
            "the task could not be created from this message; check that the "
            "channel belongs to a project you can write to"
        ) from exc

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
