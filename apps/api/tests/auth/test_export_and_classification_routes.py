"""I43/I48 over real HTTP — the enforcement a service test cannot see.

🔴 CODEX NAMED THIS EXACTLY: *"Tests call `export_version()` directly and never
exercise `get_export()` with principals. Removing
`require_permission("formula.export")` from the route would leave every test
green."*

Which is I40's lesson, four days old, applied to tests I wrote two hours ago:
a service-level test hands itself whatever authorization it likes, so it proves
the query works and cannot prove the ROUTE is gated. The mutation these exist
to catch is deleting one `Depends`.

⚠️ AND THE SCOPE STATEMENT IS ASSERTED HERE TOO. `formula.export` authorizes
and audits ONE endpoint; it does not prevent removal of formula information by
anyone holding `formula.view`. `test_the_read_endpoint_is_not_gated_by_export`
states that as an executable fact rather than a caveat in prose, so nobody
later mistakes this permission for exfiltration prevention.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from app.main import app


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def version(owner_session, lead_ctx):
    """A formula with one component, in the caller's organization.

    Commits, because the route runs on its own connection -- and therefore
    cleans up, because `lead_ctx` deletes its organization on teardown.
    """
    from app.domains.formulations.service import (
        ComponentInput,
        FormulaInput,
        create_formula,
        set_components,
    )
    from app.domains.materials.service import MaterialInput, create_material

    org, user = lead_ctx["org_id"], lead_ctx["user_id"]
    project = owner_session.execute(
        text(
            """
            INSERT INTO projects.projects
                (organization_id, project_code, name, current_stage, lead_user_id)
            VALUES (:o,:c,'Export route test','REQUIREMENTS',:u) RETURNING id
            """
        ),
        {"o": org, "c": f"RDP-{uuid.uuid4().hex[:6]}", "u": user},
    ).scalar_one()
    material = create_material(
        owner_session,
        organization_id=org,
        actor_id=user,
        spec=MaterialInput(
            material_code=f"RM-{uuid.uuid4().hex[:6]}", name="Resin", category="Resin"
        ),
    )
    created = create_formula(
        owner_session,
        project_id=project,
        organization_id=org,
        actor_id=user,
        spec=FormulaInput(formula_code=f"F-{uuid.uuid4().hex[:6]}", name="Route test"),
    )
    set_components(
        owner_session,
        version_id=created["version_id"],
        organization_id=org,
        actor_id=user,
        components=[ComponentInput(material_id=material, percentage="100.0000")],
    )
    owner_session.commit()

    yield {"formula": created["formula_id"], "version": created["version_id"], "project": project}

    owner_session.rollback()
    owner_session.execute(
        text("DELETE FROM formulations.formula_components WHERE formula_version_id = :v"),
        {"v": created["version_id"]},
    )
    owner_session.execute(
        text("DELETE FROM formulations.formula_versions WHERE formula_id = :f"),
        {"f": created["formula_id"]},
    )
    owner_session.execute(
        text("DELETE FROM formulations.formulas WHERE id = :f"), {"f": created["formula_id"]}
    )
    owner_session.execute(text("DELETE FROM materials.materials WHERE id = :m"), {"m": material})
    owner_session.execute(text("DELETE FROM projects.projects WHERE id = :p"), {"p": project})
    owner_session.commit()


def test_a_lead_may_export_and_it_is_recorded(client, auth, owner_session, version) -> None:
    """The Lead holds `formula.export`, so the route lets them through."""
    response = client.get(f"/api/formulations/versions/{version['version']}/export", headers=auth)
    assert response.status_code == 200, response.text
    assert response.json()["components"]

    recorded = owner_session.execute(
        text(
            "SELECT count(*) FROM audit.events WHERE entity_id = :e AND action = 'formula.exported'"
        ),
        {"e": str(version["version"])},
    ).scalar_one()
    assert recorded == 1, "an export over HTTP wrote no audit event"


def test_the_route_is_gated_on_export_not_merely_on_view(
    client, make_token, owner_session, lead_ctx, version
) -> None:
    """🔴 THE MUTATION: delete `require_permission("formula.export")`.

    Every service-level test in `tests/db/test_039_*` stays green against that
    change, because a service test supplies its own authorization. This is the
    one that fails.

    The caller here is a Chemist -- who holds `formula.view` and NOT
    `formula.export`, which is the asymmetry the whole separation rests on.
    """
    suffix = uuid.uuid4().hex[:8]
    sub = f"chemist-{suffix}"
    user = owner_session.execute(
        text(
            "INSERT INTO core.users (keycloak_sub,email,display_name) "
            "VALUES (:s,:e,'Chemist') RETURNING id"
        ),
        {"s": sub, "e": f"{sub}@example.test"},
    ).scalar_one()
    member = owner_session.execute(
        text(
            "INSERT INTO core.organization_members (organization_id,user_id,status) "
            "VALUES (:o,:u,'active') RETURNING id"
        ),
        {"o": lead_ctx["org_id"], "u": user},
    ).scalar_one()
    owner_session.execute(
        text(
            "INSERT INTO core.member_roles (member_id, role_id) "
            "SELECT :m, id FROM core.roles WHERE code='product_development_chemist'"
        ),
        {"m": member},
    )
    owner_session.commit()

    headers = {
        "Authorization": f"Bearer {make_token(sub=sub)}",
        "X-Organization-Id": str(lead_ctx["org_id"]),
    }
    try:
        response = client.get(
            f"/api/formulations/versions/{version['version']}/export", headers=headers
        )
        assert response.status_code == 403, (
            "a Chemist exported a formula. They hold formula.view and must not "
            "hold formula.export -- and if the route lost its permission "
            f"dependency this is the only test that would notice. {response.text}"
        )
    finally:
        owner_session.rollback()
        owner_session.execute(
            text("DELETE FROM core.member_roles WHERE member_id = :m"), {"m": member}
        )
        owner_session.execute(
            text("DELETE FROM core.organization_members WHERE id = :m"), {"m": member}
        )
        owner_session.execute(text("DELETE FROM core.users WHERE id = :u"), {"u": user})
        owner_session.commit()


def test_the_read_endpoint_is_not_gated_by_export(client, auth, version) -> None:
    """🔴 THE SCOPE STATEMENT, AS AN EXECUTABLE FACT.

    `formula.export` authorizes ONE endpoint. `GET /versions/{id}` requires
    only `formula.view` and returns the complete composition, so this
    permission does not prevent removal of formula information by anyone who
    can read it.

    Asserting it here rather than only writing it in a docstring means the day
    somebody DOES gate the read path, this test fails and forces the scope
    statement to be corrected with it -- instead of the documentation quietly
    becoming true or quietly staying false.
    """
    response = client.get(f"/api/formulations/versions/{version['version']}", headers=auth)
    assert response.status_code == 200, response.text
    assert response.json()["components"], (
        "the version endpoint no longer returns the composition. If the read "
        "path was deliberately narrowed, update the scope statement on "
        "export_version and get_export -- they currently say it is not."
    )


def test_reclassification_is_gated_and_recorded(client, auth, owner_session, version) -> None:
    """I48's writer, over HTTP.

    The Lead holds `formula.classify` (migration 040 grants it to exactly the
    export holders), so this succeeds and is audited.
    """
    response = client.post(
        f"/api/formulations/{version['formula']}/classification",
        headers=auth,
        json={"classification": "CONFIDENTIAL", "reason": "published datasheet figures"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["classification"] == "CONFIDENTIAL"

    event = (
        owner_session.execute(
            text(
                "SELECT previous_state, new_state FROM audit.events "
                "WHERE entity_id = :e AND action = 'formula.reclassified' "
                "ORDER BY id DESC LIMIT 1"
            ),
            {"e": str(version["formula"])},
        )
        .mappings()
        .one_or_none()
    )
    assert event is not None
    assert event["previous_state"]["classification"] == "R&D_RESTRICTED"
    assert event["new_state"]["lowered"] is True


def test_a_reclassification_without_a_reason_is_refused(client, auth, version) -> None:
    response = client.post(
        f"/api/formulations/{version['formula']}/classification",
        headers=auth,
        json={"classification": "PUBLIC", "reason": ""},
    )
    assert response.status_code in (400, 422), response.text
