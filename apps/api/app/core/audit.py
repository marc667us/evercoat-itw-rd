"""Audit writing and hash-chain verification.

The audit trail is the authoritative record of who did what to controlled
R&D records. An application-level "append-only" convention is bypassable
by direct SQL, scripts, failed code paths and compromised service
credentials (Codex F22), so immutability is enforced in the database:
``audit.events`` has triggers that reject UPDATE and DELETE outright, and
a SHA-256 chain that makes tampering *detectable* rather than merely
discouraged.

The chain (reused from Solar migration 016 — REUSE.md R2):

    row_hash = sha256(prev_hash || '|' || canonical_content)

Editing any row invalidates that row's ``row_hash`` and breaks every
subsequent row, because their ``prev_hash`` no longer matches. Deleting a
row breaks the chain at the next row. The verifier walks ``id ASC`` and
reports the first break.

**Why this module recomputes a hash the database already computed.**
PostgreSQL writes the chain in a BEFORE INSERT trigger. Python recomputing
it independently is not redundancy for its own sake: it means each side
can verify the other. If the two ever disagree, either the trigger was
altered or the canonical form drifted — both of which are exactly the
tampering the chain exists to surface.

That only works if both sides serialise **identically**. The field order
below is a contract with ``audit.canonical_content()`` in
``001_core_tenancy.sql``. Changing one without the other makes every row
read as tampered. If you must change it, migrate deliberately and record
a chain break with its reason.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

__all__ = [
    "AuditEvent",
    "ChainBreak",
    "canonical_content",
    "compute_row_hash",
    "verify_chain",
    "write_audit",
]

GENESIS = "GENESIS"

# Must match to_char(..., 'YYYY-MM-DD"T"HH24:MI:SS.US') in the SQL.
# A locale-dependent rendering would make the hash unreproducible across
# hosts -- the same row would verify on one machine and fail on another.
_TS_FORMAT = "%Y-%m-%dT%H:%M:%S.%f"


@dataclass(frozen=True, slots=True)
class AuditEvent:
    """One controlled action.

    ``previous_state`` and ``new_state`` are the before/after of the
    entity, not the whole request. They must never contain formula
    compositions in full, secrets or tokens -- SECURITY.md §11 forbids
    payload logging, and the audit table is not an exception.
    """

    action: str
    entity_type: str
    organization_id: uuid.UUID | None = None
    user_id: uuid.UUID | None = None
    role_code: str | None = None
    entity_id: str | None = None
    previous_state: dict[str, Any] | None = None
    new_state: dict[str, Any] | None = None
    reason: str | None = None
    session_id: str | None = None
    ip_address: str | None = None
    occurred_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class ChainBreak:
    """The first point at which the chain stops verifying."""

    event_id: int
    reason: str
    expected: str
    found: str


def _json(value: dict[str, Any] | None) -> str:
    """Serialise JSONB the way PostgreSQL renders it for the hash.

    ``sort_keys`` is what makes this reproducible: Python dict order and
    PostgreSQL's jsonb key order are both stable but not the same, so the
    canonical form pins one ordering for both sides.
    """
    if value is None:
        return ""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def canonical_content(event: AuditEvent, occurred_at: datetime) -> str:
    """Pipe-joined canonical serialisation.

    Field order is a contract with ``audit.canonical_content()`` in SQL.
    ``None`` becomes an empty string, matching COALESCE(..., '') there.
    """
    parts = [
        str(event.organization_id) if event.organization_id else "",
        str(event.user_id) if event.user_id else "",
        event.role_code or "",
        event.action or "",
        event.entity_type or "",
        event.entity_id or "",
        _json(event.previous_state),
        _json(event.new_state),
        event.reason or "",
        occurred_at.astimezone(UTC).strftime(_TS_FORMAT),
    ]
    return "|".join(parts)


def compute_row_hash(prev_hash: str, content: str) -> str:
    """sha256(prev_hash || '|' || canonical_content), hex-encoded."""
    return hashlib.sha256(f"{prev_hash}|{content}".encode()).hexdigest()


def write_audit(session: Session, event: AuditEvent) -> int:
    """Append one audit event.

    The database trigger computes ``prev_hash`` and ``row_hash`` under an
    advisory lock, so concurrent writers cannot fork the chain. This
    function therefore does *not* pass them -- doing so would race the
    trigger and produce a chain the verifier reports as tampered.

    The write joins the caller's transaction on purpose: an audit record
    for an action that rolled back would be a lie, and an action that
    committed without its audit record would be an untraceable change.
    They succeed or fail together.
    """
    occurred = event.occurred_at or datetime.now(UTC)

    result = session.execute(
        text(
            """
            INSERT INTO audit.events (
                organization_id, user_id, role_code, action, entity_type,
                entity_id, previous_state, new_state, reason,
                session_id, ip_address, occurred_at,
                prev_hash, row_hash
            ) VALUES (
                :organization_id, :user_id, :role_code, :action, :entity_type,
                :entity_id, CAST(:previous_state AS JSONB),
                CAST(:new_state AS JSONB), :reason,
                :session_id, CAST(:ip_address AS INET), :occurred_at,
                '', ''          -- overwritten by audit.chain_row()
            )
            RETURNING id
            """
        ),
        {
            "organization_id": event.organization_id,
            "user_id": event.user_id,
            "role_code": event.role_code,
            "action": event.action,
            "entity_type": event.entity_type,
            "entity_id": event.entity_id,
            "previous_state": _json(event.previous_state) or None,
            "new_state": _json(event.new_state) or None,
            "reason": event.reason,
            "session_id": event.session_id,
            "ip_address": event.ip_address,
            "occurred_at": occurred,
        },
    )
    return int(result.scalar_one())


def verify_chain(
    session: Session,
    *,
    organization_id: uuid.UUID | None,
    start_id: int = 0,
    limit: int | None = None,
) -> ChainBreak | None:
    """Walk ONE organization's chain in id order; return the first break.

    Returns on the *first* break rather than collecting all of them: after
    one break every subsequent row mismatches by construction, so a full
    list would be noise. The first break is the interesting one.

    **``organization_id`` is required, and that is the point.** Since
    migration 011 the chain is per organization: ``prev_hash`` resolves
    against the last row carrying the same ``organization_id``. A walk of
    the whole table therefore sees several independent chains interleaved
    in one id sequence and reports each boundary as a break -- a false
    alarm, and a tamper alarm that cries wolf is one that stops being read.

    Passing ``None`` is meaningful rather than a default: it verifies the
    SYSTEM chain, the rows written by the platform itself (migrations,
    maintenance, the bootstrap path) which carry no organization.

    Before 011 this argument did not exist and the function walked
    whatever RLS happened to show the caller. That worked only because the
    *writer* was filtered by the same policy, so the scope was correct by
    coincidence rather than by construction -- and it silently produced a
    different answer depending on which role called it.
    """
    # One statement with a NULL-tolerant LIMIT rather than concatenating
    # a clause. The concatenated version was in fact safe -- `limit` was
    # always a bind parameter -- but it tripped S608, and a lint
    # suppression on a query-building line is a bad habit to establish in
    # the one module whose whole purpose is tamper evidence. PostgreSQL
    # treats LIMIT NULL as "no limit", so this needs no branch at all.
    rows = session.execute(
        text(
            """
            SELECT id, organization_id, user_id, role_code, action,
                   entity_type, entity_id, previous_state, new_state,
                   reason, occurred_at, prev_hash, row_hash
            FROM audit.events
            WHERE id > :start_id
              -- IS NOT DISTINCT FROM, not `=`: the system chain is
              -- selected by organization_id IS NULL, and `= NULL` would
              -- silently match nothing and report an empty chain as
              -- intact.
              AND organization_id IS NOT DISTINCT FROM :organization_id
            ORDER BY id ASC
            LIMIT :limit
            """
        ),
        {"start_id": start_id, "limit": limit, "organization_id": organization_id},
    ).mappings()

    # Seed the expectation for the FIRST row, rather than trusting it.
    #
    # Skipping the first row's prev_hash check leaves the head of the walk
    # unauthenticated: delete an organization's genesis event and its
    # second event becomes the first row returned, whose prev_hash names a
    # row that no longer exists -- and the walk reports the chain intact.
    # Deleting a row is precisely what this mechanism exists to detect
    # (Codex review, finding 4).
    #
    # A full walk (start_id = 0) must begin at GENESIS. A bounded walk
    # must match the row_hash of the last row of the SAME chain at or
    # before the boundary, which is what the writer would have chained on.
    if start_id <= 0:
        expected_prev: str | None = GENESIS
    else:
        expected_prev = session.execute(
            text(
                """
                SELECT row_hash
                FROM audit.events
                WHERE id <= :start_id
                  AND organization_id IS NOT DISTINCT FROM :organization_id
                ORDER BY id DESC
                LIMIT 1
                """
            ),
            {"start_id": start_id, "organization_id": organization_id},
        ).scalar_one_or_none()
        # None means there is no earlier row in this chain, so the first
        # row returned really is the chain's head and must say GENESIS.
        if expected_prev is None:
            expected_prev = GENESIS

    for row in rows:
        if expected_prev is not None and row["prev_hash"] != expected_prev:
            return ChainBreak(
                event_id=row["id"],
                reason="prev_hash does not match the previous row's row_hash "
                "— a row was deleted, reordered or inserted out of band",
                expected=expected_prev,
                found=row["prev_hash"],
            )

        event = AuditEvent(
            action=row["action"],
            entity_type=row["entity_type"],
            organization_id=row["organization_id"],
            user_id=row["user_id"],
            role_code=row["role_code"],
            entity_id=row["entity_id"],
            previous_state=row["previous_state"],
            new_state=row["new_state"],
            reason=row["reason"],
        )
        recomputed = compute_row_hash(
            row["prev_hash"], canonical_content(event, row["occurred_at"])
        )

        if recomputed != row["row_hash"]:
            return ChainBreak(
                event_id=row["id"],
                reason="row_hash does not match recomputed content "
                "— this row's stored data was altered after it was written",
                expected=recomputed,
                found=row["row_hash"],
            )

        expected_prev = row["row_hash"]

    return None
