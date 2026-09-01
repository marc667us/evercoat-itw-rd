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

import datetime as dt
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
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
    # 🔴 THE ATTRIBUTES COME FROM THE MEMBERSHIP, NOT FROM `core.users` (052).
    #
    # This used to join `core.users` for the address and the name. Those
    # columns are the GLOBAL identity's, and for a person who also belongs to
    # another tenant they are that tenant's values — which is I106, and which
    # is why `evercoat_app` can no longer read them at all. `core.users` stays
    # in the query only for `id`, which is not an attribute of anybody.
    rows = session.execute(
        text(
            """
            SELECT om.id AS member_id, om.user_id, om.email::text AS email,
                   om.display_name, om.status,
                   COALESCE(array_agg(r.code ORDER BY r.code)
                            FILTER (WHERE r.code IS NOT NULL), '{}') AS roles
            FROM core.organization_members om
            LEFT JOIN core.member_roles mr ON mr.member_id = om.id
            LEFT JOIN core.roles r         ON r.id = mr.role_id
            GROUP BY om.id, om.user_id, om.email, om.display_name, om.status
            ORDER BY om.display_name
            """
        )
    ).mappings()
    _ = principal
    return [MemberRead(**r) for r in rows]


def _standing_refusal(exc: DBAPIError) -> HTTPException | None:
    """A 403 for the database's own refusal, which is not an IntegrityError.

    🔴 MIGRATION 050's STANDING CHECK ESCAPED AS A 500.

    It raises `insufficient_privilege` (SQLSTATE 42501), which psycopg surfaces
    as `ProgrammingError` -- a sibling of `IntegrityError`, not a subclass. The
    route caught only `IntegrityError` and no exception handler is registered
    on the app, so the refusal left as a 500 carrying a driver message. Raised
    by the Supervisor; measured before it was believed.

    ⚠️ THE PATH IS NARROW AND REAL. `require_permission("admin.users")` already
    guards this route, so reaching the database check means the two disagree:
    the caller's membership or role was revoked between `get_principal` and
    this write. That immediate-revocation window is the reason 048's function
    exists, so answering it with a 500 defeats the point of checking twice.

    Returns None for anything else, so an unrelated database fault keeps its
    own handling rather than being relabelled a permission problem.
    """
    if getattr(exc.orig, "sqlstate", None) != "42501":
        return None
    # Deliberately does not repeat the database's message: it says "not
    # permitted to bind members in this organization", and which of membership
    # or permission is missing is not the caller's business (050).
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="not permitted to add members to this organization",
    )


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
    # 🔴 UNKNOWN MEANS UNKNOWN, AND 409 IS NOT "UNKNOWN".
    #
    # This returned a 409 for anything it could not name -- a NOT NULL, CHECK
    # or FK violation raised inside the definer, or a second
    # `users_keycloak_sub_key` on the retry. A 409 tells the client the request
    # conflicts with existing state and that changing it will help. None of
    # those are that: they are server-side faults or contention, and the client
    # can do nothing about them. Raised by the Supervisor, against this
    # function's own docstring rule -- report the RESULT, not a guess -- which
    # I applied to the message and not to the status code.
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="the membership could not be created",
    )


def _bind_subject(
    session: Session,
    *,
    keycloak_sub: str,
    email: str,
    display_name: str,
) -> uuid.UUID:
    """Bind an existing Keycloak subject to the caller's organization.

    🔴 EXTRACTED 2026-09-01, AND NOT COPIED, BECAUSE THERE ARE NOW TWO CALLERS.

    `POST /api/admin/members` has always done this. Approving an access request
    has to do exactly the same thing, and every hard-won part of it —
    050's standing-check refusal arriving as a `ProgrammingError` rather than an
    `IntegrityError`, the three constraints that must be told apart, and the
    bounded retry whose own failure needs its own handler — would have had to be
    reproduced at the second call site. This file's own docstring names that
    shape: *"a second entry point would be the I5/I36 shape this codebase has
    already logged twice."*

    ⚠️ THE ORGANIZATION IS STILL NOT AN ARGUMENT. It comes from
    `app.current_org` inside `core.bind_subject_to_organization`. Adding an
    organization parameter here would let a caller name a tenant, which is the
    cross-tenant write ADR-029 refused.

    Returns the membership id. Raises `HTTPException` for every refusal the
    database makes, and re-raises anything it cannot classify.
    """
    try:
        with guarded_write(session):
            bound = session.execute(
                text(
                    """
                    SELECT member_id
                    FROM core.bind_subject_to_organization(:sub, :email, :name)
                    """
                ),
                {
                    "sub": keycloak_sub,
                    "email": email,
                    "name": display_name,
                },
            ).one()
    except DBAPIError as exc:
        # 🔴 THE DATABASE'S OWN REFUSAL IS NOT AN INTEGRITY ERROR.
        # 050's standing check raises SQLSTATE 42501, which arrives as
        # `ProgrammingError` -- a sibling of `IntegrityError`, not a
        # subclass -- so this handler never saw it and it left as a 500.
        refusal = _standing_refusal(exc)
        if refusal is not None:
            raise refusal from exc
        if not isinstance(exc, IntegrityError):
            # Anything else is a genuine database fault. Re-raise rather
            # than describe it: the handling below is about constraints.
            raise
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
                            SELECT member_id
                            FROM core.bind_subject_to_organization(:sub, :email, :name)
                            """
                        ),
                        {
                            "sub": keycloak_sub,
                            "email": email,
                            "name": display_name,
                        },
                    ).one()
            except DBAPIError as retry_exc:
                # The standing check can refuse HERE too -- a revocation
                # that lands between the first attempt and the retry.
                refusal = _standing_refusal(retry_exc)
                if refusal is not None:
                    raise refusal from retry_exc
                if not isinstance(retry_exc, IntegrityError):
                    raise
                raise _bind_conflict(retry_exc) from retry_exc
        else:
            # ONE classifier, here and on the retry. The address-collision case
            # used to be spelled out again at this level; two copies of a
            # message is two things to keep in agreement, and this file's own
            # history is a list of what happens when they drift.
            raise _bind_conflict(exc) from exc
    return bound.member_id  # type: ignore[no-any-return]


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
    member_id = _bind_subject(
        session,
        keycloak_sub=payload.keycloak_sub,
        email=payload.email,
        display_name=payload.display_name,
    )

    # 🔴 THE USER IS RESOLVED THROUGH THE MEMBERSHIP, NOT HANDED BACK BY THE
    # DEFINER — BECAUSE THE IDENTIFIER *WAS* THE EXISTENCE ANSWER (051).
    #
    # ⚠️ AND THE ATTRIBUTES COME BACK IN THE SAME READ (052). They used to be
    # a second SELECT against `core.users`, which for a subject that already
    # existed in another tenant returned THAT tenant's address and name — I106,
    # readable and then rolled away. `evercoat_app` cannot read those columns
    # any more; the membership carries this organization's own values.
    #
    # 050 removed `identity_created` for answering "does this subject already
    # exist somewhere on this platform" at no cost. Codex showed the answer had
    # simply moved into `user_id`, and it measures: two rolled-back binds
    # return the SAME uuid when the subject exists in another tenant and
    # DIFFERENT uuids when it does not.
    #
    # `member_id` is minted by this call, so it is fresh in both branches. This
    # read is governed by 044's policy rather than by a definer: the membership
    # was created in THIS transaction and in THIS organization, so the policy
    # matches — and if a later change breaks that, this raises instead of
    # quietly falling back, which is the failure the block below describes.
    user_id, stored_email, stored_name = session.execute(
        text(
            """
            SELECT user_id, email::text, display_name
            FROM core.organization_members WHERE id = :mid
            """
        ),
        {"mid": member_id},
    ).one()
    # ⚠️ `identity_created` IS NO LONGER SELECTED. Migration 050 removed it:
    # it was a cross-tenant existence bit that nothing here read, and the
    # "cost" said to excuse it -- a membership row and an audit record -- can
    # be rolled back, so it was never a cost. Both reviewers found it; the
    # rollback was then measured.

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
            # ⚠️ The STORED email, read back, not `payload.email`. Since 052
            # the membership records exactly what was submitted, so the two
            # now agree -- but the discipline is what matters: a forensic
            # record must report the RESULT of the write, not the request
            # that asked for it. Reading it back is what makes the record
            # true if a trigger, a default or a later migration ever changes
            # the value on the way in.
            new_state={"email": stored_email, "roles": payload.roles},
            reason="membership created via Administration",
        ),
    )
    log_audit("member_invited", member_id=str(member_id), roles=payload.roles)

    # The STORED values, read back from the membership. Before 052 this
    # mattered because a pre-existing identity kept the FIRST tenant's
    # address and the caller's submission was never written anywhere; now
    # this organization's row holds what this organization submitted, and
    # the read-back is what proves it rather than assumes it.
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
# Access requests — the landing page's "Sign Up", and its missing reader
# ---------------------------------------------------------------------------
#
# 🔴 `public_intel.access_requests` HAD A WRITER AND NO READER (L1).
#
# `POST /api/public/access-requests` has recorded interest since migration 059.
# Nothing in `apps/api/app` or `apps/web` ever read the table back, so every
# request an anonymous visitor submitted went into a queue no production path
# could open — which is this project's own most-repeated defect, stated in
# `MEMORY.md` as *"a route with no caller, a permission with no enforcement
# point and a table with no writer are one defect."* The mirror image is the
# same defect: a table with no READER.
#
# The schema was designed for this all along and was never used: `status`
# already CHECKs `new|approved|rejected`, `decided_by` already references
# `core.users`, `decided_at` already exists, and there is already an index on
# `(status, created_at DESC)`. Closing L1 therefore needs **no migration** — it
# needs the reader and the decision.
#
# ⚠️ THIS QUEUE IS PLATFORM-SCOPED, NOT TENANT-SCOPED, AND THAT IS A REAL
# LIMITATION RATHER THAN AN OVERSIGHT — RAISED AS I113.
#
# An access request names no organization: the applicant does not know which
# tenant they would be joining, so the row cannot carry an `organization_id`
# and the table has no RLS. The consequence is that in a multi-tenant
# deployment (M5 — this product is built multi-tenant) an administrator of
# organization A can read the name, work address and company of somebody who
# meant to apply to organization B. That is the applicant's own data rather
# than any tenant's, and every read is behind `admin.users`, but it is a
# genuine disclosure across a boundary this codebase otherwise enforces
# absolutely. It is named here rather than papered over, and the fix — an
# applicant-nominated organization, or a platform-operator role distinct from
# a tenant administrator — is a decision, not a cleanup.


class AccessRequestRead(BaseModel):
    """One queued request, as an administrator sees it."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    work_email: str
    company: str
    reason: str | None
    status: str
    created_at: dt.datetime
    decided_at: dt.datetime | None
    decided_by: uuid.UUID | None


class AccessRequestDecision(BaseModel):
    """Approve or reject one request.

    🔴 APPROVAL IS A BIND, NOT A REGISTRATION, AND THE PAYLOAD SAYS SO.

    The application cannot create credentials — Keycloak owns identity, and
    self-registration into a tenanted R&D system stays off (ADR-025, and the
    landing-page plan §5). So approving carries the `keycloak_sub` of an
    identity that already exists, exactly as `POST /api/admin/members` does,
    and the two go through the *same* `_bind_subject`.

    ⚠️ `roles` MUST NOT BE EMPTY ON AN APPROVAL. A membership with no role
    holds no permission, so approving into one would produce an account that
    can sign in and reach nothing — a "yes" that behaves like a "no", and the
    hardest kind of failure to notice. Refused at 422 rather than created.
    """

    decision: str = Field(pattern="^(approved|rejected)$")
    reason: str = Field(min_length=3, max_length=500)
    keycloak_sub: str | None = Field(default=None, min_length=1, max_length=255)
    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    roles: list[str] = Field(default_factory=list)


class AccessRequestDecisionResult(BaseModel):
    """What the decision actually did.

    `member_id` is present only on an approval, and it is the membership the
    bind produced — read back, not assumed. A decision that reported success
    without one would be the "three success messages over failed operations"
    failure recorded on 2026-08-31.
    """

    id: uuid.UUID
    status: str
    member_id: uuid.UUID | None = None


@router.get("/access-requests", response_model=list[AccessRequestRead], tags=["admin"])
def list_access_requests(
    status_filter: str = Query(
        default="new",
        alias="status",
        pattern="^(new|approved|rejected|all)$",
        description="Queue to read. Defaults to the undecided ones.",
    ),
    principal: Principal = Depends(require_permission("admin.users")),
    session: Session = Depends(get_db),
) -> list[AccessRequestRead]:
    """Read the access-request queue. `admin.users`.

    Bounded at 200 rows in SQL like every other collection on this API
    (`SECURITY.md` §10), newest first.
    """
    rows = session.execute(
        text(
            """
            SELECT id, full_name, work_email, company, reason, status,
                   created_at, decided_at, decided_by
              FROM public_intel.access_requests
             WHERE (:want = 'all' OR status = :want)
             ORDER BY created_at DESC
             LIMIT 200
            """
        ),
        {"want": status_filter},
    ).all()
    return [AccessRequestRead.model_validate(row) for row in rows]


@router.post(
    "/access-requests/{request_id}/decision",
    response_model=AccessRequestDecisionResult,
    tags=["admin"],
)
def decide_access_request(
    request_id: uuid.UUID,
    payload: AccessRequestDecision,
    principal: Principal = Depends(require_permission("admin.users")),
    session: Session = Depends(get_db),
) -> AccessRequestDecisionResult:
    """Decide one queued request. `admin.users`.

    🔴 `FOR UPDATE`, AND THE STATUS IS RE-READ INSIDE THE LOCK.

    Two administrators opening the same queue and approving the same row is
    the ordinary case, not the exotic one. Without the lock both would read
    `new`, both would bind, and the applicant would end up with two
    memberships — or one bind would hit `organization_members_unique` and
    surface as a 500. The row is locked, its status re-checked, and a request
    that is no longer `new` is refused with 409.

    The bind, the role grants, the status update and the audit event are ONE
    transaction. `session_scope` rolls the whole thing back on any refusal, so
    there is no state in which the queue says `approved` and no membership
    exists.
    """
    row = session.execute(
        text(
            """
            SELECT id, full_name, work_email, company, status
              FROM public_intel.access_requests
             WHERE id = :id
             FOR UPDATE
            """
        ),
        {"id": request_id},
    ).one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="no such access request",
        )
    if row.status != "new":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"this request was already {row.status}",
        )

    member_id: uuid.UUID | None = None

    if payload.decision == "approved":
        if not payload.keycloak_sub:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "approving binds an identity that already exists in "
                    "Keycloak, so keycloak_sub is required"
                ),
            )
        if not payload.roles:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="an approval must grant at least one role",
            )
        unknown = _unknown_roles(session, payload.roles)
        if unknown:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"unknown roles: {sorted(unknown)}",
            )

        # 🔴 THE SAME BIND AS `POST /api/admin/members`, NOT A SECOND ONE.
        # See `_bind_subject`'s docstring for why this is extracted rather
        # than copied.
        #
        # ⚠️ The address comes from the REQUEST ROW, not from the payload. An
        # administrator approving "somebody" must not be able to silently
        # redirect the approval to a different address than the one that was
        # submitted and reviewed — that would make the audit record describe a
        # decision nobody took. The display name may be corrected, because a
        # free-text name is a presentation detail; the address is the identity
        # the decision is about.
        member_id = _bind_subject(
            session,
            keycloak_sub=payload.keycloak_sub,
            email=row.work_email,
            display_name=payload.display_name or row.full_name,
        )
        for role_code in payload.roles:
            _grant_role(session, member_id, role_code)

    session.execute(
        text(
            """
            UPDATE public_intel.access_requests
               SET status = :status,
                   decided_by = :decided_by,
                   decided_at = clock_timestamp()
             WHERE id = :id
            """
        ),
        {
            "status": payload.decision,
            "decided_by": principal.user_id,
            "id": request_id,
        },
    )

    write_audit(
        session,
        AuditEvent(
            action=f"admin.access_request_{payload.decision}",
            entity_type="access_request",
            entity_id=str(request_id),
            organization_id=principal.organization_id,
            user_id=principal.user_id,
            previous_state={"status": "new"},
            new_state={
                "status": payload.decision,
                "member_id": str(member_id) if member_id else None,
                "roles": payload.roles if payload.decision == "approved" else [],
            },
            reason=payload.reason,
        ),
    )
    log_audit(
        "access_request_decided",
        request_id=str(request_id),
        decision=payload.decision,
    )

    return AccessRequestDecisionResult(
        id=request_id,
        status=payload.decision,
        member_id=member_id,
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
