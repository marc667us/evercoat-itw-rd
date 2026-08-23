"""I78 — the document list reports how much of the library it is showing.

`list_documents` caps the page at `limit` (100 by default) and the route never
passed one, so past that point the oldest documents simply stopped appearing:
no page two, no count, no notice. That is the same unanswerable *"why is my
document not here?"* the `chunks` column was added to prevent, one level up.

🔴 THIS FUNCTION HAD NO TEST OF ANY KIND BEFORE THIS FILE. Changing its
response from a bare array to `{documents, total, limit}` broke nothing in the
suite — 30 knowledge tests passed against the new shape without a line
changing, because `test_knowledge_routes.py` only asserts which permission the
route requires and never looks at the body. So the docstring's central claim,
that RLS alone decides what appears and there is no second predicate here, was
never checked either.

Both are checked below, and the count is checked as carefully as the page: a
`total` that ignored RLS would confidently report a number the reader is not
permitted to reach, which is a worse defect than the silent truncation it was
added to fix.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.embedding import HashingEmbedding
from app.domains.knowledge.service import ingest_document, list_documents


def _scope(session: Session, org: uuid.UUID, user: uuid.UUID) -> None:
    session.execute(text("SELECT set_config('app.current_org', :o, true)"), {"o": str(org)})
    session.execute(text("SELECT set_config('app.current_user_id', :u, true)"), {"u": str(user)})


@pytest.fixture
def two_org_libraries(owner_session: Session, app_session: Session) -> Iterator[dict[str, Any]]:
    """Three documents in organization A, one in organization B.

    The B document exists so the count can be wrong in the direction that
    matters. A fixture with one tenant would let a `count(*)` with no
    predicate at all pass.
    """
    suffix = uuid.uuid4().hex[:8]
    embedder = HashingEmbedding()
    ids: dict[str, Any] = {"suffix": suffix}

    for label, count in (("a", 3), ("b", 1)):
        org = owner_session.execute(
            text("INSERT INTO core.organizations (code, name) VALUES (:c, :n) RETURNING id"),
            {"c": f"I78-{label.upper()}-{suffix}", "n": f"I78 library {label}"},
        ).scalar_one()
        user = owner_session.execute(
            text(
                "INSERT INTO core.users (keycloak_sub, email, display_name) "
                "VALUES (:s, :e, 'I78 reader') RETURNING id"
            ),
            {"s": str(uuid.uuid4()), "e": f"i78-{label}-{suffix}@example.test"},
        ).scalar_one()
        owner_session.execute(
            text(
                "INSERT INTO core.organization_members (organization_id, user_id, status) "
                "VALUES (:o, :u, 'active')"
            ),
            {"o": org, "u": user},
        )

        _scope(owner_session, org, user)
        for n in range(count):
            ingest_document(
                owner_session,
                organization_id=org,
                actor_id=user,
                title=f"{label}-doc-{n}-{suffix}",
                body=f"Post-cure guidance number {n} for library {label} {suffix}.",
                source="procedure",
                embedder=embedder,
                project_id=None,
                classification="INTERNAL",
            )
        ids[f"org_{label}"] = org
        ids[f"user_{label}"] = user

    owner_session.commit()
    yield ids

    app_session.rollback()
    owner_session.rollback()
    for org_key in ("org_a", "org_b"):
        org = ids[org_key]
        owner_session.execute(
            text("DELETE FROM knowledge.chunks WHERE organization_id = :o"), {"o": org}
        )
        owner_session.execute(
            text("DELETE FROM knowledge.documents WHERE organization_id = :o"), {"o": org}
        )
        owner_session.execute(
            text("DELETE FROM core.organization_members WHERE organization_id = :o"),
            {"o": org},
        )
    owner_session.execute(
        text("DELETE FROM core.users WHERE id = ANY(:u)"),
        {"u": [ids["user_a"], ids["user_b"]]},
    )
    owner_session.execute(
        text("DELETE FROM core.organizations WHERE id = ANY(:o)"),
        {"o": [ids["org_a"], ids["org_b"]]},
    )
    owner_session.commit()


def test_the_listing_shows_this_organization_and_no_other(
    app_session: Session, two_org_libraries: dict[str, Any]
) -> None:
    """The docstring's claim — RLS decides, and there is no second predicate.

    Never asserted before this file existed.
    """
    fx = two_org_libraries
    _scope(app_session, fx["org_a"], fx["user_a"])
    page = list_documents(app_session, organization_id=fx["org_a"])

    titles = {d["title"] for d in page["documents"]}
    assert len(titles) == 3, f"organization A sees {len(titles)} of its 3 documents"
    assert all(t.startswith("a-doc-") for t in titles), (
        f"organization A's listing contains another tenant's documents: {sorted(titles)}"
    )


def test_the_total_counts_only_what_the_reader_may_reach(
    app_session: Session, two_org_libraries: dict[str, Any]
) -> None:
    """The count is bounded by the same thing the page is: RLS.

    `total` exists so the screen can say "showing 100 of 247", and a total
    larger than the reader may reach would leak how much another tenant holds
    through a number on this screen. Organization B's document is in the table
    and is not in A's total.

    🔴 WHAT THIS TEST PROVES, AND WHAT IT CANNOT. It was written believing the
    explicit `WHERE organization_id = :org` in the count was the control, and
    **falsification showed that is false**: with that predicate deleted
    entirely, all four tests here still pass. RLS on `knowledge.documents`
    already bounds the count for `evercoat_app`, exactly as it bounds the page,
    so the predicate is redundancy rather than the boundary.

    That is the same shape as migration 044's UPDATE policy, measured the same
    morning: check which mechanism is load-bearing before the comment claims
    one is. This test therefore asserts the BEHAVIOUR the reader depends on —
    the number is scoped — and does not claim to pin the mechanism. Pinning it
    would need a role that bypasses RLS, which the application never uses.
    """
    fx = two_org_libraries
    _scope(app_session, fx["org_a"], fx["user_a"])
    page = list_documents(app_session, organization_id=fx["org_a"])

    assert page["total"] == 3, (
        f"total is {page['total']} where organization A holds 3 documents. A "
        "count that reaches another tenant's rows discloses the size of their "
        "library through a number on this screen."
    )


def test_a_truncated_page_reports_the_whole_size(
    app_session: Session, two_org_libraries: dict[str, Any]
) -> None:
    """I78 stated directly: the page is short, and it says so.

    🔴 Proved by falsification: with `total` computed as `len(rows)` — the
    obvious wrong implementation, and what the screen fell back to before this
    shipped — this returns 2 and fails.
    """
    fx = two_org_libraries
    _scope(app_session, fx["org_a"], fx["user_a"])
    page = list_documents(app_session, organization_id=fx["org_a"], limit=2)

    assert len(page["documents"]) == 2, "the limit was not applied"
    assert page["limit"] == 2, "the response does not report the limit it applied"
    assert page["total"] == 3, (
        f"a page of 2 reported a total of {page['total']}. The reader cannot "
        "tell that a third document exists, which is exactly the silent "
        "truncation I78 names."
    )


def test_an_untruncated_page_is_not_reported_as_truncated(
    app_session: Session, two_org_libraries: dict[str, Any]
) -> None:
    """The positive twin, and it is not decoration.

    A screen that warns about hidden documents on a complete list teaches the
    reader to ignore the warning, and then it is worth nothing on the day the
    list really is short. `total == len(documents)` is what the notice keys on.
    """
    fx = two_org_libraries
    _scope(app_session, fx["org_a"], fx["user_a"])
    page = list_documents(app_session, organization_id=fx["org_a"])

    assert page["total"] == len(page["documents"]), (
        f"total {page['total']} against a page of {len(page['documents'])} on a "
        "library small enough to fit. The screen would show a truncation "
        "notice that is not true."
    )
