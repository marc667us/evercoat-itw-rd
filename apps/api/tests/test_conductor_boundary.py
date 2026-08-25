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

import ast
import uuid
from collections.abc import Callable
from pathlib import Path

import pytest

from app.agents.boundary import DepartmentDeniedError
from app.agents.conductors import (
    analysis_conductor,
    laboratory_conductor,
    testing_conductor,
)
from app.agents.orchestrators import root_orchestrator
from app.domains.dashboards.service import ROLE_DASHBOARDS


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
        analysis_conductor.VIEW,
        lambda: analysis_conductor.dashboard(
            _ExplodingSession(),
            name="lead",
            user_id=USER,
            organization_id=ORG,
            # Read from the conductor rather than restated: the point of the
            # drift test below is that this literal has exactly one home.
            permissions=frozenset({analysis_conductor.VIEW}),
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
    """§0.2's door is the orchestrator, so its surface IS the contract.

    ⚠️ BOTH DIRECTIONS. The first version only walked `__all__` and checked
    each name existed -- so adding a public function and forgetting to export
    it could not fail the test whose name promises exactly that. Codex caught
    it. A public callable missing from `__all__` is a second door that no
    reader is told about, which is the thing being prevented.
    """
    exported = set(root_orchestrator.__all__)
    for name in exported:
        assert hasattr(root_orchestrator, name), (
            f"root_orchestrator.__all__ names {name!r}, which does not exist"
        )

    public = {
        name
        for name, value in vars(root_orchestrator).items()
        if not name.startswith("_")
        and callable(value)
        and getattr(value, "__module__", "") == root_orchestrator.__name__
    }
    unexported = public - exported
    assert not unexported, (
        f"these orchestrator functions are public but not in __all__: "
        f"{sorted(unexported)}. §0.2's door is the contract, and a callable "
        "nobody is told about is a second door."
    )
    assert "answer_question" in exported, "MSD is no longer reachable through the orchestrator"


def test_msd_cannot_explain_a_test_result_without_test_view() -> None:
    """🔴 §7: MSD MUST NOT BE A PERMISSION-BYPASS CHANNEL.

    `GET /api/testing/tests/{id}` requires `test.view`. `msd_conductor`'s
    `explain_result` branch called the testing tool with NO permission check,
    so a caller holding `msd.use` and not `test.view` could ask "why did
    T-2026-0041 fail" and receive the raw replicates, the statistics, the
    requirement, the automatic evaluation and the final disposition.

    Codex found it -- the third time this file has had this exact defect,
    after `knowledge.view` and `formula.view_cost`.

    ⚠️ IT IS ALSO WHY THE NEW `testing_conductor` GATE WAS NOT LOAD-BEARING:
    that conductor guarded a door, and THIS was the door callers use. A gate
    on an unused path is decoration.

    Asserted on the SOURCE, because reaching the branch needs a database, a
    model and a seeded test. The condition is one line and its absence is the
    whole defect, so the line is what gets pinned.
    """
    src = (
        Path(__file__).resolve().parents[1] / "app" / "agents" / "conductors" / "msd_conductor.py"
    ).read_text(encoding="utf-8")

    guarded = [line.strip() for line in src.splitlines() if 'intent == "explain_result"' in line]
    assert guarded, "the explain_result branch has gone; this test is stale"
    for line in guarded:
        assert '"test.view" in permissions' in line, (
            "msd_conductor's explain_result branch does not require "
            f"'test.view': {line!r}. A caller with msd.use and without "
            "test.view can read a test's replicates and final disposition "
            "through the assistant that the screen would refuse them."
        )


def _route_permissions(module: str) -> set[str]:
    """Every `require_permission("...")` literal in an API module.

    Read from the source rather than by importing and inspecting FastAPI's
    dependency objects: the literal is what a reviewer sees, and parsing it
    keeps this test free of app startup, a database and a settings object.
    """
    path = Path(__file__).resolve().parents[1] / "app" / "api" / module
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "require_permission"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            found.add(node.args[0].value)
    return found


def test_the_analysis_gate_matches_the_route_that_serves_the_same_data() -> None:
    """🔴 TWO BOUNDARIES ANSWERING THE SAME QUESTION DIFFERENTLY.

    The first draft of `analysis_conductor` gated on `analytics.view`, because
    the permission catalogue files dashboards under the `analytics` domain.
    `app/api/dashboards.py` gates on `project.view`. Measured against the
    seeded roles, those come apart in BOTH directions:

        procurement_specialist   analytics.view YES   project.view NO
        laboratory_technician    analytics.view NO    project.view YES

    So the conductor would have GRANTED a procurement specialist a dashboard
    the route refuses, and refused a laboratory technician one the route
    allows. Not a style difference -- a bypass, and its mirror image.

    Two literals in two files cannot be type-checked into agreement, so this
    reads the route's source. If either side changes alone, this fails.
    """
    route = _route_permissions("dashboards.py")
    assert analysis_conductor.VIEW in route, (
        f"analysis_conductor gates on {analysis_conductor.VIEW!r}, which "
        f"app/api/dashboards.py does not require (it requires {sorted(route)}). "
        "The conductor and the route serve the SAME dashboards, so a caller's "
        "access must not depend on which door they came through."
    )


def test_the_conductor_serves_exactly_the_dashboards_the_service_builds() -> None:
    """The conductor must not carry its own copy of the table.

    The first draft wrote out `{"lead": lead_dashboard, ...}` beside the
    service's `ROLE_DASHBOARDS`. A dashboard added to one and not the other
    is invisible until somebody asks for it, so there is one table and this
    proves the conductor uses it.
    """
    src = (
        Path(__file__).resolve().parents[1]
        / "app"
        / "agents"
        / "conductors"
        / "analysis_conductor.py"
    ).read_text(encoding="utf-8")

    # ASSERT ON THE IMPORTS, NOT ON THE TEXT. The first version searched the
    # whole file for "lead_dashboard" and failed on the module docstring, which
    # explains the very mistake it guards against -- a test a comment can
    # redden is a test nobody trusts.
    imported: set[str] = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.update(f"{node.module}.{a.name}" for a in node.names)

    assert "app.domains.dashboards.service.ROLE_DASHBOARDS" in imported, (
        "analysis_conductor no longer imports the service's ROLE_DASHBOARDS, "
        "so it is carrying a second copy of the dashboard table"
    )
    builders = {name for name in imported if name.endswith("_dashboard")}
    assert not builders, (
        f"analysis_conductor imports dashboard builders directly "
        f"({sorted(builders)}), which is the second copy this test prevents"
    )
    assert set(ROLE_DASHBOARDS), "the service builds no dashboards at all"


def test_the_analysis_conductor_passes_the_callers_permissions_through() -> None:
    """🔴 OMITTING `held_permissions` FAILS SILENTLY AND SMALLER.

    The dashboard builders gate individual panels on it -- `"test.review" in
    held_permissions`, `held_permissions & {"batch.execute", ...}` -- and it
    DEFAULTS TO `frozenset()`. The first draft did not pass it, so the
    conductor returned the same dashboard with panels quietly missing:
    correct-looking, smaller, wrong, and raising nothing.

    Asserted on the call rather than on the source, so a refactor that keeps
    the words and drops the argument still fails.
    """
    seen: dict[str, object] = {}

    def _spy(session: object, **kwargs: object) -> dict[str, object]:
        seen.update(kwargs)
        return {}

    original = ROLE_DASHBOARDS["lead"]
    ROLE_DASHBOARDS["lead"] = _spy  # type: ignore[assignment]
    try:
        analysis_conductor.dashboard(
            object(),
            name="lead",
            user_id=USER,
            organization_id=ORG,
            permissions=frozenset({analysis_conductor.VIEW, "test.review"}),
        )
    finally:
        ROLE_DASHBOARDS["lead"] = original  # type: ignore[assignment]

    assert "held_permissions" in seen, (
        "analysis_conductor did not pass held_permissions, so every panel "
        "gated on a permission is silently omitted"
    )
    assert "test.review" in seen["held_permissions"], (  # type: ignore[operator]
        f"held_permissions reached the builder as {seen['held_permissions']!r}, "
        "not the caller's own set"
    )


def test_the_analysis_department_is_actually_reached_by_a_route() -> None:
    """🔴 THE DEFECT THIS CLOSES: A LAYER WITH NO CALLER.

    The analysis conductor was written, gated, tested — and NOTHING CALLED
    IT. `app/api/dashboards.py` imported the domain service and built the
    dashboard itself, so the "analysis department" was a Python module you
    could not reach from anywhere in the running product. Codex raised it as
    I103 and the operator put it more plainly: there was no analysis to see.

    A layer with no caller is the same defect as a route with no caller, and
    this repository has a standing rule about asking *which production path
    actually reaches this?*

    So: the dashboards route must reach the orchestrator, and must NOT reach
    the service directly. `test_no_api_route_reaches_past_the_orchestrator`
    already forbids importing a conductor; this is the positive half, and
    without it deleting the call entirely would satisfy every other test here.
    """
    imports = _imports_of("dashboards.py")

    assert "app.agents.orchestrators.root_orchestrator" in imports, (
        "app/api/dashboards.py no longer reaches the analysis department "
        "through the root orchestrator, so the conductor is unreachable again"
    )
    assert "app.domains.dashboards.service" not in imports, (
        "app/api/dashboards.py imports the dashboards service directly, which "
        "is the bypass that made the analysis conductor decoration"
    )


def _imports_of(module: str) -> set[str]:
    path = Path(__file__).resolve().parents[1] / "app" / "api" / module
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
        elif isinstance(node, ast.Import):
            found.update(a.name for a in node.names)
    return found
