"""Project dashboard.

The assertion that carries the most weight here is
:func:`test_requirement_buckets_partition_the_status_set`. A dashboard
that shows parts which do not sum to the whole is wrong in a way nobody
reports as a bug -- users quietly stop believing the tile, and by the
time somebody checks, decisions have been made on it.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy import text

from app.domains.projects.dashboard import project_context, project_dashboard


@pytest.fixture
def dash_world(owner_session):
    suffix = uuid.uuid4().hex[:8]

    org = owner_session.execute(
        text("INSERT INTO core.organizations (code, name) VALUES (:c, :n) RETURNING id"),
        {"c": f"DASH-{suffix}", "n": "Dashboard Test Org"},
    ).scalar_one()

    lead = owner_session.execute(
        text(
            """
            INSERT INTO core.users (keycloak_sub, email, display_name)
            VALUES (:s, :e, 'Dash Lead') RETURNING id
            """
        ),
        {"s": str(uuid.uuid4()), "e": f"dashlead-{suffix}@example.test"},
    ).scalar_one()
    owner_session.execute(
        text(
            "INSERT INTO core.organization_members (organization_id, user_id, status, email,"
            " display_name) SELECT :o, :u, 'active', u.email, u.display_name FROM core.users u"
            " WHERE u.id = :u"
        ),
        {"o": org, "u": lead},
    )

    project = owner_session.execute(
        text(
            """
            INSERT INTO projects.projects
                (organization_id, project_code, name, lead_user_id, priority)
            VALUES (:o, :c, 'Dashboard Project', :lead, 'high') RETURNING id
            """
        ),
        {"o": org, "c": f"RDP-D-{suffix}", "lead": lead},
    ).scalar_one()

    owner_session.flush()
    return {"org": org, "project": project, "lead": lead, "suffix": suffix}


def _requirement(owner_session, world, code, status, criticality="major"):
    owner_session.execute(
        text(
            """
            INSERT INTO projects.requirements
                (organization_id, project_id, requirement_code, name,
                 status, criticality, created_by)
            VALUES (:o, :p, :c, :n, :s, :crit, :u)
            """
        ),
        {
            "o": world["org"],
            "p": world["project"],
            "c": f"REQ-{world['suffix']}-{code}",
            "n": f"Requirement {code}",
            "s": status,
            "crit": criticality,
            "u": world["lead"],
        },
    )


def test_requirement_buckets_partition_the_status_set(owner_session, dash_world):
    """live + settled + retired must equal total, for ALL SIX statuses.

    The first version of this query counted only 'approved', 'draft' and
    'superseded', silently dropping under_review, locked and withdrawn.
    Nothing type-checks a bucket list against a CHECK constraint.
    """
    for i, status_value in enumerate(
        ["draft", "under_review", "approved", "locked", "superseded", "withdrawn"]
    ):
        _requirement(owner_session, dash_world, f"{i:02d}", status_value)
    owner_session.flush()

    reqs = project_dashboard(
        owner_session,
        project_id=dash_world["project"],
        organization_id=dash_world["org"],
    )["requirements"]

    assert reqs["total"] == 6
    assert reqs["live"] + reqs["settled"] + reqs["retired"] == reqs["total"]
    assert reqs["live"] == 2  # draft, under_review
    assert reqs["settled"] == 2  # approved, locked
    assert reqs["retired"] == 2  # superseded, withdrawn


def test_retired_criticals_do_not_raise_a_false_alarm(owner_session, dash_world):
    """A withdrawn critical requirement is closed work, not outstanding."""
    _requirement(owner_session, dash_world, "C1", "withdrawn", criticality="critical")
    _requirement(owner_session, dash_world, "C2", "superseded", criticality="critical")
    _requirement(owner_session, dash_world, "C3", "draft", criticality="critical")
    owner_session.flush()

    reqs = project_dashboard(
        owner_session,
        project_id=dash_world["project"],
        organization_id=dash_world["org"],
    )["requirements"]

    assert reqs["critical"] == 3
    # Only the draft one is genuinely outstanding.
    assert reqs["critical_unapproved"] == 1


def test_the_dashboard_answers_all_five_questions(owner_session, dash_world):
    """CLAUDE.md §11. A missing answer must be a missing key, not a
    panel somebody forgot to add."""
    data = project_dashboard(
        owner_session,
        project_id=dash_world["project"],
        organization_id=dash_world["org"],
    )
    for key in (
        "context",  # where am I
        "requirements",  # what is the status
        "milestones",
        "risks",
        "tasks",  # what requires action
        "action_items",
        "recent_transitions",  # what changed
    ):
        assert key in data, f"the dashboard does not answer '{key}'"


def test_counts_drill_down_to_real_records(owner_session, dash_world):
    """A tile saying '2 overdue' that cannot say WHICH two is a number
    the user has to re-derive by hand (CLAUDE.md §2)."""
    yesterday = date.today() - timedelta(days=1)
    for label, due, priority in [
        ("Overdue A", yesterday, "critical"),
        ("Overdue B", yesterday, "high"),
        ("Not due", date.today() + timedelta(days=10), "low"),
    ]:
        owner_session.execute(
            text(
                """
                INSERT INTO workflow.tasks
                    (organization_id, project_id, task_type, title,
                     priority, due_date, assigned_user_id)
                VALUES (:o, :p, 'review', :t, :pri, :due, :u)
                """
            ),
            {
                "o": dash_world["org"],
                "p": dash_world["project"],
                "t": label,
                "pri": priority,
                "due": due,
                "u": dash_world["lead"],
            },
        )
    owner_session.flush()

    data = project_dashboard(
        owner_session,
        project_id=dash_world["project"],
        organization_id=dash_world["org"],
    )

    assert data["tasks"]["overdue"] == 2
    assert data["tasks"]["open"] == 3
    # ...and the records behind the number are present, most urgent first.
    titles = [a["title"] for a in data["action_items"]]
    assert titles[:2] == ["Overdue A", "Overdue B"]
    assert set(titles) == {"Overdue A", "Overdue B", "Not due"}


def test_counts_do_not_fan_out_across_tables(owner_session, dash_world):
    """The classic dashboard defect: one wide join multiplying rows.

    Three requirements and three tasks joined together would report nine
    of each. Separate queries are the reason they do not.
    """
    for i in range(3):
        _requirement(owner_session, dash_world, f"F{i}", "draft")
        owner_session.execute(
            text(
                """
                INSERT INTO workflow.tasks
                    (organization_id, project_id, task_type, title, assigned_user_id)
                VALUES (:o, :p, 'review', :t, :u)
                """
            ),
            {
                "o": dash_world["org"],
                "p": dash_world["project"],
                "t": f"Fanout task {i}",
                "u": dash_world["lead"],
            },
        )
    owner_session.execute(
        text(
            """
            INSERT INTO projects.risks
                (organization_id, project_id, risk_code, title, probability, impact)
            VALUES (:o, :p, :c, 'A risk', 'high', 'high')
            """
        ),
        {"o": dash_world["org"], "p": dash_world["project"], "c": f"RSK-{dash_world['suffix']}"},
    )
    owner_session.flush()

    data = project_dashboard(
        owner_session,
        project_id=dash_world["project"],
        organization_id=dash_world["org"],
    )
    assert data["requirements"]["total"] == 3
    assert data["tasks"]["open"] == 3
    assert data["risks"]["open"] == 1
    assert data["risks"]["high_high"] == 1


def test_context_is_none_for_another_organizations_project(owner_session, dash_world):
    """Explicit organization filtering, not RLS.

    RLS is permissive while the GUC is unset and the owner role bypasses
    it entirely -- exactly the conditions this test runs under. A query
    that leans on RLS for scoping passes here and leaks in production.
    """
    other_org = owner_session.execute(
        text("INSERT INTO core.organizations (code, name) VALUES (:c, :n) RETURNING id"),
        {"c": f"OTHER-{dash_world['suffix']}", "n": "Other Org"},
    ).scalar_one()
    owner_session.flush()

    assert (
        project_context(owner_session, project_id=dash_world["project"], organization_id=other_org)
        is None
    )


def test_context_reports_position_in_the_pipeline(owner_session, dash_world):
    """'Where am I in the process' needs the whole path, not just the step."""
    for seq, code in enumerate(["CONCEPT", "FEASIBILITY", "FORMULATION"], start=1):
        owner_session.execute(
            text(
                """
                INSERT INTO workflow.stage_definitions
                    (organization_id, stage_code, name, sequence)
                VALUES (:o, :c, :n, :s)
                """
            ),
            {"o": dash_world["org"], "c": code, "n": code.title(), "s": seq},
        )
    owner_session.execute(
        text("UPDATE projects.projects SET current_stage = 'FEASIBILITY' WHERE id = :p"),
        {"p": dash_world["project"]},
    )
    owner_session.flush()

    context = project_context(
        owner_session,
        project_id=dash_world["project"],
        organization_id=dash_world["org"],
    )
    assert context is not None
    assert context["current_stage"] == "FEASIBILITY"
    assert context["current_stage_sequence"] == 2
    assert context["total_stages"] == 3
