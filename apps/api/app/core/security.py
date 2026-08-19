"""Authentication and authorization.

Implements the chain from CLAUDE.md §6, enforced in this order on every
request:

    Authentication -> Organization -> Role -> Permission
                   -> Resource Scope -> Business Rule

with PostgreSQL RLS as an independent database-layer backstop.

Two rules govern everything here.

**Authorize on permissions, never on role names.** A role is a seeded
bundle. Checking ``role == "qa_compliance_officer"`` cannot express "QA
approval may not come from someone who supplied a development-side
approval on this same test" (ADR-019), and it hard-codes a deployment's
staffing into the application. Permissions are data; roles are defaults.

**Resource scope is a separate check from permission.** Holding
``test.review`` does not grant review of a test in a project you are not
a member of. These are different questions and conflating them is how
intra-organization confidentiality gets lost -- the defect that made the
original three-layer claim false (Codex F32).

Frontend permission checks are cosmetic. Everything is re-enforced here.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any

import httpx
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import RequestContext, session_scope

__all__ = [
    "PermissionDenied",
    "Principal",
    "get_db",
    "get_principal",
    "require_permission",
    "require_project_member",
]

_bearer = HTTPBearer(auto_error=False)


class PermissionDenied(HTTPException):
    """403 with a stable shape.

    The detail deliberately does not say whether the resource exists.
    "You may not see it" and "it does not exist" must be indistinguishable
    to the caller, or the error message itself becomes a discovery channel
    for other teams' project codes.
    """

    def __init__(self, detail: str = "Not permitted") -> None:
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


@dataclass(frozen=True, slots=True)
class Principal:
    """The verified caller.

    Every field here comes from a signature-verified JWT or from the
    database. Nothing is taken from a header, query parameter or request
    body -- a client-supplied organization id would make the entire
    tenancy model advisory.
    """

    user_id: uuid.UUID
    organization_id: uuid.UUID
    keycloak_sub: str
    email: str
    display_name: str
    roles: frozenset[str] = field(default_factory=frozenset)
    permissions: frozenset[str] = field(default_factory=frozenset)
    session_id: str | None = None

    @property
    def context(self) -> RequestContext:
        return RequestContext(organization_id=self.organization_id, user_id=self.user_id)

    def has(self, permission: str) -> bool:
        return permission in self.permissions


# ---------------------------------------------------------------------------
# JWKS
# ---------------------------------------------------------------------------

_jwks_cache: dict[str, Any] = {}
_jwks_fetched_at: float = 0.0


async def _get_jwks() -> dict[str, Any]:
    """Fetch and cache the realm's signing keys.

    The cache is bounded by ``jwks_cache_seconds`` because that window is
    how long a rotated-out signing key stays trusted. On a fetch failure
    we keep serving the previous keys rather than failing every request --
    a Keycloak blip should not take the API down -- but we never extend
    the window silently past a successful refresh.
    """
    global _jwks_cache, _jwks_fetched_at

    age = time.monotonic() - _jwks_fetched_at
    if _jwks_cache and age < settings.jwks_cache_seconds:
        return _jwks_cache

    url = f"{settings.keycloak_issuer.rstrip('/')}/protocol/openid-connect/certs"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            _jwks_cache = response.json()
            _jwks_fetched_at = time.monotonic()
    except Exception:  # noqa: BLE001
        if not _jwks_cache:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="identity provider unavailable",
            ) from None
        # Stale keys beat no service; the next request retries.
    return _jwks_cache


async def _decode(token: str) -> dict[str, Any]:
    """Verify signature, issuer, audience and expiry. All four."""
    jwks = await _get_jwks()
    try:
        # cast: python-jose is untyped, so decode() is Any. The claims are
        # validated by the options below, not by the type system.
        decoded: dict[str, Any] = jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            audience=settings.keycloak_audience,
            issuer=settings.keycloak_issuer,
            options={
                "verify_signature": True,
                "verify_aud": True,
                "verify_iss": True,
                "verify_exp": True,
            },
        )
        return decoded
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


# ---------------------------------------------------------------------------
# Principal resolution
# ---------------------------------------------------------------------------

_PRINCIPAL_SQL = text(
    """
    SELECT u.id                AS user_id,
           u.email             AS email,
           u.display_name      AS display_name,
           om.organization_id  AS organization_id,
           COALESCE(array_agg(DISTINCT r.code)
                    FILTER (WHERE r.code IS NOT NULL), '{}') AS roles,
           COALESCE(array_agg(DISTINCT p.code)
                    FILTER (WHERE p.code IS NOT NULL), '{}') AS permissions
    FROM core.users u
    JOIN core.organization_members om
      ON om.user_id = u.id AND om.status = 'active'
    LEFT JOIN core.member_roles mr   ON mr.member_id = om.id
    LEFT JOIN core.roles r           ON r.id = mr.role_id
    LEFT JOIN core.role_permissions rp ON rp.role_id = r.id
    LEFT JOIN core.permissions p     ON p.id = rp.permission_id
    WHERE u.keycloak_sub = :sub
      AND u.status = 'active'
      AND om.organization_id = :org_id
    GROUP BY u.id, u.email, u.display_name, om.organization_id
    """
)


async def get_verified_subject(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    """The token's subject, with no organization required.

    🔴 THIS IS THE ONLY AUTHENTICATED ENTRY POINT THAT DOES NOT DEMAND A
    TENANT, AND IT EXISTS FOR EXACTLY ONE ROUTE.

    ``get_principal`` requires ``X-Organization-Id``, correctly -- picking
    a default tenant for a user who belongs to several writes records into
    whichever one happened to sort first. But every authenticated route
    depends on it, so a browser that had just signed in held a valid token
    and no way to discover a tenant to ask for. Authentication completed
    and the application was still unusable. ``GET /api/me`` closes that,
    and needs identity before tenancy to do it.

    The verification is identical to ``get_principal``'s -- the same
    ``_decode``, so signature, issuer, audience and expiry are all checked.
    What is deliberately absent is the ORGANIZATION step, and nothing else.

    It returns a bare ``str`` rather than a ``Principal`` on purpose: a
    Principal without an organization would be a Principal that could be
    passed to something expecting one, and ``Principal.context`` would then
    be constructed from a tenant nobody chose. There is no such object, so
    there is no such mistake to make.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    claims = await _decode(credentials.credentials)
    sub = claims.get("sub")
    if not isinstance(sub, str) or not sub:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="token has no subject")
    return sub


async def get_principal(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> Principal:
    """Resolve the caller, or refuse.

    Membership and permissions are read from the database rather than
    trusted from the token's claims. A JWT is a statement about identity;
    it is not a current statement about authorization. Revoking a
    membership must take effect immediately, not when the access token
    happens to expire.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    claims = await _decode(credentials.credentials)

    sub = claims.get("sub")
    if not sub:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="token has no subject")

    # Organization selection. A user may belong to several; the active one
    # comes from a header, but it is a *request* to use that organization,
    # validated against real membership below -- never taken on trust.
    requested_org = request.headers.get("X-Organization-Id")
    if not requested_org:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Organization-Id header is required",
        )
    try:
        org_id = uuid.UUID(requested_org)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Organization-Id is not a valid UUID",
        ) from None

    # Resolving the principal is itself a context-free read -- we cannot
    # set the RLS GUCs until we know who the caller is. It is confined to
    # core.users / core.organization_members and returns nothing from any
    # project-scoped table, which is why this is a safe exception to the
    # session_scope() rule.
    from app.core.db import unscoped_session_scope

    with unscoped_session_scope() as session:
        row = (
            session.execute(_PRINCIPAL_SQL, {"sub": sub, "org_id": org_id}).mappings().one_or_none()
        )

    if row is None:
        # Not a member of the requested organization -- or no such
        # organization. Deliberately the same answer for both.
        raise PermissionDenied("not a member of the requested organization")

    return Principal(
        user_id=row["user_id"],
        organization_id=row["organization_id"],
        keycloak_sub=sub,
        email=row["email"],
        display_name=row["display_name"],
        roles=frozenset(row["roles"]),
        permissions=frozenset(row["permissions"]),
        session_id=claims.get("sid"),
    )


def get_db(principal: Principal = Depends(get_principal)) -> Iterator[Session]:
    """Yield a session with the caller's RLS context applied.

    This is the only supported route to the database in request handling.
    Because it depends on ``get_principal``, there is no way to obtain a
    session without first having been authenticated and having proven
    organization membership.
    """
    with session_scope(principal.context) as session:
        yield session


# ---------------------------------------------------------------------------
# Authorization dependencies
# ---------------------------------------------------------------------------


def require_permission(*permissions: str, require_all: bool = False) -> Callable[..., Principal]:
    """Dependency factory: assert the caller holds the permission(s).

    Args:
        permissions: permission codes, e.g. ``"formula.approve_lab"``.
        require_all: if True the caller needs every one; default is any.
    """

    def _check(principal: Principal = Depends(get_principal)) -> Principal:
        held = principal.permissions
        ok = (
            all(p in held for p in permissions)
            if require_all
            else any(p in held for p in permissions)
        )
        if not ok:
            raise PermissionDenied()
        return principal

    return _check


def require_project_member(
    project_id_param: str = "project_id",
) -> Callable[..., Principal]:
    """Dependency factory: assert membership of the project in the path.

    Separate from :func:`require_permission` on purpose. Permission asks
    "may this person ever do this?"; scope asks "may they do it *here*?"
    Both must pass, and RLS independently enforces the same answer at the
    database layer, so a mistake in either one is caught by the other.
    """

    def _check(
        request: Request,
        principal: Principal = Depends(get_principal),
        session: Session = Depends(get_db),
    ) -> Principal:
        raw = request.path_params.get(project_id_param)
        if raw is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"route has no path parameter '{project_id_param}'",
            )
        try:
            project_id = uuid.UUID(str(raw))
        except ValueError:
            raise PermissionDenied() from None

        # core.is_project_member() is the single definition of membership,
        # shared with every RLS policy. Asking the database rather than
        # reimplementing the predicate is what stops the rule drifting
        # between the API and the policies.
        is_member = session.execute(
            text("SELECT core.is_project_member(:pid)"), {"pid": project_id}
        ).scalar_one()

        if not is_member:
            raise PermissionDenied()
        return principal

    return _check
