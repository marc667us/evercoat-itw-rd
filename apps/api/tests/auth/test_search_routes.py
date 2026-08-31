"""Global search over real HTTP — spec §29, and its permission contract.

🔴 THE ONE TEST THAT MATTERS HERE IS THE BOTH-DIRECTIONS ONE.

`/api/search` is gated on authentication rather than on a permission, because
a top-bar search box is reachable by all ten roles. That makes the per-record-
type gate the only authorization in the feature — and a gate asserted in one
direction is not a gate. This repository has counted six that could not fail.

So `test_search_filters_by_permission_in_both_directions` runs the SAME query
for two members of the SAME organization over the SAME material, and asserts
the material comes back for the one holding `material.view` and does not for
the one who does not. If the permission gate were deleted, the second half
goes red. That is the falsification, and it was run.

⚠️ THE FIXTURE COMMITS, SO IT TEARS DOWN EXPLICITLY. The route runs on its own
connection and cannot see an uncommitted transaction. A committing fixture
without teardown leaks permanently, and on 2026-08-28 that made CI's seed
idempotency gate fail while naming a file two directories away from the defect.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import text

from app.domains.search.service import _ABSENT_TABLES, ABSENT, SEARCHABLE
from app.main import app

API_ROOT = Path(__file__).resolve().parents[2]
SERVICE = API_ROOT / "app" / "domains" / "search" / "service.py"

ORG_HEADER = "X-Organization-Id"


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def search_ctx(owner_session, lead_ctx, make_token) -> Iterator[dict[str, object]]:
    """A material, and a second member who may not see materials.

    `executive_viewer` is chosen because it is the role that actually lacks
    `material.view` while still holding `project.view` — measured against
    `core.role_permissions`, not assumed. That combination is what makes the
    test able to distinguish "filtered by permission" from "sees nothing at
    all": the viewer must still get the PROJECT hit in the same response.
    """
    org_id = lead_ctx["org_id"]
    suffix = uuid.uuid4().hex[:8]
    token = f"zetaxylene{suffix}"

    material_id = owner_session.execute(
        text(
            """
            INSERT INTO materials.materials
                (organization_id, material_code, name, category, role, status,
                 description, created_by)
            VALUES (:o, :code, :name, 'resin', 'binder', 'approved', :descr, :by)
            RETURNING id
            """
        ),
        {
            "o": org_id,
            "code": f"RM-{suffix[:6].upper()}",
            "name": f"Test resin {token}",
            "descr": "created by test_search_routes",
            "by": lead_ctx["user_id"],
        },
    ).scalar_one()

    # The project the lead already owns, renamed so the same query string
    # matches BOTH a material and a project. Without that, "the viewer got
    # nothing" would be ambiguous between the gate working and the search
    # being broken.
    owner_session.execute(
        text("UPDATE projects.projects SET name = :n WHERE id = :p"),
        {"n": f"Programme {token}", "p": lead_ctx["mine"]},
    )

    viewer_sub = f"search-viewer-{suffix}"
    viewer_id = owner_session.execute(
        text(
            "INSERT INTO core.users (keycloak_sub, email, display_name) "
            "VALUES (:s, :e, 'Search Viewer') RETURNING id"
        ),
        {"s": viewer_sub, "e": f"{viewer_sub}@example.test"},
    ).scalar_one()
    viewer_member_id = owner_session.execute(
        text(
            "INSERT INTO core.organization_members "
            "(organization_id, user_id, email, display_name) "
            "SELECT :o, :u, u.email, u.display_name FROM core.users u "
            "WHERE u.id = :u RETURNING id"
        ),
        {"o": org_id, "u": viewer_id},
    ).scalar_one()
    owner_session.execute(
        text(
            "INSERT INTO core.member_roles (member_id, role_id) "
            "SELECT :m, id FROM core.roles WHERE code = 'executive_viewer'"
        ),
        {"m": viewer_member_id},
    )
    # The viewer must be a member of the project, or RLS -- not the permission
    # gate -- would be the thing hiding the project hit, and the test would
    # prove the wrong mechanism.
    owner_session.execute(
        text(
            "INSERT INTO projects.project_members "
            "(organization_id, project_id, user_id, project_role) "
            "VALUES (:o, :p, :u, 'observer') ON CONFLICT DO NOTHING"
        ),
        {"o": org_id, "p": lead_ctx["mine"], "u": viewer_id},
    )
    owner_session.commit()

    yield {
        "org_id": org_id,
        "token": token,
        "material_id": material_id,
        "material_code": f"RM-{suffix[:6].upper()}",
        "project_id": lead_ctx["mine"],
        "lead_auth": {
            "Authorization": f"Bearer {make_token(sub=lead_ctx['sub'])}",
            ORG_HEADER: str(org_id),
        },
        "viewer_auth": {
            "Authorization": f"Bearer {make_token(sub=viewer_sub)}",
            ORG_HEADER: str(org_id),
        },
    }

    owner_session.rollback()
    owner_session.execute(
        text("DELETE FROM projects.project_members WHERE user_id = :u"), {"u": viewer_id}
    )
    owner_session.execute(
        text("DELETE FROM core.member_roles WHERE member_id = :m"), {"m": viewer_member_id}
    )
    owner_session.execute(
        text("DELETE FROM core.organization_members WHERE id = :m"), {"m": viewer_member_id}
    )
    owner_session.execute(text("DELETE FROM core.users WHERE id = :u"), {"u": viewer_id})
    owner_session.execute(text("DELETE FROM materials.materials WHERE id = :m"), {"m": material_id})
    owner_session.commit()


def _types(payload: dict, record_type: str) -> list[dict]:
    return [r for r in payload["results"] if r["record_type"] == record_type]


# ---------------------------------------------------------------------------
# The permission contract
# ---------------------------------------------------------------------------


def test_search_filters_by_permission_in_both_directions(client, search_ctx):
    """The same query, the same organization, the same material, two callers.

    🔴 BOTH HALVES ARE THE TEST. The first alone would pass over a search that
    ignores permissions entirely; the second alone would pass over a search
    that is simply broken.
    """
    q = {"q": search_ctx["token"]}

    holder = client.get("/api/search", params=q, headers=search_ctx["lead_auth"])
    assert holder.status_code == 200, holder.text
    held = holder.json()

    denied = client.get("/api/search", params=q, headers=search_ctx["viewer_auth"])
    assert denied.status_code == 200, denied.text
    withheld = denied.json()

    # Direction 1 -- the holder of `material.view` gets the material.
    assert [r["id"] for r in _types(held, "material")] == [str(search_ctx["material_id"])]

    # Direction 2 -- the caller without it gets none of them...
    assert _types(withheld, "material") == []

    # ...and this is why that is the permission gate and not a broken search:
    # the very same response carries the project, which the viewer MAY see.
    assert [r["id"] for r in _types(withheld, "project")] == [str(search_ctx["project_id"])]


def test_a_type_the_caller_cannot_search_is_reported_as_such(client, search_ctx):
    """ "Not searched" and "no results" are different answers.

    A screen that renders an empty material section for the executive viewer
    would be telling them this organization holds no matching materials, which
    is false.
    """
    body = client.get(
        "/api/search", params={"q": search_ctx["token"]}, headers=search_ctx["viewer_auth"]
    ).json()

    by_type = {row["record_type"]: row for row in body["searched"]}
    assert by_type["material"]["permitted"] is False
    assert by_type["project"]["permitted"] is True


def test_asking_for_a_type_the_caller_may_not_search_still_returns_nothing(client, search_ctx):
    """The type filter narrows; it never widens.

    `types` is combined with the permission gate by `and`. A caller who names
    `material` explicitly is still refused it.
    """
    body = client.get(
        "/api/search",
        params={"q": search_ctx["token"], "types": ["material"]},
        headers=search_ctx["viewer_auth"],
    ).json()
    assert body["results"] == []


def test_a_material_in_another_organization_is_not_returned(
    client, search_ctx, lead_ctx, owner_session
):
    """RLS, not the permission gate, and worth asserting separately.

    The caller HOLDS `material.view`, so the permission branch runs. What must
    stop this row is tenancy. Reuses `lead_ctx`'s foreign organization rather
    than making a second one, because that fixture already tears it down.
    """
    foreign_org = lead_ctx["foreign_org_id"]
    owner_session.execute(
        text(
            "INSERT INTO materials.materials "
            "(organization_id, material_code, name, category, role, status, created_by) "
            "VALUES (:o, :c, :n, 'resin', 'binder', 'approved', :by)"
        ),
        {
            "o": foreign_org,
            "c": f"RM-FX{uuid.uuid4().hex[:4].upper()}",
            "n": f"Resin {search_ctx['token']}",
            "by": lead_ctx["foreign_user_id"],
        },
    )
    owner_session.commit()

    try:
        body = client.get(
            "/api/search",
            params={"q": search_ctx["token"]},
            headers=search_ctx["lead_auth"],
        ).json()
        returned = {r["id"] for r in _types(body, "material")}
        # Exactly the caller's own material -- not zero (which would mean the
        # search broke) and not two (which would be a cross-tenant leak).
        assert returned == {str(search_ctx["material_id"])}
    finally:
        owner_session.execute(
            text("DELETE FROM materials.materials WHERE organization_id = :o"),
            {"o": foreign_org},
        )
        owner_session.commit()


# ---------------------------------------------------------------------------
# Ranking and query handling
# ---------------------------------------------------------------------------


def test_an_exact_code_match_outranks_a_name_match(client, search_ctx):
    """Somebody who types a record's code wants that record.

    This is the reason global search is lexical and `knowledge.search` is
    semantic: an embedding ranking puts a similar formula above an exact code.
    """
    body = client.get(
        "/api/search",
        params={"q": search_ctx["material_code"]},
        headers=search_ctx["lead_auth"],
    ).json()
    assert body["results"], "the exact code returned nothing at all"
    assert body["results"][0]["id"] == str(search_ctx["material_id"])


def test_a_lone_wildcard_does_not_return_the_database(client, search_ctx):
    """🔴 `%` IS A LIKE WILDCARD AND A CALLER MAY TYPE IT.

    Unescaped, `%` matches every row of every branch — an authenticated caller
    could page out the entire organization's record index with one character.
    Escaped, it is the literal per-cent sign, which no fixture row contains.
    """
    body = client.get("/api/search", params={"q": "%"}, headers=search_ctx["lead_auth"]).json()
    assert body["results"] == []

    # And the guard-the-guard half: the search DOES work on this connection,
    # so an empty list above is escaping and not a broken query.
    assert client.get(
        "/api/search", params={"q": search_ctx["token"]}, headers=search_ctx["lead_auth"]
    ).json()["results"]


def test_an_underscore_is_a_literal_not_a_single_character_wildcard(client, search_ctx):
    """`_` matches one of any character in LIKE, so it must be escaped too.

    🔴 THIS ASSERTS BOTH DIRECTIONS FROM ONE QUERY, which is why it is written
    this way rather than as `results == []`. The fixture's material carries the
    description "created by test_search_routes", which contains a literal
    underscore; the fixture's project is named "Programme <token>" and its code
    is "RDP-MINE-…", neither of which does.

    - Escaped, `_` is a literal: the material comes back, the project does not.
    - Unescaped, `_` is a wildcard matching any single character: EVERY row
      with at least one character comes back, so the project would too.

    An empty-list assertion could not tell those apart from a broken query.
    """
    body = client.get("/api/search", params={"q": "_"}, headers=search_ctx["lead_auth"]).json()

    assert [r["id"] for r in _types(body, "material")] == [str(search_ctx["material_id"])]
    assert _types(body, "project") == []


def test_an_unknown_record_type_is_refused_in_words(client, search_ctx):
    response = client.get(
        "/api/search",
        params={"q": "anything", "types": ["patent"]},
        headers=search_ctx["lead_auth"],
    )
    assert response.status_code == 422
    assert "patent" in response.text


def test_search_requires_authentication(client):
    assert client.get("/api/search", params={"q": "x"}).status_code == 401


# ---------------------------------------------------------------------------
# Structural guards -- these cover types nobody remembered to test by hand
# ---------------------------------------------------------------------------


def test_every_registry_permission_exists(owner_session):
    """A gate naming a permission that does not exist is a gate nobody holds.

    That would not fail loudly: `permission in permissions` is simply always
    false, the branch never runs, and the record type silently disappears from
    search for every role in the product.
    """
    known = {r[0] for r in owner_session.execute(text("SELECT code FROM core.permissions")).all()}
    assert known, "read no permissions at all -- the guard could not have failed"

    declared = {s.permission for s in SEARCHABLE}
    assert declared <= known, f"not real permissions: {sorted(declared - known)}"


def test_every_searchable_type_has_a_branch_in_the_statement():
    """The registry and the SQL are two literals, and cannot be type-checked.

    The statement is written out by hand (no interpolation reaches `text()`),
    so a type added to `SEARCHABLE` without a matching `UNION ALL` branch would
    be offered in `searched`, gated correctly, and never return anything.
    """
    source = SERVICE.read_text(encoding="utf-8")
    # 🔴 GUARD THE GUARD FIRST. If this regex stopped matching, the assertion
    # below would compare an empty set with an empty set and pass.
    branches = set(re.findall(r"SELECT '([a-z_]+)'(?:\s+AS\s+record_type)?,", source))
    assert len(branches) >= 10, f"parsed only {len(branches)} branches -- the parse broke"

    declared = {s.record_type for s in SEARCHABLE}
    assert declared == branches, (
        f"in the registry only: {sorted(declared - branches)}; "
        f"in the statement only: {sorted(branches - declared)}"
    )


def test_absent_types_are_declared_not_forgotten(owner_session):
    """§29 names fourteen record types; two of them have no table here.

    🔴 THIS FAILS IF THE ABSENCE STOPS BEING TRUE. When patents are built in
    E10, this test goes red and forces `ABSENT` to be corrected — otherwise the
    API would go on telling callers patents are not held here while a patent
    table sits beside it. A comment asserting a rule that does not exist is a
    defect this project has a standing note about.
    """
    assert set(ABSENT) == set(_ABSENT_TABLES), "the two absence tables disagree"

    for record_type, (schema, table) in _ABSENT_TABLES.items():
        exists = owner_session.execute(
            text(
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = :s AND table_name = :t)"
            ),
            {"s": schema, "t": table},
        ).scalar_one()
        assert not exists, (
            f"{schema}.{table} now exists, so '{record_type}' is no longer absent "
            f"-- remove it from ABSENT and give it a branch"
        )

    # And prove the probe can see a table that IS there, or the loop above
    # would pass against a broken `information_schema` query.
    assert owner_session.execute(
        text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'materials' AND table_name = 'materials')"
        )
    ).scalar_one()


def test_every_path_the_registry_emits_is_a_real_web_route():
    """🔴 THE GUARD THAT WOULD HAVE CAUGHT FIFTEEN DEAD LINKS.

    The first draft of `SEARCHABLE` gave every record type a detail route —
    `/materials/{id}`, `/suppliers/{id}`, `/knowledge/{id}` and eleven more —
    and NOT ONE of them is a route this application serves. Every search result
    would have 404'd, and nothing in the API or its tests would have noticed,
    because the API does not serve those pages and never sees the click.

    So this reads `apps/web/app` and asks the router's own question: is there a
    `page.tsx` at this path? Next.js routes are directories, so
    `/projects/workspace?id={id}` must have `app/projects/workspace/page.tsx`.

    This is the `record-link.tsx` lesson enforced structurally rather than
    remembered: "a dead link is worse than no link — it looks like a working
    product until it is clicked."
    """
    web_app = API_ROOT.parent / "web" / "app"
    assert web_app.is_dir(), f"could not find the web app at {web_app}"

    served = {
        "/" + str(p.parent.relative_to(web_app)).replace("\\", "/")
        for p in web_app.rglob("page.tsx")
    }
    served = {"/" if s == "/." else s for s in served}
    # 🔴 GUARD THE GUARD. A broken glob would make every membership test below
    # trivially fail-open if it were written as a subset check the other way,
    # and would make this file's intent unverifiable either way.
    assert len(served) > 20, f"found only {len(served)} routes -- the scan broke"
    assert "/search" in served, "the scan cannot see the search page itself"

    for entry in SEARCHABLE:
        # A list screen is mandatory: it is the fallback a hit with no detail
        # screen offers, so a broken one is a dead link by another name.
        assert entry.list_path in served, (
            f"{entry.record_type}.list_path {entry.list_path} is not a route"
        )
        if entry.detail_path is None:
            continue
        route = entry.detail_path.split("?")[0]
        assert route in served, (
            f"{entry.record_type}.detail_path {entry.detail_path} is not a route"
        )


def test_a_type_with_no_detail_screen_emits_no_link(client, search_ctx):
    """Materials have no detail screen, so a material hit must carry no path.

    Asserted from the response rather than from the registry, because the
    registry is what a mistake would live in.
    """
    body = client.get(
        "/api/search", params={"q": search_ctx["token"]}, headers=search_ctx["lead_auth"]
    ).json()

    materials = _types(body, "material")
    assert materials, "no material hit -- this test proved nothing"
    assert materials[0]["path"] is None
    assert materials[0]["list_path"] == "/materials"

    # And the other direction: the project DOES have a workspace, so it links.
    projects = _types(body, "project")
    assert projects, "no project hit -- this test proved nothing"
    assert projects[0]["path"] == f"/projects/workspace?id={search_ctx['project_id']}"


def test_the_statement_contains_no_interpolation():
    """Semgrep's `avoid-sqlalchemy-text` blocked commit 5209298 on this repo.

    The rule is right about the shape even when the values are constants, so
    this asserts the property directly rather than relying on a CI-only scan —
    Semgrep does not run on this host.
    """
    source = SERVICE.read_text(encoding="utf-8")
    assert "text(f" not in source
    assert ".format(" not in source.split("def global_search")[0].split("_STATEMENT")[1]
