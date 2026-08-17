"""Tenant membership checks.

**Why this file exists.** `core.users` is not tenant-scoped -- a user
belongs to organizations through `core.organization_members`, and may
belong to several. Every foreign key to a user is therefore a plain
`REFERENCES core.users(id)`, which accepts *any* user id in the system.

Referential integrity bypasses RLS even under FORCE. So an id that RLS
would never let the caller *read* can still be *referenced*: assigned a
task, named as a project lead, enrolled as a project member. RLS answers
reachability for reads; it says nothing about references.

That makes "is this user actually a member of this organization" an
application-layer obligation, and one that must be asked in the same way
everywhere. It was originally asked in `reassign_task` and nowhere else,
which is exactly how a rule drifts: `create_task` and
`convert_to_project` both accepted a foreign-tenant user id, and
`convert_to_project` went on to enrol them as a project member.

Both were found by review (Codex C1, C2). Hence one function, imported by
every caller, rather than three hand-written EXISTS queries that agree
today.
"""

from __future__ import annotations

import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session

__all__ = ["CrossTenantReferenceError", "is_active_member", "require_active_member"]


class CrossTenantReferenceError(RuntimeError):
    """A user id was supplied that does not belong to this organization.

    Deliberately a distinct type. A caller translating this to HTTP must
    not leak whether the id names a real user in another tenant -- the
    answer is the same for "no such user" and "not your user", because
    the difference is itself information about another tenant.
    """


def is_active_member(session: Session, *, user_id: uuid.UUID, organization_id: uuid.UUID) -> bool:
    """True when the user is an ACTIVE member of the organization.

    ``status = 'active'`` is part of the predicate, not an afterthought.
    A revoked membership row still exists; treating its presence as
    membership would let a removed employee stay assignable, and the
    person removing them would have no signal that it had not worked.
    """
    return bool(
        session.execute(
            text(
                """
                SELECT EXISTS (
                    SELECT 1 FROM core.organization_members
                    WHERE user_id = :uid
                      AND organization_id = :org
                      AND status = 'active'
                )
                """
            ),
            {"uid": user_id, "org": organization_id},
        ).scalar_one()
    )


def require_active_member(
    session: Session,
    *,
    user_id: uuid.UUID,
    organization_id: uuid.UUID,
    role_description: str = "user",
) -> None:
    """Refuse unless the user is an active member of the organization.

    Args:
        role_description: what the user was being named as -- "assignee",
            "project lead". It appears in the message so an administrator
            can tell which field of a multi-user payload was wrong,
            without the message revealing anything about the id itself.
    """
    if not is_active_member(session, user_id=user_id, organization_id=organization_id):
        raise CrossTenantReferenceError(
            f"the supplied {role_description} is not an active member of this organization"
        )
