"""The four role dashboards. TODO I4.

🔴 THE FAILURE MODE THESE TESTS EXIST TO CATCH IS AN EMPTY PANEL.

A dashboard query that references the wrong column fails loudly. A dashboard
query that filters on a value the vocabulary does not contain returns ZERO
ROWS and looks perfectly healthy — and "no blocked projects" is the single
most reassuring thing a Lead's screen can say. It is also, in that case, a
lie.

That is not hypothetical here. The first draft of `dashboards/service.py`
filtered `risks.impact = 'critical'`; the vocabulary is low|medium|high, so
the blocked-projects panel would have matched nothing, forever, while
reporting confidently that nothing was blocked. It also looked for
`milestones.due_date` and `status <> 'complete'` — the columns are
`planned_date` and `name`, and the statuses are
planned|in_progress|met|missed|cancelled.

So every test below SEEDS A RECORD THAT MUST APPEAR and asserts it does, by
id. A test that only checked "the endpoint returns four panels" would have
passed against every one of those defects.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.domains.dashboards.service import (
    chemist_dashboard,
    director_dashboard,
    engineer_dashboard,
    lead_dashboard,
)

# The permissions each panel gates on. §11 counts ACTIONABLE items, so a
# dashboard built with an empty permission set must show an empty queue --
# which is asserted below, because "shows nothing" is the failure mode a
# permission check introduces.
# 🔴 EVERY PERMISSION HERE IS ASSERTED TO EXIST by
# `test_every_gated_permission_is_a_real_permission` below. The first version
# of this file hardcoded `batch.review`, WHICH DOES NOT EXIST -- so the
# deviations panel returned empty for every real user forever while this
# suite passed, because the test supplied the phantom permission to itself.
ENGINEER_PERMS = frozenset({"test.review", "batch.execute", "batch.complete"})
LEAD_PERMS = frozenset({"test.approve_development", "test.approve_lead"})
DIRECTOR_PERMS = frozenset({"opportunity.view", "opportunity.decide"})


def _org_and_people(session: Session) -> dict[str, Any]:
    suffix = uuid.uuid4().hex[:8]
    org = session.execute(
        text("INSERT INTO core.organizations (code, name) VALUES (:c, :n) RETURNING id"),
        {"c": f"DASH-{suffix}", "n": "Dashboard Org"},
    ).scalar_one()

    people: dict[str, uuid.UUID] = {}
    for role in ("chemist", "engineer", "lead", "director"):
        uid = session.execute(
            text(
                "INSERT INTO core.users (keycloak_sub, email, display_name) "
                "VALUES (:s, :e, :n) RETURNING id"
            ),
            {"s": str(uuid.uuid4()), "e": f"{role}-{suffix}@example.test", "n": role},
        ).scalar_one()
        session.execute(
            text(
                "INSERT INTO core.organization_members (organization_id, user_id, status,"
                " email, display_name) SELECT :o, :u, 'active', u.email, u.display_name FROM"
                " core.users u WHERE u.id = :u"
            ),
            {"o": org, "u": uid},
        )
        people[role] = uid

    project = session.execute(
        text(
            """
            INSERT INTO projects.projects
                (organization_id, project_code, name, confidentiality, status,
                 priority, lead_user_id)
            VALUES (:o, :c, 'Dashboard project', 'normal', 'active', 'high', :lead)
            RETURNING id
            """
        ),
        {"o": org, "c": f"RDP-D-{suffix}", "lead": people["lead"]},
    ).scalar_one()
    session.flush()
    return {"org": org, "project": project, "suffix": suffix, **people}


def test_a_chemists_active_formulation_appears_on_their_dashboard(
    owner_session: Session,
) -> None:
    """The panel finds a real record, by id.

    Asserted by ID rather than by count: a count of 1 is satisfied by the
    WRONG row, and this panel joins three tables.
    """
    fx = _org_and_people(owner_session)

    formula = owner_session.execute(
        text(
            """
            INSERT INTO formulations.formulas
                (organization_id, project_id, formula_code, name, created_by,
                 owner_user_id)
            VALUES (:o, :p, :c, 'Test filler', :u, :u) RETURNING id
            """
        ),
        {"o": fx["org"], "p": fx["project"], "c": f"FRM-D-{fx['suffix']}", "u": fx["chemist"]},
    ).scalar_one()
    version = owner_session.execute(
        text(
            """
            INSERT INTO formulations.formula_versions
                (organization_id, project_id, formula_id, version_number, version_code,
                 status, created_by)
            VALUES (:o, :p, :f, 1, :vc, 'draft', :u) RETURNING id
            """
        ),
        {
            "o": fx["org"],
            "p": fx["project"],
            "f": formula,
            "vc": f"FRM-D-{fx['suffix']}-V1",
            "u": fx["chemist"],
        },
    ).scalar_one()
    owner_session.flush()

    board = chemist_dashboard(owner_session, user_id=fx["chemist"], organization_id=fx["org"])
    panel = board["panels"]["my_active_formulations"]

    assert panel["available"] is True
    assert version in [r["id"] for r in panel["rows"]], (
        "a chemist's own draft formulation is missing from their dashboard"
    )


def test_another_chemists_work_is_not_on_my_dashboard(owner_session: Session) -> None:
    """The relevance filter, proved in the negative.

    Without this, a panel returning EVERY formulation in the organization
    passes the test above. "Mine" has to exclude something or it is not a
    filter at all.
    """
    fx = _org_and_people(owner_session)

    formula = owner_session.execute(
        text(
            """
            INSERT INTO formulations.formulas
                (organization_id, project_id, formula_code, name, created_by,
                 owner_user_id)
            VALUES (:o, :p, :c, 'Someone elses', :u, :u) RETURNING id
            """
        ),
        {"o": fx["org"], "p": fx["project"], "c": f"FRM-X-{fx['suffix']}", "u": fx["engineer"]},
    ).scalar_one()
    owner_session.execute(
        text(
            """
            INSERT INTO formulations.formula_versions
                (organization_id, project_id, formula_id, version_number, version_code,
                 status, created_by)
            VALUES (:o, :p, :f, 1, :vc, 'draft', :u)
            """
        ),
        {
            "o": fx["org"],
            "p": fx["project"],
            "f": formula,
            "vc": f"FRM-X-{fx['suffix']}-V1",
            "u": fx["engineer"],
        },
    )
    owner_session.flush()

    board = chemist_dashboard(owner_session, user_id=fx["chemist"], organization_id=fx["org"])
    assert board["panels"]["my_active_formulations"]["rows"] == [], (
        "the chemist dashboard is showing another person's formulations"
    )


def test_a_high_impact_risk_blocks_the_lead_dashboard_project(
    owner_session: Session,
) -> None:
    """🔴 THE VOCABULARY BUG THIS FILE WAS WRITTEN FOR.

    `risks.impact` is low|medium|high. The first draft filtered on
    'critical', which the constraint does not permit — so the panel matched
    NOTHING and reported "no blocked projects" no matter what was wrong.
    """
    fx = _org_and_people(owner_session)

    owner_session.execute(
        text(
            """
            INSERT INTO projects.risks
                (organization_id, project_id, risk_code, title, category,
                 probability, impact, status, owner_user_id)
            VALUES (:o, :p, :c, 'Sole-source resin', 'supply',
                    'high', 'high', 'open', :u)
            """
        ),
        {"o": fx["org"], "p": fx["project"], "c": f"RSK-{fx['suffix']}", "u": fx["lead"]},
    )
    owner_session.flush()

    board = lead_dashboard(
        owner_session,
        user_id=fx["lead"],
        organization_id=fx["org"],
        held_permissions=LEAD_PERMS,
    )

    blocked = board["panels"]["blocked_projects"]
    assert blocked["count"] >= 1, (
        "a project with an open high-impact risk is not showing as blocked - "
        "the panel is almost certainly filtering on a value the vocabulary "
        "does not contain"
    )
    assert "high-impact risk" in blocked["rows"][0]["blocked_by"]

    risks = board["panels"]["risks"]
    assert risks["count"] == 1
    assert risks["rows"][0]["title"] == "Sole-source resin"


def test_an_overdue_milestone_blocks_the_lead_dashboard_project(
    owner_session: Session,
) -> None:
    """The other half of `blocked_projects`, and the other column bug.

    The columns are `name` and `planned_date`, not `title` and `due_date`,
    and there is no `complete` status.
    """
    fx = _org_and_people(owner_session)

    owner_session.execute(
        text(
            """
            INSERT INTO projects.milestones
                (organization_id, project_id, name, planned_date, status)
            VALUES (:o, :p, 'Pilot batch ready', CURRENT_DATE - 7, 'planned')
            """
        ),
        {"o": fx["org"], "p": fx["project"]},
    )
    owner_session.flush()

    board = lead_dashboard(
        owner_session,
        user_id=fx["lead"],
        organization_id=fx["org"],
        held_permissions=LEAD_PERMS,
    )

    blocked = board["panels"]["blocked_projects"]
    assert blocked["count"] == 1
    assert "overdue milestone" in blocked["rows"][0]["blocked_by"], (
        "an overdue milestone is not blocking its project"
    )
    assert board["panels"]["milestones"]["count"] == 1


def test_a_met_milestone_does_not_block_anything(owner_session: Session) -> None:
    """The negative that makes the test above mean something.

    Without it, a panel that listed EVERY milestone regardless of status
    would pass. `met` and `missed` are the closed states.
    """
    fx = _org_and_people(owner_session)

    owner_session.execute(
        text(
            """
            INSERT INTO projects.milestones
                (organization_id, project_id, name, planned_date, status, actual_date)
            VALUES (:o, :p, 'Kickoff', CURRENT_DATE - 30, 'met', CURRENT_DATE - 29)
            """
        ),
        {"o": fx["org"], "p": fx["project"]},
    )
    owner_session.flush()

    board = lead_dashboard(
        owner_session,
        user_id=fx["lead"],
        organization_id=fx["org"],
        held_permissions=LEAD_PERMS,
    )
    assert board["panels"]["blocked_projects"]["rows"] == []
    assert board["panels"]["milestones"]["rows"] == []


def test_an_open_deviation_reaches_the_engineer(owner_session: Session) -> None:
    """Process deviations, and only unresolved ones."""
    fx = _org_and_people(owner_session)

    material = owner_session.execute(
        text(
            """
            INSERT INTO materials.materials
                (organization_id, material_code, name, category, role, status, created_by)
            VALUES (:o, :c, 'Resin', 'Resin', 'resin', 'approved', :u) RETURNING id
            """
        ),
        {"o": fx["org"], "c": f"RM-D-{fx['suffix']}", "u": fx["chemist"]},
    ).scalar_one()
    formula = owner_session.execute(
        text(
            """
            INSERT INTO formulations.formulas
                (organization_id, project_id, formula_code, name, created_by,
                 owner_user_id)
            VALUES (:o, :p, :c, 'Dev filler', :u, :u) RETURNING id
            """
        ),
        {"o": fx["org"], "p": fx["project"], "c": f"FRM-DV-{fx['suffix']}", "u": fx["chemist"]},
    ).scalar_one()
    version = owner_session.execute(
        text(
            """
            INSERT INTO formulations.formula_versions
                (organization_id, project_id, formula_id, version_number, version_code,
                 status, created_by, approved_by, approved_at)
            -- An 'approved' version must NAME its approver
            -- (`formula_versions_approved_states_have_an_approver`). §8's rule
            -- that humans approve, enforced by the schema rather than trusted
            -- to the writer.
            VALUES (:o, :p, :f, 1, :vc, 'approved', :u, :u, now()) RETURNING id
            """
        ),
        {
            "o": fx["org"],
            "p": fx["project"],
            "f": formula,
            "vc": f"FRM-DV-{fx['suffix']}-V1",
            "u": fx["chemist"],
        },
    ).scalar_one()
    assert material is not None

    batch = owner_session.execute(
        text(
            """
            INSERT INTO laboratory.batches
                (organization_id, project_id, formula_version_id, batch_number,
                 planned_quantity_kg, status, authorized_by, authorized_at, created_by)
            VALUES (:o, :p, :v, :bn, :q, 'in_progress', :u, now(), :u) RETURNING id
            """
        ),
        {
            "o": fx["org"],
            "p": fx["project"],
            "v": version,
            "bn": f"LB-D-{fx['suffix']}",
            "q": Decimal("1.0"),
            "u": fx["engineer"],
        },
    ).scalar_one()

    owner_session.execute(
        text(
            """
            INSERT INTO laboratory.batch_deviations
                (organization_id, project_id, batch_id, description, severity, raised_by)
            VALUES (:o, :p, :b, 'Mixer ran 4 minutes long', 'major', :u)
            """
        ),
        {"o": fx["org"], "p": fx["project"], "b": batch, "u": fx["engineer"]},
    )
    owner_session.flush()

    board = engineer_dashboard(
        owner_session,
        user_id=fx["engineer"],
        organization_id=fx["org"],
        held_permissions=ENGINEER_PERMS,
    )
    deviations = board["panels"]["process_deviations"]
    assert deviations["count"] == 1
    assert deviations["rows"][0]["severity"] == "major"


def test_an_opportunity_awaiting_decision_reaches_the_director(
    owner_session: Session,
) -> None:
    """The Director's queue is the innovation gate, not a project list."""
    fx = _org_and_people(owner_session)

    owner_session.execute(
        text(
            """
            INSERT INTO innovation.opportunities
                (organization_id, opportunity_code, title, status, priority, created_by)
            VALUES (:o, :c, 'New putty line', 'awaiting_decision', 'high', :u)
            """
        ),
        {"o": fx["org"], "c": f"OPP-D-{fx['suffix']}", "u": fx["director"]},
    )
    owner_session.flush()

    board = director_dashboard(
        owner_session,
        user_id=fx["director"],
        organization_id=fx["org"],
        held_permissions=DIRECTOR_PERMS,
    )
    awaiting = board["panels"]["projects_awaiting_approval"]
    assert awaiting["count"] == 1
    assert awaiting["rows"][0]["title"] == "New putty line"


def test_every_role_returns_every_panel_the_source_names(owner_session: Session) -> None:
    """The shape contract, including the panels that cannot be answered.

    🔴 A MISSING PANEL AND AN EMPTY ONE ARE OPPOSITE STATEMENTS. `available:
    false` with a reason says "not built"; an empty list says "nothing to
    report". A screen cannot tell them apart, so the API must.
    """
    fx = _org_and_people(owner_session)
    expected = {
        "chemist": (
            chemist_dashboard,
            {
                "my_active_formulations",
                "pending_lab_results",
                "failed_tests",
                "reformulations",
                "doe_experiments",
                "validation_candidates",
                # §27's chemist widgets (Phase 5).
                "safety_reviews_required",
                "research_investigations",
                "experiment_proposals",
                "material_alerts",
            },
        ),
        "engineer": (
            engineer_dashboard,
            {
                "pending_test_plans",
                "engineering_reviews",
                "pilot_projects",
                "scale_up",
                "process_deviations",
                "qualification_tasks",
                # §27's engineer widgets (Phase 5).
                "research_linked_tests",
                "safety_process_issues",
                "benchmark_investigations",
            },
        ),
        "lead": (
            lead_dashboard,
            {
                "assigned_projects",
                "pipeline_status",
                "blocked_projects",
                "pending_approvals",
                "risks",
                "milestones",
                # §27's lead widgets (Phase 5).
                "research_pipeline",
                "critical_safety_alerts",
                "knowledge_gaps",
                "experiment_proposal_queue",
            },
        ),
        "director": (
            director_dashboard,
            {
                "rd_portfolio",
                "innovation_pipeline",
                "critical_risks",
                "projects_awaiting_approval",
                # §27's director widgets (Phase 5).
                "competitor_intelligence",
                "technology_opportunities",
                "critical_material_risks",
                "research_portfolio",
                "pilot_qualification_pipeline",
                "products_awaiting_release",
            },
        ),
    }

    perms = {
        "chemist": frozenset(),
        "engineer": ENGINEER_PERMS,
        "lead": LEAD_PERMS,
        "director": DIRECTOR_PERMS,
    }
    for role, (builder, panels) in expected.items():
        board = builder(
            owner_session,
            user_id=fx[role],
            organization_id=fx["org"],
            held_permissions=perms[role],
        )
        assert board["role"] == role
        assert set(board["panels"]) == panels, f"{role}: panels do not match the source"

        for name, panel in board["panels"].items():
            assert set(panel) == {"available", "reason", "rows", "count", "truncated"}
            assert panel["count"] == len(panel["rows"])
            if panel["available"] is False:
                assert panel["reason"], (
                    f"{role}.{name} is unavailable and does not say why - a screen "
                    "cannot tell that from 'nothing to report'"
                )
                assert panel["rows"] == []


def test_an_unbuilt_panel_says_which_slice_will_build_it(owner_session: Session) -> None:
    """The reason has to be actionable, not merely present.

    "Not available" tells a reader nothing they can plan around. Naming the
    slice is the difference between a gap and a schedule.
    """
    fx = _org_and_people(owner_session)
    board = chemist_dashboard(owner_session, user_id=fx["chemist"], organization_id=fx["org"])
    doe = board["panels"]["doe_experiments"]

    assert doe["available"] is False
    assert "Slice 12" in doe["reason"]


def test_a_panel_gated_on_a_permission_is_empty_without_it(
    owner_session: Session,
) -> None:
    """🔴 THE NEGATIVE THAT MAKES THE PERMISSION CHECK MEAN SOMETHING.

    Codex found that `engineering_reviews`, `process_deviations` and
    `pending_approvals` counted work the caller cannot perform — RLS says
    what may be SEEN, a permission says what may be DONE, and §11 counts the
    second.

    Without this test a check that silently did nothing would pass every
    other test in this file, because they all supply the permission.
    """
    fx = _org_and_people(owner_session)

    owner_session.execute(
        text(
            """
            INSERT INTO projects.risks
                (organization_id, project_id, risk_code, title, category,
                 probability, impact, status, owner_user_id)
            VALUES (:o, :p, :c, 'Something', 'supply', 'high', 'high', 'open', :u)
            """
        ),
        {"o": fx["org"], "p": fx["project"], "c": f"RSK-N-{fx['suffix']}", "u": fx["lead"]},
    )
    owner_session.flush()

    # No permissions at all.
    board = lead_dashboard(
        owner_session,
        user_id=fx["lead"],
        organization_id=fx["org"],
        held_permissions=frozenset(),
    )

    assert board["panels"]["pending_approvals"]["rows"] == [], (
        "a caller holding no approval permission was offered approval work"
    )
    # ...but the panels that are about VISIBILITY rather than action still
    # answer. A dashboard that went blank without permissions would be a
    # different defect.
    assert board["panels"]["risks"]["count"] == 1
    assert board["panels"]["assigned_projects"]["count"] == 1

    engineer = engineer_dashboard(
        owner_session,
        user_id=fx["engineer"],
        organization_id=fx["org"],
        held_permissions=frozenset(),
    )
    # 🔴 AND THEY SAY "NOT PERMITTED", NOT "NOTHING TO REPORT" (Supervisor
    # finding 3). An empty list is byte-identical to a genuinely empty queue,
    # so a technician was told there were no deviations while there were
    # twelve.
    reviews = engineer["panels"]["engineering_reviews"]
    assert reviews["available"] is False
    assert "test.review" in reviews["reason"]
    deviations = engineer["panels"]["process_deviations"]
    assert deviations["available"] is False
    assert "batch.execute" in deviations["reason"]


def test_blocked_projects_counts_projects_not_blockers(owner_session: Session) -> None:
    """🔴 ONE PROJECT WITH THREE BLOCKERS IS ONE BLOCKED PROJECT.

    Codex finding 5: the first version UNION ALL'd risks and milestones, so a
    project with three risks and two overdue milestones reported `count: 5`
    on a panel named "blocked projects". Every other test here seeds ONE
    blocker, so none of them could have caught it.
    """
    fx = _org_and_people(owner_session)

    for n in range(3):
        owner_session.execute(
            text(
                """
                INSERT INTO projects.risks
                    (organization_id, project_id, risk_code, title, category,
                     probability, impact, status, owner_user_id)
                VALUES (:o, :p, :c, :t, 'supply', 'high', 'high', 'open', :u)
                """
            ),
            {
                "o": fx["org"],
                "p": fx["project"],
                "c": f"RSK-M{n}-{fx['suffix']}",
                "t": f"Risk {n}",
                "u": fx["lead"],
            },
        )
    for n in range(2):
        owner_session.execute(
            text(
                """
                INSERT INTO projects.milestones
                    (organization_id, project_id, name, planned_date, status)
                VALUES (:o, :p, :n, CURRENT_DATE - 3, 'planned')
                """
            ),
            {"o": fx["org"], "p": fx["project"], "n": f"Milestone {n}"},
        )
    owner_session.flush()

    board = lead_dashboard(
        owner_session,
        user_id=fx["lead"],
        organization_id=fx["org"],
        held_permissions=LEAD_PERMS,
    )
    blocked = board["panels"]["blocked_projects"]

    assert blocked["count"] == 1, (
        f"five blockers on one project reported as {blocked['count']} blocked projects"
    )
    row = blocked["rows"][0]
    assert row["blocker_count"] == 5
    assert sorted(row["blocked_by"]) == ["high-impact risk", "overdue milestone"]


def test_every_gated_permission_is_a_real_permission(owner_session: Session) -> None:
    """🔴 THE TEST THAT WOULD HAVE CAUGHT `batch.review`.

    The dashboards gate four panels on permissions. A gate naming a
    permission that DOES NOT EXIST cannot ever open, so the panel returns
    empty for every real user forever — and the suite passed anyway, because
    the tests supplied the phantom permission to themselves.

    `core.permissions` is the authority. This asserts every string the module
    gates on is in it. Raised by the Supervisor, after Codex's permission
    fixes introduced the phantom.
    """
    import re
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[2] / "app" / "domains" / "dashboards" / "service.py"
    ).read_text(encoding="utf-8")

    # Every permission-looking literal the module tests membership against.
    gated = set(re.findall(r'"([a-z_]+\.[a-z_]+)" in held_permissions', source))
    gated |= set(
        (
            re.findall(r"held_permissions & \{([^}]*)\}", source)
            and re.findall(
                r'"([a-z_]+\.[a-z_]+)"', re.findall(r"held_permissions & \{([^}]*)\}", source)[0]
            )
        )
        or []
    )
    assert gated, "found no permission gates to check - the regex has drifted from the code"

    real = {r[0] for r in owner_session.execute(text("SELECT code FROM core.permissions"))}
    phantom = gated - real
    assert not phantom, (
        f"these panels gate on permissions that do not exist: {sorted(phantom)}. "
        "No user can ever hold one, so the panel is empty for everyone while "
        "reporting itself available."
    )


def test_a_director_without_opportunity_view_sees_no_innovation_pipeline(
    owner_session: Session,
) -> None:
    """🔴 THE DISCLOSURE THE `project.view` FLOOR ALLOWED.

    `innovation.opportunities` carries an ORGANIZATION-ONLY RLS policy — no
    project predicate, no confidentiality — while `/api/opportunities` guards
    the same rows with `opportunity.view`. The dashboard's floor was
    `project.view`, so a laboratory_technician calling
    `/api/dashboards/director` received every unannounced opportunity in the
    company, including the Director's whole decision queue.

    The route docstring's argument — "RLS decides what the caller sees" —
    was false for org-scoped tables. Raised by the Supervisor.
    """
    fx = _org_and_people(owner_session)
    owner_session.execute(
        text(
            """
            INSERT INTO innovation.opportunities
                (organization_id, opportunity_code, title, status, priority, created_by)
            VALUES (:o, :c, 'Confidential new line', 'awaiting_decision', 'high', :u)
            """
        ),
        {"o": fx["org"], "c": f"OPP-S-{fx['suffix']}", "u": fx["director"]},
    )
    owner_session.flush()

    # Somebody with project access and no opportunity permissions at all.
    board = director_dashboard(
        owner_session,
        user_id=fx["chemist"],
        organization_id=fx["org"],
        held_permissions=frozenset({"project.view"}),
    )

    pipeline = board["panels"]["innovation_pipeline"]
    assert pipeline["available"] is False, (
        "the innovation pipeline was disclosed to somebody without opportunity.view"
    )
    assert pipeline["rows"] == []

    queue = board["panels"]["projects_awaiting_approval"]
    assert queue["available"] is False
    assert queue["rows"] == []
