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
from sqlalchemy.orm import Session

from app.core.audit import AuditEvent, write_audit
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

    user_id = session.execute(
        text(
            """
            INSERT INTO core.users (keycloak_sub, email, display_name)
            VALUES (:sub, :email, :name)
            ON CONFLICT (keycloak_sub) DO UPDATE
                SET display_name = EXCLUDED.display_name
            RETURNING id
            """
        ),
        {"sub": payload.keycloak_sub, "email": payload.email, "name": payload.display_name},
    ).scalar_one()

    existing = session.execute(
        text(
            """
            SELECT id FROM core.organization_members
            WHERE organization_id = :org AND user_id = :uid
            """
        ),
        {"org": principal.organization_id, "uid": user_id},
    ).scalar_one_or_none()

    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="user is already a member of this organization",
        )

    member_id = session.execute(
        text(
            """
            INSERT INTO core.organization_members (organization_id, user_id)
            VALUES (:org, :uid)
            RETURNING id
            """
        ),
        {"org": principal.organization_id, "uid": user_id},
    ).scalar_one()

    for role_code in payload.roles:
        _grant_role(session, member_id, role_code)

    write_audit(
        session,
        AuditEvent(
            action="admin.member_invited",
            entity_type="organization_member",
            entity_id=str(member_id),
            organization_id=principal.organization_id,
            user_id=principal.user_id,
            new_state={"email": str(payload.email), "roles": payload.roles},
            reason="membership created via Administration",
        ),
    )
    log_audit("member_invited", member_id=str(member_id), roles=payload.roles)

    return MemberRead(
        member_id=member_id,
        user_id=user_id,
        email=str(payload.email),
        display_name=payload.display_name,
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
