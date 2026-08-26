"""Administration — section 1: users, roles, permissions, organization.

Administration is a thread through the build, not a single slice
(ADR-021). This is section 1, and it ships in Slice 1 because nothing
can be *granted* without it.

That is the whole point. Both earlier plan versions said role→permission
mapping was "editable in Administration" while no slice ever built the
screen — the operator's own most-repeated lesson turned on itself:
*ask of every role, which production path **writes** it?* Seeding a
Keycloak realm is not a write path. An administrator who can be read but
never granted does not exist.

Every mutation here writes an audit event in the same transaction as the
change. An role grant that committed without its audit row would be an
untraceable privilege escalation.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.audit import AuditEvent, write_audit
from app.core.db import guarded_write
from app.core.logging import log_audit, log_security
from app.core.security import Principal, get_db, require_permission

router = APIRouter()

__all__ = ["router"]


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
# Separate schemas per operation, so server-owned fields are structurally
# unreachable from a client payload (SECURITY.md §8). There is no generic
# "update" model that could carry organization_id or a timestamp.


class MemberRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    member_id: uuid.UUID
    user_id: uuid.UUID
    email: str
    display_name: str
    status: str
    roles: list[str] = Field(default_factory=list)


class MemberInvite(BaseModel):
    """Create a membership for a user who already exists in Keycloak.

    The application deliberately cannot create credentials — Keycloak
    owns identity. This binds an existing subject to an organization.
    """

    keycloak_sub: str = Field(min_length=1, max_length=255)
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=200)
    roles: list[str] = Field(default_factory=list)


class MemberStatusUpdate(BaseModel):
    status: str = Field(pattern="^(active|inactive)$")
    reason: str = Field(min_length=3, max_length=500)


class RoleRead(BaseModel):
    code: str
    name: str
    is_seeded: bool
    description: str | None
    permissions: list[str] = Field(default_factory=list)


class PermissionRead(BaseModel):
    code: str
    domain: str
    description: str


class RoleAssignment(BaseModel):
    role_code: str = Field(min_length=1, max_length=100)
    reason: str = Field(min_length=3, max_length=500)


# ---------------------------------------------------------------------------
# Permissions catalogue
# ---------------------------------------------------------------------------


@router.get("/permissions", response_model=list[PermissionRead], tags=["admin"])
def list_permissions(
    _: Principal = Depends(require_permission("admin.roles")),
    session: Session = Depends(get_db),
) -> list[PermissionRead]:
    """The fixed vocabulary the code checks.

    Read-only by design. Permissions are added by migration, never at
    runtime: a permission created through an API would have no
    enforcement point anywhere in the source, which reads as a control in
    an audit and is inert in production.
    """
    rows = session.execute(
        text("SELECT code, domain, description FROM core.permissions ORDER BY domain, code")
    ).mappings()
    return [PermissionRead(**r) for r in rows]


# ---------------------------------------------------------------------------
# Roles
# ---------------------------------------------------------------------------


@router.get("/roles", response_model=list[RoleRead], tags=["admin"])
def list_roles(
    _: Principal = Depends(require_permission("admin.roles")),
    session: Session = Depends(get_db),
) -> list[RoleRead]:
    rows = session.execute(
        text(
            """
            SELECT r.code, r.name, r.is_seeded, r.description,
                   COALESCE(array_agg(p.code ORDER BY p.code)
                            FILTER (WHERE p.code IS NOT NULL), '{}') AS permissions
            FROM core.roles r
            LEFT JOIN core.role_permissions rp ON rp.role_id = r.id
            LEFT JOIN core.permissions p       ON p.id = rp.permission_id
            GROUP BY r.code, r.name, r.is_seeded, r.description
            ORDER BY r.code
            """
        )
    ).mappings()
    return [RoleRead(**r) for r in rows]


# ---------------------------------------------------------------------------
# Members
# ---------------------------------------------------------------------------


@router.get("/members", response_model=list[MemberRead], tags=["admin"])
def list_members(
    principal: Principal = Depends(require_permission("admin.users")),
    session: Session = Depends(get_db),
) -> list[MemberRead]:
    """Members of the caller's organization.

    No organization parameter: the scope comes from the verified
    principal and RLS enforces it independently. An endpoint that let an
    admin name the organization would be a cross-tenant read waiting for
    one missing check.
    """
    rows = session.execute(
        text(
            """
            SELECT om.id AS member_id, u.id AS user_id, u.email::text AS email,
                   u.display_name, om.status,
                   COALESCE(array_agg(r.code ORDER BY r.code)
                            FILTER (WHERE r.code IS NOT NULL), '{}') AS roles
            FROM core.organization_members om
            JOIN core.users u            ON u.id = om.user_id
            LEFT JOIN core.member_roles mr ON mr.member_id = om.id
            LEFT JOIN core.roles r         ON r.id = mr.role_id
            GROUP BY om.id, u.id, u.email, u.display_name, om.status
            ORDER BY u.display_name
            """
        )
    ).mappings()
    _ = principal
    return [MemberRead(**r) for r in rows]


def _bind_conflict(exc: IntegrityError) -> HTTPException:
    """Translate an integrity failure from the bind into an honest 409.

    🔴 AN UNKNOWN CONSTRAINT MUST NOT BE REPORTED AS A MEMBERSHIP.

    This used to answer "user is already a member of this organization" for
    ANYTHING whose constraint was not one of the two it named -- a NULL
    constraint name, a NOT NULL or CHECK violation raised inside the definer,
    the primary key, or whatever a later migration adds. An administrator
    would be told a membership exists that does not. Raised by both
    reviewers, and it is the same rule the audit record follows: report the
    RESULT, not a guess at it.

    The two named constraints are safe to name because both facts are already
    visible to this caller -- `list_members` returns every member of their own
    organization with their address -- so neither discloses anything across a
    tenant boundary. That is the whole difference between these messages and
    the GLOBAL constraint I83 removed.
    """
    constraint = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)

    if constraint == "organization_members_unique":
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="user is already a member of this organization",
        )
    if constraint == "organization_members_one_address_per_organization":
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="another active member of this organization already uses that email address",
        )
    # Unknown. Generic on purpose: the driver message names tables and
    # columns, and asserting a specific outcome here would be a report of
    # something nobody checked.
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="the membership could not be created",
    )


@router.post(
    "/members",
    response_model=MemberRead,
    status_code=status.HTTP_201_CREATED,
    tags=["admin"],
)
def invite_member(
    payload: MemberInvite,
    principal: Principal = Depends(require_permission("admin.users")),
    session: Session = Depends(get_db),
) -> MemberRead:
    """Bind an existing Keycloak subject to this organization."""
    unknown = _unknown_roles(session, payload.roles)
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"unknown roles: {sorted(unknown)}",
        )

    # 🔴 ONE STATEMENT: RESOLVE, CREATE IF NEW, AND BIND (I82).
    #
    # This used to be `core.user_id_for_subject(:sub)` followed by a
    # conditional INSERT and then a separate membership INSERT. That resolver
    # answered, for an exact subject in ANY organization, with the user's uuid
    # and their existence -- on a SELECT, leaving no row behind. Narrow (it
    # needs `admin.users` and the exact subject) but an oracle, and the shape
    # migration 048 had just gone out of its way to avoid.
    #
    # `core.bind_subject_to_organization` returns the identifier only after
    # the membership exists. If the bind fails the whole thing rolls back and
    # nothing is returned; if it succeeds, the caller shares an organization
    # with that user and 044's read policy admits them anyway. So the id is
    # never learned by someone not entitled to it.
    #
    # ⚠️ THE ORGANIZATION IS NOT PASSED. It comes from `app.current_org`
    # inside the function. A SECURITY DEFINER taking an organization argument
    # would create memberships in any tenant the caller named -- a
    # cross-tenant WRITE inside the change that removes a cross-tenant READ,
    # which is the exact reflex ADR-029 caught in its own first draft.
    #
    # ⚠️ AND IT STILL RACES, SO IT IS STILL GUARDED. Two administrators
    # inviting the same brand-new subject concurrently both find no row and
    # both insert; the loser hits `users_keycloak_sub_key`. Atomicity removes
    # the read-then-write GAP within one call, not the contention between two.
    # `guarded_write` keeps the violation from destroying the request
    # transaction (I30), and the retry re-resolves through the same function.
    try:
        with guarded_write(session):
            bound = session.execute(
                text(
                    """
                    SELECT user_id, member_id
                    FROM core.bind_subject_to_organization(:sub, :email, :name)
                    """
                ),
                {
                    "sub": payload.keycloak_sub,
                    "email": payload.email,
                    "name": payload.display_name,
                },
            ).one()
    except IntegrityError as exc:
        # 🔴 THREE DIFFERENT REFUSALS ARRIVE HERE, AND TWO OF THEM WOULD BE
        # DESCRIBED WRONGLY BY THE THIRD'S MESSAGE.
        #
        #   organization_members_unique .............. already a member
        #   organization_members_one_address_per_org . 046's per-tenant guard
        #   users_keycloak_sub_key ................... the concurrent-invite race
        #
        # The first two are told apart because BOTH facts are already visible
        # to this caller -- `list_members` returns every member of their own
        # organization with their address -- so naming them discloses nothing
        # across a boundary. That is the whole difference between these
        # messages and the GLOBAL constraint I83 removed.
        constraint = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)

        # 🔴 THE RETRY GETS ITS OWN HANDLER, BECAUSE IT CAN FAIL TOO.
        #
        # Raised by both reviewers, with the same concrete scenario: two
        # administrators IN THE SAME ORGANIZATION invite the same brand-new
        # subject. A wins. B hits `users_keycloak_sub_key`, retries, now
        # resolves A's identity -- and the membership INSERT hits
        # `organization_members_unique`. That exception is raised INSIDE this
        # `except` block, so this `try` cannot catch it and it leaves the route
        # as a 500. The code deleted from here handled it, because its
        # membership INSERT had its own `try`.
        #
        # One bounded retry, and every outcome goes through the SAME
        # classifier below.
        if constraint == "users_keycloak_sub_key":
            # The other administrator's transaction has COMMITTED by the time
            # this handler runs -- PostgreSQL raises a unique violation only
            # then; while it is in flight the INSERT blocks. So the identity
            # now exists and one retry through the same function binds it.
            try:
                with guarded_write(session):
                    bound = session.execute(
                        text(
                            """
                            SELECT user_id, member_id
                            FROM core.bind_subject_to_organization(:sub, :email, :name)
                            """
                        ),
                        {
                            "sub": payload.keycloak_sub,
                            "email": payload.email,
                            "name": payload.display_name,
                        },
                    ).one()
            except IntegrityError as retry_exc:
                raise _bind_conflict(retry_exc) from retry_exc
        else:
            # ONE classifier, here and on the retry. The address-collision case
            # used to be spelled out again at this level; two copies of a
            # message is two things to keep in agreement, and this file's own
            # history is a list of what happens when they drift.
            raise _bind_conflict(exc) from exc

    user_id = bound.user_id
    member_id = bound.member_id
    # ⚠️ `identity_created` IS NO LONGER SELECTED. Migration 050 removed it:
    # it was a cross-tenant existence bit that nothing here read, and the
    # "cost" said to excuse it -- a membership row and an audit record -- can
    # be rolled back, so it was never a cost. Both reviewers found it; the
    # rollback was then measured.

    for role_code in payload.roles:
        _grant_role(session, member_id, role_code)

    # 🔴 READ THE STORED ATTRIBUTES *AFTER* THE MEMBERSHIP EXISTS, NOT BEFORE.
    #
    # This read used to sit in the `else` branch above, and the Supervisor
    # showed it was DEAD CODE: 044's read policy admits a row only when the
    # reader shares an organization with that user (or is that user), and both
    # conditions imply a membership row -- which the check above would already
    # have turned into a 409. So on every path that reached a 201, the lookup
    # returned None and the response fell back to echoing the caller's own
    # submission. The commit claimed it returned stored values; it could not.
    #
    # Moving it here makes it true rather than removing it. The membership
    # INSERT above is visible to this transaction, so the policy's EXISTS now
    # matches and the real row is readable. `one()`, not `one_or_none()`: after
    # a successful bind there is no legitimate way for this to miss, and a
    # silent fallback is what produced the false report in the first place.
    stored_email, stored_name = session.execute(
        text("SELECT email::text, display_name FROM core.users WHERE id = :uid"),
        {"uid": user_id},
    ).one()

    write_audit(
        session,
        AuditEvent(
            action="admin.member_invited",
            entity_type="organization_member",
            entity_id=str(member_id),
            organization_id=principal.organization_id,
            user_id=principal.user_id,
            # ⚠️ The STORED email, not the submitted one. This recorded
            # `payload.email` -- for a pre-existing identity that address was
            # never written anywhere, so the audit trail asserted a value the
            # database does not hold. A forensic record that reports the
            # request instead of the result is worse than no record.
            new_state={"email": stored_email, "roles": payload.roles},
            reason="membership created via Administration",
        ),
    )
    log_audit("member_invited", member_id=str(member_id), roles=payload.roles)

    # The STORED values, not the submitted ones. For an identity that already
    # existed, the caller's email and display name were not written and
    # echoing them would report a change that did not happen — the same
    # class of defect as the upsert above, one layer up.
    return MemberRead(
        member_id=member_id,
        user_id=user_id,
        email=stored_email,
        display_name=stored_name,
        status="active",
        roles=payload.roles,
    )


@router.post("/members/{member_id}/roles", status_code=status.HTTP_204_NO_CONTENT, tags=["admin"])
def grant_role(
    member_id: uuid.UUID,
    payload: RoleAssignment,
    principal: Principal = Depends(require_permission("admin.roles")),
    session: Session = Depends(get_db),
) -> None:
    """Grant a role. This is the write path ADR-021 exists to guarantee."""
    if _unknown_roles(session, [payload.role_code]):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"unknown role: {payload.role_code}",
        )

    # RLS confines this to the caller's organization, so a member_id from
    # another tenant simply is not found -- indistinguishable from one
    # that does not exist, which is the intended answer.
    if not _member_exists(session, member_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="member not found")

    _grant_role(session, member_id, payload.role_code)

    write_audit(
        session,
        AuditEvent(
            action="admin.role_granted",
            entity_type="organization_member",
            entity_id=str(member_id),
            organization_id=principal.organization_id,
            user_id=principal.user_id,
            new_state={"role": payload.role_code},
            reason=payload.reason,
        ),
    )
    log_security(
        "role_granted",
        member_id=str(member_id),
        role=payload.role_code,
        granted_by=str(principal.user_id),
    )


@router.delete(
    "/members/{member_id}/roles/{role_code}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["admin"],
)
def revoke_role(
    member_id: uuid.UUID,
    role_code: str,
    payload: RoleAssignment,
    principal: Principal = Depends(require_permission("admin.roles")),
    session: Session = Depends(get_db),
) -> None:
    """Revoke a role.

    Guards against removing the last administrator. An organization with
    no one holding ``admin.roles`` cannot grant anything ever again, and
    recovering from that needs direct database access — the same class of
    dead end as a role with no write path.
    """
    if not _member_exists(session, member_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="member not found")

    if _would_orphan_administration(session, member_id, role_code):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "refusing to revoke the last role holding admin.roles — "
                "the organization would be unable to grant any role again"
            ),
        )

    session.execute(
        text(
            """
            DELETE FROM core.member_roles
            WHERE member_id = :mid
              AND role_id = (SELECT id FROM core.roles WHERE code = :code)
            """
        ),
        {"mid": member_id, "code": role_code},
    )

    write_audit(
        session,
        AuditEvent(
            action="admin.role_revoked",
            entity_type="organization_member",
            entity_id=str(member_id),
            organization_id=principal.organization_id,
            user_id=principal.user_id,
            previous_state={"role": role_code},
            reason=payload.reason,
        ),
    )
    log_security(
        "role_revoked", member_id=str(member_id), role=role_code, revoked_by=str(principal.user_id)
    )


@router.patch("/members/{member_id}/status", status_code=status.HTTP_204_NO_CONTENT, tags=["admin"])
def set_member_status(
    member_id: uuid.UUID,
    payload: MemberStatusUpdate,
    principal: Principal = Depends(require_permission("admin.users")),
    session: Session = Depends(get_db),
) -> None:
    """Activate or deactivate a membership.

    Deactivation, never deletion. Removing the row would orphan every
    audit event and approval that names this member, and R&D history is
    retired by status rather than destroyed (CLAUDE.md §5).
    """
    if member_id == _self_member_id(session, principal):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="refusing to change your own membership status",
        )

    previous = session.execute(
        text("SELECT status FROM core.organization_members WHERE id = :mid"),
        {"mid": member_id},
    ).scalar_one_or_none()

    if previous is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="member not found")

    session.execute(
        text("UPDATE core.organization_members SET status = :s WHERE id = :mid"),
        {"s": payload.status, "mid": member_id},
    )

    write_audit(
        session,
        AuditEvent(
            action="admin.member_status_changed",
            entity_type="organization_member",
            entity_id=str(member_id),
            organization_id=principal.organization_id,
            user_id=principal.user_id,
            previous_state={"status": previous},
            new_state={"status": payload.status},
            reason=payload.reason,
        ),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _unknown_roles(session: Session, codes: list[str]) -> set[str]:
    if not codes:
        return set()
    known = {
        r[0]
        for r in session.execute(
            text("SELECT code FROM core.roles WHERE code = ANY(:codes)"),
            {"codes": codes},
        ).all()
    }
    return set(codes) - known


def _member_exists(session: Session, member_id: uuid.UUID) -> bool:
    return (
        session.execute(
            text("SELECT 1 FROM core.organization_members WHERE id = :mid"),
            {"mid": member_id},
        ).scalar_one_or_none()
        is not None
    )


def _self_member_id(session: Session, principal: Principal) -> uuid.UUID | None:
    return session.execute(
        text(
            """
            SELECT id FROM core.organization_members
            WHERE organization_id = :org AND user_id = :uid
            """
        ),
        {"org": principal.organization_id, "uid": principal.user_id},
    ).scalar_one_or_none()


def _grant_role(session: Session, member_id: uuid.UUID, role_code: str) -> None:
    session.execute(
        text(
            """
            INSERT INTO core.member_roles (member_id, role_id)
            SELECT :mid, id FROM core.roles WHERE code = :code
            ON CONFLICT DO NOTHING
            """
        ),
        {"mid": member_id, "code": role_code},
    )


def _would_orphan_administration(session: Session, member_id: uuid.UUID, role_code: str) -> bool:
    """True if revoking this role leaves nobody able to grant roles."""
    remaining = session.execute(
        text(
            """
            SELECT count(DISTINCT om.id)
            FROM core.organization_members om
            JOIN core.member_roles mr      ON mr.member_id = om.id
            JOIN core.roles r              ON r.id = mr.role_id
            JOIN core.role_permissions rp  ON rp.role_id = r.id
            JOIN core.permissions p        ON p.id = rp.permission_id
            WHERE p.code = 'admin.roles'
              AND om.status = 'active'
              AND NOT (om.id = :mid AND r.code = :code)
            """
        ),
        {"mid": member_id, "code": role_code},
    ).scalar_one()
    return int(remaining) == 0
