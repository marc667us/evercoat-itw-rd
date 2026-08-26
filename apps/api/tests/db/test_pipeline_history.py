"""Stage history must survive, including going backwards.

The whole point of `workflow.project_stages` + `stage_transitions` is
that a project's path is recoverable after the fact. A `current_stage`
column answers "where is it now" and destroys everything else.

The decisive test here is `test_rework_preserves_the_first_visit`: a
project goes Formulation → Testing → back to Formulation. With a mutable
column that history is simply gone, and the Lead dashboard's
"average days in Rework" — a named requirement — becomes uncomputable.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

from app.domains.pipeline.service import (
    StageNotFoundError,
    TransitionNotPermittedError,
    advance_stage,
    project_pipeline,
    stage_history,
)

pytestmark = pytest.mark.db


@pytest.fixture
def pipeline_project(owner_session):
    """An organization with three stages and one project, committed."""
    suffix = uuid.uuid4().hex[:8]

    org_id = owner_session.execute(
        text("INSERT INTO core.organizations (code, name) VALUES (:c,:n) RETURNING id"),
        {"c": f"PIPE-{suffix}", "n": "Pipeline Test Org"},
    ).scalar_one()

    actor_id = owner_session.execute(
        text(
            "INSERT INTO core.users (keycloak_sub, email, display_name) "
            "VALUES (:s,:e,'Pipeline Actor') RETURNING id"
        ),
        {"s": f"pipe-{suffix}", "e": f"pipe-{suffix}@example.test"},
    ).scalar_one()

    # 🔴 THE ACTOR IS A MEMBER, WHICH THIS FIXTURE USED TO SKIP.
    #
    # Somebody who transitions a stage necessarily belongs to the
    # organization the project is in — a session cannot act otherwise. The
    # fixture built an identity with no membership anywhere, and the history
    # query still named them because it read `core.users` globally. Since 052
    # attribution resolves through the membership, so an actor with none is a
    # state production cannot reach and the fixture should not manufacture.
    owner_session.execute(
        text(
            "INSERT INTO core.organization_members"
            " (organization_id, user_id, email, display_name)"
            " SELECT :o, :u, u.email, u.display_name FROM core.users u WHERE u.id = :u"
        ),
        {"o": org_id, "u": actor_id},
    )

    for code, name, seq in [
        ("FORMULATION", "Formulation", 1),
        ("LABORATORY", "Laboratory", 2),
        ("TESTING", "Testing", 3),
    ]:
        owner_session.execute(
            text(
                "INSERT INTO workflow.stage_definitions "
                "(organization_id, stage_code, name, sequence) "
                "VALUES (:o,:c,:n,:s)"
            ),
            {"o": org_id, "c": code, "n": name, "s": seq},
        )

    project_id = owner_session.execute(
        text(
            "INSERT INTO projects.projects "
            "(organization_id, project_code, name, confidentiality) "
            "VALUES (:o,:c,'Pipeline Project','normal') RETURNING id"
        ),
        {"o": org_id, "c": f"RDP-P-{suffix}"},
    ).scalar_one()

    owner_session.commit()

    yield {"org_id": org_id, "project_id": project_id, "actor_id": actor_id}

    # audit.events is deliberately NOT cleaned up: it is append-only by
    # trigger, and an earlier version of this teardown tried to delete
    # from it. The trigger raised (correctly), the rollback discarded the
    # transaction, and every subsequent delete failed -- one expected
    # refusal became nine teardown errors that looked like real failures.
    # Audit rows carry no FK to these tables, so leaving them is harmless.
    #
    # rollback() rather than begin(): the test body's queries autobegan a
    # transaction, so an explicit begin() here raises "a transaction is
    # already begun". Rolling back ends whatever is open and lets the
    # deletes below autobegin cleanly.
    owner_session.rollback()
    for stmt in [
        "DELETE FROM workflow.stage_transitions WHERE organization_id = :o",
        "DELETE FROM workflow.project_stages WHERE organization_id = :o",
        "DELETE FROM workflow.stage_definitions WHERE organization_id = :o",
        "DELETE FROM projects.projects WHERE organization_id = :o",
        # Before the organization, because the FK is RESTRICT by design.
        "DELETE FROM core.organization_members WHERE organization_id = :o",
        "DELETE FROM core.organizations WHERE id = :o",
    ]:
        owner_session.execute(text(stmt), {"o": org_id})
    owner_session.execute(text("DELETE FROM core.users WHERE id = :u"), {"u": actor_id})
    owner_session.commit()


def _advance(session, ctx, code, reason="test transition", force=False):
    return advance_stage(
        session,
        project_id=ctx["project_id"],
        to_stage_code=code,
        actor_id=ctx["actor_id"],
        organization_id=ctx["org_id"],
        reason=reason,
        force=force,
    )


def test_first_transition_has_no_origin(owner_session, pipeline_project):
    result = _advance(owner_session, pipeline_project, "FORMULATION", "project start")
    assert result.from_stage_code is None
    assert result.to_stage_code == "FORMULATION"
    assert result.is_rework is False


def test_pipeline_returns_every_stage_not_only_visited_ones(owner_session, pipeline_project):
    """The UI shows the whole path; position is meaningless without it."""
    _advance(owner_session, pipeline_project, "FORMULATION")
    stages = project_pipeline(
        owner_session, pipeline_project["project_id"], pipeline_project["org_id"]
    )

    assert [s["stage_code"] for s in stages] == ["FORMULATION", "LABORATORY", "TESTING"]
    assert stages[0]["status"] == "active"
    assert stages[1]["status"] == "not_started"
    assert stages[2]["status"] == "not_started"


def test_advancing_closes_the_previous_stage(owner_session, pipeline_project):
    _advance(owner_session, pipeline_project, "FORMULATION")
    _advance(owner_session, pipeline_project, "LABORATORY")

    stages = {
        s["stage_code"]: s
        for s in project_pipeline(
            owner_session, pipeline_project["project_id"], pipeline_project["org_id"]
        )
    }
    assert stages["FORMULATION"]["status"] == "completed"
    # completed_at is what makes "average days in this stage" computable.
    assert stages["FORMULATION"]["completed_at"] is not None
    assert stages["LABORATORY"]["status"] == "active"


def test_rework_preserves_the_first_visit(owner_session, pipeline_project):
    """The test a mutable current_stage column cannot pass.

    Formulation → Testing → back to Formulation. Both visits must remain
    as distinct rows with their own timings, and the second must be
    linked to the first as rework.
    """
    _advance(owner_session, pipeline_project, "FORMULATION", "initial formulation")
    _advance(owner_session, pipeline_project, "TESTING", "samples ready")

    # Mark it for rework, as a failed test would.
    owner_session.execute(
        text(
            "UPDATE workflow.project_stages SET status = 'rework_required' "
            "WHERE project_id = :p AND stage_definition_id = "
            "(SELECT id FROM workflow.stage_definitions "
            " WHERE organization_id = :o AND stage_code = 'FORMULATION')"
        ),
        {"p": pipeline_project["project_id"], "o": pipeline_project["org_id"]},
    )

    result = _advance(
        owner_session, pipeline_project, "FORMULATION", "adhesion failure — reformulating"
    )

    assert result.is_rework is True, "re-entering a stage must be recorded as rework"

    visits = (
        owner_session.execute(
            text(
                """
            SELECT ps.id, ps.started_at, ps.rework_of_stage_id
            FROM workflow.project_stages ps
            JOIN workflow.stage_definitions sd ON sd.id = ps.stage_definition_id
            WHERE ps.project_id = :p AND sd.stage_code = 'FORMULATION'
            ORDER BY ps.created_at
            """
            ),
            {"p": pipeline_project["project_id"]},
        )
        .mappings()
        .all()
    )

    assert len(visits) == 2, (
        "both visits to Formulation must survive as separate rows — "
        "a single mutated row loses the first visit's timing entirely"
    )
    assert visits[1]["rework_of_stage_id"] == visits[0]["id"], (
        "the second visit must point at the first, or 'why was this re-entered' is unanswerable"
    )


def test_history_records_going_backwards(owner_session, pipeline_project):
    _advance(owner_session, pipeline_project, "FORMULATION", "start")
    _advance(owner_session, pipeline_project, "TESTING", "ready to test")
    owner_session.execute(
        text(
            "UPDATE workflow.project_stages SET status='rework_required' "
            "WHERE project_id=:p AND stage_definition_id="
            "(SELECT id FROM workflow.stage_definitions "
            " WHERE organization_id=:o AND stage_code='FORMULATION')"
        ),
        {"p": pipeline_project["project_id"], "o": pipeline_project["org_id"]},
    )
    _advance(owner_session, pipeline_project, "FORMULATION", "sag failure")

    history = stage_history(owner_session, pipeline_project["project_id"])

    assert [h["to_stage"] for h in history] == ["FORMULATION", "TESTING", "FORMULATION"]
    assert history[-1]["reason"] == "sag failure"
    assert history[-1]["actor"] == "Pipeline Actor"
    # Every entry attributable. An anonymous transition is one nobody can
    # be asked about.
    assert all(h["actor"] for h in history)


def test_transition_requires_a_reason(owner_session, pipeline_project):
    with pytest.raises(TransitionNotPermittedError, match="reason is required"):
        _advance(owner_session, pipeline_project, "FORMULATION", "")


def test_unknown_stage_is_refused(owner_session, pipeline_project):
    with pytest.raises(StageNotFoundError):
        _advance(owner_session, pipeline_project, "NOT_A_STAGE")


def test_reentering_an_active_stage_is_refused(owner_session, pipeline_project):
    """Without this, a double-click creates two active visits."""
    _advance(owner_session, pipeline_project, "FORMULATION")
    with pytest.raises(TransitionNotPermittedError, match="already active"):
        _advance(owner_session, pipeline_project, "FORMULATION")


def test_force_records_itself_in_the_reason(owner_session, pipeline_project):
    """An override must be visible in the history, not silent."""
    _advance(owner_session, pipeline_project, "FORMULATION")
    _advance(owner_session, pipeline_project, "FORMULATION", "override", force=True)

    history = stage_history(owner_session, pipeline_project["project_id"])
    assert history[-1]["reason"].startswith("[FORCED]")


def test_transitions_are_append_only(owner_session, pipeline_project):
    """A rewritable log answers none of the questions it exists for."""
    _advance(owner_session, pipeline_project, "FORMULATION")

    with pytest.raises(ProgrammingError, match="append-only"):
        owner_session.execute(
            text(
                "UPDATE workflow.stage_transitions SET reason = 'rewritten' WHERE project_id = :p"
            ),
            {"p": pipeline_project["project_id"]},
        )
        owner_session.flush()

    # The failed statement poisoned the transaction; roll back so the
    # fixture teardown can run. No begin() -- the next statement
    # autobegins.
    owner_session.rollback()
