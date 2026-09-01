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
import re
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
    # 🔴 THIS ONE IS EXPECTED TO BE REFUSED, AND THAT IS WHY IT IS HERE.
    #
    # `epa.gov/robots.txt` disallows this feed for this agent. The Supervisor's
    # finding was exact: the module docstring cited the EPA refusal as evidence
    # the guard works, while no entry in this list actually exercised the deny
    # branch — so the guard had never been observed returning False during a
    # real run, only during a probe nobody could re-run.
    #
    # Listing it makes the refusal happen on EVERY run and appear in the report.
    # A guard that has only ever allowed has not been shown to refuse, and the
    # cheapest way to keep that true is to give it something to refuse.
    (
        "U.S. Environmental Protection Agency (expected: refused by robots.txt)",
        1,
        "https://www.epa.gov/",
        "https://www.epa.gov/newsreleases/search/rss",
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
#
# 🔴 MATCHED ON WORD BOUNDARIES, AND THE FIRST VERSION WAS NOT. Raised by the
# Supervisor: a plain substring test put *"Association advocates for shop safety
# standards"* under `regulation`, because "advocates" contains "voc". Two
# neighbouring entries already carried a trailing space (`"reach "`, `"epa "`)
# as a hand-rolled boundary, which is the tell that the rule was known and
# applied unevenly. `\b` applies it to all of them, so a phrase like
# "supply chain" still matches and "advocate" no longer does.
KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("regulation", ("regulation", "regulatory", "directive", "reach", "epa", "voc")),
    ("chemical-safety", ("safety", "hazard", "toxic", "exposure", "osha", "carcinogen")),
    ("patents", ("patent",)),
    ("supply", ("supply chain", "shortage", "capacity", "plant closure")),
    ("materials", ("resin", "pigment", "filler", "additive", "raw material")),
    ("product-launches", ("launches", "launch of", "introduces", "unveils")),
]

MAX_PER_SOURCE = 25

# The four demonstration sources migration 059 seeded. Named literally, because
# this script is entitled to remove them and is entitled to remove nothing else
# it did not write. Their `(illustrative)` suffix is part of the seeded name.
_DEMO_SOURCE_NAMES: tuple[str, ...] = (
    "Industry Journal (illustrative)",
    "Market Report (illustrative)",
    "Regulatory Register (illustrative)",
    "Trade Web Digest (illustrative)",
)

# A feed is a remote document from a host this script does not control, so it is
# untrusted input and sized and shaped before it is parsed.
MAX_FEED_BYTES = 5 * 1024 * 1024

# Redirects are followed by hand so `robots.txt` can be consulted for each
# destination BEFORE it is requested; see `fetch_feed`.
MAX_REDIRECTS = 5
_REDIRECT_CODES = frozenset({301, 302, 303, 307, 308})


def parse_feed(payload: bytes) -> ET.Element:
    """Parse a feed, having first REMOVED the capabilities that make XML unsafe.

    🔴 A SUPPRESSION WAS THE WRONG FIX HERE, AS IT WAS IN
    `seed_public_intel_real.py`.

    Ruff's `S314` flags `xml.etree` on untrusted data — entity expansion and
    external-entity resolution. `seed_public_intel_real.py` records the rule
    this project settled on when it hit the sibling finding: a `nosemgrep`
    comment *"leaves the capability one edit away from being reachable, and asks
    every future reader to re-derive why it is safe"*. So the capability is
    removed rather than argued about.

    🔴 AND THE FIRST VERSION OF THIS GUARD DID NOT WORK. Raised by Codex,
    then MEASURED before it was believed:

        payload = '<?xml version="1.0" encoding="UTF-16"?>…'.encode("utf-16")
        b"<!DOCTYPE" in payload      -> False
        ET.fromstring(payload)       -> parses fine

    A UTF-16 document interleaves NUL bytes through every ASCII character, so
    a byte-string search for `<!DOCTYPE` matches nothing while ElementTree
    honours the declared encoding and parses the document anyway — including
    its entity declarations. The guard read as a check on the payload and was
    a check on one *encoding* of the payload. **That is the "a guard that
    cannot fail is not a guard" defect in its purest form**, and it was found
    by a reviewer rather than by me.

    So the encoding is pinned FIRST and the token check runs on text:

      - anything that is not decodable as UTF-8 is refused outright. Every
        feed in `SOURCES` is UTF-8; a UTF-16 feed would be a new source and a
        deliberate decision, not something this parser silently accepts;
      - a decoded document declaring a DTD or an ENTITY is refused, which is
        what both entity attacks need;
      - the payload is size-capped, so a well-formed but enormous feed cannot
        exhaust this process either.

    ⚠️ THE HONEST CLAIM IS NARROWER THAN "SAFE". This closes entity expansion
    and external entities for the inputs this script accepts. `defusedxml`
    would close the class rather than the instance; it is not a declared
    dependency of this repository and adding one for a script is a decision
    rather than a fix, so it is recorded in `TODO.md` instead of assumed.
    """
    if len(payload) > MAX_FEED_BYTES:
        raise ET.ParseError(f"feed is larger than {MAX_FEED_BYTES} bytes")
    try:
        document = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ET.ParseError(f"feed is not UTF-8 and is refused: {exc}") from exc
    upper = document.upper()
    if "<!DOCTYPE" in upper or "<!ENTITY" in upper:
        raise ET.ParseError("feed declares a DTD or entity and is refused")
    return ET.fromstring(document)  # noqa: S314 - encoding pinned, DTD refused


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


class FeedRefusedError(RuntimeError):
    """A fetch this script refuses to complete or to keep."""


def fetch_feed(url: str) -> tuple[int, bytes]:
    """Fetch a feed under a real byte budget, re-checking robots on redirect.

    🔴 TWO SUPERVISOR FINDINGS, AND BOTH WERE COMMENTS DESCRIBING SOMETHING THE
    CODE DID NOT DO.

    **The size cap could not cap anything.** `parse_feed` checked
    `len(payload) > MAX_FEED_BYTES` — but the caller had already done a
    non-streaming `httpx.get`, so the entire response was in memory before the
    check ran. The docstring claimed *"a well-formed but enormous feed cannot
    exhaust this process"*, and only the PARSE was bounded. Now the body is
    streamed and abandoned the moment it exceeds the budget, so the claim is
    true of the fetch as well.

    **`robots.txt` was checked for the configured URL and the fetch followed
    redirects**, so a feed that moved to another host was fetched from a host
    whose `robots.txt` was never consulted.

    🔴 THE FIRST FIX FOR THAT DID NOT WORK EITHER, and Codex caught it on the
    second pass. It kept `follow_redirects=True` and re-checked
    `response.url` afterwards — by which time httpx had already made the
    request. **A check that runs after the thing it guards is a report.** It is
    the same shape as the invariant that ran after the commit, in the same
    file, in the same commit.

    Redirects are now followed BY HAND, one hop at a time, with robots asked
    about each destination *before* it is requested, an https-only rule, and a
    hop limit.

    Both are the same defect this repository keeps cataloguing: a comment
    asserting a control that is not there.
    """
    target = url
    for hop in range(MAX_REDIRECTS + 1):
        with httpx.stream(
            "GET",
            target,
            headers={"User-Agent": UA},
            timeout=30,
            follow_redirects=False,
        ) as response:
            if response.status_code in _REDIRECT_CODES:
                location = response.headers.get("location")
                if not location:
                    raise FeedRefusedError(f"{response.status_code} with no Location header")
                nxt = urllib.parse.urljoin(target, location)
                if not nxt.lower().startswith("https://"):
                    raise FeedRefusedError(f"redirect to a non-https target: {nxt}")
                if hop == MAX_REDIRECTS:
                    raise FeedRefusedError(f"more than {MAX_REDIRECTS} redirects")
                # 🔴 THE CHECK HAPPENS BEFORE THE NEXT REQUEST, WHICH IS THE
                # WHOLE POINT. Asked for every hop, not only a cross-host one:
                # a same-host redirect can still move to a path `robots.txt`
                # disallows, and asking twice costs one cached fetch.
                allowed, why = robots_allows(nxt)
                if not allowed:
                    raise FeedRefusedError(f"redirect to {nxt} refused by robots: {why}")
                target = nxt
                continue

            if response.status_code != 200:
                return (response.status_code, b"")

            chunks: list[bytes] = []
            total = 0
            for chunk in response.iter_bytes():
                total += len(chunk)
                if total > MAX_FEED_BYTES:
                    raise FeedRefusedError(
                        f"feed exceeded {MAX_FEED_BYTES} bytes and was abandoned"
                    )
                chunks.append(chunk)
            return (200, b"".join(chunks))

    raise FeedRefusedError("redirect loop")


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
        if any(re.search(rf"\b{re.escape(word)}\b", lowered) for word in words):
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
            code, payload = fetch_feed(feed_url)
        except FeedRefusedError as exc:
            refused.append(f"{name} ({exc})")
            print(f"  [ guard] DROP   {name} — {exc}")
            continue
        except Exception as exc:  # noqa: BLE001
            refused.append(f"{name} ({type(exc).__name__})")
            print(f"  [  net ] DROP   {name} — {type(exc).__name__}")
            continue
        if code != 200:
            refused.append(f"{name} (HTTP {code})")
            print(f"  [{code:>6}] DROP   {name}")
            continue
        try:
            root = parse_feed(payload)
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
        # 🔴 ONLY ORPHANS THIS SCRIPT ACTUALLY OWNS, BY NAME.
        #
        # The first version deleted EVERY orphaned source. Codex called that a
        # destructive side effect of a routine job on rows this script did not
        # create. The second version narrowed it to `source_type` — and Codex
        # was right again on the next pass: **a type is not provenance.** Any
        # other tool writing a `syndicated_feed` source would still have been
        # deleted by a news refresh.
        #
        # The set is now enumerated. Exactly two kinds are in scope: the names
        # in `SOURCES`, which this script owns because it writes them, and the
        # migration-059 demonstration rows, which are what this ingestion
        # replaces and which are identified by their literal seeded names
        # rather than by a shape. Anything else survives, whatever its type.
        owned = [name for name, _t, _h, _f, _s in SOURCES] + list(_DEMO_SOURCE_NAMES)
        conn.execute(
            text(
                "DELETE FROM public_intel.news_sources s"
                " WHERE s.name = ANY(:owned)"
                "   AND NOT EXISTS (SELECT 1 FROM public_intel.news_items i"
                "                    WHERE i.source_id = s.id)"
            ),
            {"owned": owned},
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

        # 🔴 THE INVARIANT IS CHECKED INSIDE THE TRANSACTION, AND IT WAS NOT.
        #
        # Raised by Codex, and it is the sharpest finding of the review. The
        # first version read these counts AFTER `with engine.begin()` had
        # closed, so the delete-and-replace had already COMMITTED and a failure
        # exited 1 over a database already in the state the check exists to
        # prevent. A guard that runs after the thing it guards is a report.
        #
        # Raising here rolls the whole ingestion back, so the previous
        # catalogue survives a run that would have published something
        # dishonest.
        #
        # ⚠️ SCOPED TO THE ROWS THIS RUN WROTE. Asserting over every published
        # row would make this script fail on somebody else's data, which is a
        # different defect wearing the same clothes.
        published, demo, unsourced, with_summary = conn.execute(
            text(
                """
                SELECT count(*),
                       count(*) FILTER (WHERE is_demonstration_data),
                       count(*) FILTER (WHERE source_url IS NULL OR source_url = ''),
                       count(*) FILTER (WHERE summary IS NOT NULL)
                  FROM public_intel.news_items
                 WHERE publication_status = 'published'
                   AND generated_by = 'ingest_public_news.py'
                """
            )
        ).one()
        if demo or unsourced or with_summary:
            raise SystemExit(
                "REFUSING AND ROLLING BACK: of the rows this run published, "
                f"{demo} are demonstration data, {unsourced} are unsourced and "
                f"{with_summary} reproduce the publisher's prose."
            )

    print("\nPUBLISHED")
    print(f"  news items       {published}")
    print(f"  written this run {written}")
    print(f"  still_demo       {demo}")
    print(f"  unsourced        {unsourced}")
    print(f"  carrying prose   {with_summary}")
    print("OK")


if __name__ == "__main__":
    main()
