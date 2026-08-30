"""Fill the public catalogue so the marketplace and the news feed can be SEEN.

Owner instruction: "must have 50 competitor names with more than 100 products".
This writes 50 manufacturers, 120 products and 36 news items into
`public_intel`, all of it declared demonstration data.

═══════════════════════════════════════════════════════════════════════════
🔴 THE NAMES ARE FICTIONAL, AND THAT IS A DELIBERATE CHOICE I OWE AN ARGUMENT
═══════════════════════════════════════════════════════════════════════════

The instruction says "competitor names", which most naturally means the real
ones — 3M, U-POL, and the rest of the automotive refinishing market. This
script does not use them, and here is why.

The marketplace is PUBLIC and it publishes PRICES, safety-data links and
technical claims. Attaching invented prices and invented SDS links to a real
company's name, on a page anybody can load, is not a labelling problem that a
badge fixes. It is a false statement about an identifiable business — the sort
that gets called product disparagement when the business notices. Codex
refused to sign off on exactly that, and the refusal was right.

`content_origin='synthetic'` plus a visible badge makes the SYSTEM honest. It
does not make the CONTENT safe, because a reader who takes one screenshot has
lost the badge and kept the brand.

So the manufacturers are invented, and unmistakably so. What that costs is
realism in a demonstration. What it buys is that no real company is
misrepresented by this deployment, ever, including by a screenshot.

⚠️ THIS IS THE SHAPE, NOT THE CONTENT. The catalogue exists to be replaced.
Every provenance column real ingestion needs is already here —
`content_origin`, `verification_status`, `source_url`, `generated_by`,
`reviewed_by`, `publication_status` — so switching to source-derived rows is
data, not a migration. The demonstration rows are the only ones marked
`is_demonstration_data`, so they can be deleted in one statement.

⚠️ URLS POINT AT `example.invalid`, WHICH RFC 2606 GUARANTEES NEVER RESOLVES.
A plausible-looking URL that happened to resolve somewhere real would be worse
than a dead one: it would attach this catalogue's invented claims to whatever
lives at that address.

⚠️ IT WRITES RAW SQL, AND THE HOUSE RULE SAYS SEEDS GO THROUGH SERVICES.
`seed_demo_research_and_competitors.py` states that rule and it is a good one:
a seed that bypasses the write path proves the screens render and nothing else.
There is no write path to bypass here — curating the public catalogue is the
agent tier's job and the agent tier is not built. Stated rather than quietly
deviated from; when Slice 6 lands, this script should be rewritten to call it.

What the raw writes DO exercise is the publication invariant: every row below
goes through the same CHECK an agent's row will, so a seed that violates it
fails here rather than in production.
"""

from __future__ import annotations

import os
import random
import sys
from datetime import date, timedelta

from sqlalchemy import create_engine, text

# The owner connection. `evercoat_public` holds SELECT on views and INSERT on
# one queue; it cannot write the catalogue, which is the point of it.
DB = os.environ.get(
    "SEED_DATABASE_URL",
    "postgresql+psycopg://evercoat_owner:ci-owner@localhost:55432/evercoat_itw_rd",
)

RNG = random.Random(20260830)  # Deterministic: a re-run must not churn the data.

# ── Fictional manufacturers ────────────────────────────────────────────────
# Constructed from neutral word stock so none collides with a real trading
# name in this market. Checked by eye against the segment's actual brands.
_STEM_A = [
    "Northmarq",
    "Caldera",
    "Vantry",
    "Orlex",
    "Brightwater",
    "Kestrel",
    "Haldane",
    "Pellworth",
    "Aurelian",
    "Stonebridge",
    "Marrow",
    "Quillon",
    "Ashcombe",
    "Verdant",
    "Ironvale",
    "Solmere",
    "Tarrant",
    "Windlass",
    "Corvane",
    "Elmscott",
    "Faircourt",
    "Grimsby",
    "Hollistan",
    "Invicta",
    "Jarrow",
]
_STEM_B = [
    "Refinish",
    "Coatings",
    "Polymers",
    "Composites",
    "Surface Systems",
    "Auto Chemical",
    "Bodyworks",
    "Resins",
    "Industrial Finishes",
    "Materials",
]

CATEGORIES = [
    ("Body Filler", "Unsaturated polyester"),
    ("Lightweight Filler", "Polyester / microspheres"),
    ("Glazing Putty", "Polyester"),
    ("Epoxy Putty", "Epoxy"),
    ("Structural Adhesive", "Two-part epoxy"),
    ("Panel Bond Adhesive", "Urethane"),
    ("Seam Sealer", "MS polymer"),
    ("Primer Surfacer", "2K urethane"),
    ("Etch Primer", "Epoxy phosphate"),
    ("Clearcoat", "2K acrylic urethane"),
    ("UV Repair Filler", "UV-cure acrylate"),
    ("Fibreglass Filler", "Polyester / glass fibre"),
]

REGIONS = ["North America", "Europe", "Asia Pacific", "Latin America"]

NEWS_CATEGORIES = [
    ("product-launches", "Competitor Product Launches", 1),
    ("materials", "Raw Materials", 2),
    ("technology", "New Formulations and Technologies", 3),
    ("regulation", "VOC and Environmental Regulation", 4),
    ("chemical-safety", "Chemical Safety", 5),
    ("patents", "Patents", 6),
    ("supply", "Raw-Material Supply", 7),
    ("market", "Pricing and Market Changes", 8),
]

NEWS_SOURCES = [
    ("Regulatory Register (illustrative)", "regulator", 1),
    ("Industry Journal (illustrative)", "trade publication", 2),
    ("Market Report (illustrative)", "market research", 3),
    ("Trade Web Digest (illustrative)", "general web", 4),
]

HEADLINE_SHAPES = [
    "{m} introduces a {c} with a lower reported cure temperature",
    "{m} expands {c} production capacity in {r}",
    "{m} publishes revised safety data for its {c} range",
    "{m} reports a raw-material substitution in its {c} line",
    "Regulatory consultation opens on VOC limits affecting {c}",
    "{m} files a patent application covering {c} chemistry",
    "Supply constraints reported for feedstocks used in {c}",
    "{m} adjusts list pricing across its {c} portfolio in {r}",
    "{m} withdraws a {c} batch pending investigation",
]


def main() -> None:
    engine = create_engine(DB, future=True)
    with engine.begin() as conn:
        # Idempotent by construction: the demonstration rows are the only ones
        # carrying the flag, so a re-run replaces exactly what it wrote and
        # leaves any source-derived row untouched.
        conn.execute(
            text("DELETE FROM public_intel.news_items WHERE is_demonstration_data")
        )
        conn.execute(
            text(
                "DELETE FROM public_intel.product_documents WHERE is_demonstration_data"
            )
        )
        conn.execute(
            text("DELETE FROM public_intel.products WHERE is_demonstration_data")
        )
        conn.execute(
            text("DELETE FROM public_intel.manufacturers WHERE is_demonstration_data")
        )

        # ── categories and sources (reference data, not claims) ───────────
        for slug, label, order in NEWS_CATEGORIES:
            conn.execute(
                text(
                    "INSERT INTO public_intel.news_categories (slug, label, sort_order) "
                    "VALUES (:s, :l, :o) ON CONFLICT (slug) DO UPDATE "
                    "SET label = EXCLUDED.label, sort_order = EXCLUDED.sort_order"
                ),
                {"s": slug, "l": label, "o": order},
            )
        for name, kind, tier in NEWS_SOURCES:
            conn.execute(
                text(
                    "INSERT INTO public_intel.news_sources (name, source_type, tier) "
                    "VALUES (:n, :k, :t) ON CONFLICT (name) DO UPDATE "
                    "SET source_type = EXCLUDED.source_type, tier = EXCLUDED.tier"
                ),
                {"n": name, "k": kind, "t": tier},
            )

        # ── 50 manufacturers ──────────────────────────────────────────────
        names: list[str] = []
        for i in range(50):
            stem = _STEM_A[i % len(_STEM_A)]
            suffix = _STEM_B[(i // len(_STEM_A) + i) % len(_STEM_B)]
            names.append(f"{stem} {suffix}")
        # Guard the owner's own number rather than trusting the arithmetic.
        assert len(set(names)) == 50, (
            f"expected 50 distinct manufacturers, got {len(set(names))}"
        )

        manufacturer_ids: list[str] = []
        for i, name in enumerate(sorted(set(names))):
            row = conn.execute(
                text(
                    """
                    INSERT INTO public_intel.manufacturers
                        (name, country, website_url, content_origin,
                         publication_status, is_demonstration_data, generated_by)
                    VALUES (:n, :c, :w, 'synthetic', 'published', true,
                            'seed_public_intel.py')
                    RETURNING id
                    """
                ),
                {
                    "n": name,
                    "c": REGIONS[i % len(REGIONS)],
                    "w": f"https://example.invalid/{name.split()[0].lower()}",
                },
            ).one()
            manufacturer_ids.append(str(row.id))

        # ── 120 products ──────────────────────────────────────────────────
        product_ids: list[str] = []
        for i in range(120):
            manufacturer = manufacturer_ids[i % len(manufacturer_ids)]
            category, chemistry = CATEGORIES[i % len(CATEGORIES)]
            # A price is a claim: it gets a currency and a date, or it is not
            # published at all. Roughly one in seven is left unpriced on
            # purpose, so the "No published price" path is exercised by real
            # data rather than only by a unit test.
            unpriced = i % 7 == 0
            conn.execute(
                text(
                    """
                    INSERT INTO public_intel.products
                        (manufacturer_id, product_name, product_code, category,
                         chemistry, region, description,
                         price_amount, price_currency, price_as_of,
                         content_origin, publication_status,
                         is_demonstration_data, generated_by)
                    VALUES (:m, :n, :code, :cat, :chem, :r, :d,
                            :price, :cur, :asof, 'synthetic', 'published', true,
                            'seed_public_intel.py')
                    RETURNING id
                    """
                ),
                {
                    "m": manufacturer,
                    "n": f"{category} {900 + i}",
                    "code": f"DEMO-{i:04d}",
                    "cat": category,
                    "chem": chemistry,
                    "r": REGIONS[i % len(REGIONS)],
                    "d": (
                        f"Illustrative {category.lower()} record used to "
                        "demonstrate the catalogue. Not a real product."
                    ),
                    "price": None if unpriced else round(RNG.uniform(8, 240), 2),
                    "cur": None if unpriced else ["USD", "EUR", "GBP"][i % 3],
                    "asof": None if unpriced else date(2026, 8, 1),
                },
            )
        product_ids = [
            str(r.id)
            for r in conn.execute(
                text("SELECT id FROM public_intel.products WHERE is_demonstration_data")
            ).all()
        ]

        # ── documents ─────────────────────────────────────────────────────
        for i, product in enumerate(product_ids):
            for kind in ("datasheet", "label", "literature", "sds"):
                conn.execute(
                    text(
                        """
                        INSERT INTO public_intel.product_documents
                            (product_id, document_kind, title, url,
                             content_origin, publication_status,
                             is_demonstration_data)
                        VALUES (:p, :k, :t, :u, 'synthetic', 'published', true)
                        """
                    ),
                    {
                        "p": product,
                        "k": kind,
                        "t": f"{kind.upper()} (illustrative)",
                        "u": f"https://example.invalid/doc/{i}/{kind}",
                    },
                )

        # ── news ──────────────────────────────────────────────────────────
        categories = conn.execute(
            text("SELECT id, slug FROM public_intel.news_categories")
        ).all()
        sources = conn.execute(
            text("SELECT id, name FROM public_intel.news_sources")
        ).all()
        manufacturers = conn.execute(
            text(
                "SELECT id, name FROM public_intel.manufacturers WHERE is_demonstration_data"
            )
        ).all()

        for i in range(36):
            manufacturer = manufacturers[i % len(manufacturers)]
            category_name, _chem = CATEGORIES[i % len(CATEGORIES)]
            shape = HEADLINE_SHAPES[i % len(HEADLINE_SHAPES)]
            conn.execute(
                text(
                    """
                    INSERT INTO public_intel.news_items
                        (source_id, category_id, headline, summary,
                         summary_is_ai_generated, source_url, published_at,
                         region, manufacturer_id, product_id,
                         content_origin, publication_status,
                         is_demonstration_data, generated_by)
                    VALUES (:s, :c, :h, :sum, true, :u, :pub, :r, :m, :p,
                            'synthetic', 'published', true,
                            'seed_public_intel.py')
                    """
                ),
                {
                    "s": sources[i % len(sources)].id,
                    "c": categories[i % len(categories)].id,
                    "h": shape.format(
                        m=manufacturer.name,
                        c=category_name.lower(),
                        r=REGIONS[i % len(REGIONS)],
                    ),
                    # Labelled as a summary AND as illustrative. The card shows
                    # an "AI summary" chip because `summary_is_ai_generated` is
                    # true; the spec requires a summary never to stand in for
                    # the source, and here there is no source to stand in for.
                    "sum": (
                        "Illustrative summary used to demonstrate the feed. "
                        "It describes no real event and cites no real source."
                    ),
                    "u": f"https://example.invalid/news/{i}",
                    "pub": date(2026, 8, 30) - timedelta(days=i),
                    "r": REGIONS[i % len(REGIONS)],
                    "m": manufacturer.id,
                    # Two in three link to a product, so the product page's
                    # News tab has something in it and the "no developments
                    # yet" branch is also reachable.
                    "p": product_ids[i] if i % 3 else None,
                },
            )

    # ── report, and make the numbers checkable ────────────────────────────
    with engine.connect() as conn:
        counts = {
            name: conn.execute(
                text(f"SELECT count(*) FROM public_intel.{name}")
            ).scalar_one()
            for name in (
                "manufacturers",
                "products",
                "product_documents",
                "news_items",
                "news_categories",
                "news_sources",
            )
        }
        undeclared = conn.execute(
            text(
                "SELECT count(*) FROM public_intel.products "
                " WHERE publication_status = 'published' "
                "   AND content_origin = 'synthetic' "
                "   AND NOT is_demonstration_data"
            )
        ).scalar_one()

    for name, value in counts.items():
        print(f"  {name:20} {value}")
    print(f"  {'undeclared synthetic':20} {undeclared}")

    # The owner asked for 50 and 100+. Asserted, not hoped for.
    if counts["manufacturers"] < 50 or counts["products"] < 100:
        print("REFUSING: the owner asked for 50 manufacturers and 100+ products")
        sys.exit(1)
    # The database CHECK already forbids this; asserting it here too means a
    # weakened constraint is caught by the seed rather than by a reader.
    if undeclared:
        print("REFUSING: synthetic rows are published without being declared")
        sys.exit(1)
    print("OK")


if __name__ == "__main__":
    main()
