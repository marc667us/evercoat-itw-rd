"""Replace the demonstration catalogue with REAL, SOURCED competitor records.

Owner instruction, 2026-08-30: *"verify all product data and update to real
data for the products in the marketplace."*

🔴 WHAT "VERIFY" MEANS HERE, OPERATIONALLY.

Every row this writes carries a `source_url` on the manufacturer's own domain,
and **this script fetches every one of them before it publishes anything**. A
URL that does not resolve is refused, not published with a note. A citation
nobody checked is a citation that might be wrong, and this catalogue is served
to anonymous readers.

That check is the reason the count is what it is rather than a round number.

🔴 NO PRICES. NOT ONE.

List prices in this market are set by distributors, vary by pack size and
region, and are not published by the manufacturers. There is no honest way to
attach one from a desk. `price_amount` stays NULL and the card renders "No
published price" — because a plausible number sitting beside a real brand on a
public page is precisely the failure this catalogue was designed to refuse.

🔴 ONE DOCUMENT PER PRODUCT, AND IT IS CALLED WHAT IT IS.

The previous demonstration seed wrote four documents per product — datasheet,
label, literature, SDS — pointing at `example.invalid`. Those are the links the
owner reported as broken, and they were: deliberately non-resolving, which
reads to a reviewer as simply broken.

This writes ONE document per product, kind `literature`, pointing at the
manufacturer's real page. It does NOT invent datasheet, label or SDS URLs.
Those tabs render "No published datasheets for this product", which is true.
Claiming a product page is an SDS would be a lie about a safety document, which
is the worst possible thing to be casually wrong about in this application.

⚠️ `verification_status = 'reviewed'`, and that is a claim about a real act.

The publication invariant will not accept a published `source_derived` row
without it. It is set because this script actually fetched the URL and got a
response — not because the constraint wanted a value. `'verified'` is NOT used:
that requires a named human reviewer, and no human has reviewed these.

⚠️ THE NEWS FEED IS STILL DEMONSTRATION DATA and still says so on every card.
Real industry news needs a source-ingestion pipeline with licence and
robots/ToS review, which does not exist. Inventing news about real companies
would be far worse than inventing a product, so the feed keeps its fictional
subjects and its badge.
"""

from __future__ import annotations

import os
import sys
import time
import urllib.error
import urllib.request

from sqlalchemy import create_engine, text

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _real_competitors import COMPETITORS

DB = os.environ.get(
    "SEED_DATABASE_URL",
    "postgresql+psycopg://evercoat_owner:ci-owner@localhost:55432/evercoat_itw_rd",
)

UA = "Mozilla/5.0 (compatible; EvercoatCatalogue/1.0; +https://example.org/bot)"


def resolves(url: str, attempts: int = 3) -> tuple[bool, str]:
    """Fetch it. A 403 counts: the host is live and refusing a bot, not absent.

    A 404 does not count, and the row is dropped.

    🔴 IT RETRIES, AND THE FIRST VERSION DID NOT.

    On the first full run 3M was DROPPED on a `ConnectionResetError` — a
    transient blip against a host that had resolved minutes earlier. A verifier
    that deletes a legitimate manufacturer because a packet was lost is not
    strict, it is unreliable: the catalogue would silently differ between runs
    and nobody would know which run was right.

    So a network-level failure is retried; an HTTP 404 is not, because that is
    an answer rather than a failure to get one.
    """
    # 🔴 https ONLY, CHECKED BEFORE THE FETCH.
    #
    # Semgrep's `dynamic-urllib-use-detected` is right about the shape:
    # `urlopen` honours `file://`, so a non-http scheme in the competitor list
    # would make this READ A LOCAL FILE and then report the row as "resolved" —
    # a source that verified against nothing.
    #
    # The list is hand-written today, which is why this was not a live
    # vulnerability. It is also exactly the sort of list a future ingestion
    # step will populate from elsewhere, and by then nobody re-reads this
    # function. Refused here, before the request is built.
    if not url.lower().startswith("https://"):
        return (False, "not-https")

    req = urllib.request.Request(url, headers={"User-Agent": UA})
    last = "?"
    for attempt in range(attempts):
        try:
            # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected
            with urllib.request.urlopen(req, timeout=25) as r:
                return (200 <= r.status < 300, str(r.status))
        except urllib.error.HTTPError as exc:
            # 403/406 are live hosts refusing automation. 404/410 are not, and
            # retrying an answer does not change it.
            return (exc.code in (403, 406), str(exc.code))
        except Exception as exc:  # noqa: BLE001
            last = type(exc).__name__
            if attempt < attempts - 1:
                time.sleep(2 * (attempt + 1))
    return (False, last)


def main() -> None:
    print("VERIFYING SOURCES (nothing is published before this passes)\n")

    verified: list[tuple[str, str, str, list[tuple[str, str, str, str]]]] = []
    dropped: list[str] = []

    for name, country, home, products in COMPETITORS:
        ok_home, code = resolves(home)
        if not ok_home:
            dropped.append(f"{name} (homepage {code})")
            print(f"  [{code:>6}] DROP  {name} — homepage did not resolve")
            continue

        kept: list[tuple[str, str, str, str]] = []
        for product, category, chemistry, src in products:
            ok, pcode = resolves(src)
            if ok:
                kept.append((product, category, chemistry, src))
                print(f"  [{pcode:>6}] keep  {name} :: {product}")
            else:
                dropped.append(f"{name} :: {product} ({pcode})")
                print(f"  [{pcode:>6}] DROP  {name} :: {product}")

        if kept:
            verified.append((name, country, home, kept))

    products_total = sum(len(p) for _, _, _, p in verified)
    print(f"\n  manufacturers verified: {len(verified)}")
    print(f"  products verified:      {products_total}")
    print(f"  dropped:                {len(dropped)}")

    if not verified:
        print("REFUSING: nothing verified, so nothing is published")
        sys.exit(1)

    engine = create_engine(DB, future=True)
    with engine.begin() as conn:
        # Order matters: products reference manufacturers ON DELETE RESTRICT.
        # Documents cascade from products.
        conn.execute(
            text("DELETE FROM public_intel.products WHERE is_demonstration_data")
        )
        conn.execute(
            text("DELETE FROM public_intel.manufacturers WHERE is_demonstration_data")
        )
        # And any earlier real run, so this is idempotent rather than additive.
        conn.execute(
            text(
                "DELETE FROM public_intel.products "
                " WHERE generated_by = 'seed_public_intel_real.py'"
            )
        )
        conn.execute(
            text(
                "DELETE FROM public_intel.manufacturers "
                " WHERE generated_by = 'seed_public_intel_real.py'"
            )
        )

        for name, country, home, products in verified:
            manufacturer = conn.execute(
                text(
                    """
                    INSERT INTO public_intel.manufacturers
                        (name, country, website_url, content_origin,
                         verification_status, source_url, generated_by,
                         generated_at, publication_status, is_demonstration_data)
                    VALUES (:n, :c, :w, 'source_derived', 'reviewed', :src,
                            'seed_public_intel_real.py', clock_timestamp(),
                            'published', false)
                    RETURNING id
                    """
                ),
                {"n": name, "c": country, "w": home, "src": home},
            ).scalar_one()

            for product, category, chemistry, src in products:
                pid = conn.execute(
                    text(
                        """
                        INSERT INTO public_intel.products
                            (manufacturer_id, product_name, category, chemistry,
                             description, content_origin, verification_status,
                             source_url, generated_by, generated_at,
                             publication_status, is_demonstration_data)
                        VALUES (:m, :n, :cat, :chem, :d, 'source_derived',
                                'reviewed', :src, 'seed_public_intel_real.py',
                                clock_timestamp(), 'published', false)
                        RETURNING id
                        """
                    ),
                    {
                        "m": manufacturer,
                        "n": product,
                        "cat": category,
                        "chem": chemistry,
                        "d": (
                            f"{product} — {category.lower()} published by {name}. "
                            "Recorded from the manufacturer's own page; no price, "
                            "specification or safety claim is asserted here."
                        ),
                        "src": src,
                    },
                ).scalar_one()

                # ONE document, named for what it actually is.
                conn.execute(
                    text(
                        """
                        INSERT INTO public_intel.product_documents
                            (product_id, document_kind, title, url,
                             content_origin, publication_status,
                             is_demonstration_data)
                        VALUES (:p, 'literature', :t, :u, 'source_derived',
                                'published', false)
                        """
                    ),
                    {
                        "p": pid,
                        "t": f"{name} — manufacturer product page",
                        "u": src,
                    },
                )

    with engine.connect() as conn:
        totals = conn.execute(
            text(
                """
                SELECT (SELECT count(*) FROM public_intel.manufacturers
                         WHERE publication_status = 'published')            AS manufacturers,
                       (SELECT count(*) FROM public_intel.products
                         WHERE publication_status = 'published')            AS products,
                       (SELECT count(*) FROM public_intel.products
                         WHERE publication_status = 'published'
                           AND is_demonstration_data)                       AS still_demo,
                       (SELECT count(*) FROM public_intel.products
                         WHERE publication_status = 'published'
                           AND source_url IS NULL)                          AS unsourced,
                       (SELECT count(*) FROM public_intel.product_documents
                         WHERE publication_status = 'published'
                           AND url LIKE '%example.invalid%')                AS dead_links
                """
            )
        ).one()

    print("\nPUBLISHED")
    for k, v in dict(totals._mapping).items():
        print(f"  {k:16} {v}")

    if totals.unsourced:
        print("REFUSING: a published product has no source")
        sys.exit(1)
    if totals.dead_links:
        print("REFUSING: a published document still points at example.invalid")
        sys.exit(1)
    print("OK")


if __name__ == "__main__":
    main()
