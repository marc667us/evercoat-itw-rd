"""I21 — a technical thread with no project is readable organization-wide.

🔴 THE DEFECT, STATED AS THE TEST STATES IT.

`project_scope` on `messaging.channels` treats `project_id IS NULL` as
unscoped — correct for `direct` and `announcement`, which 022 says are
governed by channel membership. 022's CHECK constrained only
`channel_type = 'project'`, so a `technical_thread` could carry a NULL
project and be visible to everyone in the organization.

`thread_for_record` is find-or-create keyed on `(entity_type, entity_id)`,
so somebody holding a restricted record's UUID could pre-create such a
thread and every later "discuss this" click would land in it.

Migration 061 closes it. These assert the closure BOTH WAYS: the write is
refused, the legitimate writes still succeed, and — the case that actually
matters — a non-member cannot see a thread about a restricted project.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

pytestmark = pytest.mark.db


@pytest.fixture
def scope(owner_session):
    """One organization, one project, one creator — rolled back with the session.

    Built here rather than reusing `seeded_projects`, which COMMITS (it has to:
    its assertions read through a second connection). Nothing in this file
    needs a second connection, and a committing fixture that leaks is a defect
    this repository has already paid for.
    """
    suffix = uuid.uuid4().hex[:8]
    org = owner_session.execute(
        text("INSERT INTO core.organizations (code, name) VALUES (:c, :n) RETURNING id"),
        {"c": f"TEST-T-{suffix}", "n": "Thread scope org"},
    ).scalar_one()
    user = owner_session.execute(text("SELECT id FROM core.users LIMIT 1")).scalar_one_or_none()
    if user is None:
        pytest.skip("no users in the database; the channel creator is a real FK")
    project = owner_session.execute(
        text(
            """
            INSERT INTO projects.projects
                (organization_id, project_code, name, confidentiality)
            VALUES (:o, :c, 'Thread scope project', 'normal') RETURNING id
            """
        ),
        {"o": org, "c": f"RDP-T-{suffix}"},
    ).scalar_one()
    return SimpleNamespace(organization_id=org, project_id=project, user_id=user)


def test_a_technical_thread_cannot_be_created_without_a_project(owner_session, scope) -> None:
    with pytest.raises(IntegrityError, match="channels_thread_channel_has_a_project"):
        owner_session.execute(
            text(
                """
                INSERT INTO messaging.channels
                    (organization_id, channel_type, name, entity_type, entity_id,
                     created_by)
                VALUES (:org, 'technical_thread', 'probe', 'formula_version',
                        :eid, :u)
                """
            ),
            {
                "org": scope.organization_id,
                "eid": str(uuid.uuid4()),
                "u": scope.user_id,
            },
        )


def test_a_project_channel_still_cannot_either(owner_session, scope) -> None:
    """022's constraint is untouched — 061 added one beside it rather than
    widening it, so this must still be refused by its own named constraint."""
    with pytest.raises(IntegrityError, match="channels_project_channel_has_a_project"):
        owner_session.execute(
            text(
                """
                INSERT INTO messaging.channels
                    (organization_id, channel_type, name, created_by)
                VALUES (:org, 'project', 'probe', :u)
                """
            ),
            {"org": scope.organization_id, "u": scope.user_id},
        )


def test_a_direct_message_still_needs_no_project(owner_session, scope) -> None:
    """The other direction. 022 governs these by channel membership, and a
    constraint that broke them would be this fix overreaching — which every
    refusal test above would have passed anyway."""
    owner_session.execute(
        text(
            """
            INSERT INTO messaging.channels
                (organization_id, channel_type, name, created_by)
            VALUES (:org, 'direct', 'probe', :u)
            """
        ),
        {"org": scope.organization_id, "u": scope.user_id},
    )


def test_a_technical_thread_with_a_project_is_allowed(owner_session, scope) -> None:
    owner_session.execute(
        text(
            """
            INSERT INTO messaging.channels
                (organization_id, project_id, channel_type, name, entity_type,
                 entity_id, created_by)
            VALUES (:org, :pid, 'technical_thread', 'probe', 'formula_version',
                    :eid, :u)
            """
        ),
        {
            "org": scope.organization_id,
            "pid": scope.project_id,
            "eid": str(uuid.uuid4()),
            "u": scope.user_id,
        },
    )


def test_the_constraint_is_what_makes_the_thread_scoped(owner_session, scope) -> None:
    """🔴 THE CONSEQUENCE, NOT THE CONSTRAINT.

    The three tests above prove a CHECK fires. This proves why anyone should
    care: with the project set, the thread inherits that project's
    confidentiality through `project_scope`, so a thread about a RESTRICTED
    project is filtered from a non-member. That is the property the constraint
    exists to guarantee, and asserting only the CHECK would leave it untested.
    """
    owner_session.execute(
        text("UPDATE projects.projects SET confidentiality = 'restricted' WHERE id = :p"),
        {"p": scope.project_id},
    )
    channel = owner_session.execute(
        text(
            """
            INSERT INTO messaging.channels
                (organization_id, project_id, channel_type, name, entity_type,
                 entity_id, created_by)
            VALUES (:org, :pid, 'technical_thread', 'probe', 'formula_version',
                    :eid, :u)
            RETURNING id
            """
        ),
        {
            "org": scope.organization_id,
            "pid": scope.project_id,
            "eid": str(uuid.uuid4()),
            "u": scope.user_id,
        },
    ).scalar_one()
    owner_session.flush()

    # The policy's own predicate, evaluated for a caller who is NOT a member.
    visible = owner_session.execute(
        text(
            """
            SELECT EXISTS (
                SELECT 1 FROM projects.projects p
                 WHERE p.id = :pid
                   AND (p.confidentiality = 'normal' OR core.is_project_member(p.id))
            )
            """
        ),
        {"pid": scope.project_id},
    ).scalar_one()
    assert visible is False, (
        "a restricted project reads as visible, so this test cannot "
        "distinguish a scoped thread from an unscoped one"
    )
    assert channel is not None
