"""I112 — the competitor routes over real HTTP, and the permission contract.

🔴 WHY THIS FILE EXISTS.

`tests/db/test_056_competitor_intelligence.py` has 23 cases and they are all
DATABASE cases: constraints, triggers, RLS, two of them falsified by breaking
the database on purpose. It touches none of the 11 routes and none of the 11
service functions — and that is exactly why **three real defects were green**
when the Supervisor found them on 2026-08-28:

  1. `verify_evidence` had no `guarded_write` and no `except DBAPIError`, so a
     refusal 056 itself raises escaped as a **500 over an aborted transaction**
     instead of the 409 the design intended.
  2. `laboratory` was offered as an evidence source and the database refused it
     **every time** — a menu option nobody could use.
  3. `_translate` returned the raw PostgreSQL message — schema, table and the
     constraint expression — as the **response body** for four constraints.

Every one of those is a route- or service-level behaviour. A database test
cannot observe any of them by construction, and neither can a service test that
hands itself its own inputs: `test_document_upload_routes.py` records the same
lesson ("a service-level test cannot see a permission floor that is too low").

So these drive the real app through FastAPI's dependency graph, with real
tokens, and assert what a CLIENT receives.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import text

from app.main import app

API_ROOT = Path(__file__).resolve().parents[2]
ROUTES = API_ROOT / "app" / "api" / "competitors.py"


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def competitor_ctx(owner_session, lead_ctx) -> Iterator[dict[str, uuid.UUID]]:
    """Two competitor products, a sample on the first, and an approved label.

    🔴 IT COMMITS, BECAUSE THE ROUTE RUNS ON ITS OWN CONNECTION and cannot see
    an uncommitted transaction — and it therefore TEARS DOWN EXPLICITLY.
    A committing fixture without teardown leaks permanently: on 2026-08-28 that
    made CI's seed-idempotency gate fail while naming the seed, which is two
    files away from the defect.

    The caller is granted the chemist and QA roles, because a
    `product_development_lead` holds neither `material.edit` nor
    `compliance.review_sds` — measured, not assumed.
    """
    org_id = lead_ctx["org_id"]
    user_id = lead_ctx["user_id"]
    suffix = uuid.uuid4().hex[:8]

    owner_session.execute(
        text(
            """
            INSERT INTO core.member_roles (member_id, role_id)
            SELECT m.id, r.id
              FROM core.organization_members m, core.roles r
             WHERE m.user_id = :u AND m.organization_id = :o
               AND r.code IN ('product_development_chemist', 'qa_compliance_officer')
            ON CONFLICT DO NOTHING
            """
        ),
        {"u": user_id, "o": org_id},
    )

    # FORCE RLS binds the owner too; without the tenant declared these INSERTs
    # are refused, which is the guard working rather than a defect.
    owner_session.execute(
        text("SELECT set_config('app.current_org', :o, true)"), {"o": str(org_id)}
    )

    product_a, product_b = (
        owner_session.execute(
            text(
                "INSERT INTO competitors.products "
                "(organization_id, manufacturer, product_name, registered_by) "
                "VALUES (:o, 'Rival Chemicals', :n, :u) RETURNING id"
            ),
            {"o": org_id, "n": name, "u": user_id},
        ).scalar_one()
        for name in (f"Route A {suffix}", f"Route B {suffix}")
    )

    sample_a = owner_session.execute(
        text(
            "INSERT INTO competitors.samples "
            "(organization_id, competitor_product_id, sample_reference, registered_by) "
            "VALUES (:o, :p, :ref, :u) RETURNING id"
        ),
        {"o": org_id, "p": product_a, "ref": f"ROUTE-{suffix}", "u": user_id},
    ).scalar_one()

    label_a = owner_session.execute(
        text(
            """
            INSERT INTO materials.material_documents
                (organization_id, competitor_product_id, document_type, title,
                 storage_key, content_type, byte_size, checksum_sha256, status,
                 scan_status, scanner_name, scanner_version, scanned_at, uploaded_by)
            VALUES (:o, :p, 'label', 'Label for route tests', :key, 'application/pdf',
                    2048, :checksum, 'approved', 'clean', 'test-scanner', '1.0',
                    now(), :u)
            RETURNING id
            """
        ),
        {
            "o": org_id,
            "p": product_a,
            "key": f"test/route-{suffix}",
            "checksum": uuid.uuid4().hex * 2,
            "u": user_id,
        },
    ).scalar_one()
    owner_session.commit()

    yield {
        "org_id": org_id,
        "user_id": user_id,
        "product_a": product_a,
        "product_b": product_b,
        "sample_a": sample_a,
        "label_a": label_a,
    }

    owner_session.rollback()
    owner_session.begin()
    owner_session.execute(
        text("SELECT set_config('app.current_org', :o, true)"), {"o": str(org_id)}
    )
    for statement in (
        "DELETE FROM competitors.composition_evidence WHERE organization_id = :o",
        "DELETE FROM competitors.benchmarks WHERE organization_id = :o",
        "DELETE FROM competitors.samples WHERE organization_id = :o",
        "DELETE FROM materials.material_documents WHERE organization_id = :o",
        "DELETE FROM competitors.products WHERE organization_id = :o",
    ):
        owner_session.execute(text(statement), {"o": org_id})
    owner_session.execute(
        text(
            """
            DELETE FROM core.member_roles
             WHERE member_id IN (SELECT id FROM core.organization_members
                                  WHERE user_id = :u AND organization_id = :o)
               AND role_id IN (SELECT id FROM core.roles
                                WHERE code IN ('product_development_chemist',
                                               'qa_compliance_officer'))
            """
        ),
        {"u": user_id, "o": org_id},
    )
    owner_session.commit()


# ---------------------------------------------------------------------------
# The permission contract — a STATIC guard, because the defect was structural
# ---------------------------------------------------------------------------


def _handlers() -> list[tuple[str, str, str]]:
    """(verb, summary-or-path, permission expression) for every route in the module.

    Each decorator is read with its OWN handler. A lazy match across the file
    would bind a decorator to the next `require_permission` anywhere below it,
    so a handler with no permission at all would silently borrow its
    neighbour's — the hole `test_knowledge_routes.py` records having had.
    """
    source = ROUTES.read_text(encoding="utf-8")
    blocks = re.split(r"\n@router\.", source)[1:]
    found: list[tuple[str, str, str]] = []
    for block in blocks:
        verb = block.split("(", 1)[0].strip()
        head = block.split("\ndef ", 1)[0].split("\nasync def ", 1)[0]
        body = block[: block.find('"""')] if '"""' in block else block
        perms = re.search(r"require_permission\(([^)]*)\)", body, re.S)
        found.append((verb, head.splitlines()[0][:60], perms.group(1) if perms else ""))
    return found


def test_every_competitor_route_declares_a_permission() -> None:
    """A route with no permission is reachable by any authenticated member."""
    naked = [(v, s) for v, s, p in _handlers() if not p.strip()]
    assert not naked, f"competitor routes with no require_permission: {naked}"


def test_no_write_route_is_gated_only_on_a_view_permission() -> None:
    """🔴 THE GUARD FOR THE DEFECT CODEX RAISED AS P1 ON 2026-08-28.

    `POST /{id}/benchmarks` required only `test.view` — a READ permission on a
    WRITE route. Anybody who could merely look at tests could author competitor
    comparisons, and RLS cannot stop it: the writer is inside a project they
    legitimately reach, so the policy passes.

    Stated structurally rather than as a list of routes, so a write route added
    next month is covered without anybody remembering this file exists.
    """
    offenders = []
    for verb, summary, perms in _handlers():
        if verb.lower() != "post":
            continue
        codes = re.findall(r'"([a-z_]+\.[a-z_]+)"', perms)
        assert codes, f"POST {summary} names no permission code"
        if all(code.endswith(".view") for code in codes):
            offenders.append((summary, codes))
    assert not offenders, (
        "these WRITE routes are gated only on read permissions, so anybody who "
        f"can look can also write: {offenders}"
    )


# ---------------------------------------------------------------------------
# The two readers that did not exist — and refuse anonymously
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", ["samples", "benchmarks", "documents", "composition"])
def test_a_reader_refuses_without_a_token(client, competitor_ctx, path) -> None:
    """Every GET added for Phase 3 refuses an anonymous caller."""
    response = client.get(f"/api/competitors/{competitor_ctx['product_a']}/{path}")
    assert response.status_code in (401, 403), (
        f"GET /{path} answered {response.status_code} with no token"
    )


def test_the_sample_reader_returns_the_sample_the_fixture_registered(
    client, auth, competitor_ctx
) -> None:
    """🔴 `competitors.samples` HAD A WRITER AND NO READER AT ALL.

    The row could be created by a route and read by nothing, which is the
    defect class this project has counted 23+ times. This is the assertion that
    the reader exists and answers.
    """
    response = client.get(f"/api/competitors/{competitor_ctx['product_a']}/samples", headers=auth)
    assert response.status_code == 200, response.text
    references = [row["sample_reference"] for row in response.json()]
    assert len(references) == 1, f"expected the one registered sample, got {references}"
    assert response.json()[0]["evidence_count"] == 0


def test_the_benchmark_reader_answers_before_anything_is_recorded(
    client, auth, competitor_ctx
) -> None:
    """An empty list, not a 404: the product exists and has no comparisons yet."""
    response = client.get(
        f"/api/competitors/{competitor_ctx['product_a']}/benchmarks", headers=auth
    )
    assert response.status_code == 200, response.text
    assert response.json() == []


# ---------------------------------------------------------------------------
# The three defects that a database test could not see
# ---------------------------------------------------------------------------


def _record(client, auth, product_id, **overrides):
    payload = {
        "component_name": "Styrene",
        "evidence_source": "document",
        "evidence_grade": "A",
        "source_locator": "Section 3",
    }
    payload.update(overrides)
    return client.post(f"/api/competitors/{product_id}/evidence", json=payload, headers=auth)


def test_a_laboratory_claim_without_a_sample_is_refused_in_words(
    client, auth, competitor_ctx
) -> None:
    """🔴 DEFECT 2 AND 3 TOGETHER, AND NEITHER WAS VISIBLE FROM THE DATABASE.

    `composition_evidence_laboratory_shape` requires a sample or a test. The
    screen offered "Our own laboratory result" and sent neither, so the request
    was refused every time — and the refusal arrived as the RAW PostgreSQL
    message, naming the schema, the table and the constraint expression.

    Both halves are asserted: a 4xx rather than a 500, and a body that reads as
    an instruction rather than as a database error.
    """
    response = _record(client, auth, competitor_ctx["product_a"], evidence_source="laboratory")
    assert response.status_code == 422, response.text
    detail = response.json()["detail"]
    assert "sample" in detail.lower() or "test" in detail.lower(), detail
    for leak in ("composition_evidence_laboratory_shape", "competitors.", "CHECK"):
        assert leak not in detail, f"the response body leaks database internals: {detail}"


def test_an_inverted_concentration_range_is_refused_in_words(client, auth, competitor_ctx) -> None:
    """From 50 to 10 was enough to disclose the constraint expression."""
    response = _record(
        client,
        auth,
        competitor_ctx["product_a"],
        source_document_id=str(competitor_ctx["label_a"]),
        concentration_low="50",
        concentration_high="10",
    )
    assert response.status_code == 422, response.text
    detail = response.json()["detail"]
    assert "composition_evidence_range_ordered" not in detail, detail


def test_verifying_an_observation_is_a_refusal_not_a_crash(client, auth, competitor_ctx) -> None:
    """🔴 DEFECT 1. `verify_evidence` WAS THE ONLY WRITE WITH NO `guarded_write`.

    An observation can never be `verified` — there is nothing anybody else can
    re-check, and `composition_evidence_verifiable_source` says so. That
    refusal escaped as a raw `DBAPIError` past `post_grade`'s
    `except CompetitorError`, giving a 500 over an aborted transaction instead
    of a 409.

    The proof it was meant to be translated: `_translate` already carried a
    branch for this refusal, and the branch was unreachable.
    """
    created = _record(
        client,
        auth,
        competitor_ctx["product_a"],
        evidence_source="manual_observation",
        rationale="Read from the back of the tin",
        sample_id=str(competitor_ctx["sample_a"]),
    )
    assert created.status_code == 201, created.text
    evidence_id = created.json()["id"]

    response = client.post(
        f"/api/competitors/evidence/{evidence_id}/grade",
        json={"confidence": "verified"},
        headers=auth,
    )
    assert response.status_code != 500, (
        "verifying an observation crashed instead of refusing -- the DBAPIError "
        "escaped the service again"
    )
    assert response.status_code == 409, response.text
    assert "verified" in response.json()["detail"].lower()


def test_a_claim_can_still_be_graded_to_a_reachable_confidence(
    client, auth, competitor_ctx
) -> None:
    """🔴 THE OTHER DIRECTION — A GRADE ROUTE THAT REFUSED EVERYTHING WOULD ALSO
    PASS THE TEST ABOVE.

    `POST /evidence/{id}/grade` had no browser caller at all until 2026-08-28,
    so nothing had ever exercised its success path.
    """
    created = _record(
        client,
        auth,
        competitor_ctx["product_a"],
        source_document_id=str(competitor_ctx["label_a"]),
    )
    assert created.status_code == 201, created.text

    response = client.post(
        f"/api/competitors/evidence/{created.json()['id']}/grade",
        json={"confidence": "supported"},
        headers=auth,
    )
    assert response.status_code == 200, response.text
    assert response.json()["confidence"] == "supported"


def test_a_sample_of_another_product_cannot_back_a_claim_over_http(
    client, auth, competitor_ctx
) -> None:
    """Migration 057, through the API this time rather than through SQL.

    The schema hole was latent only because no client sent `sample_id`; the
    browser now does, so the refusal has to be a clean 409 rather than a 500.
    """
    response = _record(
        client,
        auth,
        competitor_ctx["product_b"],
        evidence_source="manual_observation",
        rationale="Read from the tin",
        sample_id=str(competitor_ctx["sample_a"]),
    )
    assert response.status_code == 409, response.text
    assert "product" in response.json()["detail"].lower()
