"""The approval ladder's dangerous transitions. TODO I5.

Every test here was raised by Codex against the first version of I5, and each
gap existed for the same reason: the HAPPY ladder was the only path with a
test, so the states that only occur when something goes wrong were the states
nothing checked.

The three defects these cover:

* A non-approving decision (`return_for_correction`, `request_retest`) leaves a
  NON-NULL decision on a mandatory step while the route stays open by design.
  The reachability queries tested ``decision IS NULL``, so that group counted
  as satisfied and **every later rung became signable** — a qualification
  ladder could be completed past a step that had been sent back.

* A re-review after a correction called ``open_route`` unconditionally, hit
  ``approval_routes_one_open_per_entity``, raised, and `session_scope` rolled
  the whole request back — so every retry hit the identical collision and the
  test could never be approved again. **A permanent wedge.**

* ``route_outcome`` kept ``max(condition_text)``, so with two conditional
  approvals one limitation survived and the other was silently discarded.

See `test_018_testing.py` for the happy ladder and ADR-019.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.domains.testing.service import (
    DecisionInput,
    SegregationOfDutiesError,
    complete_execution,
    get_test,
    record_decision,
)

# The ladder helpers live beside the happy-path tests. `testable` is imported
# for its side effect of registering the fixture in this module's namespace,
# which is how pytest finds a fixture defined in another test module — and it
# is then shadowed by the parameter of the same name in every test below,
# which is exactly what F811 is for. Silenced here rather than restructured:
# moving a testing-specific fixture into the shared `conftest.py` would make
# every db test module pay for it.
from .test_018_testing import (  # noqa: F401
    DEV,
    LEAD,
    _measure,
    _plan,
    testable,
)


def _review(session: Session, fx: dict[str, uuid.UUID], test_id: uuid.UUID) -> None:
    """Complete technical review, which is what OPENS the approval route."""
    record_decision(
        session,
        test_id=test_id,
        organization_id=fx["org"],
        actor_id=fx["engineer"],
        spec=DecisionInput(decision="approve", stage="review"),
    )


def _ready(session: Session, fx: dict[str, uuid.UUID], authority: str = "development") -> uuid.UUID:
    """A passing, reviewed test with its approval route open."""
    test_id = _plan(session, fx, authority_level=authority)
    _measure(session, fx, test_id, ["12.0", "12.0", "12.0"])
    complete_execution(
        session, test_id=test_id, organization_id=fx["org"], actor_id=fx["technician"]
    )
    _review(session, fx, test_id)
    return test_id


def test_a_returned_rung_blocks_every_later_rung(
    owner_session: Session,
    testable: dict[str, uuid.UUID],  # noqa: F811
) -> None:
    """A NON-APPROVING DECISION IS NOT A SATISFIED RUNG.

    QUALIFICATION_CONFIRMATION's group 1 has two development rungs. One is
    approved, the other RETURNED FOR CORRECTION. The lead (group 2) must then
    have nothing to decide — before the fix, the returned rung read as
    "decided" and the lead's rung was offered.
    """
    fx = testable
    test_id = _ready(owner_session, fx, authority="qualification")

    record_decision(
        owner_session,
        test_id=test_id,
        organization_id=fx["org"],
        actor_id=fx["engineer"],
        held_permissions=DEV,
        spec=DecisionInput(decision="approve", stage="approval"),
    )
    record_decision(
        owner_session,
        test_id=test_id,
        organization_id=fx["org"],
        actor_id=fx["chemist"],
        held_permissions=DEV,
        spec=DecisionInput(
            decision="return_for_correction",
            stage="approval",
            rationale="the replicate spread needs explaining",
        ),
    )

    with pytest.raises(SegregationOfDutiesError):
        record_decision(
            owner_session,
            test_id=test_id,
            organization_id=fx["org"],
            actor_id=fx["lead"],
            held_permissions=LEAD,
            spec=DecisionInput(decision="approve", stage="approval"),
        )

    seen = get_test(owner_session, test_id=test_id, organization_id=fx["org"])
    assert seen["final_disposition"]["colour"] != "green", (
        "a test with a rung sent back for correction must not be green"
    )


def test_re_review_after_a_correction_does_not_wedge_the_test(
    owner_session: Session,
    testable: dict[str, uuid.UUID],  # noqa: F811
) -> None:
    """THE WEDGE: every retry used to hit the same collision, forever.

    The stalled route is now cancelled and a fresh ladder snapshotted. The old
    route's signatures survive on it — cancelling is not erasing.
    """
    fx = testable
    test_id = _ready(owner_session, fx)

    record_decision(
        owner_session,
        test_id=test_id,
        organization_id=fx["org"],
        actor_id=fx["lead"],
        held_permissions=DEV,
        spec=DecisionInput(
            decision="return_for_correction",
            stage="approval",
            rationale="rework the sample preparation",
        ),
    )

    # The work comes back and is reviewed again. This used to raise, and the
    # rollback meant the test could never be approved by any route again.
    _review(owner_session, fx, test_id)

    result = record_decision(
        owner_session,
        test_id=test_id,
        organization_id=fx["org"],
        actor_id=fx["lead"],
        held_permissions=DEV,
        spec=DecisionInput(decision="approve", stage="approval"),
    )
    assert result["state"] == "approved"

    cancelled = owner_session.execute(
        text(
            "SELECT count(*) FROM workflow.approval_routes "
            "WHERE entity_type = 'test' AND entity_id = :t AND status = 'cancelled'"
        ),
        {"t": test_id},
    ).scalar_one()
    assert cancelled == 1, "the superseded route was destroyed rather than kept as the record"


def test_every_conditional_limitation_is_preserved(
    owner_session: Session,
    testable: dict[str, uuid.UUID],  # noqa: F811
) -> None:
    """TWO CONDITIONS MEAN TWO LIMITATIONS, AND A CHEMIST MUST READ BOTH.

    The conditions are deliberately chosen so one sorts before the other:
    under the old `max(condition_text)` the "AAA" limitation was the one
    thrown away, and a discarded limitation is a restriction on the use of a
    result that nobody is told about.
    """
    fx = testable
    test_id = _ready(owner_session, fx, authority="qualification")

    for actor, condition in (
        (fx["engineer"], "AAA valid for development comparison only"),
        (fx["chemist"], "ZZZ not valid above 40 degrees C"),
    ):
        record_decision(
            owner_session,
            test_id=test_id,
            organization_id=fx["org"],
            actor_id=actor,
            held_permissions=DEV,
            spec=DecisionInput(
                decision="approve_with_condition",
                stage="approval",
                condition_text=condition,
            ),
        )

    stored = owner_session.execute(
        text("SELECT approval_condition FROM testing.tests WHERE id = :t"),
        {"t": test_id},
    ).scalar_one()

    assert "AAA valid for development comparison only" in stored
    assert "ZZZ not valid above 40 degrees C" in stored


def test_a_rejected_rung_makes_the_test_red(
    owner_session: Session,
    testable: dict[str, uuid.UUID],  # noqa: F811
) -> None:
    """Rule 3 of §10, driven through the engine: one reject closes the route."""
    fx = testable
    test_id = _ready(owner_session, fx)

    result = record_decision(
        owner_session,
        test_id=test_id,
        organization_id=fx["org"],
        actor_id=fx["lead"],
        held_permissions=DEV,
        spec=DecisionInput(
            decision="reject",
            stage="approval",
            rationale="the method was out of calibration on the day",
        ),
    )
    assert result["state"] == "rejected"

    seen = get_test(owner_session, test_id=test_id, organization_id=fx["org"])
    assert seen["final_disposition"]["colour"] == "red"


def test_every_independent_qa_step_in_every_template_declares_its_independence(
    owner_session: Session,
    testable: dict[str, uuid.UUID],  # noqa: F811
) -> None:
    """🔴 ADR-019 IS NOW CARRIED AS DATA, SO THE DATA IS WHAT MUST BE CHECKED.

    Raised by Codex: deleting `_refuse_conflicted_approver` moved the rule onto
    `must_differ_from_group`, which migration 020 sets on
    QUALIFICATION_CONFIRMATION and RELEASE_CRITICAL. Nothing structural stops a
    future template — or an edit to an existing one — from carrying a QA rung
    with that column left null, which would silently permit exactly the
    one-person-signing-twice that ADR-019 forbids.

    So the invariant is asserted across EVERY template in the organization,
    not just the two that happen to have it today.
    """
    fx = testable

    unguarded = [
        f"{r['template_code']} step {r['step_number']} ({r['step_label']})"
        for r in owner_session.execute(
            text(
                """
                SELECT t.template_code, s.step_number, s.step_label
                FROM workflow.approval_template_steps s
                JOIN workflow.approval_templates t ON t.id = s.template_id
                WHERE t.organization_id = :o
                  AND s.permission_required = 'test.approve_qa'
                  AND s.must_differ_from_group IS NULL
                """
            ),
            {"o": fx["org"]},
        ).mappings()
    ]

    assert not unguarded, (
        "these independent-QA steps do not declare must_differ_from_group, so a "
        f"development approver could also supply the QA signature (ADR-019): {unguarded}"
    )
