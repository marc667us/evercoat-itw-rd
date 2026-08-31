"""Global search — spec §29, "Existing search integration".

🔴 THIS IS RECORD LOOKUP, AND IT IS NOT `knowledge.search`. THE DIFFERENCE IS
THE WHOLE REASON THERE ARE TWO.

`app.domains.knowledge.service.search_knowledge` retrieves *passages* by
embedding distance: it answers "what does the library say about epoxy
yellowing?" and it can be approximately right. This answers "where is F008?" —
a caller who types a record's code wants that record, and an embedding ranking
would put a semantically similar formula above an exact code match. Lexical
matching is the correct instrument for identifiers, and it needs no embedder,
so search keeps working on a host where none is installed.

Spec §29 says *extend* global search rather than build another search box.
There was no global search to extend — measured, not assumed: before this
module the only `/search` route in the API was `knowledge.get_search`, over
passages.

⚠️ THE AGENT TIER DOES NOT CALL THIS YET, AND SAYING OTHERWISE WOULD BE A
CLAIM ABOUT A PATH THAT DOES NOT EXIST. §29 intends the Material Safety Data
Assistant to use "the same indexed records with permission filtering", and
`global_search` is shaped for that — it takes the caller's permission set as an
argument precisely so a second adapter can supply its own. But Codex measured
the call sites and found exactly one: the HTTP route. An earlier version of
this paragraph said the assistant "is expected to call" it, which reads as a
description of the system rather than of an intention. When an agent tool is
written, it must derive organization and permissions from its authenticated
execution context and never accept them as model-visible tool arguments.

🔴 PERMISSION FILTERING IS PER RECORD TYPE, AND IT IS NOT A POST-FILTER.

Each entry in `SEARCHABLE` names the permission that governs its record type.
A caller without `material.view` does not get materials *ranked lower* — the
branch does not run, because its gate is a bound `false`. Two reasons this is a
gate and not a filter over results:

- a post-filter leaks the total. "247 results, 3 shown" tells an unauthorized
  caller how many materials match "isocyanate", which is most of the answer.
- this project has counted a gate on an unused path as decoration. Here the
  gate is the only thing that puts the branch in the query at all, so a test
  that removes it changes the returned rows — it can fail.

TENANCY IS ENFORCED IN TWO PLACES, AND THIS FILE IS ONE OF THEM.

✅ CORRECTED after review. This paragraph said "tenancy is NOT done here" while
fourteen of the fifteen branches carry an explicit `organization_id = :org`.
That is application-layer tenancy enforcement, and describing it as merely
decorative was wrong in the direction that invites somebody to delete it. RLS
is the independent database-layer backstop (§5), not a reason the predicate
above it is optional — the two are belt AND braces, and neither is "the" one.

The fifteenth branch, `catalogue_product`, has no organization predicate
because `public_intel` is the anonymous catalogue and its rows belong to no
tenant. Its boundary is publication status instead.

🔴 NO INTERPOLATION REACHES `text()`.

The statement is one literal `UNION ALL` with every table name written out.
An earlier draft built it by looping over `SEARCHABLE` and f-stringing the
schema and table in, which is not injectable — the registry is a module
constant — and which Semgrep's `avoid-sqlalchemy-text` is still right to
block: the tuple is one edit away from holding something a caller chose, and
by then nobody re-reads the loop. That exact finding blocked commit `5209298`
on this repository a week ago. So the branches are spelled out, the registry
carries only metadata Python uses (permission, label, path), and the two are
held together by `test_every_searchable_type_has_a_branch_in_the_statement`.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

# The largest page this endpoint will build. Chosen to match
# `knowledge.MAX_SEARCH_RESULTS` so the two search surfaces cannot disagree
# about what "a lot of results" means.
MAX_SEARCH_RESULTS = 50

# 🔴 THE TWO BOUNDS ON WHAT ONE SEARCH MAY COST. CODEX P1.
#
# Escaping `%` and `_` closed pattern INJECTION and did nothing about pattern
# COST. `lower(col) LIKE '%a%'` has a leading wildcard, so no ordinary index
# can serve it; a single common letter makes every permitted branch scan its
# table and PostgreSQL sort the whole union before `LIMIT` throws it away.
# `limit <= 50` bounds the RESPONSE, not the WORK. That is an authenticated
# availability-abuse path: cheap to send, expensive to answer, repeatable.
#
# Two bounds, because neither alone is enough:
#
# - `MIN_QUERY_LENGTH` removes the cheapest and worst case. It is not a fix on
#   its own -- "ab" scans almost as much as "a" -- and it is not claimed as one.
# - `STATEMENT_TIMEOUT_MS` is the actual bound. It is set `LOCAL`, so it lasts
#   only for this transaction, and a query that exceeds it is CANCELLED by the
#   database rather than left to run. The caller gets a refusal that says the
#   search was too broad, which is true and actionable.
#
# A single-character search is still legitimate for a person looking up a code;
# they can type two. Neither bound is a rate limit, and this does not pretend
# to be one -- I18 owns that, at the edge, for every route at once.
MIN_QUERY_LENGTH = 2
STATEMENT_TIMEOUT_MS = 5000


@dataclass(frozen=True)
class Searchable:
    """One record type the global search can return.

    `permission` is the permission a caller must hold for this type's branch to
    run at all.

    🔴 `detail_path` IS NULLABLE, AND MOST OF THEM ARE NULL. THAT IS THE POINT.

    The first draft of this registry gave every type a detail route — and
    fourteen of the fifteen did not exist. `/materials/{id}`, `/suppliers/{id}`,
    `/knowledge/{id}` and the rest are not routes this application serves; only
    the five workspace screens take a record id, and they take it as a QUERY
    PARAMETER (`?id=`), not a path segment.

    That would have shipped a search box where every result 404s. This
    repository has the lesson already, in `components/ui/record-link.tsx`:
    *"A dead link is worse than no link. It looks like a working product until
    it is clicked, and then it looks broken rather than unfinished."* Every
    live row linked to a 404 once here and the list looked fine.

    So a hit is a link only where a detail screen genuinely exists, and
    otherwise the screen renders it as text and offers `list_path` — the screen
    that does show that record type — instead.
    `test_every_path_the_registry_emits_is_a_real_web_route` reads the web app's
    own filesystem and fails if either claim drifts.
    """

    record_type: str
    label: str
    #: The permission a caller must hold, or None where the data is public and
    #: reading it requires none (`catalogue_product`). None is not "unguarded"
    #: -- it is a claim that this record type is anonymously readable, and
    #: `test_only_public_data_may_declare_no_permission` holds it to that.
    permission: str | None
    #: The screen showing one record, or None when this product has none yet.
    detail_path: str | None
    #: The screen listing this record type. Every type has one.
    list_path: str


# ─── the registry ────────────────────────────────────────────────────────────
#
# Order is the order ties are broken in, so the types a person searching by
# code most often means come first.
SEARCHABLE: tuple[Searchable, ...] = (
    Searchable("project", "Project", "project.view", "/projects/workspace?id={id}", "/projects"),
    Searchable("material", "Material", "material.view", None, "/materials"),
    Searchable("sds", "SDS", "material.view", None, "/material-safety"),
    Searchable("supplier", "Supplier", "material.view", None, "/suppliers"),
    # 🔴 THE FORMULA WORKSPACE OPENS A VERSION, NOT A FORMULA. `?version=` is
    # a `formula_versions.id`, so the branch projects the LATEST version's id
    # as `link_id`. A formula with no version yet links nowhere, correctly.
    Searchable(
        "formula", "Formula", "formula.view", "/formulations/formula?version={id}", "/formulations"
    ),
    Searchable("batch", "Lab batch", "batch.view", "/laboratory/batch?id={id}", "/laboratory"),
    Searchable("sample", "Sample", "batch.view", None, "/laboratory"),
    Searchable("test", "Test", "test.view", "/testing/test?id={id}", "/testing"),
    Searchable(
        "failure", "Failure", "failure.view", "/failures/investigation?id={id}", "/failures"
    ),
    Searchable(
        "research_investigation",
        "Research workspace",
        "research.view",
        None,
        "/material-safety/research",
    ),
    Searchable(
        "research_finding",
        "Research finding",
        "research.view",
        None,
        "/material-safety/research",
    ),
    # 🔴 `material.view`, NOT `research.view`. SUPERVISOR.
    # `app/api/competitors.py:140` gates every competitor read on
    # `material.view` and says why: "a competitor product is technical
    # reference material of the same kind as a raw material". `research.view`
    # is held by only five of the ten roles (058), so a laboratory technician
    # who can browse `/material-safety/competitors` perfectly well was told by
    # the search page "Not searched — you do not hold `research.view`". A false
    # claim about the caller's own access, on the one screen whose stated
    # purpose is not to lie about what it did not search.
    Searchable(
        "competitor_product",
        "Competitor product",
        "material.view",
        None,
        "/material-safety/competitors",
    ),
    Searchable("document", "Document", "knowledge.view", None, "/knowledge"),
    Searchable("opportunity", "Opportunity", "opportunity.view", None, "/innovation"),
    # 🔴 NO PERMISSION AT ALL, AND THAT IS THE HONEST ANSWER. SUPERVISOR.
    # `public_intel` is the ANONYMOUS catalogue -- `/marketplace` serves it to
    # visitors with no session. Gating it on `research.view` told five of the
    # ten roles that published, publicly-readable products "were not searched",
    # which is false in the same way the competitor entry above was. There is
    # no permission that means "may read public data", because reading it needs
    # none. `None` says so rather than borrowing the nearest available code.
    Searchable("catalogue_product", "Catalogue product", None, None, "/marketplace"),
)

_BY_TYPE = {s.record_type: s for s in SEARCHABLE}


# ─── the record types spec §29 names that this cannot return, and why ────────
#
# 🔴 NAMED, NOT OMITTED. §29 lists fourteen record types. Two of them have no
# table in this database, and a search that silently returns nothing for
# "patent" is indistinguishable from one that searched and found none. The API
# reports these so a screen can say "patents are not held in this system"
# rather than "no results". `test_absent_types_are_declared_not_forgotten`
# fails if a table is later created for one of these and this note is not
# removed — an absence that stopped being true is a stale claim, and this
# repository has a standing rule about comments asserting rules that do not
# exist.
ABSENT: dict[str, str] = {
    "patent": (
        "Patent records are extension slice E10 (external research gateway) and "
        "no patent table exists in this database."
    ),
    "released_product": (
        "Released-product records are full-build Slice 18 (Qualification + "
        "Release); the catalogue product type below is competitor market "
        "intelligence, not an ITW Evercoat released product."
    ),
}

# The table each absent type would live in, so the guard can prove the absence
# rather than trust this dictionary.
_ABSENT_TABLES: dict[str, tuple[str, str]] = {
    "patent": ("research", "patents"),
    "released_product": ("products", "released_products"),
}


class SearchError(ValueError):
    """A query this endpoint will not run."""


class SearchTooBroadError(SearchError):
    """The database cancelled the query at `STATEMENT_TIMEOUT_MS`.

    🔴 THIS CLASS EXISTS BECAUSE THE COMMENT ABOVE PROMISED IT AND NOTHING
    DELIVERED IT. SUPERVISOR.

    `STATEMENT_TIMEOUT_MS`'s note said "the caller gets a refusal that says the
    search was too broad, which is true and actionable". Nothing caught the
    cancellation: it surfaced as `OperationalError`, only `SearchError` was
    handled in the route, and there is no global DBAPI exception handler in
    this application. So the real behaviour was a 500 and a screen reading
    "the search could not be run: <generic>".

    A comment asserting behaviour that does not exist is a defect in its own
    right here, and this one asserted the *outcome of a security control*.
    """


_STATEMENT = text(
    """
    WITH hits AS (
        SELECT 'project' AS record_type, p.id AS id, p.project_code AS code,
               p.name AS title, p.product_family AS subtitle, p.status AS state,
               p.id AS project_id, p.created_at AS created_at,
               CASE WHEN lower(p.project_code) = :q THEN 0
                    WHEN lower(p.project_code) LIKE :prefix THEN 1
                    WHEN lower(p.name) LIKE :like THEN 2
                    ELSE 3 END AS score
          FROM projects.projects p
         WHERE CAST(:may_project AS BOOLEAN)
           AND p.organization_id = :org
           AND (lower(p.project_code) LIKE :like
             OR lower(p.name) LIKE :like
             OR lower(coalesce(p.product_family, '')) LIKE :like)

        UNION ALL
        SELECT 'material', m.id, m.material_code, m.name, m.category, m.status,
               NULL::uuid, m.created_at,
               CASE WHEN lower(m.material_code) = :q THEN 0
                    WHEN lower(m.material_code) LIKE :prefix THEN 1
                    WHEN lower(m.name) LIKE :like THEN 2
                    ELSE 3 END
          FROM materials.materials m
         WHERE CAST(:may_material AS BOOLEAN)
           AND m.organization_id = :org
           AND (lower(m.material_code) LIKE :like
             OR lower(m.name) LIKE :like
             OR lower(coalesce(m.cas_number, '')) LIKE :like
             OR lower(coalesce(m.description, '')) LIKE :like)

        UNION ALL
        SELECT 'sds', s.id, s.supplier_revision, m2.name, s.manufacturer,
               s.review_state, NULL::uuid, s.created_at,
               CASE WHEN lower(coalesce(s.supplier_revision, '')) = :q THEN 0
                    WHEN lower(coalesce(s.supplier_revision, '')) LIKE :prefix THEN 1
                    WHEN lower(coalesce(m2.name, '')) LIKE :like THEN 2
                    ELSE 3 END
          FROM safety.sds_versions s
          JOIN materials.materials m2
            ON m2.id = s.material_id AND m2.organization_id = s.organization_id
         WHERE CAST(:may_sds AS BOOLEAN)
           AND s.organization_id = :org
           AND (lower(coalesce(s.supplier_revision, '')) LIKE :like
             OR lower(coalesce(s.manufacturer, '')) LIKE :like
             OR lower(m2.name) LIKE :like
             OR lower(m2.material_code) LIKE :like)

        UNION ALL
        SELECT 'supplier', sp.id, sp.supplier_code, sp.name, sp.country,
               sp.status, NULL::uuid, sp.created_at,
               CASE WHEN lower(sp.supplier_code) = :q THEN 0
                    WHEN lower(sp.supplier_code) LIKE :prefix THEN 1
                    WHEN lower(sp.name) LIKE :like THEN 2
                    ELSE 3 END
          FROM materials.suppliers sp
         WHERE CAST(:may_supplier AS BOOLEAN)
           AND sp.organization_id = :org
           AND (lower(sp.supplier_code) LIKE :like
             OR lower(sp.name) LIKE :like
             OR lower(coalesce(sp.country, '')) LIKE :like)

        UNION ALL
        SELECT 'formula', f.id, f.formula_code, f.name, f.product_family,
               f.status, f.project_id, f.created_at,
               CASE WHEN lower(f.formula_code) = :q THEN 0
                    WHEN lower(f.formula_code) LIKE :prefix THEN 1
                    WHEN lower(f.name) LIKE :like THEN 2
                    ELSE 3 END
          FROM formulations.formulas f
         WHERE CAST(:may_formula AS BOOLEAN)
           AND f.organization_id = :org
           AND (lower(f.formula_code) LIKE :like
             OR lower(f.name) LIKE :like
             OR lower(coalesce(f.description, '')) LIKE :like)

        UNION ALL
        SELECT 'batch', b.id, b.batch_number, coalesce(b.purpose, b.batch_number),
               b.mixing_procedure, b.status, b.project_id, b.created_at,
               CASE WHEN lower(b.batch_number) = :q THEN 0
                    WHEN lower(b.batch_number) LIKE :prefix THEN 1
                    WHEN lower(coalesce(b.purpose, '')) LIKE :like THEN 2
                    ELSE 3 END
          FROM laboratory.batches b
         WHERE CAST(:may_batch AS BOOLEAN)
           AND b.organization_id = :org
           AND (lower(b.batch_number) LIKE :like
             OR lower(coalesce(b.purpose, '')) LIKE :like
             OR lower(coalesce(b.notes, '')) LIKE :like)

        UNION ALL
        SELECT 'sample', sa.id, sa.sample_number,
               coalesce(sa.purpose, sa.sample_number), sa.storage_location,
               sa.status, sa.project_id, sa.created_at,
               CASE WHEN lower(sa.sample_number) = :q THEN 0
                    WHEN lower(sa.sample_number) LIKE :prefix THEN 1
                    WHEN lower(coalesce(sa.purpose, '')) LIKE :like THEN 2
                    ELSE 3 END
          FROM laboratory.samples sa
         WHERE CAST(:may_sample AS BOOLEAN)
           AND sa.organization_id = :org
           AND (lower(sa.sample_number) LIKE :like
             OR lower(coalesce(sa.purpose, '')) LIKE :like
             OR lower(coalesce(sa.storage_location, '')) LIKE :like)

        UNION ALL
        SELECT 'test', t.id, t.test_number,
               coalesce(t.test_purpose, t.test_number), t.validity_status,
               t.execution_status, t.project_id, t.created_at,
               CASE WHEN lower(t.test_number) = :q THEN 0
                    WHEN lower(t.test_number) LIKE :prefix THEN 1
                    WHEN lower(coalesce(t.test_purpose, '')) LIKE :like THEN 2
                    ELSE 3 END
          FROM testing.tests t
         WHERE CAST(:may_test AS BOOLEAN)
           AND t.organization_id = :org
           AND (lower(t.test_number) LIKE :like
             OR lower(coalesce(t.test_purpose, '')) LIKE :like
             OR lower(coalesce(t.notes, '')) LIKE :like)

        UNION ALL
        SELECT 'failure', fl.id, fl.failure_code, fl.title, fl.severity,
               fl.status, fl.project_id, fl.created_at,
               CASE WHEN lower(fl.failure_code) = :q THEN 0
                    WHEN lower(fl.failure_code) LIKE :prefix THEN 1
                    WHEN lower(fl.title) LIKE :like THEN 2
                    ELSE 3 END
          FROM quality.failures fl
         WHERE CAST(:may_failure AS BOOLEAN)
           AND fl.organization_id = :org
           AND (lower(fl.failure_code) LIKE :like
             OR lower(fl.title) LIKE :like
             OR lower(coalesce(fl.description, '')) LIKE :like)

        UNION ALL
        SELECT 'research_investigation', ri.id, ri.investigation_code, ri.title,
               ri.research_question, ri.status, ri.project_id, ri.created_at,
               CASE WHEN lower(ri.investigation_code) = :q THEN 0
                    WHEN lower(ri.investigation_code) LIKE :prefix THEN 1
                    WHEN lower(ri.title) LIKE :like THEN 2
                    ELSE 3 END
          FROM research.investigations ri
         WHERE CAST(:may_research_investigation AS BOOLEAN)
           AND ri.organization_id = :org
           AND (lower(ri.investigation_code) LIKE :like
             OR lower(ri.title) LIKE :like
             OR lower(coalesce(ri.research_question, '')) LIKE :like)

        UNION ALL
        SELECT 'research_finding', rf.id, rf.finding_code, rf.subject,
               rf.confidence, rf.status, NULL::uuid, rf.created_at,
               CASE WHEN lower(rf.finding_code) = :q THEN 0
                    WHEN lower(rf.finding_code) LIKE :prefix THEN 1
                    WHEN lower(rf.subject) LIKE :like THEN 2
                    ELSE 3 END
          FROM research.findings rf
         WHERE CAST(:may_research_finding AS BOOLEAN)
           AND rf.organization_id = :org
           AND (lower(rf.finding_code) LIKE :like
             OR lower(rf.subject) LIKE :like
             OR lower(coalesce(rf.statement, '')) LIKE :like)

        UNION ALL
        -- ✅ `market_segment` MOVED OUT OF THE `state` SLOT. Codex P2: it is a
        -- taxonomy, not a lifecycle state, and the screen renders `state` in
        -- the state position -- so "Automotive refinish" appeared where a
        -- reader looks for "approved" or "withdrawn". A competitor product has
        -- no lifecycle column at all, so `state` is NULL, which is honest.
        SELECT 'competitor_product', cp.id, cp.product_code, cp.product_name,
               -- ⚠️ `concat_ws`, NOT `||`. SUPERVISOR. `market_segment` is
               -- nullable (056) and `manufacturer` is NOT NULL, so `a || b`
               -- yields NULL for a product with no segment -- dropping the
               -- MANUFACTURER, the one field that tells two same-named
               -- products apart. `concat_ws` skips nulls instead.
               concat_ws(' · ', cp.manufacturer, cp.market_segment), NULL::text,
               cp.project_id, cp.created_at,
               CASE WHEN lower(coalesce(cp.product_code, '')) = :q THEN 0
                    WHEN lower(coalesce(cp.product_code, '')) LIKE :prefix THEN 1
                    WHEN lower(cp.product_name) LIKE :like THEN 2
                    ELSE 3 END
          FROM competitors.products cp
         WHERE CAST(:may_competitor_product AS BOOLEAN)
           AND cp.organization_id = :org
           AND (lower(coalesce(cp.product_code, '')) LIKE :like
             OR lower(cp.product_name) LIKE :like
             OR lower(cp.manufacturer) LIKE :like)

        UNION ALL
        SELECT 'document', kd.id, NULL, kd.title, kd.source, kd.classification,
               kd.project_id, kd.ingested_at,
               CASE WHEN lower(kd.title) = :q THEN 0
                    WHEN lower(kd.title) LIKE :prefix THEN 1
                    WHEN lower(kd.title) LIKE :like THEN 2
                    ELSE 3 END
          FROM knowledge.documents kd
         WHERE CAST(:may_document AS BOOLEAN)
           AND kd.organization_id = :org
           AND (lower(kd.title) LIKE :like
             OR lower(coalesce(kd.source, '')) LIKE :like)

        UNION ALL
        SELECT 'opportunity', o.id, o.opportunity_code, o.title,
               o.product_family, o.status, NULL::uuid, o.created_at,
               CASE WHEN lower(o.opportunity_code) = :q THEN 0
                    WHEN lower(o.opportunity_code) LIKE :prefix THEN 1
                    WHEN lower(o.title) LIKE :like THEN 2
                    ELSE 3 END
          FROM innovation.opportunities o
         WHERE CAST(:may_opportunity AS BOOLEAN)
           AND o.organization_id = :org
           AND (lower(o.opportunity_code) LIKE :like
             OR lower(o.title) LIKE :like
             OR lower(coalesce(o.market_need, '')) LIKE :like)

        UNION ALL
        -- ⚠️ NO `organization_id` HERE, AND THAT IS NOT AN OVERSIGHT.
        -- `public_intel` is the anonymous-readable catalogue; its rows belong
        -- to no tenant. The boundary that matters for it is publication:
        -- a `draft` row is an agent's unreviewed proposal, and only a human
        -- may publish one (commit 775285c). Withdrawn rows stay withdrawn.
        -- ✅ Same correction as the competitor branch above: `category` is a
        -- taxonomy. Here `state` CAN be a real state -- the publication status
        -- the branch already filters on -- so it carries that rather than NULL.
        SELECT 'catalogue_product', pp.id, pp.product_code, pp.product_name,
               -- Same nullability trap as the competitor branch: `category`
               -- is nullable, `pm.name` is not.
               concat_ws(' · ', pm.name, pp.category), pp.publication_status::text,
               NULL::uuid, pp.created_at,
               CASE WHEN lower(coalesce(pp.product_code, '')) = :q THEN 0
                    WHEN lower(coalesce(pp.product_code, '')) LIKE :prefix THEN 1
                    WHEN lower(pp.product_name) LIKE :like THEN 2
                    ELSE 3 END
          FROM public_intel.products pp
          JOIN public_intel.manufacturers pm ON pm.id = pp.manufacturer_id
         WHERE CAST(:may_catalogue_product AS BOOLEAN)
           AND pp.publication_status = 'published'
           AND pm.publication_status = 'published'
           AND (lower(coalesce(pp.product_code, '')) LIKE :like
             OR lower(pp.product_name) LIKE :like
             OR lower(pm.name) LIKE :like)
    )
    SELECT h.record_type, h.id, h.code, h.title, h.subtitle, h.state,
           h.project_id, h.created_at, h.score,
           -- 🔴 THE ID THE DETAIL SCREEN OPENS, WHICH IS NOT ALWAYS THE ROW'S.
           -- `/formulations/formula?version=` takes a `formula_versions.id`;
           -- every other detail screen takes the row's own id. Resolved here,
           -- in one lateral, rather than by giving fifteen branches a column
           -- fourteen of them would fill with `h.id`.
           --
           -- A formula with no version yet yields NULL and therefore no link,
           -- which is correct: there is no version for the workspace to open.
           CASE WHEN h.record_type = 'formula' THEN fv.id ELSE h.id END AS link_id
      FROM hits h
      LEFT JOIN LATERAL (
          SELECT v.id
            FROM formulations.formula_versions v
           WHERE h.record_type = 'formula'
             AND v.formula_id = h.id
           ORDER BY v.version_number DESC
           LIMIT 1
      ) fv ON TRUE
     ORDER BY h.score ASC, h.created_at DESC, h.title ASC
     LIMIT :limit
    """
)


def global_search(
    session: Session,
    *,
    organization_id: uuid.UUID,
    permissions: frozenset[str] | set[str],
    question: str,
    limit: int = MAX_SEARCH_RESULTS,
    types: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Records matching `question`, inside the caller's permission boundary.

    `permissions` is the caller's own permission set — passed in rather than
    read from a session variable, because a function that cannot identify its
    caller cannot authorize the call, and this one is reached from both the
    HTTP route and the agent tier.

    `types`, when given, narrows the search to those record types. It can only
    ever *remove* branches: a caller asking for `material` without
    `material.view` still gets nothing, because the type filter is combined
    with the permission gate by `and`, never by `or`.
    """
    cleaned = question.strip()
    if not cleaned:
        raise SearchError("a search needs something to search for")
    if len(cleaned) < MIN_QUERY_LENGTH:
        raise SearchError(
            f"a search needs at least {MIN_QUERY_LENGTH} characters — "
            "one letter matches most of the database and cannot use an index"
        )
    if len(cleaned) > 200:
        raise SearchError("a search term this long is a paste, not a query")

    if types is not None:
        unknown = sorted(set(types) - set(_BY_TYPE))
        if unknown:
            named = ", ".join(unknown)
            raise SearchError(f"not a record type this system holds: {named}")

    lowered = cleaned.lower()
    # `\` is LIKE's escape character and `%`/`_` are its wildcards. A caller
    # searching for "100%" means the three characters, not "100 followed by
    # anything" -- and a lone "%" would otherwise return the whole database.
    escaped = lowered.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")

    params: dict[str, Any] = {
        "org": organization_id,
        "q": lowered,
        "like": f"%{escaped}%",
        "prefix": f"{escaped}%",
        # 🔴 ONE MORE THAN ASKED FOR. CODEX P2: `truncated` USED TO LIE.
        #
        # It was computed as `len(results) == limit`, which is also true when
        # the answer is exactly complete — the screen then said "the list is
        # capped; narrow the search" about a result set that was whole.
        # Fetching one extra row makes the question answerable rather than
        # guessable: more rows than asked for means there were more.
        "limit": max(1, min(int(limit), MAX_SEARCH_RESULTS)) + 1,
    }
    for entry in SEARCHABLE:
        wanted = types is None or entry.record_type in types
        held = entry.permission is None or entry.permission in permissions
        params[f"may_{entry.record_type}"] = wanted and held

    # 🔴 CODEX P1 — BOUND THE WORK, NOT ONLY THE RESPONSE. `LOCAL` scopes this
    # to the current transaction, so it cannot leak into anything else running
    # on this connection afterwards. A search that exceeds it is cancelled by
    # PostgreSQL and surfaces as a refusal, not as a hung request.
    #
    # ⚠️ `set_config`, NOT `SET LOCAL`. `SET LOCAL statement_timeout = :ms` is a
    # syntax error -- SET takes a literal, never a bind parameter, and
    # PostgreSQL reports it as `syntax error at or near "$1"`. `set_config` is
    # an ordinary function, so its arguments ARE values. Same reason
    # `has_table_privilege` takes the table name as a bind parameter in d0775ab.
    # Its third argument `true` is what makes it transaction-local.
    session.execute(
        text("SELECT set_config('statement_timeout', :ms, true)"),
        {"ms": str(STATEMENT_TIMEOUT_MS)},
    )

    try:
        rows = session.execute(_STATEMENT, params).mappings().all()
    except OperationalError as exc:
        # 🔴 NO `session.rollback()` HERE, AND THE REPOSITORY'S OWN GUARD IS
        # WHY. `tests/test_no_transaction_destroyers.py` failed on the first
        # version of this handler, which rolled back to leave the session
        # usable.
        #
        # `Session.rollback()` always ends the TOPMOST transaction, not the
        # statement that failed. That is harmless while this function is the
        # whole request and destructive the moment it is not -- and composing
        # this service into a larger unit of work is the stated plan for the
        # agent tier, three paragraphs into this module's docstring. The two
        # defects that rule was written for (`open_failure`, `record_driver`)
        # were both found by looking at the call that introduced the
        # composition, not by reading the function.
        #
        # So the exception propagates and `session_scope` -- which owns the
        # transaction -- ends it. Nothing runs another statement on this
        # session in between: the route returns through the raise.
        if "canceling statement due to statement timeout" not in str(exc).lower():
            raise
        raise SearchTooBroadError(
            "that search matched too much of the database to complete — "
            "add a few more characters, or narrow it to one record type"
        ) from exc

    asked_for = max(1, min(int(limit), MAX_SEARCH_RESULTS))
    truncated = len(rows) > asked_for

    out: list[dict[str, Any]] = []
    for row in rows[:asked_for]:
        entry = _BY_TYPE[row["record_type"]]
        link_id = row["link_id"]
        out.append(
            {
                "record_type": entry.record_type,
                "label": entry.label,
                "id": str(row["id"]),
                "code": row["code"],
                "title": row["title"],
                "subtitle": row["subtitle"],
                "state": row["state"],
                "project_id": str(row["project_id"]) if row["project_id"] else None,
                # None when this product has no detail screen for the type, or
                # when the row has nothing for one to open. The screen renders
                # those as text and offers `list_path`, because a dead link is
                # worse than no link.
                "path": (
                    entry.detail_path.format(id=link_id) if entry.detail_path and link_id else None
                ),
                "list_path": entry.list_path,
            }
        )
    return {"results": out, "truncated": truncated}


def searchable_types(
    permissions: frozenset[str] | set[str],
    types: tuple[str, ...] | None = None,
) -> list[dict[str, Any]]:
    """The record types this caller could get hits from, and the ones nobody can.

    A screen that offers a type filter must not offer a type the caller cannot
    search — and must not silently drop the two §29 names that have no table,
    because "no results" and "not held here" are different answers.

    🔴 `searched` AND `permitted` ARE TWO DIFFERENT FACTS. CODEX P2.

    This used to report only `permitted`, and the route called the result
    `searched`. With `types=material` that was simply false: fourteen branches
    did not run, and the response said they had. A field whose name is a claim
    about what the query DID must be computed from what the query did.

    So `permitted` answers "may this caller search it", `searched` answers "did
    this request search it", and they differ exactly when a type filter was
    supplied. The screen needs both: a type the caller may not search is a gap
    in their answer, while one they deselected is not.
    """
    rows = []
    for entry in SEARCHABLE:
        # A null permission means the data is public; the caller holds it by
        # virtue of being a caller at all.
        permitted = entry.permission is None or entry.permission in permissions
        rows.append(
            {
                "record_type": entry.record_type,
                "label": entry.label,
                "permission": entry.permission,
                "permitted": permitted,
                "searched": permitted and (types is None or entry.record_type in types),
                "has_detail_screen": entry.detail_path is not None,
                "list_path": entry.list_path,
            }
        )
    return rows
