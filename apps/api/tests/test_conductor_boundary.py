"""The conductor tier refuses, and it refuses at the door.

`test_agent_topology.py` checks the SHAPE of §0.2 — who may import whom. This
checks the thing that shape exists to carry: every department conductor
applies its permission gate before it touches a domain service.

🔴 WHY THIS IS NOT COVERED BY THE ROUTE TESTS.

On the HTTP path `require_permission(...)` has already run, so a conductor
that forgot its gate would still look correct in every route test. The path
with no route — the root orchestrator, on behalf of MSD or any later agent —
is the one where this is the check, and it is exactly the path §7 is about:
*MSD operates under exactly the calling user's authorization boundary.*

These tests need no database and no network: the gate must fire BEFORE any
service call, so a session that would explode if touched is the strongest
available statement of that. If a conductor ever starts querying first and
filtering after, `_ExplodingSession` turns it into a failure rather than a
subtle §7 violation.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable

import pytest

from app.agents.boundary import DepartmentDeniedError
from app.agents.conductors import (
    analysis_conductor,
    laboratory_conductor,
    testing_conductor,
)
from app.agents.orchestrators import root_orchestrator


class _ExplodingSession:
    """A session that fails loudly if anything touches the database.

    The point of the gate is that it runs FIRST. A conductor that called its
    service and filtered afterwards would pass a test using a real session and
    an empty result set; it cannot pass this one.
    """

    def __getattr__(self, name: str) -> object:  # pragma: no cover - defensive
        raise AssertionError(
            f"the conductor reached the database (session.{name}) before its "
            "permission gate refused. §7 requires filtering BEFORE anything "
            "reads, never after."
        )


ORG = uuid.uuid4()
USER = uuid.uuid4()
THING = uuid.uuid4()

# (label, callable) for every read entry point the conductor tier exposes.
# Written out rather than discovered, so that adding a conductor function
# without a gate is a visible omission here rather than an invisible one.
DENIED_CASES = [
    (
        "laboratory.batches",
        lambda: laboratory_conductor.batches(
            _ExplodingSession(), organization_id=ORG, permissions=frozenset()
        ),
    ),
    (
        "laboratory.batch",
        lambda: laboratory_conductor.batch(
            _ExplodingSession(),
            batch_id=THING,
            organization_id=ORG,
            permissions=frozenset(),
        ),
    ),
    (
        "testing.tests",
        lambda: testing_conductor.tests(
            _ExplodingSession(), organization_id=ORG, permissions=frozenset()
        ),
    ),
    (
        "testing.test",
        lambda: testing_conductor.test(
            _ExplodingSession(),
            test_id=THING,
            organization_id=ORG,
            permissions=frozenset(),
        ),
    ),
    (
        "testing.methods",
        lambda: testing_conductor.methods(
            _ExplodingSession(), organization_id=ORG, permissions=frozenset()
        ),
    ),
    (
        "analysis.dashboard",
        lambda: analysis_conductor.dashboard(
            _ExplodingSession(),
            name="lead",
            user_id=USER,
            organization_id=ORG,
            permissions=frozenset(),
        ),
    ),
]


@pytest.mark.parametrize(("label", "call"), DENIED_CASES, ids=[c[0] for c in DENIED_CASES])
def test_a_caller_without_the_permission_is_refused(label: str, call: Callable[[], object]) -> None:
    with pytest.raises(DepartmentDeniedError) as caught:
        call()
    assert caught.value.permission, f"{label} refused without naming a permission"


ALLOWED_CASES = [
    (
        "laboratory.batches",
        "batch.view",
        lambda: laboratory_conductor.batches(
            _ExplodingSession(), organization_id=ORG, permissions=frozenset({"batch.view"})
        ),
    ),
    (
        "testing.tests",
        "test.view",
        lambda: testing_conductor.tests(
            _ExplodingSession(), organization_id=ORG, permissions=frozenset({"test.view"})
        ),
    ),
    (
        "analysis.dashboard",
        "analytics.view",
        lambda: analysis_conductor.dashboard(
            _ExplodingSession(),
            name="lead",
            user_id=USER,
            organization_id=ORG,
            permissions=frozenset({"analytics.view"}),
        ),
    ),
]


@pytest.mark.parametrize(
    ("label", "permission", "call"), ALLOWED_CASES, ids=[c[0] for c in ALLOWED_CASES]
)
def test_the_gate_is_the_permission_and_not_a_blanket_refusal(
    label: str, permission: str, call: Callable[[], object]
) -> None:
    """🔴 THE HALF THAT CATCHES A CONDUCTOR THAT REFUSES EVERYONE.

    Every test above passes against a conductor whose gate is a bare `raise`
    -- a department nobody can reach, and a green suite. So each gate is also
    shown to OPEN for the right permission.

    It opens onto `_ExplodingSession`, so the proof that the gate passed is
    the session's own AssertionError rather than a query result. That keeps
    this free of a database while still telling "refused by the gate" apart
    from "allowed through it" -- and it is why the assertion below checks the
    MESSAGE and not merely that something was raised.
    """
    with pytest.raises(AssertionError) as caught:
        call()
    assert "reached the database" in str(caught.value), (
        f"{label} did not reach its domain service when given {permission!r}: {caught.value}"
    )


def test_every_orchestrator_entry_point_is_exported() -> None:
    """§0.2's door is the orchestrator, so its surface is the contract.

    A function reachable only by importing the module privately is a second
    door. `__all__` is the list a reader trusts, so it must match what is
    actually callable.
    """
    for name in root_orchestrator.__all__:
        assert hasattr(root_orchestrator, name), (
            f"root_orchestrator.__all__ names {name!r}, which does not exist"
        )
    assert "answer_question" in root_orchestrator.__all__, (
        "MSD is no longer reachable through the orchestrator"
    )
