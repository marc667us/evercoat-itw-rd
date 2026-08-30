"""The public surface: the global competitor marketplace and the news feed.

🔴 EVERY OTHER ROUTER IN THIS APPLICATION TAKES A PRINCIPAL. THIS ONE TAKES
   NOBODY, AND THAT IS NOT A FLAG -- IT IS A DIFFERENT CONNECTION.

The landing page answers before anyone signs in, so there is no principal to
check and no organization to scope to. The single mechanism keeping an
anonymous read away from tenant rows is the role at the other end of
``PUBLIC_DATABASE_URL``: migration 059 gives `evercoat_public` USAGE on nothing
but `public` and `public_intel`, SELECT on five published views, INSERT on one
queue, and no privilege on any tenant table. A query added here that reaches
for a tenant row fails; it does not read across tenants.

⚠️ WHY NOT `permit_anonymous` ON `/api/competitors`. Those routes require
`material.view`, derive the organization from the principal, and share a router
with writes, document access, samples, evidence and benchmarks. Making that
dependency optional would put an authentication-bypass seam on a connection
that can read everything, and would invite a fabricated default organization.
Codex refused to sign off on it and so do I.

🔴 THE VIEWS DECIDE WHAT IS PUBLIC, NOT THIS MODULE.

`publication_status = 'published'` lives in the view definitions, and internal
columns -- `generated_by`, `reviewed_by`, `verification_status` -- are
projected away there rather than filtered here. A reader learns that a row is
demonstration data and nothing about who reviewed it. If this module forgot a
filter, the view would still refuse; if the view were widened, migration 059's
probes would fail.

⚠️ MONEY GOES OUT AS A STRING. `price_amount` is NUMERIC, and FastAPI's encoder
maps `Decimal` to FLOAT -- which is exactly how `get_material` broke its own
client on 2026-08-29, twice, on two different code paths. `_public_row` is the
one place a row becomes a response, so there is no second path to forget.

⚠️ THE ACCESS REQUEST IS AN UNAUTHENTICATED WRITE AND THIS API HAS NO RATE
LIMITER. Stated rather than papered over: there is no rate-limiting mechanism
anywhere in this backend (the only mention is a comment recording its absence,
I18). The exposure is bounded -- the row grants nothing until a human acts, and
the queue cannot be read back on this connection -- and the source address is
recorded so abuse is attributable. Writing "rate-limited" here would assert a
control that does not exist.
"""

from __future__ import annotations

import datetime as dt
import ipaddress
import uuid
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.core.db import PublicConnectionNotConfiguredError, public_session_scope

router = APIRouter()

# Every NUMERIC that may reach a response. Kept as a set rather than checked by
# `isinstance` at the call site so a new numeric column is a one-line change in
# one place.
_QUANTITY_KEYS = frozenset({"price_amount", "relevance_score"})


def _public_row(row: Any) -> dict[str, Any]:
    """One row, as a response.

    🔴 THE ONLY PLACE A PUBLIC ROW BECOMES JSON.

    `Decimal` goes out as a string. FastAPI encodes `Decimal` as a float, which
    silently loses scale and fails a client that parses the field as a string.
    That defect shipped twice on 2026-08-29 -- once on a list path, once on a
    detail path that had been written by hand and went through neither helper.
    One function, so there is no second path.
    """
    out: dict[str, Any] = {}
    for key, value in dict(row._mapping).items():
        if value is not None and key in _QUANTITY_KEYS and isinstance(value, Decimal):
            out[key] = str(value)
        else:
            out[key] = value
    return out


def _client_ip(request: Request) -> str | None:
    """The caller's address, or nothing — never a value `inet` will reject.

    Deliberately does NOT read `X-Forwarded-For`. That header is caller-supplied
    and trusting it here would let the submitter choose what gets recorded
    against them, which is worse than recording nothing.
    """
    host = request.client.host if request.client else None
    if not host:
        return None
    try:
        return str(ipaddress.ip_address(host))
    except ValueError:
        return None


def _unavailable() -> HTTPException:
    """503, and never a fallback to the runtime pool.

    A public route that answered over `evercoat_app` because the public
    connection was missing would turn a configuration outage into an anonymous
    cross-tenant read. Refusing is the only correct answer.
    """
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="the public catalogue is not configured on this deployment",
    )


# ---------------------------------------------------------------------------
# Marketplace
# ---------------------------------------------------------------------------


@router.get("/products", summary="Browse the global competitor marketplace")
def list_products(
    q: str | None = Query(default=None, max_length=200),
    category: str | None = Query(default=None, max_length=120),
    manufacturer_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=48, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    """Published competitor products. No token, no organization, no principal."""
    try:
        with public_session_scope() as session:
            rows = session.execute(
                text(
                    """
                    SELECT id, manufacturer_id, manufacturer_name, product_name,
                           product_code, category, chemistry, region, description,
                           price_amount, price_currency, price_as_of,
                           price_source_url, content_origin,
                           is_demonstration_data, source_url
                      FROM public_intel.v_products
                     -- 🔴 EVERY OPTIONAL PARAMETER IS CAST EXPLICITLY.
                     -- `:q IS NULL` alone fails with "could not determine data
                     -- type of parameter $1": the server has no column to infer
                     -- the type from when the only other use is inside a
                     -- concatenation. Found by issuing a real request with no
                     -- filters -- the shape of call the landing page makes on
                     -- its first paint, and a 500 on every one of them.
                     WHERE (cast(:q AS text) IS NULL
                            OR product_name ILIKE '%' || cast(:q AS text) || '%'
                            OR manufacturer_name ILIKE '%' || cast(:q AS text) || '%'
                            OR coalesce(product_code, '') ILIKE '%' || cast(:q AS text) || '%')
                       AND (cast(:category AS text) IS NULL
                            OR category = cast(:category AS text))
                       AND (cast(:manufacturer_id AS uuid) IS NULL
                            OR manufacturer_id = cast(:manufacturer_id AS uuid))
                     ORDER BY manufacturer_name, product_name
                     LIMIT :limit OFFSET :offset
                    """
                ),
                {
                    "q": q,
                    "category": category,
                    "manufacturer_id": manufacturer_id,
                    "limit": limit,
                    "offset": offset,
                },
            ).all()
            total = session.execute(
                text("SELECT count(*) FROM public_intel.v_products")
            ).scalar_one()
    except PublicConnectionNotConfiguredError as exc:
        raise _unavailable() from exc
    return {"products": [_public_row(r) for r in rows], "total": total}


@router.get("/products/{product_id}", summary="One competitor product")
def get_product(product_id: uuid.UUID) -> dict[str, Any]:
    try:
        with public_session_scope() as session:
            row = session.execute(
                text(
                    """
                    SELECT id, manufacturer_id, manufacturer_name, product_name,
                           product_code, category, chemistry, region, description,
                           price_amount, price_currency, price_as_of,
                           price_source_url, content_origin,
                           is_demonstration_data, source_url
                      FROM public_intel.v_products WHERE id = :id
                    """
                ),
                {"id": product_id},
            ).one_or_none()
            if row is None:
                # A draft and a nonexistent product are the same answer here.
                # Distinguishing them would let an anonymous caller enumerate
                # unpublished rows by their identifiers.
                raise HTTPException(status_code=404, detail="not found")
            documents = session.execute(
                text(
                    """
                    SELECT id, document_kind, title, url, content_origin,
                           is_demonstration_data
                      FROM public_intel.v_product_documents
                     WHERE product_id = :id
                     ORDER BY document_kind, title
                    """
                ),
                {"id": product_id},
            ).all()
            news = session.execute(
                text(
                    """
                    SELECT id, headline, summary, summary_is_ai_generated,
                           source_url, published_at, category_slug,
                           category_label, source_name, source_tier,
                           content_origin, is_demonstration_data
                      FROM public_intel.v_news_items
                     WHERE product_id = :id
                     ORDER BY published_at DESC NULLS LAST
                     LIMIT 20
                    """
                ),
                {"id": product_id},
            ).all()
    except PublicConnectionNotConfiguredError as exc:
        raise _unavailable() from exc

    product = _public_row(row)
    product["documents"] = [_public_row(d) for d in documents]
    # The spec's "News & Developments" tab. It is real rather than promised
    # because `news_items` carries a nullable FK to a PUBLIC product -- there is
    # deliberately no FK to any tenant table, which would make an anonymous read
    # a tenant read.
    product["news"] = [_public_row(n) for n in news]
    return product


# ---------------------------------------------------------------------------
# Industry news feed
# ---------------------------------------------------------------------------


@router.get("/news/categories", summary="The feed's controlled categories")
def list_news_categories() -> dict[str, Any]:
    try:
        with public_session_scope() as session:
            rows = session.execute(
                text(
                    "SELECT id, slug, label, sort_order "
                    "FROM public_intel.v_news_categories ORDER BY sort_order, label"
                )
            ).all()
    except PublicConnectionNotConfiguredError as exc:
        raise _unavailable() from exc
    return {"categories": [_public_row(r) for r in rows]}


@router.get("/news", summary="The Global Competitor Industry News Feed")
def list_news(
    category: str | None = Query(default=None, max_length=80),
    manufacturer_id: uuid.UUID | None = Query(default=None),
    region: str | None = Query(default=None, max_length=80),
    limit: int = Query(default=24, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    try:
        with public_session_scope() as session:
            rows = session.execute(
                text(
                    """
                    SELECT id, headline, summary, summary_is_ai_generated,
                           source_url, published_at, region, country,
                           manufacturer_id, product_id, category_slug,
                           category_label, source_name, source_type,
                           source_tier, content_origin, is_demonstration_data
                      FROM public_intel.v_news_items
                     -- Cast for the same reason as `list_products`.
                     WHERE (cast(:category AS text) IS NULL
                            OR category_slug = cast(:category AS text))
                       AND (cast(:manufacturer_id AS uuid) IS NULL
                            OR manufacturer_id = cast(:manufacturer_id AS uuid))
                       AND (cast(:region AS text) IS NULL
                            OR region = cast(:region AS text))
                     ORDER BY published_at DESC NULLS LAST
                     LIMIT :limit OFFSET :offset
                    """
                ),
                {
                    "category": category,
                    "manufacturer_id": manufacturer_id,
                    "region": region,
                    "limit": limit,
                    "offset": offset,
                },
            ).all()
    except PublicConnectionNotConfiguredError as exc:
        raise _unavailable() from exc
    return {"items": [_public_row(r) for r in rows]}


@router.get("/manufacturers", summary="Competitor manufacturers")
def list_manufacturers() -> dict[str, Any]:
    try:
        with public_session_scope() as session:
            rows = session.execute(
                text(
                    "SELECT id, name, country, website_url, content_origin, "
                    "is_demonstration_data FROM public_intel.v_manufacturers "
                    "ORDER BY name"
                )
            ).all()
    except PublicConnectionNotConfiguredError as exc:
        raise _unavailable() from exc
    return {"manufacturers": [_public_row(r) for r in rows]}


# ---------------------------------------------------------------------------
# Access request — "Sign Up" is a REQUEST, not an account
# ---------------------------------------------------------------------------


class AccessRequestIn(BaseModel):
    """What the landing page's Sign Up collects.

    🔴 IT CREATES NO IDENTITY AND NO MEMBERSHIP. Keycloak self-registration is
    off and stays off: registration into a tenanted R&D system needs an
    approval path, not an open form. An administrator holding `admin.users`
    reads this queue and uses the existing bind route to create and bind the
    identity to a chosen organization with a least-privilege role.
    """

    full_name: str = Field(min_length=1, max_length=200)
    work_email: str = Field(min_length=3, max_length=320)
    company: str = Field(min_length=1, max_length=200)
    reason: str | None = Field(default=None, max_length=2000)


@router.post(
    "/access-requests",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Request access to the R&D environment",
)
def create_access_request(payload: AccessRequestIn, request: Request) -> dict[str, Any]:
    """Queue a request for a human to decide on.

    202, not 201: nothing has been created that the caller may look at. The
    response deliberately carries no identifier -- `evercoat_public` holds
    INSERT and not SELECT on this table, so there is nothing to fetch, and
    returning a key would invite an enumeration attempt that would only ever
    return 403.
    """
    # 🔴 `request.client.host` IS NOT NECESSARILY AN IP ADDRESS, and `inet`
    # rejects anything that is not one -- which surfaced as a 500 on every
    # submission the moment the route was actually called. It is whatever the
    # ASGI server put in the scope: a hostname behind some proxies, and the
    # literal string "testclient" under Starlette's test client.
    #
    # An unparseable address must not cost the caller their request. The
    # address is here to make abuse attributable, not to gate anything, so a
    # value that is not an address is simply not recorded.
    client_host = _client_ip(request)
    user_agent = request.headers.get("user-agent")
    try:
        with public_session_scope() as session:
            session.execute(
                text(
                    """
                    INSERT INTO public_intel.access_requests
                        (full_name, work_email, company, reason,
                         source_ip, user_agent)
                    VALUES (:full_name, :work_email, :company, :reason,
                            cast(:source_ip AS inet), :user_agent)
                    """
                ),
                {
                    "full_name": payload.full_name.strip(),
                    "work_email": payload.work_email.strip(),
                    "company": payload.company.strip(),
                    "reason": payload.reason,
                    "source_ip": client_host,
                    "user_agent": (user_agent or "")[:500] or None,
                },
            )
    except PublicConnectionNotConfiguredError as exc:
        raise _unavailable() from exc
    return {
        "status": "received",
        "message": (
            "Your request has been queued for review. Access to the R&D "
            "environment is granted by an administrator, not automatically."
        ),
        "received_at": dt.datetime.now(dt.UTC).isoformat(),
    }
