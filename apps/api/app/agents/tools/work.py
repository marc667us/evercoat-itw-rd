"""What is waiting for the person asking."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.domains.tasks.service import my_work

__all__ = ["pending_work"]


def pending_work(
    session: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    role_codes: frozenset[str],
    limit: int = 20,
) -> list[dict[str, Any]]:
    """The caller's actionable inbox, per Concept Note §38.

    🔴 IT DELEGATES. THE FIRST VERSION OF THIS TOOL DID NOT, AND THAT WAS
    THE BUG.

    It was written with its own `SELECT ... WHERE assigned_user_id = ...
    AND status IN ('open','in_progress','blocked')`. That query is not
    wrong so much as it is a THIRD definition of "pending work", beside
    `my_work` (the My Work screen) and `my_work_counts` (the sidebar
    badge) — and those two exist as a matched pair precisely because, in
    that module's own words, *"a count and a list that disagree is a
    defect users notice immediately and developers never do"*.

    Three definitions is worse than two. MSD telling a chemist they have
    four things waiting while the sidebar says six is not a rounding
    difference — it is the assistant contradicting the application, which
    destroys trust in both. And the hand-rolled version had already
    dropped the role-addressed unclaimed tasks that `my_work` includes,
    so it was ALREADY giving a different answer.

    `user_id` is supplied by the orchestrator from the verified
    principal, never from the request body — the caller cannot ask about
    a colleague.
    """
    return my_work(
        session,
        user_id=user_id,
        organization_id=organization_id,
        role_codes=role_codes,
    )[:limit]
