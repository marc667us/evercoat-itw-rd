"""Tasks and the My Work inbox.

Every query in this file is scoped by ``organization_id``. That is not
defensive style -- it is a bug this suite has already produced twice.
The database is multi-tenant and the tests share it, so a query filtered
only by ``title`` or ``task_type`` matches rows another test created and
the failure reads like a logic error in the code under test.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy import text

from app.core.tenancy import CrossTenantReferenceError
from app.domains.tasks.service import (
    TaskInput,
    TaskNotFoundError,
    TaskStateError,
    claim_task,
    complete_task,
    create_task,
    my_work,
    my_work_counts,
    project_tasks,
    reassign_task,
)


@pytest.fixture
def task_world(owner_session):
    """One org, one project, two users. Rolled back by owner_session."""
    suffix = uuid.uuid4().hex[:8]

    org = owner_session.execute(
        text("INSERT INTO core.organizations (code, name) VALUES (:c, :n) RETURNING id"),
        {"c": f"TASK-{suffix}", "n": "Task Test Org"},
    ).scalar_one()

    users = {}
    for label in ("alice", "bob"):
        users[label] = owner_session.execute(
            text(
                """
                INSERT INTO core.users (keycloak_sub, email, display_name)
                VALUES (:s, :e, :n) RETURNING id
                """
            ),
            {
                "s": str(uuid.uuid4()),
                "e": f"{label}-{suffix}@example.test",
                "n": label.title(),
            },
        ).scalar_one()
        owner_session.execute(
            text(
                """
                INSERT INTO core.organization_members
                    (organization_id, user_id, status)
                VALUES (:o, :u, 'active')
                """
            ),
            {"o": org, "u": users[label]},
        )

    project = owner_session.execute(
        text(
            """
            INSERT INTO projects.projects
                (organization_id, project_code, name, lead_user_id)
            VALUES (:o, :c, 'Task Project', :lead) RETURNING id
            """
        ),
        {"o": org, "c": f"RDP-T-{suffix}", "lead": users["alice"]},
    ).scalar_one()

    owner_session.flush()
    return {"org": org, "project": project, **users}


def test_a_task_needs_an_owner(owner_session, task_world):
    """Neither an assignee nor a role means nobody does it."""
    with pytest.raises(TaskStateError, match="needs an owner"):
        create_task(
            owner_session,
            data=TaskInput(task_type="review", title="Orphan task"),
            actor_id=task_world["alice"],
            organization_id=task_world["org"],
        )


def test_role_task_appears_for_role_holders_and_nobody_else(owner_session, task_world):
    """A role-addressed task reaches the role, not the whole organization."""
    create_task(
        owner_session,
        data=TaskInput(
            task_type="lab_execution",
            title="Run batch LB001",
            assigned_role="laboratory_technician",
            project_id=task_world["project"],
        ),
        actor_id=task_world["alice"],
        organization_id=task_world["org"],
    )
    owner_session.flush()

    technician_view = my_work(
        owner_session,
        user_id=task_world["bob"],
        organization_id=task_world["org"],
        role_codes=frozenset({"laboratory_technician"}),
    )
    assert [t["title"] for t in technician_view] == ["Run batch LB001"]

    # Same user, different role. The task must not appear.
    chemist_view = my_work(
        owner_session,
        user_id=task_world["bob"],
        organization_id=task_world["org"],
        role_codes=frozenset({"product_development_chemist"}),
    )
    assert chemist_view == []


def test_claiming_removes_it_from_everyone_elses_inbox(owner_session, task_world):
    """The defect this guards: five people working the same queue item."""
    task_id = create_task(
        owner_session,
        data=TaskInput(
            task_type="lab_execution",
            title="Shared queue item",
            assigned_role="laboratory_technician",
            project_id=task_world["project"],
        ),
        actor_id=task_world["alice"],
        organization_id=task_world["org"],
    )
    owner_session.flush()

    claim_task(
        owner_session,
        task_id=task_id,
        user_id=task_world["alice"],
        organization_id=task_world["org"],
        role_codes=frozenset({"laboratory_technician"}),
    )
    owner_session.flush()

    mine = my_work(
        owner_session,
        user_id=task_world["alice"],
        organization_id=task_world["org"],
        role_codes=frozenset({"laboratory_technician"}),
    )
    assert [t["title"] for t in mine] == ["Shared queue item"]

    # Bob holds the same role and must no longer see it.
    theirs = my_work(
        owner_session,
        user_id=task_world["bob"],
        organization_id=task_world["org"],
        role_codes=frozenset({"laboratory_technician"}),
    )
    assert theirs == []


def test_a_second_claim_is_refused_not_silently_stolen(owner_session, task_world):
    task_id = create_task(
        owner_session,
        data=TaskInput(
            task_type="lab_execution",
            title="Contested item",
            assigned_role="laboratory_technician",
        ),
        actor_id=task_world["alice"],
        organization_id=task_world["org"],
    )
    owner_session.flush()

    claim_task(
        owner_session,
        task_id=task_id,
        user_id=task_world["alice"],
        organization_id=task_world["org"],
        role_codes=frozenset({"laboratory_technician"}),
    )
    owner_session.flush()

    with pytest.raises(TaskStateError, match="not available to claim"):
        claim_task(
            owner_session,
            task_id=task_id,
            user_id=task_world["bob"],
            organization_id=task_world["org"],
            role_codes=frozenset({"laboratory_technician"}),
        )


def test_only_the_assignee_may_complete(owner_session, task_world):
    task_id = create_task(
        owner_session,
        data=TaskInput(
            task_type="review",
            title="Alice's task",
            assigned_user_id=task_world["alice"],
        ),
        actor_id=task_world["alice"],
        organization_id=task_world["org"],
    )
    owner_session.flush()

    with pytest.raises(TaskStateError, match="only the assignee"):
        complete_task(
            owner_session,
            task_id=task_id,
            actor_id=task_world["bob"],
            organization_id=task_world["org"],
        )


def test_completion_writes_both_columns_the_check_requires(owner_session, task_world):
    """tasks_completion_complete demands completed_at AND completed_by."""
    task_id = create_task(
        owner_session,
        data=TaskInput(
            task_type="review",
            title="Completable",
            assigned_user_id=task_world["alice"],
        ),
        actor_id=task_world["alice"],
        organization_id=task_world["org"],
    )
    owner_session.flush()

    complete_task(
        owner_session,
        task_id=task_id,
        actor_id=task_world["alice"],
        organization_id=task_world["org"],
        outcome_note="done",
    )
    owner_session.flush()

    row = (
        owner_session.execute(
            text(
                """
                SELECT status, completed_at, completed_by
                FROM workflow.tasks WHERE id = :t AND organization_id = :o
                """
            ),
            {"t": task_id, "o": task_world["org"]},
        )
        .mappings()
        .one()
    )
    assert row["status"] == "completed"
    assert row["completed_at"] is not None
    assert row["completed_by"] == task_world["alice"]


def test_a_completed_task_cannot_be_completed_again(owner_session, task_world):
    task_id = create_task(
        owner_session,
        data=TaskInput(task_type="review", title="Once only", assigned_user_id=task_world["alice"]),
        actor_id=task_world["alice"],
        organization_id=task_world["org"],
    )
    owner_session.flush()
    complete_task(
        owner_session,
        task_id=task_id,
        actor_id=task_world["alice"],
        organization_id=task_world["org"],
    )
    owner_session.flush()

    with pytest.raises(TaskStateError, match="cannot be completed"):
        complete_task(
            owner_session,
            task_id=task_id,
            actor_id=task_world["alice"],
            organization_id=task_world["org"],
        )


def test_counts_and_list_agree(owner_session, task_world):
    """The badge and the inbox are built from one predicate on purpose.

    A count that disagrees with its list is a defect users spot at once
    and developers never do.
    """
    yesterday = date.today() - timedelta(days=1)
    for title, priority, due in [
        ("Overdue critical", "critical", yesterday),
        ("Future low", "low", date.today() + timedelta(days=30)),
        ("No due date", "medium", None),
    ]:
        create_task(
            owner_session,
            data=TaskInput(
                task_type="review",
                title=title,
                priority=priority,
                assigned_user_id=task_world["alice"],
                due_date=due,
            ),
            actor_id=task_world["alice"],
            organization_id=task_world["org"],
        )
    owner_session.flush()

    listed = my_work(
        owner_session,
        user_id=task_world["alice"],
        organization_id=task_world["org"],
        role_codes=frozenset(),
    )
    counts = my_work_counts(
        owner_session,
        user_id=task_world["alice"],
        organization_id=task_world["org"],
        role_codes=frozenset(),
    )

    assert counts["total"] == len(listed) == 3
    assert counts["overdue"] == 1
    assert counts["urgent"] == 1
    # Urgency ordering: overdue first, whatever its creation order.
    assert listed[0]["title"] == "Overdue critical"
    assert listed[0]["is_overdue"] is True


def test_completed_work_leaves_the_actionable_count(owner_session, task_world):
    """Sidebar counts are ACTIONABLE items, not row counts (CLAUDE.md §11)."""
    task_id = create_task(
        owner_session,
        data=TaskInput(
            task_type="review", title="Will finish", assigned_user_id=task_world["alice"]
        ),
        actor_id=task_world["alice"],
        organization_id=task_world["org"],
    )
    owner_session.flush()

    before = my_work_counts(
        owner_session,
        user_id=task_world["alice"],
        organization_id=task_world["org"],
        role_codes=frozenset(),
    )
    complete_task(
        owner_session,
        task_id=task_id,
        actor_id=task_world["alice"],
        organization_id=task_world["org"],
    )
    owner_session.flush()
    after = my_work_counts(
        owner_session,
        user_id=task_world["alice"],
        organization_id=task_world["org"],
        role_codes=frozenset(),
    )

    assert before["total"] == 1
    assert after["total"] == 0

    # ...but it is still findable with include_done, because the work
    # happened and the record of it is the point.
    assert (
        len(
            my_work(
                owner_session,
                user_id=task_world["alice"],
                organization_id=task_world["org"],
                role_codes=frozenset(),
                include_done=True,
            )
        )
        == 1
    )


def test_reassignment_refuses_a_user_from_another_organization(owner_session, task_world):
    """RI bypasses RLS, so the FK alone would permit this."""
    outsider = owner_session.execute(
        text(
            """
            INSERT INTO core.users (keycloak_sub, email, display_name)
            VALUES (:s, :e, 'Outsider') RETURNING id
            """
        ),
        {"s": str(uuid.uuid4()), "e": f"outsider-{uuid.uuid4().hex[:8]}@example.test"},
    ).scalar_one()

    task_id = create_task(
        owner_session,
        data=TaskInput(task_type="review", title="Delegable", assigned_user_id=task_world["alice"]),
        actor_id=task_world["alice"],
        organization_id=task_world["org"],
    )
    owner_session.flush()

    # CrossTenantReferenceError, not TaskStateError: a cross-tenant
    # reference is a tenancy violation rather than a task-lifecycle one,
    # and the shared check in app.core.tenancy raises its own type so
    # every caller translates it the same way.
    with pytest.raises(CrossTenantReferenceError, match="not an active member"):
        reassign_task(
            owner_session,
            task_id=task_id,
            to_user_id=outsider,
            actor_id=task_world["alice"],
            organization_id=task_world["org"],
            reason="trying to hand it outside the tenant",
        )


def test_reassignment_requires_a_reason(owner_session, task_world):
    task_id = create_task(
        owner_session,
        data=TaskInput(
            task_type="review", title="Needs reason", assigned_user_id=task_world["alice"]
        ),
        actor_id=task_world["alice"],
        organization_id=task_world["org"],
    )
    owner_session.flush()

    with pytest.raises(TaskStateError, match="reason is required"):
        reassign_task(
            owner_session,
            task_id=task_id,
            to_user_id=task_world["bob"],
            actor_id=task_world["alice"],
            organization_id=task_world["org"],
            reason="   ",
        )


def test_missing_task_is_404_not_a_state_error(owner_session, task_world):
    with pytest.raises(TaskNotFoundError):
        complete_task(
            owner_session,
            task_id=uuid.uuid4(),
            actor_id=task_world["alice"],
            organization_id=task_world["org"],
        )


def test_project_view_shows_everyones_work(owner_session, task_world):
    """Unlike My Work, the project view is not filtered by assignee."""
    for owner_label in ("alice", "bob"):
        create_task(
            owner_session,
            data=TaskInput(
                task_type="review",
                title=f"{owner_label}'s item",
                assigned_user_id=task_world[owner_label],
                project_id=task_world["project"],
            ),
            actor_id=task_world["alice"],
            organization_id=task_world["org"],
        )
    owner_session.flush()

    rows = project_tasks(
        owner_session,
        project_id=task_world["project"],
        organization_id=task_world["org"],
    )
    assert {r["title"] for r in rows} == {"alice's item", "bob's item"}
    assert {r["assignee"] for r in rows} == {"Alice", "Bob"}
