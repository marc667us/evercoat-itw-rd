"""Replace the demonstration news feed with REAL, SYNDICATED industry news (L3).

`TODO.md` L3, verbatim: *"The news feed is still demonstration data and says so
on every card. Real industry news needs a source-ingestion pipeline with licence
and robots/ToS review."*

🔴 WHAT THE LICENCE QUESTION ACTUALLY IS, AND HOW THIS ANSWERS IT.

The blocker was never "can we fetch a page". It was: on what basis may this
application republish another organisation's journalism? This script's answer is
narrow and checkable:

  1. **Only sources that PUBLISH A FEED FOR SYNDICATION.** An RSS or Atom feed
     is a publisher's own offer of headline and link for reuse. That is a
     different act from scraping an article page, and it is the reason the
     allowlist below is feeds rather than sites.
  2. **`robots.txt` IS CHECKED BEFORE EVERY FETCH, AND IT IS A REAL CHECK.**
     Measured 2026-09-01: the EPA's newsroom feed is DISALLOWED by
     `epa.gov/robots.txt` for this agent, and it is therefore not ingested —
     the guard refused a source this script would otherwise have wanted, on its
     first run, which is the only kind of evidence that a guard works.
     RFC 9309 semantics: 4xx on `robots.txt` means allow; 5xx or unreachable
     means DISALLOW, because "we could not ask" is not permission.
  3. 🔴 **HEADLINE AND LINK ONLY. NO ARTICLE TEXT, NOT EVEN THE FEED'S OWN
     `<description>`.** `summary` is written NULL and stays NULL. Reproducing a
     publisher's prose is the part that needs a licence; naming their headline
     and sending the reader to them is the part that does not. The card links
     out, and the reader reads it at the source.

⚠️ CATEGORISATION IS OURS AND THE ROWS SAY SO.

`news_items.category_id` is NOT NULL and no feed carries this product's
taxonomy, so each source has a default category and a small keyword override.
That is an editorial act by this application, not a claim by the publisher.
`relevance_score` stays NULL because nothing here scores relevance — a number
with no model behind it is exactly the invented figure this catalogue refuses.

⚠️ `verification_status = 'reviewed'`, and that is a claim about a real act:
the feed was fetched and parsed at ingestion time. `'verified'` is NOT used —
that needs a named human reviewer, and no human has reviewed these.

⚠️ WHAT THIS IS NOT. It is not the ten-stage pipeline of the source spec: no
entity extraction, no relevance scoring, no material or project linkage, no
saved items. Those are `IMPLEMENTATION_PLAN_PUBLIC_LANDING.md` §7's named
deferrals and remain deferred. This closes L3 — the feed carries real news
instead of demonstration data — and nothing more.
"""

from __future__ import annotations

import datetime as dt
import email.utils
import os
import sys
import urllib.parse
import urllib.robotparser
import xml.etree.ElementTree as ET

import httpx
from sqlalchemy import create_engine, text

DB = os.environ.get(
    "SEED_DATABASE_URL",
    "postgresql+psycopg://evercoat_owner:ci-owner@localhost:55432/evercoat_itw_rd",
)

UA = "EvercoatCatalogue/1.0"
ATOM = "{http://www.w3.org/2005/Atom}"

# (name, tier, homepage, feed url, default category slug)
#
# Tier follows the source spec's 1..4 governance ranking: 1 regulator/standards
# body, 2 established trade press, 3 specialist trade press, 4 aggregator.
#
# Every entry below was probed on 2026-09-01: robots.txt consulted, feed
# fetched, XML parsed, items counted. Sources whose feed 403s an automated
# client (Coatings World, PCI, Adhesives & Sealants Industry, BodyShop
# Business) are ABSENT rather than worked around — a publisher refusing a bot
# is an answer.
SOURCES: list[tuple[str, int, str, str, str]] = [
    (
        "Federal Register — Environmental Protection Agency",
        1,
        "https://www.federalregister.gov/",
        (
            "https://www.federalregister.gov/api/v1/documents.rss"
            "?conditions%5Bagencies%5D%5B%5D=environmental-protection-agency"
        ),
        "regulation",
    ),
    (
        "U.S. Occupational Safety and Health Administration",
        1,
        "https://www.osha.gov/",
        "https://www.osha.gov/news/newsreleases.xml",
        "chemical-safety",
    ),
    (
        "European Coatings",
        2,
        "https://www.european-coatings.com/",
        "https://www.european-coatings.com/feed",
        "technology",
    ),
    (
        "American Coatings Association",
        2,
        "https://www.paint.org/",
        "https://www.paint.org/feed/",
        "market",
    ),
    (
        "Repairer Driven News",
        3,
        "https://www.repairerdrivennews.com/",
        "https://www.repairerdrivennews.com/feed/",
        "market",
    ),
    (
        "CompositesWorld",
        3,
        "https://www.compositesworld.com/",
        "https://www.compositesworld.com/rss/news",
        "materials",
    ),
    (
        "Products Finishing",
        3,
        "https://www.pfonline.com/",
        "https://www.pfonline.com/rss/news",
        "technology",
    ),
    (
        "PlasticsToday",
        3,
        "https://www.plasticstoday.com/",
        "https://www.plasticstoday.com/rss.xml",
        "materials",
    ),
]

# Conservative overrides. A headline has to actually say the word; nothing here
# infers a topic from a synonym, because a mis-filed regulatory item is worse
# than a broadly-filed one.
KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("regulation", ("regulation", "regulatory", "directive", "reach ", "epa ", "voc")),
    ("chemical-safety", ("safety", "hazard", "toxic", "exposure", "osha", "carcinogen")),
    ("patents", ("patent",)),
    ("supply", ("supply chain", "shortage", "capacity", "plant closure")),
    ("materials", ("resin", "pigment", "filler", "additive", "raw material")),
    ("product-launches", ("launches", "launch of", "introduces", "unveils")),
]

MAX_PER_SOURCE = 25

# A feed is a remote document from a host this script does not control, so it is
# untrusted input and sized and shaped before it is parsed.
MAX_FEED_BYTES = 5 * 1024 * 1024


def parse_feed(payload: bytes) -> ET.Element:
    """Parse a feed, having first REMOVED the capabilities that make XML unsafe.

    🔴 A SUPPRESSION WAS THE WRONG FIX HERE, AS IT WAS IN
    `seed_public_intel_real.py`.

    Ruff's `S314` flags `xml.etree` on untrusted data — entity expansion and
    external-entity resolution. `seed_public_intel_real.py` records the rule
    this project settled on when it hit the sibling finding: a `nosemgrep`
    comment *"leaves the capability one edit away from being reachable, and asks
    every future reader to re-derive why it is safe"*. So the capability is
    removed rather than argued about:

      - a payload declaring a DTD or an ENTITY is REFUSED before parsing, which
        is what both attacks need; and
      - the payload is size-capped, so a well-formed but enormous feed cannot
        exhaust this process either.

    Both are checkable in one line each, which a paragraph of reasoning about
    CPython's expat configuration is not.
    """
    if len(payload) > MAX_FEED_BYTES:
        raise ET.ParseError(f"feed is larger than {MAX_FEED_BYTES} bytes")
    head = payload[:4096].lstrip().upper()
    if b"<!DOCTYPE" in head or b"<!ENTITY" in payload.upper():
        raise ET.ParseError("feed declares a DTD or entity and is refused")
    return ET.fromstring(payload)  # noqa: S314 - guarded above


def robots_allows(url: str) -> tuple[bool, str]:
    """Consult `robots.txt` for this exact URL, and fail CLOSED when unsure.

    🔴 "COULD NOT ASK" IS NOT PERMISSION. A 5xx or an unreachable host returns
    False. RFC 9309 treats 4xx as full allow, which is what a site with no
    `robots.txt` means, so that case proceeds.
    """
    parts = urllib.parse.urlsplit(url)
    robots = f"{parts.scheme}://{parts.netloc}/robots.txt"
    try:
        response = httpx.get(robots, headers={"User-Agent": UA}, timeout=15, follow_redirects=True)
    except Exception as exc:  # noqa: BLE001
        return (False, f"robots-unreachable:{type(exc).__name__}")
    if response.status_code >= 500:
        return (False, f"robots-{response.status_code}")
    if response.status_code >= 400:
        return (True, f"robots-{response.status_code}-allow")
    parser = urllib.robotparser.RobotFileParser()
    parser.parse(response.text.splitlines())
    return (parser.can_fetch(UA, url), "robots-parsed")


def _published(item: ET.Element) -> dt.datetime | None:
    """The publisher's own timestamp, or None.

    ⚠️ NEVER `now()` AS A FALLBACK. A missing date rendered as today's date is
    the "a calendar date is not an instant" defect from 2026-08-30 in a new
    costume: an invented timestamp beside a real headline. The card shows no
    date when the feed gave none.
    """
    raw = (
        item.findtext("pubDate")
        or item.findtext(f"{ATOM}published")
        or item.findtext(f"{ATOM}updated")
        or item.findtext("{http://purl.org/dc/elements/1.1/}date")
    )
    if not raw:
        return None
    try:
        parsed = email.utils.parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        try:
            parsed = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.UTC)
    return parsed


def _link(item: ET.Element) -> str | None:
    link = item.findtext("link")
    if link and link.strip():
        return link.strip()
    for element in item.findall(f"{ATOM}link"):
        href = element.get("href")
        if href and element.get("rel", "alternate") == "alternate":
            return href.strip()
    return None


def _categorise(headline: str, default_slug: str) -> str:
    lowered = headline.lower()
    for slug, words in KEYWORDS:
        if any(word in lowered for word in words):
            return slug
    return default_slug


def main() -> None:
    print("INGESTING SYNDICATED INDUSTRY NEWS")
    print("robots.txt is consulted before every fetch; headline and link only.\n")

    harvested: list[dict[str, object]] = []
    refused: list[str] = []

    for name, tier, homepage, feed_url, default_slug in SOURCES:
        allowed, why = robots_allows(feed_url)
        if not allowed:
            refused.append(f"{name} ({why})")
            print(f"  [robots] REFUSE {name} — {why}")
            continue
        try:
            response = httpx.get(
                feed_url, headers={"User-Agent": UA}, timeout=30, follow_redirects=True
            )
        except Exception as exc:  # noqa: BLE001
            refused.append(f"{name} ({type(exc).__name__})")
            print(f"  [  net ] DROP   {name} — {type(exc).__name__}")
            continue
        if response.status_code != 200:
            refused.append(f"{name} (HTTP {response.status_code})")
            print(f"  [{response.status_code:>6}] DROP   {name}")
            continue
        try:
            root = parse_feed(response.content)
        except ET.ParseError as exc:
            refused.append(f"{name} (unparseable: {exc})")
            print(f"  [ parse] DROP   {name}")
            continue

        items = root.findall(".//item") or root.findall(f".//{ATOM}entry")
        kept = 0
        seen: set[str] = set()
        for item in items:
            if kept >= MAX_PER_SOURCE:
                break
            headline = (item.findtext("title") or item.findtext(f"{ATOM}title") or "").strip()
            url = _link(item)
            if not headline or not url or not url.lower().startswith("https://"):
                continue
            if url in seen:
                continue
            seen.add(url)
            harvested.append(
                {
                    "source_name": name,
                    "tier": tier,
                    "homepage": homepage,
                    "headline": headline[:500],
                    "url": url,
                    "published_at": _published(item),
                    "category": _categorise(headline, default_slug),
                }
            )
            kept += 1
        print(f"  [   200] keep   {name} — {kept} items ({why})")

    print(f"\n  sources ingested: {len({row['source_name'] for row in harvested})}")
    print(f"  items harvested:  {len(harvested)}")
    print(f"  sources refused:  {len(refused)}")
    for line in refused:
        print(f"    - {line}")

    if not harvested:
        print("REFUSING: nothing harvested, so nothing is published")
        sys.exit(1)

    engine = create_engine(DB, future=True)
    with engine.begin() as conn:
        categories = dict(
            conn.execute(text("SELECT slug, id FROM public_intel.news_categories")).all()
        )
        missing = {row["category"] for row in harvested} - set(categories)
        if missing:
            raise SystemExit(f"unknown category slugs: {sorted(missing)}")

        # Items before sources: `news_items.source_id` is ON DELETE RESTRICT.
        # Both the demonstration rows and any earlier run of THIS script go, so
        # re-running replaces rather than accumulates.
        conn.execute(text("DELETE FROM public_intel.news_items WHERE is_demonstration_data"))
        conn.execute(
            text("DELETE FROM public_intel.news_items WHERE generated_by = 'ingest_public_news.py'")
        )
        conn.execute(
            text(
                "DELETE FROM public_intel.news_sources s"
                " WHERE NOT EXISTS (SELECT 1 FROM public_intel.news_items i"
                "                    WHERE i.source_id = s.id)"
            )
        )

        source_ids: dict[str, object] = {}
        for name, tier, homepage, _feed, _slug in SOURCES:
            if not any(row["source_name"] == name for row in harvested):
                continue
            source_ids[name] = conn.execute(
                text(
                    """
                    INSERT INTO public_intel.news_sources
                        (name, homepage_url, source_type, tier)
                    VALUES (:n, :h, 'syndicated_feed', :t)
                    ON CONFLICT (name) DO UPDATE
                        SET homepage_url = EXCLUDED.homepage_url,
                            source_type  = EXCLUDED.source_type,
                            tier         = EXCLUDED.tier
                    RETURNING id
                    """
                ),
                {"n": name, "h": homepage, "t": tier},
            ).scalar_one()

        written = 0
        for row in harvested:
            written += conn.execute(
                text(
                    """
                    INSERT INTO public_intel.news_items
                        (source_id, category_id, headline, summary,
                         summary_is_ai_generated, source_url, published_at,
                         retrieved_at, content_origin, verification_status,
                         publication_status, is_demonstration_data,
                         generated_by, generated_at)
                    VALUES (:s, :c, :h, NULL, false, :u, :p, clock_timestamp(),
                            'source_derived', 'reviewed', 'published', false,
                            'ingest_public_news.py', clock_timestamp())
                    ON CONFLICT (source_id, source_url) DO NOTHING
                    """
                ),
                {
                    "s": source_ids[row["source_name"]],
                    "c": categories[row["category"]],
                    "h": row["headline"],
                    "u": row["url"],
                    "p": row["published_at"],
                },
            ).rowcount

        published, demo, unsourced, with_summary = conn.execute(
            text(
                """
                SELECT count(*),
                       count(*) FILTER (WHERE is_demonstration_data),
                       count(*) FILTER (WHERE source_url IS NULL OR source_url = ''),
                       count(*) FILTER (WHERE summary IS NOT NULL)
                  FROM public_intel.news_items
                 WHERE publication_status = 'published'
                """
            )
        ).one()

    print("\nPUBLISHED")
    print(f"  news items       {published}")
    print(f"  written this run {written}")
    print(f"  still_demo       {demo}")
    print(f"  unsourced        {unsourced}")
    print(f"  carrying prose   {with_summary}")
    if demo or unsourced or with_summary:
        print(
            "REFUSING TO REPORT OK: a published row is demonstration data, "
            "unsourced, or reproduces the publisher's prose"
        )
        sys.exit(1)
    print("OK")


if __name__ == "__main__":
    main()
