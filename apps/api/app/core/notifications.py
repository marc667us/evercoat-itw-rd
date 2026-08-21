"""The single writer of notifications. TODO I36.

🔴 WHY THIS IS IN `core` AND NOT IN `messaging`.

§12 lists `NotificationService` as SHARED infrastructure that no module may
rebuild — the same standing as `AuditHook` and the approval engine. It lived
inside `app/domains/messaging/service.py` because messaging was the first
module to need it, and that made every other domain reach INTO messaging to
notify anybody.

That was tolerable until two domains needed to reach in the other direction:

    tasks     --> messaging   (to notify an assignee)
    messaging --> tasks       (to raise a task from a promoted message)

which is an import cycle, and the cycle is what kept `promote_message`
duplicating `create_task`'s INSERT instead of calling it. A defect held in
place by an architectural accident, not by a decision.

Notifications are infrastructure, so they live beside `write_audit`, which
every domain also calls and which nobody would think to put inside one.

The TABLE stays in the `messaging` schema. Where a row lives and which module
owns the code that writes it are different questions, and moving the table
would be a migration with no benefit — `messaging.notifications` is where
every existing query, policy and grant already points.

Reading notifications (`my_notifications`, `mark_notification_read`) stays in
`app/domains/messaging/service.py`: those are a user-facing feature of the
messaging module, not infrastructure other domains call.
"""

from __future__ import annotations

import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session

__all__ = ["notify"]


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

    THE single writer, in the same sense as one approval engine: every module
    calls this rather than growing its own table.

    `is_actionable` separates "you must do something" from "this happened",
    because §11 requires a badge to count items needing action and that
    distinction has to exist in the data or every count is a row total.

    🔴 THE CALLER DECIDES WHETHER THE RECIPIENT MAY SEE THIS. §7: a
    notification must not disclose what its recipient cannot reach — a mention
    in a restricted project's channel would otherwise name that project to
    somebody with no access, and the notification becomes the leak. This
    function cannot make that judgement, because it does not know what the
    entity is or who may read it. Every call site must, and each one says how.
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
