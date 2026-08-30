"""Curating the public competitor catalogue — as drafts, never as fact.

The owner's instruction: "the global competitor product marketplace must be
managed by agents". These are the tools that management is made of.

🔴 EVERY WRITE HERE IS A DRAFT, AND THAT IS NOT ENFORCED HERE.

Nothing in this module is what stops an agent publishing. These functions
write `publication_status='draft'` because that is what they are for, but a
check in Python is a MISUSE BARRIER: it stops the tool being used wrongly by
somebody reading the code, and stops nothing if a different path writes the
same row.

What stops it is migration 060: a trigger on `public_intel` that refuses any
non-draft write from `evercoat_agent`, keyed on `session_user`, which nothing
but the connection decides. So these functions must run on
`agent_session_scope()`, and `tests/test_agent_pool_boundary.py` asserts they
do — because a boundary on a path nothing takes is decoration.

🔴 AND THEY MAY NOT RECORD A REVIEW. `reviewed_by`/`reviewed_at` is what the
publication invariant reads before it will accept a `verified` row. An agent
able to set it could manufacture the evidence for its own publication. 060
refuses that too.

⚠️ WHAT THIS TIER IS ALLOWED TO CLAIM. A row it writes carries
`content_origin='source_derived'` and a `source_url`, or `'synthetic'`. It can
never write `'verified'`: verification requires a human, by rule 4, and the
publication invariant will not accept a verified row without a named reviewer
that only a human can be.

⚠️ THESE ARE PLAIN FUNCTIONS. No LangGraph import, per the framework-leak rule
— the graph layer lives in `app/agents/graphs/` and nothing here knows it
exists. `test_no_orchestration_framework_leaks_outside_graphs` enforces it.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.orm import Session

__all__ = [
    "DraftedNews",
    "DraftedProduct",
    "draft_manufacturer",
    "draft_news_item",
    "draft_product",
    "review_queue",
]


@dataclass(frozen=True, slots=True)
class DraftedProduct:
    """What was proposed, and on whose authority — which is nobody's yet."""

    product_id: uuid.UUID
    manufacturer_id: uuid.UUID
    product_name: str
    publication_status: str


@dataclass(frozen=True, slots=True)
class DraftedNews:
    news_id: uuid.UUID
    headline: str
    publication_status: str


def _origin_for(source_url: str | None) -> str:
    """A claim with a source is source-derived; one without is synthetic.

    🔴 NOT A PARAMETER. If the caller chose the origin, an agent could label
    invented content `source_derived` and the label would mean nothing. It is
    derived from whether a source actually exists, so the two cannot disagree.
    `'verified'` is unreachable from here by construction.
    """
    return "source_derived" if source_url else "synthetic"


def draft_manufacturer(
    session: Session,
    *,
    name: str,
    country: str | None = None,
    website_url: str | None = None,
    source_url: str | None = None,
    generated_by: str,
) -> uuid.UUID:
    """Propose a manufacturer. Returns the existing row if it is already known.

    Idempotent on name because an agent re-reading the same source must not
    mint a second record for the same company — and `manufacturers_name_key`
    would refuse it anyway, turning a re-run into a crash.
    """
    existing = session.execute(
        text("SELECT id FROM public_intel.manufacturers WHERE name = :n"),
        {"n": name},
    ).one_or_none()
    if existing is not None:
        return uuid.UUID(str(existing.id))

    row = session.execute(
        text(
            """
            INSERT INTO public_intel.manufacturers
                (name, country, website_url, content_origin, source_url,
                 generated_by, generated_at, publication_status)
            VALUES (:n, :c, :w, cast(:origin AS public_intel.content_origin),
                    :src, :by, clock_timestamp(), 'draft')
            RETURNING id
            """
        ),
        {
            "n": name,
            "c": country,
            "w": website_url,
            "origin": _origin_for(source_url),
            "src": source_url,
            "by": generated_by,
        },
    ).one()
    return uuid.UUID(str(row.id))


def draft_product(
    session: Session,
    *,
    manufacturer_id: uuid.UUID,
    product_name: str,
    category: str | None = None,
    chemistry: str | None = None,
    region: str | None = None,
    description: str | None = None,
    price_amount: Decimal | None = None,
    price_currency: str | None = None,
    price_as_of: str | None = None,
    price_source_url: str | None = None,
    source_url: str | None = None,
    generated_by: str,
) -> DraftedProduct:
    """Propose a competitor product.

    ⚠️ A PRICE IS A CLAIM AND IS REFUSED WITHOUT ITS CONTEXT. The database
    CHECK requires a currency and an as-of date beside an amount; this raises
    before the statement so the caller gets a sentence rather than a
    constraint name. Both exist on purpose — the CHECK is the boundary, this
    is the message.
    """
    if price_amount is not None and (price_currency is None or price_as_of is None):
        raise ValueError(
            "a price needs a currency and an as-of date: an amount with "
            "neither is a number with no meaning, and this catalogue is public"
        )

    row = session.execute(
        text(
            """
            INSERT INTO public_intel.products
                (manufacturer_id, product_name, category, chemistry, region,
                 description, price_amount, price_currency, price_as_of,
                 price_source_url, content_origin, source_url, generated_by,
                 generated_at, publication_status)
            VALUES (:m, :n, :cat, :chem, :r, :d, :price, :cur,
                    cast(:asof AS date), :psrc,
                    cast(:origin AS public_intel.content_origin), :src, :by,
                    clock_timestamp(), 'draft')
            RETURNING id, publication_status
            """
        ),
        {
            "m": str(manufacturer_id),
            "n": product_name,
            "cat": category,
            "chem": chemistry,
            "r": region,
            "d": description,
            "price": price_amount,
            "cur": price_currency,
            "asof": price_as_of,
            "psrc": price_source_url,
            "origin": _origin_for(source_url),
            "src": source_url,
            "by": generated_by,
        },
    ).one()
    return DraftedProduct(
        product_id=uuid.UUID(str(row.id)),
        manufacturer_id=manufacturer_id,
        product_name=product_name,
        publication_status=row.publication_status,
    )


def draft_news_item(
    session: Session,
    *,
    source_id: uuid.UUID,
    category_id: uuid.UUID,
    headline: str,
    source_url: str,
    summary: str | None = None,
    summary_is_ai_generated: bool = True,
    published_at: str | None = None,
    region: str | None = None,
    manufacturer_id: uuid.UUID | None = None,
    product_id: uuid.UUID | None = None,
    generated_by: str,
) -> DraftedNews:
    """Propose a news item.

    ⚠️ `source_url` IS REQUIRED, AND NOT BY ACCIDENT. The specification is
    explicit that a summary must never replace the original article, and a
    news record with no way back to its source is a summary standing alone.
    The column is NOT NULL for the same reason.

    ⚠️ `summary_is_ai_generated` DEFAULTS TRUE. If this tier wrote the summary,
    it is AI-generated; a default of False would let an omission quietly
    present a generated sentence as an editor's.
    """
    if not source_url:
        raise ValueError(
            "a news item needs its source: a summary with no link back to the "
            "article it summarises becomes the record"
        )

    row = session.execute(
        text(
            """
            INSERT INTO public_intel.news_items
                (source_id, category_id, headline, summary,
                 summary_is_ai_generated, source_url,
                 published_at, region, manufacturer_id, product_id,
                 content_origin, generated_by, generated_at,
                 publication_status)
            VALUES (:s, :c, :h, :sum, :ai, :u,
                    cast(:pub AS timestamptz), :r, :m, :p,
                    'source_derived', :by, clock_timestamp(), 'draft')
            RETURNING id, publication_status
            """
        ),
        {
            "s": str(source_id),
            "c": str(category_id),
            "h": headline,
            "sum": summary,
            "ai": summary_is_ai_generated,
            "u": source_url,
            "pub": published_at,
            "r": region,
            "m": str(manufacturer_id) if manufacturer_id else None,
            "p": str(product_id) if product_id else None,
            "by": generated_by,
        },
    ).one()
    return DraftedNews(
        news_id=uuid.UUID(str(row.id)),
        headline=headline,
        publication_status=row.publication_status,
    )


def review_queue(session: Session, *, limit: int = 50) -> list[dict[str, object]]:
    """What the agent tier has proposed and nobody has decided on.

    This is the whole point of drafting: the queue is the handover to a human.
    A tier that proposed into a queue nobody could read would be a tier whose
    output never reached anyone.
    """
    rows = session.execute(
        text(
            """
            SELECT 'product' AS kind, p.id, p.product_name AS title,
                   m.name AS manufacturer, p.generated_by, p.generated_at,
                   p.content_origin::text AS content_origin, p.source_url
              FROM public_intel.products p
              JOIN public_intel.manufacturers m ON m.id = p.manufacturer_id
             WHERE p.publication_status = 'draft'
            UNION ALL
            SELECT 'news', n.id, n.headline, NULL, n.generated_by,
                   n.generated_at, n.content_origin::text, n.source_url
              FROM public_intel.news_items n
             WHERE n.publication_status = 'draft'
             ORDER BY generated_at DESC NULLS LAST
             LIMIT :limit
            """
        ),
        {"limit": limit},
    ).all()
    return [dict(row._mapping) for row in rows]
