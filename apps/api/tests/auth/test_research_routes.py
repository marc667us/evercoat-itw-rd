"""The research routes over real HTTP, and the permission contract.

🔴 WHY THIS FILE EXISTS, IN THE SAME WORDS I112 USED.

`tests/db/test_058_research.py` has 13 cases and every one of them is a DATABASE
case: constraints, policies, FORCE RLS, a trigger, two of them falsified by
breaking the database on purpose. It touches none of the 25 routes.

That is precisely the gap that made three real defects green on Phase 3 —
a refusal escaping as a 500 over an aborted transaction, a menu option the
database refused every time, and `_translate` returning the raw PostgreSQL
message as the response body. All three are route- or service-level behaviours
that a database test cannot observe by construction.

🔴 AND ONE GUARD HERE IS STRUCTURAL RATHER THAN ENUMERATED.

`test_no_write_route_is_gated_only_on_a_view_permission` parses this module's
own source, so a write route added next month is covered whether or not anybody
remembers this file exists. Its sibling
`test_accepting_a_proposal_requires_the_formula_permissions_too` is the specific
case: accepting a proposal produces a formula version through the same service
`/formulations/.../revise` uses, so requiring only `experiment.accept` would be
a second door to a controlled act with a weaker lock — the I104 shape.
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
ROUTES = API_ROOT / "app" / "api" / "research.py"


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def research_ctx(owner_session, lead_ctx) -> Iterator[dict[str, uuid.UUID]]:
    """A workspace on a project, and one that is organization-wide.

    🔴 IT COMMITS, BECAUSE THE ROUTE RUNS ON ITS OWN CONNECTION and cannot see
    an uncommitted transaction — and it therefore TEARS DOWN EXPLICITLY. A
    committing fixture without teardown leaks permanently; on 2026-08-28 that
    made CI's seed-idempotency gate fail while naming a file two directories
    away from the defect.

    The caller is granted the chemist role as well, because the six research
    permissions are split across roles and a `product_development_lead` holds
    neither `experiment.propose` nor `knowledge.promote` — measured against
    migration 058's own grants, not assumed.
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

    owner_session.execute(
        text("SELECT set_config('app.current_org', :o, true)"), {"o": str(org_id)}
    )
    owner_session.execute(
        text("SELECT set_config('app.current_user_id', :u, true)"), {"u": str(user_id)}
    )

    project_id = owner_session.execute(
        text(
            "INSERT INTO projects.projects (organization_id, project_code, name, "
            "confidentiality) VALUES (:o, :c, 'Research route project', 'normal') "
            "RETURNING id"
        ),
        {"o": org_id, "c": f"RTP-{suffix}"},
    ).scalar_one()

    def _workspace(project: uuid.UUID | None, code: str) -> uuid.UUID:
        return owner_session.execute(  # type: ignore[no-any-return]
            text(
                """
                INSERT INTO research.investigations
                    (organization_id, project_id, investigation_code, title,
                     research_question, owner_user_id, opened_by)
                VALUES (:o, :p, :c, 'Route workspace', 'Does this route work?', :u, :u)
                RETURNING id
                """
            ),
            {"o": org_id, "p": project, "c": code, "u": user_id},
        ).scalar_one()

    scoped = _workspace(project_id, f"RES-RT-{suffix}")
    orgwide = _workspace(None, f"RES-OW-{suffix}")
    owner_session.commit()

    yield {
        "org_id": org_id,
        "user_id": user_id,
        "project_id": project_id,
        "scoped": scoped,
        "orgwide": orgwide,
        "suffix": suffix,
    }

    owner_session.rollback()
    owner_session.begin()
    owner_session.execute(
        text("SELECT set_config('app.current_org', :o, true)"), {"o": str(org_id)}
    )
    owner_session.execute(
        text("SELECT set_config('app.current_user_id', :u, true)"), {"u": str(user_id)}
    )
    # ⚠️ NO APPROVAL ROUTES ARE REMOVED HERE, BECAUSE NONE ARE CREATED --
    # see `test_submitting_is_covered_here_only_by_its_refusal_and_this_says_why`.
    # An earlier draft of this teardown deleted them and was refused outright:
    # `workflow.approval_route_steps is append-only; DELETE is not permitted`.
    for statement in (
        "DELETE FROM research.experiment_proposals WHERE organization_id = :o",
        "DELETE FROM research.knowledge_gaps WHERE organization_id = :o",
        "DELETE FROM research.hypotheses WHERE organization_id = :o",
        "DELETE FROM research.evidence WHERE organization_id = :o",
        "DELETE FROM research.findings WHERE organization_id = :o",
        "DELETE FROM research.sources WHERE organization_id = :o",
        "DELETE FROM research.questions WHERE organization_id = :o",
        "DELETE FROM research.investigations WHERE organization_id = :o",
        "DELETE FROM projects.projects WHERE id = :p AND organization_id = :o",
    ):
        owner_session.execute(text(statement), {"o": org_id, "p": project_id})
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
# The permission contract — STATIC, because the defect class is structural
# ---------------------------------------------------------------------------


def _handlers() -> list[tuple[str, str, str]]:
    """(verb, first decorator line, permission expression) for every route here.

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
        # 🔴 THE WHOLE DECORATOR, NOT ITS FIRST LINE. A multi-line
        # `@router.post(` puts the PATH on line two, so a first-line summary
        # would make every path-matching assertion below search "" and find
        # nothing -- passing, while measuring nothing.
        summary = " ".join(head.split())[:200]
        found.append((verb, summary, perms.group(1) if perms else ""))
    return found


def test_the_parser_finds_the_routes_it_is_meant_to_check() -> None:
    """The guard on the guard.

    A regex that stops matching turns every assertion below into a test that
    proves nothing — and it would still be green. `test_054` shipped exactly
    that shape: a refusal matching zero rows, reporting a clean `INSERT 0 0`.
    """
    handlers = _handlers()
    assert len(handlers) >= 20, f"only {len(handlers)} routes parsed out of research.py"
    assert any(verb.lower() == "post" for verb, _, _ in handlers)
    assert any(verb.lower() == "get" for verb, _, _ in handlers)


def test_every_research_route_declares_a_permission() -> None:
    """A route with no permission is reachable by any authenticated member."""
    naked = [(v, s) for v, s, p in _handlers() if not p.strip()]
    assert not naked, f"research routes with no require_permission: {naked}"


def test_no_write_route_is_gated_only_on_a_view_permission() -> None:
    """Structural, so a route added next month is covered on arrival."""
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


def test_accepting_a_proposal_requires_the_formula_permissions_too() -> None:
    """🔴 THE SPECIFIC CASE, AND THE ONE MOST LIKELY TO BE 'SIMPLIFIED' AWAY.

    `POST /proposals/{id}/accept` calls `formulations.revise_version`, which
    `/formulations/versions/{id}/revise` gates on `formula.clone` AND
    `formula.modify_draft`. Dropping either from this route would leave a
    second door to a controlled act with a weaker lock, and nothing else in
    the suite would notice: the route would still work, for the person testing
    it, who holds all three.
    """
    accept = [
        perms
        for verb, summary, perms in _handlers()
        if verb.lower() == "post" and "proposals/{proposal_id}/accept" in summary
    ]
    assert accept, "the accept route was not found; has its path changed?"
    codes = set(re.findall(r'"([a-z_]+\.[a-z_]+)"', accept[0]))
    assert {"experiment.accept", "formula.clone", "formula.modify_draft"} <= codes, codes
    assert "require_all=True" in accept[0], (
        "the accept route names the three permissions but does not require ALL "
        "of them, so holding any one is enough — which is the same hole with "
        "an extra step"
    )


# ---------------------------------------------------------------------------
# Anonymous callers
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    ["/api/research", "/api/research/findings", "/api/research/proposals"],
)
def test_a_reader_refuses_without_a_token(client, path) -> None:
    response = client.get(path)
    assert response.status_code in (401, 403), (
        f"GET {path} answered {response.status_code} with no token"
    )


def test_a_writer_refuses_without_a_token(client) -> None:
    response = client.post("/api/research", json={"title": "x", "research_question": "y"})
    assert response.status_code in (401, 403)


# ---------------------------------------------------------------------------
# The unfiltered list — the shape that 500s and that no filtered test sees
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    ["/api/research", "/api/research/findings", "/api/research/proposals"],
)
def test_the_unfiltered_list_answers(client, research_ctx, auth, path) -> None:
    """🔴 THE CALL A BROWSER MAKES, WHICH A FILTERED TEST NEVER MAKES.

    An optional filter whose bind is compared to NULL without a CAST gives the
    planner no type to infer, and PostgreSQL refuses the WHOLE statement — but
    only when the filter is absent. On 2026-08-22 that returned 500 to every
    signed-in user on three of the five wired screens while the suite stayed
    green, because every test passed a filter value.
    """
    response = client.get(path, headers=auth)
    assert response.status_code == 200, response.text
    assert isinstance(response.json(), list)


def test_the_workspace_the_fixture_opened_is_in_the_list(client, research_ctx, auth) -> None:
    """The other direction: a 200 over an empty list would also pass above."""
    response = client.get("/api/research", headers=auth)
    assert response.status_code == 200, response.text
    ids = {row["id"] for row in response.json()}
    assert str(research_ctx["scoped"]) in ids
    assert str(research_ctx["orgwide"]) in ids


# ---------------------------------------------------------------------------
# The vertical, over HTTP
# ---------------------------------------------------------------------------


def test_a_workspace_can_be_opened_and_gets_a_code(client, research_ctx, auth) -> None:
    response = client.post(
        "/api/research",
        headers=auth,
        json={
            "title": "Sanding performance",
            "research_question": "What drives sand-through time?",
            "project_id": str(research_ctx["project_id"]),
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["investigation_code"].startswith("RES-"), body


def test_evidence_that_cites_nothing_is_refused_with_a_readable_message(
    client, research_ctx, auth
) -> None:
    """🔴 THE MESSAGE, NOT ONLY THE STATUS.

    Phase 3 shipped four constraints that fell through `_translate` to the
    generic branch, which returned the raw PostgreSQL message — schema, table
    and the constraint expression — as the response body. So this asserts what
    a client actually reads, and that it does NOT contain the constraint name.
    """
    response = client.post(
        f"/api/research/{research_ctx['scoped']}/evidence",
        headers=auth,
        json={"summary": "Trust me.", "stance": "supports"},
    )
    assert response.status_code == 422, response.text
    detail = response.json()["detail"]
    assert "must cite something" in detail, detail
    assert "evidence_cites_something" not in detail, (
        f"the constraint name leaked into the response body: {detail}"
    )


def test_a_finding_on_an_organization_wide_workspace_cannot_be_submitted(
    client, research_ctx, auth
) -> None:
    """🔴 THE REFUSAL SAYS WHAT TO DO, AND IT IS NOT A 500.

    `approvals.open_route` requires a project, and §1.2 deliberately allows an
    investigation to have none. Without this branch the submit would reach the
    approval service and raise — a design decision surfacing as a stack trace.
    """
    drafted = client.post(
        f"/api/research/{research_ctx['orgwide']}/findings",
        headers=auth,
        json={
            "subject": "Microsphere loading",
            "statement": "More loading sands sooner.",
            "applicability": "Lightweight polyester filler",
            "confidence": "moderate",
        },
    )
    assert drafted.status_code == 201, drafted.text

    response = client.post(
        f"/api/research/findings/{drafted.json()['id']}/submit",
        headers=auth,
    )
    assert response.status_code == 409, response.text
    detail = response.json()["detail"]
    assert "organization-wide" in detail, detail
    assert "project" in detail, detail


def test_submitting_is_covered_here_only_by_its_refusal_and_this_says_why() -> None:
    """🔴 A GAP, STATED RATHER THAN LEFT FOR SOMEBODY TO DISCOVER.

    The successful submit is NOT tested over HTTP, and that is a property of
    the system rather than an oversight:

      * the route runs on its own connection, so a fixture must COMMIT for the
        request to see its data -- `tests/auth/conftest.py` installs no
        `dependency_overrides` for `get_db`, measured, not assumed;
      * `submit_finding` opens an approval route, and
        `workflow.approval_route_steps` carries `audit.deny_mutation` on DELETE
        -- an UNCONDITIONAL trigger, so not even `evercoat_owner` can remove a
        step. §9 requires an approval decision to be permanent history;
      * `approval_routes.project_id` is a RESTRICT foreign key, so the project
        and therefore the organization cannot be removed either.

    A committing HTTP test of the success path would therefore leak an
    organization, a project and an approval route on EVERY run, permanently.
    That is the defect that made CI's seed-idempotency gate fail on 2026-08-28
    while naming a file two directories away.

    So the success path is asserted where it can be rolled back --
    `tests/db/test_058_research.py::test_submitting_a_finding_opens_a_route_and_promotion_follows_it`
    -- and what is asserted HERE is the refusal, which writes nothing.

    This test exists to keep that reasoning attached to the gap. If the
    approval engine ever gains a way to retire a route, delete this and write
    the HTTP test.
    """
    from pathlib import Path

    db_test = Path(__file__).resolve().parents[1] / "db" / "test_058_research.py"
    body = db_test.read_text(encoding="utf-8")
    assert "def test_submitting_a_finding_opens_a_route_and_promotion_follows_it" in body, (
        "the database-level cover for the submit path is gone; either it was "
        "renamed, in which case fix this pointer, or the success path is now "
        "untested in both places"
    )


def test_an_unapproved_finding_cannot_be_promoted(client, research_ctx, auth) -> None:
    """`knowledge.promote`'s first enforcement point, refusing the wrong case.

    The message must not be the trigger's raw text either: a client reads it.
    """
    drafted = client.post(
        f"/api/research/{research_ctx['scoped']}/findings",
        headers=auth,
        json={
            "subject": "Not approved yet",
            "statement": "Something plausible.",
            "applicability": "Filler family",
            "confidence": "low",
        },
    )
    assert drafted.status_code == 201, drafted.text

    response = client.post(
        f"/api/research/findings/{drafted.json()['id']}/promote",
        headers=auth,
    )
    assert response.status_code == 409, response.text
    detail = response.json()["detail"]
    assert "not been approved" in detail, detail
    assert "never been submitted" in detail, detail


def test_a_proposal_is_inert_and_rejecting_it_demands_a_reason(client, research_ctx, auth) -> None:
    """§20: a proposal changes nothing until a person decides.

    And a rejection with no reason teaches the next person nothing, so it is
    refused — asserted here because it is a service rule with no constraint
    behind it, which is the kind that quietly disappears.
    """
    proposed = client.post(
        f"/api/research/{research_ctx['scoped']}/proposals",
        headers=auth,
        json={
            "objective": "Improve sanding",
            "basis": "RF-0001",
            "variables": "Microsphere loading",
            "expected_direction": "Shorter sand-through time",
            "required_tests": "Density; sanding",
            "confidence": "moderate",
        },
    )
    assert proposed.status_code == 201, proposed.text
    assert proposed.json()["status"] == "proposed"
    proposal_id = proposed.json()["id"]

    blank = client.post(
        f"/api/research/proposals/{proposal_id}/reject",
        headers=auth,
        json={"decision_note": "   "},
    )
    assert blank.status_code == 409, blank.text
    assert "why" in blank.json()["detail"]

    rejected = client.post(
        f"/api/research/proposals/{proposal_id}/reject",
        headers=auth,
        json={"decision_note": "The loading is already at the process ceiling."},
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["status"] == "rejected"

    # A decision is taken once.
    again = client.post(
        f"/api/research/proposals/{proposal_id}/reject",
        headers=auth,
        json={"decision_note": "Changed my mind."},
    )
    assert again.status_code == 409, again.text


def test_the_hypothesis_reader_returns_what_the_writer_wrote(client, research_ctx, auth) -> None:
    """🔴 THIS READER DID NOT EXIST UNTIL THE SCREEN NEEDED IT.

    `record_hypothesis` and `decide_hypothesis` were written before anything
    could list what they wrote — a table with a writer, no reader and no
    control. Found while building the screen, which is why §10 requires the
    writer and its control in the same phase.
    """
    created = client.post(
        f"/api/research/{research_ctx['scoped']}/hypotheses",
        headers=auth,
        json={"statement": "Raising loading by 2% improves sanding."},
    )
    assert created.status_code == 201, created.text

    listed = client.get(
        f"/api/research/{research_ctx['scoped']}/hypotheses",
        headers=auth,
    )
    assert listed.status_code == 200, listed.text
    rows = listed.json()
    assert [row["id"] for row in rows] == [created.json()["id"]]
    assert rows[0]["status"] == "open"

    decided = client.post(
        f"/api/research/hypotheses/{created.json()['id']}/decide",
        headers=auth,
        json={"status": "refuted"},
    )
    assert decided.status_code == 200, decided.text
    assert decided.json()["status"] == "refuted"
