"""Regression tests for the Slice 2 review findings.

One test per defect Codex found, named after what breaks rather than
after the function, so a future failure reads as a statement about the
product.

Two classes of defect dominate, and both are invisible to a type-checker:

  **Cross-tenant references.** Every FK to `core.users` is a plain
  `REFERENCES core.users(id)`, because users are not tenant-scoped.
  Referential integrity bypasses RLS even under FORCE, so RLS -- the
  thing that makes every other query safe -- provides no protection here
  at all.

  **Read-then-write races.** A rule checked in a SELECT and enforced in a
  later UPDATE is true at read time and unknown at write time. These
  matter more than usual in this codebase because two of them are the
  stated justification for other decisions: "only the assignee may
  complete" is why `/api/my-work` carries no permission dependency, and
  "a second decision is refused" is why decision history is claimed to be
  preserved.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.core.tenancy import CrossTenantReferenceError
from app.domains.opportunities.service import (
    OpportunityDecision,
    OpportunityInput,
    OpportunityStateError,
    convert_to_project,
    create_opportunity,
    decide_opportunity,
)
from app.domains.tasks.service import (
    TaskInput,
    TaskStateError,
    complete_task,
    create_task,
    reassign_task,
)


@pytest.fixture
def two_tenants(owner_session):
    """Two organizations, each with one active member, plus a project."""
    suffix = uuid.uuid4().hex[:8]
    out = {"suffix": suffix}

    for label in ("a", "b"):
        org = owner_session.execute(
            text("INSERT INTO core.organizations (code, name) VALUES (:c, :n) RETURNING id"),
            {"c": f"XT-{label.upper()}-{suffix}", "n": f"Tenant {label.upper()}"},
        ).scalar_one()
        user = owner_session.execute(
            text(
                """
                INSERT INTO core.users (keycloak_sub, email, display_name)
                VALUES (:s, :e, :n) RETURNING id
                """
            ),
            {
                "s": str(uuid.uuid4()),
                "e": f"{label}-{suffix}@example.test",
                "n": f"User {label.upper()}",
            },
        ).scalar_one()
        owner_session.execute(
            text(
                """
                INSERT INTO core.organization_members (organization_id, user_id, status)
                VALUES (:o, :u, 'active')
                """
            ),
            {"o": org, "u": user},
        )
        out[f"org_{label}"] = org
        out[f"user_{label}"] = user

    out["project_a"] = owner_session.execute(
        text(
            """
            INSERT INTO projects.projects
                (organization_id, project_code, name, lead_user_id)
            VALUES (:o, :c, 'Tenant A project', :u) RETURNING id
            """
        ),
        {"o": out["org_a"], "c": f"RDP-XT-{suffix}", "u": out["user_a"]},
    ).scalar_one()

    owner_session.flush()
    return out


# ---------------------------------------------------------------------------
# C1 -- create_task accepted a foreign-tenant assignee
# ---------------------------------------------------------------------------


def test_a_task_cannot_be_assigned_to_another_tenants_user(owner_session, two_tenants):
    """The FK permits it. Nothing below the service would have caught it."""
    with pytest.raises(CrossTenantReferenceError, match="assignee"):
        create_task(
            owner_session,
            data=TaskInput(
                task_type="review",
                title="Cross-tenant assignment",
                assigned_user_id=two_tenants["user_b"],
                project_id=two_tenants["project_a"],
            ),
            actor_id=two_tenants["user_a"],
            organization_id=two_tenants["org_a"],
        )


def test_the_database_alone_would_have_allowed_it(owner_session, two_tenants):
    """Proves the service check is load-bearing, not belt-and-braces.

    If the FK already refused this, the test above would pass for the
    wrong reason and the service check could be deleted without any test
    noticing. It does not refuse: users are not tenant-scoped.
    """
    owner_session.execute(
        text(
            """
            INSERT INTO workflow.tasks
                (organization_id, project_id, task_type, title, assigned_user_id)
            VALUES (:o, :p, 'review', 'Raw cross-tenant insert', :u)
            """
        ),
        {
            "o": two_tenants["org_a"],
            "p": two_tenants["project_a"],
            "u": two_tenants["user_b"],
        },
    )
    owner_session.flush()  # succeeds -- which is exactly the problem


# ---------------------------------------------------------------------------
# C2 -- convert_to_project enrolled a foreign-tenant lead as a member
# ---------------------------------------------------------------------------


def test_a_project_lead_must_belong_to_the_organization(owner_session, two_tenants):
    """The worst of the cross-tenant findings.

    This did not merely store a foreign id: it went on to INSERT that
    user into project_members, handing them access to the new project.
    """
    opportunity_id = create_opportunity(
        owner_session,
        data=OpportunityInput(
            opportunity_code=f"OPP-XT-{two_tenants['suffix']}",
            title="Cross-tenant lead",
        ),
        actor_id=two_tenants["user_a"],
        organization_id=two_tenants["org_a"],
    )
    owner_session.execute(
        text(
            """
            UPDATE innovation.opportunities SET status = 'awaiting_decision'
            WHERE id = :i AND organization_id = :o
            """
        ),
        {"i": opportunity_id, "o": two_tenants["org_a"]},
    )
    owner_session.flush()
    decide_opportunity(
        owner_session,
        opportunity_id=opportunity_id,
        decision=OpportunityDecision("approve", "Approved"),
        actor_id=two_tenants["user_a"],
        organization_id=two_tenants["org_a"],
    )
    owner_session.flush()

    with pytest.raises(CrossTenantReferenceError, match="project lead"):
        convert_to_project(
            owner_session,
            opportunity_id=opportunity_id,
            project_code=f"RDP-XTL-{two_tenants['suffix']}",
            name="Should not exist",
            lead_user_id=two_tenants["user_b"],
            actor_id=two_tenants["user_a"],
            organization_id=two_tenants["org_a"],
        )

    # And no membership row was created as a side effect.
    leaked = owner_session.execute(
        text(
            """
            SELECT COUNT(*) FROM projects.project_members
            WHERE user_id = :u AND organization_id = :o
            """
        ),
        {"u": two_tenants["user_b"], "o": two_tenants["org_a"]},
    ).scalar_one()
    assert leaked == 0


def test_an_inactive_member_is_not_a_member(owner_session, two_tenants):
    """`status = 'active'` is part of the predicate, not decoration.

    A revoked membership row still exists. Treating its presence as
    membership leaves a removed employee assignable, and the person who
    removed them gets no signal that it did not take effect.
    """
    owner_session.execute(
        text(
            """
            UPDATE core.organization_members SET status = 'inactive'
            WHERE user_id = :u AND organization_id = :o
            """
        ),
        {"u": two_tenants["user_a"], "o": two_tenants["org_a"]},
    )
    owner_session.flush()

    with pytest.raises(CrossTenantReferenceError):
        create_task(
            owner_session,
            data=TaskInput(
                task_type="review",
                title="To a revoked member",
                assigned_user_id=two_tenants["user_a"],
            ),
            actor_id=two_tenants["user_a"],
            organization_id=two_tenants["org_a"],
        )


# ---------------------------------------------------------------------------
# C3 / C6 -- read-then-write races in the task service
# ---------------------------------------------------------------------------


def _task_for(owner_session, two_tenants, title="Race subject"):
    return create_task(
        owner_session,
        data=TaskInput(
            task_type="review",
            title=title,
            assigned_user_id=two_tenants["user_a"],
            project_id=two_tenants["project_a"],
        ),
        actor_id=two_tenants["user_a"],
        organization_id=two_tenants["org_a"],
    )


def test_ownership_is_enforced_at_write_time_not_read_time(owner_session, two_tenants):
    """C3. The guarantee `/api/my-work` relies on to carry no permission.

    Simulated by changing the assignee out from under the caller between
    the moment they would have read the row and the moment they write --
    which is what a concurrent reassignment does.
    """
    task_id = _task_for(owner_session, two_tenants)

    # A second active member of the SAME tenant, to reassign to.
    #
    # Not NULL: `tasks_has_an_owner` forbids a task with neither an
    # assignee nor a role, so blanking the column tests the CHECK rather
    # than the race. Reassigning to a real person is also what actually
    # happens.
    other = owner_session.execute(
        text(
            """
            INSERT INTO core.users (keycloak_sub, email, display_name)
            VALUES (:s, :e, 'Second A') RETURNING id
            """
        ),
        {"s": str(uuid.uuid4()), "e": f"seconda-{two_tenants['suffix']}@example.test"},
    ).scalar_one()
    owner_session.execute(
        text(
            """
            INSERT INTO core.organization_members (organization_id, user_id, status)
            VALUES (:o, :u, 'active')
            """
        ),
        {"o": two_tenants["org_a"], "u": other},
    )
    owner_session.flush()

    # The concurrent reassignment lands between read and write.
    owner_session.execute(
        text("UPDATE workflow.tasks SET assigned_user_id = :u WHERE id = :t"),
        {"t": task_id, "u": other},
    )
    owner_session.flush()

    with pytest.raises(TaskStateError, match="only the assignee"):
        complete_task(
            owner_session,
            task_id=task_id,
            actor_id=two_tenants["user_a"],
            organization_id=two_tenants["org_a"],
        )

    still_open = owner_session.execute(
        text("SELECT status FROM workflow.tasks WHERE id = :t"), {"t": task_id}
    ).scalar_one()
    assert still_open != "completed"


def test_a_completed_task_cannot_be_reassigned(owner_session, two_tenants):
    """C6. Otherwise assigned_user_id and completed_by disagree about
    who did the work -- on a completed record, permanently."""
    task_id = _task_for(owner_session, two_tenants)
    owner_session.flush()
    complete_task(
        owner_session,
        task_id=task_id,
        actor_id=two_tenants["user_a"],
        organization_id=two_tenants["org_a"],
    )
    owner_session.flush()

    # A second active member to delegate to.
    other = owner_session.execute(
        text(
            """
            INSERT INTO core.users (keycloak_sub, email, display_name)
            VALUES (:s, :e, 'Other A') RETURNING id
            """
        ),
        {"s": str(uuid.uuid4()), "e": f"othera-{two_tenants['suffix']}@example.test"},
    ).scalar_one()
    owner_session.execute(
        text(
            """
            INSERT INTO core.organization_members (organization_id, user_id, status)
            VALUES (:o, :u, 'active')
            """
        ),
        {"o": two_tenants["org_a"], "u": other},
    )
    owner_session.flush()

    with pytest.raises(TaskStateError, match="cannot be reassigned"):
        reassign_task(
            owner_session,
            task_id=task_id,
            to_user_id=other,
            actor_id=two_tenants["user_a"],
            organization_id=two_tenants["org_a"],
            reason="trying to delegate finished work",
        )

    row = (
        owner_session.execute(
            text(
                """
                SELECT assigned_user_id, completed_by FROM workflow.tasks
                WHERE id = :t
                """
            ),
            {"t": task_id},
        )
        .mappings()
        .one()
    )
    # The two columns still agree about who did the work.
    assert row["assigned_user_id"] == row["completed_by"] == two_tenants["user_a"]


# ---------------------------------------------------------------------------
# C5 -- decide_opportunity read-then-write race
# ---------------------------------------------------------------------------


def test_a_decision_is_refused_at_write_time(owner_session, two_tenants):
    """C5. Two Directors deciding at once both reported success and only
    the last rationale survived -- the exact history loss this rule
    exists to prevent."""
    opportunity_id = create_opportunity(
        owner_session,
        data=OpportunityInput(
            opportunity_code=f"OPP-RACE-{two_tenants['suffix']}",
            title="Contested gate",
        ),
        actor_id=two_tenants["user_a"],
        organization_id=two_tenants["org_a"],
    )
    owner_session.execute(
        text(
            """
            UPDATE innovation.opportunities SET status = 'awaiting_decision'
            WHERE id = :i AND organization_id = :o
            """
        ),
        {"i": opportunity_id, "o": two_tenants["org_a"]},
    )
    owner_session.flush()

    decide_opportunity(
        owner_session,
        opportunity_id=opportunity_id,
        decision=OpportunityDecision("reject", "No commercial case"),
        actor_id=two_tenants["user_a"],
        organization_id=two_tenants["org_a"],
    )
    owner_session.flush()

    with pytest.raises(OpportunityStateError, match="cannot be decided"):
        decide_opportunity(
            owner_session,
            opportunity_id=opportunity_id,
            decision=OpportunityDecision("approve", "Overriding"),
            actor_id=two_tenants["user_a"],
            organization_id=two_tenants["org_a"],
        )

    surviving = owner_session.execute(
        text(
            """
            SELECT decision_rationale FROM innovation.opportunities
            WHERE id = :i AND organization_id = :o
            """
        ),
        {"i": opportunity_id, "o": two_tenants["org_a"]},
    ).scalar_one()
    # The FIRST decision survived, not the last write.
    assert surviving == "No commercial case"


# ---------------------------------------------------------------------------
# C8 -- stage_transitions.from_stage_id had no foreign key at all
# ---------------------------------------------------------------------------


def test_from_stage_id_cannot_name_another_tenants_stage(owner_session, two_tenants):
    """Migration 010.

    `to_stage_id` had a composite tenant FK from migration 003 and
    `from_stage_id` had NONE -- an asymmetry nothing would surface until
    another tenant's stage name appeared on this tenant's dashboard.
    """
    stage_def_b = owner_session.execute(
        text(
            """
            INSERT INTO workflow.stage_definitions
                (organization_id, stage_code, name, sequence)
            VALUES (:o, 'B_STAGE', 'B Stage', 1) RETURNING id
            """
        ),
        {"o": two_tenants["org_b"]},
    ).scalar_one()
    project_b = owner_session.execute(
        text(
            """
            INSERT INTO projects.projects (organization_id, project_code, name)
            VALUES (:o, :c, 'Tenant B project') RETURNING id
            """
        ),
        {"o": two_tenants["org_b"], "c": f"RDP-B-{two_tenants['suffix']}"},
    ).scalar_one()
    foreign_stage = owner_session.execute(
        text(
            """
            INSERT INTO workflow.project_stages
                (organization_id, project_id, stage_definition_id, status, started_at)
            VALUES (:o, :p, :sd, 'active', now()) RETURNING id
            """
        ),
        {"o": two_tenants["org_b"], "p": project_b, "sd": stage_def_b},
    ).scalar_one()

    # Tenant A's own stage, to satisfy the to_stage_id FK.
    stage_def_a = owner_session.execute(
        text(
            """
            INSERT INTO workflow.stage_definitions
                (organization_id, stage_code, name, sequence)
            VALUES (:o, 'A_STAGE', 'A Stage', 1) RETURNING id
            """
        ),
        {"o": two_tenants["org_a"]},
    ).scalar_one()
    own_stage = owner_session.execute(
        text(
            """
            INSERT INTO workflow.project_stages
                (organization_id, project_id, stage_definition_id, status, started_at)
            VALUES (:o, :p, :sd, 'active', now()) RETURNING id
            """
        ),
        {
            "o": two_tenants["org_a"],
            "p": two_tenants["project_a"],
            "sd": stage_def_a,
        },
    ).scalar_one()
    owner_session.flush()

    with pytest.raises(IntegrityError):
        owner_session.execute(
            text(
                """
                INSERT INTO workflow.stage_transitions
                    (organization_id, project_id, from_stage_id, to_stage_id,
                     to_status, transitioned_by, reason)
                VALUES (:o, :p, :from_id, :to_id, 'active', :u, 'cross-tenant from')
                """
            ),
            {
                "o": two_tenants["org_a"],
                "p": two_tenants["project_a"],
                "from_id": foreign_stage,
                "to_id": own_stage,
                "u": two_tenants["user_a"],
            },
        )
        owner_session.flush()


def test_a_null_from_stage_id_is_still_allowed(owner_session, two_tenants):
    """The composite FK must not break the FIRST transition.

    `from_stage_id` is nullable because entering a pipeline has no
    predecessor -- almost certainly why the FK was omitted originally. A
    composite FK permits NULL and constrains every non-NULL value, so
    adding it must not have cost the ordinary case.
    """
    stage_def_a = owner_session.execute(
        text(
            """
            INSERT INTO workflow.stage_definitions
                (organization_id, stage_code, name, sequence)
            VALUES (:o, 'FIRST', 'First', 1) RETURNING id
            """
        ),
        {"o": two_tenants["org_a"]},
    ).scalar_one()
    own_stage = owner_session.execute(
        text(
            """
            INSERT INTO workflow.project_stages
                (organization_id, project_id, stage_definition_id, status, started_at)
            VALUES (:o, :p, :sd, 'active', now()) RETURNING id
            """
        ),
        {
            "o": two_tenants["org_a"],
            "p": two_tenants["project_a"],
            "sd": stage_def_a,
        },
    ).scalar_one()
    owner_session.flush()

    owner_session.execute(
        text(
            """
            INSERT INTO workflow.stage_transitions
                (organization_id, project_id, from_stage_id, to_stage_id,
                 to_status, transitioned_by, reason)
            VALUES (:o, :p, NULL, :to_id, 'active', :u, 'entering the pipeline')
            """
        ),
        {
            "o": two_tenants["org_a"],
            "p": two_tenants["project_a"],
            "to_id": own_stage,
            "u": two_tenants["user_a"],
        },
    )
    owner_session.flush()  # must not raise
