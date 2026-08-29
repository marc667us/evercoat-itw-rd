"""§27's fifteen widgets — each shown to FIND the row it exists to surface.

🔴 WHY THIS FILE EXISTS.

Every one of these panels returned `count=0` the moment it was written, against
a real database, and every one of them looked exactly like a panel that was
broken. *A guard that passes when it cannot see is worse than one that cannot
fail* — and a dashboard widget is a guard in that sense: it is supposed to be
the thing that tells somebody there is work waiting.

So each test here writes ONE row of the subject and asserts the widget returns
it. The permission-gated ones are additionally asserted in the refused
direction, because `_forbidden` and an empty list are different statements and
the whole `_panel` / `_unavailable` / `_forbidden` design exists to keep them
apart.

⚠️ THE FIXTURE DOES NOT COMMIT, so nothing here needs teardown — every test
rolls back. That is deliberate and different from `test_058_research.py`, which
had to commit because a ROUTE ran on its own connection. Nothing in this file
crosses a connection.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.domains.dashboards.service import (
    chemist_dashboard,
    director_dashboard,
    engineer_dashboard,
    lead_dashboard,
)

pytestmark = pytest.mark.db

ALL_PERMISSIONS = frozenset(
    {
        "research.view",
        # 🔴 `material.view` AND `test.view` ARE HERE BECAUSE THE PANELS READ
        # OTHER MODULES' ROWS. Codex found the safety-alert, competitor and
        # research-linked-test panels ungated or under-gated — a dashboard that
        # is a softer door to the same data than the endpoint owning it. The
        # gate tests below assert the refusals; this set is the "holds
        # everything" case those refusals are measured against.
        "material.view",
        "compliance.review_sds",
        "test.view",
        "test.review",
        "opportunity.view",
        "opportunity.decide",
        "batch.execute",
        "batch.complete",
    }
)


@pytest.fixture
def fx(owner_session: Session) -> dict[str, Any]:
    """One organization, one project, one person, and a research workspace."""
    suffix = uuid.uuid4().hex[:8]
    org = owner_session.execute(
        text("INSERT INTO core.organizations (code, name) VALUES (:c, :n) RETURNING id"),
        {"c": f"W27-{suffix}", "n": "Widget Org"},
    ).scalar_one()
    user = owner_session.execute(
        text(
            "INSERT INTO core.users (keycloak_sub, email, display_name) "
            "VALUES (:s, :e, 'Widget Person') RETURNING id"
        ),
        {"s": f"w27-{suffix}", "e": f"w27-{suffix}@example.test"},
    ).scalar_one()
    owner_session.execute(
        text(
            "INSERT INTO core.organization_members (organization_id, user_id, status,"
            " email, display_name) SELECT :o, :u, 'active', u.email, u.display_name"
            " FROM core.users u WHERE u.id = :u"
        ),
        {"o": org, "u": user},
    )
    project = owner_session.execute(
        text(
            "INSERT INTO projects.projects (organization_id, project_code, name,"
            " confidentiality, status, priority, lead_user_id)"
            " VALUES (:o, :c, 'Widget project', 'normal', 'active', 'high', :u)"
            " RETURNING id"
        ),
        {"o": org, "c": f"RDP-W-{suffix}", "u": user},
    ).scalar_one()

    # FORCE RLS binds the owner too, so the tenant must be declared before any
    # `research`, `safety` or `competitors` insert.
    owner_session.execute(text("SELECT set_config('app.current_org', :o, true)"), {"o": str(org)})
    owner_session.execute(
        text("SELECT set_config('app.current_user_id', :u, true)"), {"u": str(user)}
    )

    investigation = owner_session.execute(
        text(
            """
            INSERT INTO research.investigations
                (organization_id, project_id, investigation_code, title,
                 research_question, owner_user_id, opened_by)
            VALUES (:o, :p, :c, 'Widget investigation', 'Does the widget find it?',
                    :u, :u)
            RETURNING id
            """
        ),
        {"o": org, "p": project, "c": f"RES-W-{suffix}", "u": user},
    ).scalar_one()
    owner_session.flush()

    return {
        "org": org,
        "user": user,
        "project": project,
        "investigation": investigation,
        "suffix": suffix,
    }


def _panels(fn: Any, fx: dict[str, Any], session: Session, **kw: Any) -> dict[str, Any]:
    return fn(
        session,
        user_id=fx["user"],
        organization_id=fx["org"],
        held_permissions=kw.get("permissions", ALL_PERMISSIONS),
    )["panels"]


def _material(session: Session, fx: dict[str, Any]) -> uuid.UUID:
    return session.execute(  # type: ignore[no-any-return]
        text(
            "INSERT INTO materials.materials (organization_id, material_code, name,"
            " category, role, status, created_by)"
            " VALUES (:o, :c, 'Widget resin', 'Resin', 'resin', 'approved', :u)"
            " RETURNING id"
        ),
        {"o": fx["org"], "c": f"RM-W-{fx['suffix']}", "u": fx["user"]},
    ).scalar_one()


def _alert(session: Session, fx: dict[str, Any], severity: str) -> uuid.UUID:
    """A safety alert on a material, which needs an SDS version to hang off."""
    material = _material(session, fx)
    document = session.execute(
        text(
            """
            INSERT INTO materials.material_documents
                (organization_id, material_id, document_type, title, storage_key,
                 content_type, byte_size, checksum_sha256, status, scan_status,
                 scanner_name, scanner_version, scanned_at, uploaded_by)
            VALUES (:o, :m, 'SDS', 'Widget SDS', :k, 'application/pdf', 1024,
                    :sum, 'approved', 'clean', 'test', '1.0', now(), :u)
            RETURNING id
            """
        ),
        {
            "o": fx["org"],
            "m": material,
            "k": f"test/w27-{fx['suffix']}",
            "sum": uuid.uuid4().hex * 2,
            "u": fx["user"],
        },
    ).scalar_one()
    version = session.execute(
        text(
            "INSERT INTO safety.sds_versions (organization_id, document_id, material_id,"
            " supplier_revision, interpreted_by)"
            " VALUES (:o, :d, :m, 'rev 1', :u) RETURNING id"
        ),
        {"o": fx["org"], "d": document, "m": material, "u": fx["user"]},
    ).scalar_one()
    return session.execute(  # type: ignore[no-any-return]
        text(
            """
            INSERT INTO safety.safety_alerts
                (organization_id, sds_version_id, project_id, material_id, severity,
                 change_summary)
            VALUES (:o, :v, :p, :m, :sev, 'A hazard statement changed.')
            RETURNING id
            """
        ),
        {
            "o": fx["org"],
            "v": version,
            "p": fx["project"],
            "m": material,
            "sev": severity,
        },
    ).scalar_one()


def _cited_test(
    session: Session, fx: dict[str, Any], investigation: uuid.UUID, stance: str
) -> uuid.UUID:
    """A test, and one evidence card in `investigation` that cites it.

    The digital thread means a test cannot exist on its own: it needs a method,
    a sample, a batch, a version and a formula. Building all six here rather
    than in each test keeps the assertions about the WIDGET.
    """
    tag = uuid.uuid4().hex[:6]
    formula = session.execute(
        text(
            "INSERT INTO formulations.formulas (organization_id, project_id,"
            " formula_code, name, owner_user_id, created_by)"
            " VALUES (:o, :p, :c, 'Cited formula', :u, :u) RETURNING id"
        ),
        {"o": fx["org"], "p": fx["project"], "c": f"F-C{tag}", "u": fx["user"]},
    ).scalar_one()
    version = session.execute(
        text(
            "INSERT INTO formulations.formula_versions (organization_id, project_id,"
            " formula_id, version_number, version_code, status, created_by)"
            " VALUES (:o, :p, :f, 1, :c, 'draft', :u) RETURNING id"
        ),
        {
            "o": fx["org"],
            "p": fx["project"],
            "f": formula,
            "c": f"F-C{tag}-V1",
            "u": fx["user"],
        },
    ).scalar_one()
    batch = session.execute(
        text(
            "INSERT INTO laboratory.batches (organization_id, project_id,"
            " formula_version_id, batch_number, planned_quantity_kg, status, created_by)"
            " VALUES (:o, :p, :v, :b, 2.5, 'draft', :u) RETURNING id"
        ),
        {
            "o": fx["org"],
            "p": fx["project"],
            "v": version,
            "b": f"LB-C{tag}",
            "u": fx["user"],
        },
    ).scalar_one()
    sample = session.execute(
        text(
            "INSERT INTO laboratory.samples (organization_id, project_id, batch_id,"
            " sample_number, taken_by) VALUES (:o, :p, :b, :s, :u) RETURNING id"
        ),
        {
            "o": fx["org"],
            "p": fx["project"],
            "b": batch,
            "s": f"SA-C{tag}",
            "u": fx["user"],
        },
    ).scalar_one()
    method = session.execute(
        text(
            "INSERT INTO testing.test_methods (organization_id, method_code, name,"
            " property_measured, canonical_unit, created_by)"
            " VALUES (:o, :c, 'Sand-through time', 'sanding', 'minutes', :u)"
            " RETURNING id"
        ),
        {"o": fx["org"], "c": f"TM-C{tag}", "u": fx["user"]},
    ).scalar_one()
    test_id = session.execute(
        text(
            "INSERT INTO testing.tests (organization_id, project_id, sample_id,"
            " method_id, test_number, test_purpose, authority_level, created_by)"
            " VALUES (:o, :p, :s, :m, :n, 'screening', 'preliminary', :u) RETURNING id"
        ),
        {
            "o": fx["org"],
            "p": fx["project"],
            "s": sample,
            "m": method,
            "n": f"T-C{tag}",
            "u": fx["user"],
        },
    ).scalar_one()

    source = session.execute(
        text(
            "INSERT INTO research.sources (organization_id, investigation_id,"
            " source_kind, evidence_grade, title, recorded_by)"
            " VALUES (:o, :i, 'laboratory', 'A', 'Our own result', :u) RETURNING id"
        ),
        {"o": fx["org"], "i": investigation, "u": fx["user"]},
    ).scalar_one()
    session.execute(
        text(
            "INSERT INTO research.evidence (organization_id, investigation_id,"
            " source_id, test_id, stance, summary, recorded_by)"
            " VALUES (:o, :i, :s, :t, :st, 'The result is relevant.', :u)"
        ),
        {
            "o": fx["org"],
            "i": investigation,
            "s": source,
            "t": test_id,
            "st": stance,
            "u": fx["user"],
        },
    )
    return test_id  # type: ignore[no-any-return]


# ---------------------------------------------------------------------------
# Chemist
# ---------------------------------------------------------------------------


def test_an_active_investigation_reaches_the_chemist(
    owner_session: Session, fx: dict[str, Any]
) -> None:
    panels = _panels(chemist_dashboard, fx, owner_session)
    rows = panels["research_investigations"]["rows"]
    assert [r["id"] for r in rows] == [fx["investigation"]]
    assert rows[0]["finding_count"] == 0


def test_a_closed_investigation_does_not_reach_the_chemist(
    owner_session: Session, fx: dict[str, Any]
) -> None:
    """The other direction. Without it the panel could be listing everything."""
    owner_session.execute(
        text(
            "UPDATE research.investigations SET status = 'closed',"
            " closed_at = clock_timestamp() WHERE id = :i"
        ),
        {"i": fx["investigation"]},
    )
    panels = _panels(chemist_dashboard, fx, owner_session)
    assert panels["research_investigations"]["count"] == 0


def test_a_proposed_experiment_reaches_the_chemist_and_a_decided_one_does_not(
    owner_session: Session, fx: dict[str, Any]
) -> None:
    """🔴 §20 MAKES THIS PANEL A DECISION QUEUE, NOT A HISTORY."""
    proposals = [
        owner_session.execute(
            text(
                """
                INSERT INTO research.experiment_proposals
                    (organization_id, investigation_id, proposal_code, objective,
                     basis, variables, expected_direction, required_tests, confidence,
                     proposed_by)
                VALUES (:o, :i, :c, 'Improve sanding', 'RF-1', 'Loading', 'Shorter',
                        'Density', 'moderate', :u)
                RETURNING id
                """
            ),
            {
                "o": fx["org"],
                "i": fx["investigation"],
                "c": f"EXP-W{n}-{fx['suffix']}",
                "u": fx["user"],
            },
        ).scalar_one()
        for n in (1, 2)
    ]
    owner_session.execute(
        text(
            "UPDATE research.experiment_proposals SET status = 'rejected',"
            " decided_by = :u, decided_at = clock_timestamp(),"
            " decision_note = 'no' WHERE id = :p"
        ),
        {"u": fx["user"], "p": proposals[1]},
    )

    panels = _panels(chemist_dashboard, fx, owner_session)
    rows = panels["experiment_proposals"]["rows"]
    assert [r["id"] for r in rows] == [proposals[0]], "a decided proposal is not a queue item"


def test_an_unacknowledged_alert_reaches_the_chemist_and_an_acknowledged_one_does_not(
    owner_session: Session, fx: dict[str, Any]
) -> None:
    # `high`, because the vocabulary is critical|high|informational -- there
    # is no "medium", and the CHECK says so.
    alert = _alert(owner_session, fx, "high")
    panels = _panels(chemist_dashboard, fx, owner_session)
    assert [r["id"] for r in panels["material_alerts"]["rows"]] == [alert]
    assert panels["material_alerts"]["rows"][0]["material_code"] is not None

    owner_session.execute(
        text(
            "UPDATE safety.safety_alerts SET acknowledged_by = :u,"
            " acknowledged_at = clock_timestamp() WHERE id = :a"
        ),
        {"u": fx["user"], "a": alert},
    )
    panels = _panels(chemist_dashboard, fx, owner_session)
    assert panels["material_alerts"]["count"] == 0, "an alert already read is not an action"


def test_the_research_panels_are_refused_without_research_view(
    owner_session: Session, fx: dict[str, Any]
) -> None:
    """🔴 REFUSED, NOT EMPTY. Three different statements, one shape each."""
    panels = _panels(chemist_dashboard, fx, owner_session, permissions=frozenset({"material.view"}))
    for name in ("research_investigations", "experiment_proposals"):
        panel = panels[name]
        assert panel["available"] is False
        assert "research.view" in panel["reason"]
    assert panels["safety_reviews_required"]["available"] is False
    assert "compliance.review_sds" in panels["safety_reviews_required"]["reason"]


# ---------------------------------------------------------------------------
# Engineer
# ---------------------------------------------------------------------------


def test_a_test_cited_by_evidence_reaches_the_engineer(
    owner_session: Session, fx: dict[str, Any]
) -> None:
    """🔴 THE JOIN IS THE CLAIM. "Research-linked" means an evidence card cites
    this test — not that a test and an investigation share a project."""
    source = owner_session.execute(
        text(
            "INSERT INTO research.sources (organization_id, investigation_id,"
            " source_kind, evidence_grade, title, recorded_by)"
            " VALUES (:o, :i, 'laboratory', 'A', 'Our own result', :u) RETURNING id"
        ),
        {"o": fx["org"], "i": fx["investigation"], "u": fx["user"]},
    ).scalar_one()

    formula = owner_session.execute(
        text(
            "INSERT INTO formulations.formulas (organization_id, project_id,"
            " formula_code, name, owner_user_id, created_by)"
            " VALUES (:o, :p, :c, 'Widget formula', :u, :u) RETURNING id"
        ),
        {"o": fx["org"], "p": fx["project"], "c": f"F-W-{fx['suffix']}", "u": fx["user"]},
    ).scalar_one()
    version = owner_session.execute(
        text(
            "INSERT INTO formulations.formula_versions (organization_id, project_id,"
            " formula_id, version_number, version_code, status, created_by)"
            " VALUES (:o, :p, :f, 1, :c, 'draft', :u) RETURNING id"
        ),
        {
            "o": fx["org"],
            "p": fx["project"],
            "f": formula,
            "c": f"F-W-{fx['suffix']}-V1",
            "u": fx["user"],
        },
    ).scalar_one()
    batch = owner_session.execute(
        text(
            "INSERT INTO laboratory.batches (organization_id, project_id,"
            " formula_version_id, batch_number, planned_quantity_kg, status,"
            " created_by)"
            " VALUES (:o, :p, :v, :b, 2.5, 'draft', :u) RETURNING id"
        ),
        {
            "o": fx["org"],
            "p": fx["project"],
            "v": version,
            "b": f"LB-W-{fx['suffix']}",
            "u": fx["user"],
        },
    ).scalar_one()
    sample = owner_session.execute(
        text(
            "INSERT INTO laboratory.samples (organization_id, project_id, batch_id,"
            " sample_number, taken_by) VALUES (:o, :p, :b, :s, :u) RETURNING id"
        ),
        {
            "o": fx["org"],
            "p": fx["project"],
            "b": batch,
            "s": f"SA-W-{fx['suffix']}",
            "u": fx["user"],
        },
    ).scalar_one()
    method = owner_session.execute(
        text(
            "INSERT INTO testing.test_methods (organization_id, method_code, name,"
            " property_measured, canonical_unit, created_by)"
            " VALUES (:o, :c, 'Sand-through time', 'sanding', 'minutes', :u)"
            " RETURNING id"
        ),
        {"o": fx["org"], "c": f"TM-W-{fx['suffix']}", "u": fx["user"]},
    ).scalar_one()
    test_id = owner_session.execute(
        text(
            "INSERT INTO testing.tests (organization_id, project_id, sample_id,"
            " method_id, test_number, test_purpose, authority_level, created_by)"
            " VALUES (:o, :p, :s, :m, :n, 'screening', 'preliminary', :u) RETURNING id"
        ),
        {
            "o": fx["org"],
            "p": fx["project"],
            "s": sample,
            "m": method,
            "n": f"T-W-{fx['suffix']}",
            "u": fx["user"],
        },
    ).scalar_one()

    before = _panels(engineer_dashboard, fx, owner_session)["research_linked_tests"]
    assert before["count"] == 0, "the test is not linked yet, so it must not appear"

    owner_session.execute(
        text(
            "INSERT INTO research.evidence (organization_id, investigation_id,"
            " source_id, test_id, stance, summary, recorded_by)"
            " VALUES (:o, :i, :s, :t, 'supports', 'The result supports it.', :u)"
        ),
        {
            "o": fx["org"],
            "i": fx["investigation"],
            "s": source,
            "t": test_id,
            "u": fx["user"],
        },
    )
    after = _panels(engineer_dashboard, fx, owner_session)["research_linked_tests"]
    assert [r["id"] for r in after["rows"]] == [test_id]
    # The panel aggregates per TEST now (Codex P2: `DISTINCT` over a select
    # list carrying the investigation and the stance was not one row per
    # test), so the stance arrives as the set of stances it was cited with.
    assert after["rows"][0]["stances"] == ["supports"]
    assert after["rows"][0]["citation_count"] == 1


def test_the_engineers_process_issue_panel_says_it_does_not_exist(
    owner_session: Session, fx: dict[str, Any]
) -> None:
    """🔴 §27 ASKS FOR IT AND THERE IS NOTHING TO ANSWER IT WITH.

    Approximating it from safety alerts would answer a different question under
    §27's heading, and look like an answer to this one.
    """
    panel = _panels(engineer_dashboard, fx, owner_session)["safety_process_issues"]
    assert panel["available"] is False
    assert "process-deviation" in panel["reason"]
    assert panel["rows"] == []


# ---------------------------------------------------------------------------
# Lead
# ---------------------------------------------------------------------------


def test_critical_and_high_alerts_reach_the_lead_and_informational_does_not(
    owner_session: Session, fx: dict[str, Any]
) -> None:
    """🔴 THE VOCABULARY IS `critical | high | informational`, AND THIS TEST IS
    WHY THAT MATTERS.

    The panel first filtered on `severity = 'high'`, on the assumption that
    severities run low/medium/high. That would have hidden every CRITICAL alert
    from a panel headed "Critical Safety Alerts" — the worst direction for the
    mistake to go, and invisible without asserting the top severity explicitly.

    `informational` stays out: a panel headed critical that lists everything
    teaches a lead to ignore it.
    """
    _alert(owner_session, fx, "informational")
    panels = _panels(lead_dashboard, fx, owner_session)
    assert panels["critical_safety_alerts"]["count"] == 0

    high = _alert(owner_session, dict(fx, suffix=uuid.uuid4().hex[:8]), "high")
    critical = _alert(owner_session, dict(fx, suffix=uuid.uuid4().hex[:8]), "critical")
    panels = _panels(lead_dashboard, fx, owner_session)
    rows = panels["critical_safety_alerts"]["rows"]
    assert {r["id"] for r in rows} == {high, critical}
    # Worst first, so the top of the panel is the thing to act on.
    assert rows[0]["id"] == critical, [r["severity"] for r in rows]


def test_an_open_knowledge_gap_reaches_the_lead_worst_impact_first(
    owner_session: Session, fx: dict[str, Any]
) -> None:
    gaps = {
        impact: owner_session.execute(
            text(
                "INSERT INTO research.knowledge_gaps (organization_id,"
                " investigation_id, description, impact, identified_by)"
                " VALUES (:o, :i, :d, :imp, :u) RETURNING id"
            ),
            {
                "o": fx["org"],
                "i": fx["investigation"],
                "d": f"A {impact} gap.",
                "imp": impact,
                "u": fx["user"],
            },
        ).scalar_one()
        for impact in ("low", "high", "moderate")
    }
    panels = _panels(lead_dashboard, fx, owner_session)
    rows = panels["knowledge_gaps"]["rows"]
    assert [r["impact"] for r in rows] == ["high", "moderate", "low"], rows

    owner_session.execute(
        text("UPDATE research.knowledge_gaps SET status = 'closed' WHERE id = :g"),
        {"g": gaps["high"]},
    )
    panels = _panels(lead_dashboard, fx, owner_session)
    assert [r["impact"] for r in panels["knowledge_gaps"]["rows"]] == ["moderate", "low"]


def test_the_lead_research_pipeline_is_not_scoped_to_the_leads_own_work(
    owner_session: Session, fx: dict[str, Any]
) -> None:
    """The chemist panel is "mine"; the lead's is the team's. Different queries
    for different questions, and a copy of one under the other's name would be
    a lead who cannot see their own team's research."""
    other = owner_session.execute(
        text(
            "INSERT INTO core.users (keycloak_sub, email, display_name)"
            " VALUES (:s, :e, 'Somebody else') RETURNING id"
        ),
        {"s": f"other-{fx['suffix']}", "e": f"other-{fx['suffix']}@example.test"},
    ).scalar_one()
    owner_session.execute(
        text(
            "INSERT INTO core.organization_members (organization_id, user_id, status,"
            " email, display_name) SELECT :o, :u, 'active', u.email, u.display_name"
            " FROM core.users u WHERE u.id = :u"
        ),
        {"o": fx["org"], "u": other},
    )
    theirs = owner_session.execute(
        text(
            """
            INSERT INTO research.investigations
                (organization_id, project_id, investigation_code, title,
                 research_question, owner_user_id, opened_by)
            VALUES (:o, :p, :c, 'Their investigation', 'Theirs?', :other, :other)
            RETURNING id
            """
        ),
        {
            "o": fx["org"],
            "p": fx["project"],
            "c": f"RES-T-{fx['suffix']}",
            "other": other,
        },
    ).scalar_one()

    chemist = _panels(chemist_dashboard, fx, owner_session)["research_investigations"]
    assert theirs not in [r["id"] for r in chemist["rows"]], "the chemist panel is MINE"

    lead = _panels(lead_dashboard, fx, owner_session)["research_pipeline"]
    assert {fx["investigation"], theirs} <= {r["id"] for r in lead["rows"]}


# ---------------------------------------------------------------------------
# Director
# ---------------------------------------------------------------------------


def test_a_competitor_product_reaches_the_director_with_its_counts(
    owner_session: Session, fx: dict[str, Any]
) -> None:
    product = owner_session.execute(
        text(
            "INSERT INTO competitors.products (organization_id, manufacturer,"
            " product_name, registered_by) VALUES (:o, 'Rival', :n, :u) RETURNING id"
        ),
        {"o": fx["org"], "n": f"Widget rival {fx['suffix']}", "u": fx["user"]},
    ).scalar_one()

    panels = _panels(director_dashboard, fx, owner_session)
    rows = [r for r in panels["competitor_intelligence"]["rows"] if r["id"] == product]
    assert len(rows) == 1
    assert rows[0]["evidence_count"] == 0
    assert rows[0]["benchmark_count"] == 0


def test_the_research_portfolio_counts_what_the_director_can_reach(
    owner_session: Session, fx: dict[str, Any]
) -> None:
    panels = _panels(director_dashboard, fx, owner_session)
    portfolio = panels["research_portfolio"]
    assert portfolio["available"] is True
    active = [r for r in portfolio["rows"] if r["status"] == "active"]
    assert len(active) == 1, portfolio["rows"]
    assert active[0]["investigations"] >= 1


def test_the_director_research_portfolio_is_refused_without_research_view(
    owner_session: Session, fx: dict[str, Any]
) -> None:
    panels = _panels(
        director_dashboard, fx, owner_session, permissions=frozenset({"opportunity.view"})
    )
    panel = panels["research_portfolio"]
    assert panel["available"] is False
    assert "research.view" in panel["reason"]


# ---------------------------------------------------------------------------
# The gates Codex found missing — refused, not empty
# ---------------------------------------------------------------------------


def test_the_safety_alert_panels_are_refused_without_material_view(
    owner_session: Session, fx: dict[str, Any]
) -> None:
    """🔴 THE DASHBOARD MUST NOT BE A SOFTER DOOR THAN THE ROUTE.

    `GET /api/material-safety/alerts` requires `material.view`. All three alert
    panels returned the same rows to anybody who could load a dashboard.

    ⚠️ AND THE REFUSAL IS THE POINT, NOT JUST THE GATE. Returning an empty
    `_panel` to a caller without the permission would say "no safety alerts" —
    a false all-clear — where `_forbidden` says "not yours to act on".
    """
    _alert(owner_session, fx, "critical")
    without = frozenset(ALL_PERMISSIONS - {"material.view"})

    chemist = _panels(chemist_dashboard, fx, owner_session, permissions=without)
    assert chemist["material_alerts"]["available"] is False
    assert "material.view" in chemist["material_alerts"]["reason"]

    lead = _panels(lead_dashboard, fx, owner_session, permissions=without)
    assert lead["critical_safety_alerts"]["available"] is False
    assert "material.view" in lead["critical_safety_alerts"]["reason"]

    director = _panels(director_dashboard, fx, owner_session, permissions=without)
    assert director["critical_material_risks"]["available"] is False
    assert "material.view" in director["critical_material_risks"]["reason"]

    # The other direction: with the permission, the alert is actually there.
    held = _panels(chemist_dashboard, fx, owner_session)
    assert held["material_alerts"]["count"] == 1


def test_competitor_intelligence_needs_both_permissions_it_reads(
    owner_session: Session, fx: dict[str, Any]
) -> None:
    """It lists products (`material.view`) AND counts benchmarks (`test.view`)."""
    owner_session.execute(
        text(
            "INSERT INTO competitors.products (organization_id, manufacturer,"
            " product_name, registered_by) VALUES (:o, 'Rival', :n, :u)"
        ),
        {"o": fx["org"], "n": f"Gate rival {fx['suffix']}", "u": fx["user"]},
    )
    for missing in ("material.view", "test.view"):
        panels = _panels(
            director_dashboard,
            fx,
            owner_session,
            permissions=frozenset(ALL_PERMISSIONS - {missing}),
        )
        panel = panels["competitor_intelligence"]
        assert panel["available"] is False, f"not refused when {missing} is absent"
        assert missing in panel["reason"]

    assert _panels(director_dashboard, fx, owner_session)["competitor_intelligence"]["count"] >= 1


def test_research_linked_tests_needs_test_view_as_well(
    owner_session: Session, fx: dict[str, Any]
) -> None:
    """🔴 IT RETURNS `testing.tests` ROWS, WHOSE ROUTES REQUIRE `test.view`.

    Gated on `research.view` alone, a research-only caller could read test
    numbers, execution state and calculated results through the dashboard.
    """
    panels = _panels(
        engineer_dashboard,
        fx,
        owner_session,
        permissions=frozenset(ALL_PERMISSIONS - {"test.view"}),
    )
    panel = panels["research_linked_tests"]
    assert panel["available"] is False
    assert "test.view" in panel["reason"]


def test_a_test_cited_twice_is_counted_once(owner_session: Session, fx: dict[str, Any]) -> None:
    """🔴 `SELECT DISTINCT` DID NOT DO WHAT IT LOOKED LIKE (Codex P2).

    The select list carried the investigation and the stance, so a test cited by
    two investigations produced two "distinct" rows — and §11 says a dashboard
    count is of items needing ACTION, so a double-counted test is a wrong
    answer, not a cosmetic one. The original test cited each test once and
    therefore could not have seen it.
    """
    second = owner_session.execute(
        text(
            """
            INSERT INTO research.investigations
                (organization_id, project_id, investigation_code, title,
                 research_question, owner_user_id, opened_by)
            VALUES (:o, :p, :c, 'Second workspace', 'Also about this test?', :u, :u)
            RETURNING id
            """
        ),
        {
            "o": fx["org"],
            "p": fx["project"],
            "c": f"RES-2W-{fx['suffix']}",
            "u": fx["user"],
        },
    ).scalar_one()

    test_id = _cited_test(owner_session, fx, fx["investigation"], "supports")
    # The SAME test, cited by a DIFFERENT investigation with a DIFFERENT stance
    # -- the two columns that made `DISTINCT` useless.
    source2 = owner_session.execute(
        text(
            "INSERT INTO research.sources (organization_id, investigation_id,"
            " source_kind, evidence_grade, title, recorded_by)"
            " VALUES (:o, :i, 'laboratory', 'A', 'Same result, other workspace', :u)"
            " RETURNING id"
        ),
        {"o": fx["org"], "i": second, "u": fx["user"]},
    ).scalar_one()
    owner_session.execute(
        text(
            "INSERT INTO research.evidence (organization_id, investigation_id,"
            " source_id, test_id, stance, summary, recorded_by)"
            " VALUES (:o, :i, :s, :t, 'contradicts', 'Reads the other way.', :u)"
        ),
        {"o": fx["org"], "i": second, "s": source2, "t": test_id, "u": fx["user"]},
    )

    panel = _panels(engineer_dashboard, fx, owner_session)["research_linked_tests"]
    assert panel["count"] == 1, f"the test was counted {panel['count']} times"
    row = panel["rows"][0]
    assert row["citation_count"] == 2
    assert sorted(row["stances"]) == ["contradicts", "supports"]
