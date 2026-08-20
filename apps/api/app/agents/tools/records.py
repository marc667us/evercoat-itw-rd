"""Find controlled records the caller may actually read."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.domains.msd.retrieval import RetrievedRecord, retrieve_for_question

__all__ = ["find_records"]


def find_records(
    session: Session,
    *,
    organization_id: uuid.UUID,
    question: str,
    project_id: uuid.UUID | None = None,
    entity_types: tuple[str, ...] | None = None,
) -> list[RetrievedRecord]:
    """Records inside the caller's authorization boundary.

    A thin, deliberate wrapper over `retrieve_for_question`. It adds
    nothing, and that is the point: the boundary is enforced in one place
    (`app/domains/msd/retrieval.py`, on the caller's RLS-scoped session)
    and every tool that needs records goes through it rather than writing
    its own query.

    A second retrieval path is exactly how a filter gets forgotten — the
    defect §7 calls "AI becoming a permission-bypass channel".
    """
    return retrieve_for_question(
        session,
        organization_id=organization_id,
        question=question,
        project_id=project_id,
        entity_types=entity_types,
    )
