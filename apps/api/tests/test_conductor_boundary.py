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
import dataclasses
import uuid
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.agents.boundary import DepartmentDeniedError, UnverifiedPrincipalError, require
from app.agents.conductors import (
    analysis_conductor,
    laboratory_conductor,
    msd_conductor,
    testing_conductor,
)
from app.agents.orchestrators import root_orchestrator
from app.agents.principal import AgentPrincipal, SessionIdentityError
from app.core.security import Principal
from app.domains.dashboards.service import ROLE_DASHBOARDS


class _ExplodingSession:
    """A session that fails loudly if anything touches the database.

    Used only where NOTHING should reach the database at all — the
    `authorize()` identity checks below, which must refuse before querying.
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


def principal(*permissions: str, user_id: uuid.UUID = USER, org: uuid.UUID = ORG) -> AgentPrincipal:
    """A caller CLAIMING these permissions.

    🔴 SINCE I105 THE CLAIM IS NOT WHAT THE GATE CONSULTS, AND THAT IS THE
    WHOLE POINT. `authorize()` replaces this set with the one
    `core.permissions_for_current_session()` returns for the session's own
    GUC. So in every conductor test below, what this helper claims and what
    `_ProbeSession` reports are supplied SEPARATELY — and
    `test_the_gate_ignores_a_claimed_permission_the_database_denies` sets them
    in deliberate opposition.

    🔴 GOING THROUGH `Principal` IS THE TEST OBEYING THE RULE IT CHECKS (I104).
    `AgentPrincipal` refuses direct construction, so even the tests must state
    an identity rather than assemble one.
    """
    return AgentPrincipal.of(
        Principal(
            user_id=user_id,
            organization_id=org,
            keycloak_sub=f"sub-{user_id}",
            email="caller@example.test",
            display_name="Caller",
            roles=frozenset(),
            permissions=frozenset(permissions),
        )
    )


class _ProbeSession:
    """Answers `authorize()`'s one query, then explodes.

    🔴 WHY THE STUBS HAD TO CHANGE FOR I105.

    `authorize()` now runs BEFORE the gate and asks the database two things in
    one round trip: whose session this is, and what that person may do. So a
    session that explodes on first touch can no longer be used to prove the
    gate fires early — it would refuse the authorize query itself.

    This answers exactly that one query and explodes on everything after it.
    Reaching the explosion therefore proves, in order: the identity matched,
    the database supplied a permission set, the gate opened, and the domain
    service was called. Refusing before it proves the gate closed without any
    domain read — which is what §7 requires.

    ⚠️ `granted` IS THE DATABASE'S ANSWER, deliberately independent of what
    the principal claims.
    """

    def __init__(
        self,
        *granted: str,
        roles: tuple[str, ...] = (),
        org: uuid.UUID = ORG,
        user: uuid.UUID = USER,
    ) -> None:
        self._row = SimpleNamespace(
            org=str(org), usr=str(user), perms=list(granted), roles=list(roles)
        )
        self._probed = False

    def execute(self, _statement: object, *args: object, **kwargs: object) -> object:
        if not self._probed:
            self._probed = True
            return SimpleNamespace(one=lambda: self._row)
        raise AssertionError(
            "the conductor reached the database (session.execute) after its "
            "permission gate and identity check passed"
        )

    def __getattr__(self, name: str) -> object:  # pragma: no cover - defensive
        raise AssertionError(
            f"the conductor reached the database (session.{name}) after its "
            "permission gate and identity check passed"
        )


# (label, callable) for every read entry point the conductor tier exposes.
# Written out rather than discovered, so that adding a conductor function
# without a gate is a visible omission here rather than an invisible one.
DENIED_CASES = [
    (
        "laboratory.batches",
        lambda: laboratory_conductor.batches(_ProbeSession(), caller=principal()),
    ),
    (
        "laboratory.batch",
        lambda: laboratory_conductor.batch(_ProbeSession(), batch_id=THING, caller=principal()),
    ),
    (
        "testing.tests",
        lambda: testing_conductor.tests(_ProbeSession(), caller=principal()),
    ),
    (
        "testing.test",
        lambda: testing_conductor.test(_ProbeSession(), test_id=THING, caller=principal()),
    ),
    (
        "testing.methods",
        lambda: testing_conductor.methods(_ProbeSession(), caller=principal()),
    ),
    (
        "analysis.dashboard",
        lambda: analysis_conductor.dashboard(_ProbeSession(), name="lead", caller=principal()),
    ),
    (
        "analysis.report",
        lambda: analysis_conductor.report(_ProbeSession(), caller=principal()),
    ),
    (
        "analysis.analytics",
        lambda: analysis_conductor.analytics(_ProbeSession(), caller=principal()),
    ),
    # MSD -- the department that was NOT on this gate until it was brought on.
    (
        "msd.threads",
        lambda: msd_conductor.threads(_ProbeSession(), caller=principal()),
    ),
    (
        "msd.turns",
        lambda: msd_conductor.turns(_ProbeSession(), caller=principal(), thread_id=THING),
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
            _ProbeSession("batch.view"), caller=principal("batch.view")
        ),
    ),
    (
        "testing.tests",
        "test.view",
        lambda: testing_conductor.tests(_ProbeSession("test.view"), caller=principal("test.view")),
    ),
    (
        "analysis.dashboard",
        analysis_conductor.VIEW,
        lambda: analysis_conductor.dashboard(
            _ProbeSession(analysis_conductor.VIEW),
            name="lead",
            # Read from the conductor rather than restated: the point of the
            # drift test below is that this literal has exactly one home.
            caller=principal(analysis_conductor.VIEW),
        ),
    ),
    (
        "analysis.report",
        analysis_conductor.REPORT,
        lambda: analysis_conductor.report(
            _ProbeSession(analysis_conductor.REPORT), caller=principal(analysis_conductor.REPORT)
        ),
    ),
    (
        "analysis.analytics",
        analysis_conductor.ANALYTICS,
        lambda: analysis_conductor.analytics(
            _ProbeSession(analysis_conductor.ANALYTICS),
            caller=principal(analysis_conductor.ANALYTICS),
        ),
    ),
    (
        "msd.threads",
        msd_conductor.USE,
        lambda: msd_conductor.threads(
            _ProbeSession(msd_conductor.USE), caller=principal(msd_conductor.USE)
        ),
    ),
    (
        "msd.turns",
        msd_conductor.USE,
        lambda: msd_conductor.turns(
            _ProbeSession(msd_conductor.USE), caller=principal(msd_conductor.USE), thread_id=THING
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

    It opens onto `_ProbeSession`, so the proof that the gate passed is
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
    # And it got there THROUGH the identity check, not around it. The stub
    # answers the `current_setting` probe first and explodes only afterwards,
    # so this message can only come from a call made after `bind` succeeded.
    assert "identity check passed" in str(caught.value), (
        f"{label} reached the database without passing the I104 session "
        "identity check -- the bind was skipped or reordered"
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
            # 🔴 THE GRANT IS ON THE SESSION, NOT ON THE PRINCIPAL (I105).
            # `authorize()` replaces the claimed set with the database's, so
            # what reaches the builder as `held_permissions` must come from
            # here. Both are listed on the principal too, so that this test
            # would still pass if the direction were reversed -- it is
            # asserting the ARGUMENT is passed, not where it came from; the
            # test below asserts the direction.
            _ProbeSession(analysis_conductor.VIEW, "test.review"),
            name="lead",
            caller=principal(analysis_conductor.VIEW, "test.review"),
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
    for module in ("dashboards.py", "laboratory.py", "testing.py"):
        imports = _imports_of(module)
        assert "app.agents.orchestrators.root_orchestrator" in imports, (
            f"app/api/{module} no longer reaches its department through the "
            "root orchestrator, so that conductor is unreachable again"
        )

    # ⚠️ ONLY dashboards.py IS FULLY OFF ITS SERVICE. laboratory.py and
    # testing.py still import theirs, and that is CORRECT: §4 keeps every
    # write-side function off the orchestrator door, so authorize_batch,
    # confirm_test and the rest must still be called directly. Asserting
    # "imports no service" there would be asserting a §4 violation.
    assert "app.domains.dashboards.service" not in _imports_of("dashboards.py"), (
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


def test_the_report_needs_report_generate_not_merely_view() -> None:
    """🔴 `report.generate`'s FIRST ENFORCEMENT POINT, ANYWHERE.

    Measured before the report was written: `report.generate` is granted to
    FIVE roles, `analytics.portfolio` to two, `analytics.view` to nine — and
    not one of the three was referenced by a single line of application code.
    Permissions with no production path that reads them: this repository's
    most-repeated question, turned on the permission catalogue itself.

    Generating a report aggregates across records and is the thing a person
    exports and sends onwards, so it takes its own permission rather than
    riding on the dashboard's `project.view`. Holding VIEW must NOT be enough.
    """
    assert analysis_conductor.REPORT == "report.generate"
    assert analysis_conductor.REPORT != analysis_conductor.VIEW, (
        "the report rides on the dashboard's permission, so report.generate still enforces nothing"
    )

    # VIEW alone is refused...
    with pytest.raises(DepartmentDeniedError) as caught:
        analysis_conductor.report(
            _ProbeSession(analysis_conductor.VIEW), caller=principal(analysis_conductor.VIEW)
        )
    assert caught.value.permission == analysis_conductor.REPORT

    # ...and REPORT reaches the service, proving the gate opens rather than
    # refusing everyone. Same both-directions rule as every gate above.
    with pytest.raises(AssertionError) as reached:
        analysis_conductor.report(
            _ProbeSession(analysis_conductor.REPORT), caller=principal(analysis_conductor.REPORT)
        )
    assert "reached the database" in str(reached.value)


def test_the_report_route_is_reachable_and_gated_identically() -> None:
    """The route lands with the report, and asks for the same permission.

    The analysis conductor was written with no caller once already. This
    asserts the endpoint exists, reaches the orchestrator, and requires the
    permission the conductor requires — two literals in two files that a test
    keeps in agreement.
    """
    imports = _imports_of("analysis.py")
    assert "app.agents.orchestrators.root_orchestrator" in imports, (
        "app/api/analysis.py does not reach the analysis department through the root orchestrator"
    )
    assert not any(m.startswith("app.domains.reporting") for m in imports), (
        "app/api/analysis.py imports the reporting service directly, which "
        "bypasses the conductor's report.generate gate"
    )

    route_perms = _route_permissions("analysis.py")
    assert analysis_conductor.REPORT in route_perms, (
        f"app/api/analysis.py does not require {analysis_conductor.REPORT!r} "
        f"(it requires {sorted(route_perms)}), so the route and the conductor "
        "disagree about who may generate a report"
    )


def test_the_report_router_is_actually_registered() -> None:
    """A router written and not included is the no-caller defect one level up."""
    main = (Path(__file__).resolve().parents[1] / "app" / "main.py").read_text(encoding="utf-8")
    # Split, because ruff is right that a compound assertion cannot say WHICH
    # half failed -- and "the router is missing" and "it is mounted at the
    # wrong prefix" are different bugs with different fixes.
    assert "analysis_router" in main, (
        "app/main.py does not import the analysis router, so the report "
        "endpoint does not exist on the running API"
    )
    assert '"/api/analysis"' in main, (
        "app/main.py imports the analysis router but does not mount it at "
        "/api/analysis, so the report endpoint answers 404"
    )


# ---------------------------------------------------------------------------
# I104 — the orchestrator used to trust its arguments
# ---------------------------------------------------------------------------


def test_an_agent_principal_cannot_be_forged() -> None:
    """🔴 I104: THE HOLE WAS THAT PERMISSIONS WERE AN ARGUMENT.

    Every orchestrator entry point took `permissions: frozenset[str]` and
    `user_id: uuid.UUID` as ordinary keyword arguments, with a docstring
    asking callers to pass real ones. An in-process caller could therefore
    claim any permission set, or substitute a colleague's id and read what
    was waiting for them. Raised by Codex; the docstring was the only thing
    enforcing it, which is this repository's most-repeated defect.

    The fix has to be a MECHANISM, not a longer docstring. This is it: the
    type refuses to exist unless something already held a verified
    `Principal`.
    """
    with pytest.raises(TypeError) as caught:
        AgentPrincipal(ORG, USER, frozenset(), frozenset({"test.confirm"}))
    assert "AgentPrincipal.of" in str(caught.value)


def test_an_agent_principal_cannot_be_widened_after_the_gate_reads_it() -> None:
    """Frozen, because a gate that consults a mutable set is advisory.

    `require()` checks `caller.permissions` and the conductor then calls the
    service. Anything holding a reference in between could otherwise widen
    the set after the check and before the read.
    """
    caller = principal("batch.view")
    with pytest.raises(dataclasses.FrozenInstanceError):
        caller.permissions = frozenset({"test.confirm"})  # type: ignore[misc]


IDENTITY_REFUSALS = [
    # (label, the GUCs PostgreSQL reports for the session handed in, the
    #  phrase the refusal must contain)
    #
    # 🔴 THE EXPECTED PHRASE IS NOT DECORATION, AND FALSIFICATION PROVED IT.
    #
    # The first version of this test asserted only that SOMETHING raised.
    # Deleting the unset-GUC branch on purpose left it GREEN: with the GUCs
    # NULL, the next check compares the string "None" against a uuid and
    # refuses anyway. The guard still refused, so the test could not tell
    # that the branch it was named for had been removed -- and the message a
    # developer would then see says "the session's tenant is not this
    # principal's" about a session that has no tenant at all.
    #
    # Pinning the phrase makes each case prove its own branch.
    ("no RLS context at all", (None, None), "no RLS context"),
    ("another tenant's session", (str(uuid.uuid4()), str(USER)), "tenant is not this principal"),
    ("a colleague's session", (str(ORG), str(uuid.uuid4())), "user is not this principal"),
]


@pytest.mark.parametrize(
    ("label", "gucs", "expected"), IDENTITY_REFUSALS, ids=[c[0] for c in IDENTITY_REFUSALS]
)
def test_the_session_must_belong_to_the_principal(
    label: str, gucs: tuple[str | None, str | None], expected: str
) -> None:
    """🔴 THE ONE CHECK A PYTHON CALLER CANNOT TALK ITS WAY PAST.

    The type stops a permission set being invented. It cannot stop somebody
    passing a real principal alongside somebody ELSE's session — and that is
    the same substitution wearing different clothes, because RLS decides
    which rows exist from the session's GUCs, not from the principal.

    So `bind()` asks PostgreSQL: does `app.current_org` /
    `app.current_user_id` agree with this caller? Three ways it must not: an
    unscoped session (which sees across tenants), another tenant's, and a
    colleague's.

    ⚠️ THE FIRST CASE IS THE ONE THAT MATTERS MOST. `current_setting(..., true)`
    returns NULL rather than raising when a GUC was never set, so an
    implementation that only compared the two values would PASS on exactly
    the session that has no tenant scoping at all. *A guard that passes when
    it cannot see is not a guard.*
    """
    org, usr = gucs

    class _Session:
        def execute(self, _statement: object) -> object:
            return SimpleNamespace(one=lambda: SimpleNamespace(org=org, usr=usr))

    with pytest.raises(SessionIdentityError) as caught:
        principal("batch.view").authorize(_Session())
    assert expected in str(caught.value), (
        f"{label} was refused, but by the wrong check: {caught.value}. The "
        "branch this case exists to cover has been removed or reordered."
    )


def test_the_session_check_admits_the_callers_own_session() -> None:
    """The other direction — otherwise `authorize` could be a bare `raise`."""
    verified = principal().authorize(_ProbeSession("batch.view"))
    assert verified.verified, "authorize returned an unverified principal"
    assert verified.permissions == frozenset({"batch.view"}), (
        "authorize did not take the permission set FROM THE DATABASE"
    )


# ---------------------------------------------------------------------------
# analytics.view and analytics.portfolio — permissions that enforced nothing
# ---------------------------------------------------------------------------


def test_the_analytics_gate_matches_the_route_that_serves_it() -> None:
    """🔴 THE SAME DRIFT TEST AS THE DASHBOARD'S, POINTED AT THE OTHER ROUTE.

    `analysis_conductor.dashboard` gates on `project.view` because
    `app/api/dashboards.py` always has. `analysis_conductor.analytics` gates
    on `analytics.view` because `app/api/analysis.py` does, and because
    `apps/web/lib/navigation.ts` has declared this screen that way since the
    navigation was written.

    Two functions in one conductor gating on two different permissions is
    exactly the shape that needs pinning rather than trusting: each is read
    from the source of the route it serves, so neither can drift alone.
    """
    route = _route_permissions("analysis.py")
    assert analysis_conductor.ANALYTICS in route, (
        f"analysis_conductor.analytics gates on {analysis_conductor.ANALYTICS!r}, "
        f"which app/api/analysis.py does not require (it requires {sorted(route)})"
    )
    assert analysis_conductor.REPORT in route, "the report route no longer requires report.generate"


def test_the_two_analytics_permissions_are_distinct_gates() -> None:
    """🔴 COLLAPSING THEM WOULD RE-COMMIT THE DEFECT BEING FIXED.

    The catalogue reserves two permissions and describes the difference
    itself — 'View analytics in scope' against 'View organization-wide
    portfolio analytics'. If both halves of the screen rode on one gate, the
    other permission would still be held by two roles and read by nothing,
    which is precisely the condition this work exists to end.
    """
    assert analysis_conductor.ANALYTICS != analysis_conductor.PORTFOLIO
    assert analysis_conductor.ANALYTICS == "analytics.view"
    assert analysis_conductor.PORTFOLIO == "analytics.portfolio"


def _analytics_fn() -> ast.FunctionDef:
    src = (
        Path(__file__).resolve().parents[1]
        / "app"
        / "agents"
        / "conductors"
        / "analysis_conductor.py"
    ).read_text(encoding="utf-8")
    return next(
        node
        for node in ast.walk(ast.parse(src))
        if isinstance(node, ast.FunctionDef) and node.name == "analytics"
    )


def test_the_portfolio_section_is_withheld_before_it_is_computed() -> None:
    """🔴 §7 FILTERS BEFORE, NEVER AFTER — AND HERE THAT IS ALSO THE BILL.

    A caller with `analytics.view` and without `analytics.portfolio` must not
    have `portfolio_by_project` run on their behalf and the result discarded.
    That function issues one test-results report PER PROJECT in the
    organization, and each of those costs one detail read per test. So
    "compute then hide" would mean performing the entire privileged
    aggregation for somebody not entitled to its result — the "filter after
    generation" mistake with a large bill attached.

    Asserted on the source: every reference to `portfolio_by_project` must
    sit inside a conditional.
    """
    fn = _analytics_fn()
    conditional = {
        id(node)
        for parent in ast.walk(fn)
        if isinstance(parent, ast.IfExp | ast.If)
        for node in ast.walk(parent)
    }
    unguarded = [
        node
        for node in ast.walk(fn)
        if isinstance(node, ast.Name)
        and node.id == "portfolio_by_project"
        and id(node) not in conditional
    ]
    assert not unguarded, (
        "analysis_conductor.analytics references portfolio_by_project outside "
        "a conditional: the organization-wide aggregation would run for "
        "callers without analytics.portfolio and then be thrown away"
    )


def test_absent_is_not_empty_for_the_portfolio_section() -> None:
    """`by_project` must be `None`, never `[]`, when the section is withheld.

    An empty list says "this organization has no projects". That is a
    different claim, usually a false one, and it is the failure mode this
    project shipped once already when a failed `/api/me` became demonstration
    data.

    ⚠️ READ FROM THE AST, NEVER BY STRING SEARCH. A comment mentioning `None`
    would satisfy a substring test, and this file has already been bitten by
    the mirror image of that — a test its own explanatory comment reddened.

    ⚠️ AND IT ACCEPTS BOTH SHAPES ON PURPOSE. The withholding was a
    conditional expression and became an `if/else` when the portfolio grew a
    truncation flag; the previous version of this test hard-coded `IfExp` and
    reported itself STALE rather than passing quietly, which is the right
    failure. What matters is that SOME branch assigns `None`, not which syntax
    expresses it.
    """
    fn = _analytics_fn()

    assigns_none = False
    assigns_empty_list = False
    for node in ast.walk(fn):
        if not isinstance(node, ast.Assign | ast.IfExp):
            continue
        values = [node.orelse] if isinstance(node, ast.IfExp) else [node.value]
        for value in values:
            if isinstance(value, ast.Constant) and value.value is None:
                assigns_none = True
            if isinstance(value, ast.List) and not value.elts:
                assigns_empty_list = True

    assert assigns_none, (
        "nothing in analysis_conductor.analytics assigns None -- the withheld "
        "portfolio section must be absent, not empty"
    )
    assert not assigns_empty_list, (
        "analysis_conductor.analytics assigns an empty list, which would claim "
        "this organization has no projects"
    )


def test_msd_is_on_the_shared_department_gate() -> None:
    """🔴 MSD WAS THE ONE DEPARTMENT THAT WAS NOT.

    `app/agents/boundary.py` was written citing MSD's inline per-capability
    checks as the pattern it was generalising — *"this is the same rule,
    named once, so the next department does not have to remember it"*. Three
    departments were then built on `require()` and MSD kept remembering,
    which it did not: on 2026-08-25 `explain_result` called the testing tool
    with no check at all, the third instance of that shape in that one file.

    So the department now declares its permission the same way the others do.
    """
    assert msd_conductor.DEPARTMENT == "msd"
    assert msd_conductor.USE == "msd.use"


def test_every_msd_route_reaches_the_orchestrator() -> None:
    """🔴 THREE OF MSD's FOUR ENDPOINTS WENT AROUND THE DOOR.

    §0.2 names this department explicitly: *"MSD is reached through the
    orchestrator."* Only `POST /threads/{id}/ask` did. The other three
    imported `app.domains.msd.service` and called it, so the department had
    one governed door and three ordinary ones.

    `test_agent_topology.py` could not catch it: a domain service is not a
    conductor and not a tool, so importing one breaks no import rule. What it
    broke was the sentence §0.2 actually wrote down.

    The two READS now go through the orchestrator. The two WRITES stay
    direct, deliberately — the agent tier is read-only by §4 — so this test
    names exactly which service functions may still be imported there. A new
    read appearing in that import list is the regression.
    """
    src = (Path(__file__).resolve().parents[1] / "app" / "api" / "msd.py").read_text(
        encoding="utf-8"
    )
    imported: set[str] = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("app.domains.msd"):
            imported |= {alias.name for alias in node.names}

    reads = imported & {"list_threads", "list_turns"}
    assert not reads, (
        "app/api/msd.py still reads MSD's conversations through the domain "
        f"service instead of the orchestrator: {sorted(reads)}"
    )
    assert imported <= {"MsdNotFoundError", "open_thread", "record_exchange"}, (
        f"app/api/msd.py imports more of the MSD service than the two writes "
        f"§4 keeps off the agent tier: {sorted(imported)}"
    )


def test_reading_an_msd_conversation_requires_the_same_permission_as_asking() -> None:
    """🔴 HALF A SWITCH IS NOT A SWITCH.

    `msd.use` is *"what an administrator revokes when MSD must be switched
    off for somebody"*. It gated `POST /ask` and nothing else, so revoking it
    left that person able to re-open every answer MSD had ever given them —
    the turns ARE the answers.

    ⚠️ MEASURED BEFORE CHANGING IT: the two seeded roles without `msd.use`
    are `executive_viewer` and `administrator`, and both were already refused
    by `/ask`. Neither can own a thread, so neither loses a conversation.

    🔴 AND IT COUNTS PER ROUTE, BECAUSE A SET COMPARISON CANNOT.

    This test first read `_route_permissions("msd.py") == {"msd.use"}`.
    Removing the dependency from ONE of the four handlers on purpose left it
    GREEN — the other three still contributed the same single element, so the
    set was unchanged and the ungated route was invisible to it. That is the
    defect being tested for, hiding inside the test for it. Found by breaking
    the code deliberately; nothing else would have shown it.
    """
    path = Path(__file__).resolve().parents[1] / "app" / "api" / "msd.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))

    ungated: list[str] = []
    routes = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        if not any(
            isinstance(d, ast.Call)
            and isinstance(d.func, ast.Attribute)
            and isinstance(d.func.value, ast.Name)
            and d.func.value.id == "router"
            for d in node.decorator_list
        ):
            continue
        routes += 1
        # The dependency sits in the signature's defaults, which belong to
        # this FunctionDef, so walking the node alone finds this route's own
        # gate and never a neighbour's.
        gated = any(
            isinstance(call, ast.Call)
            and isinstance(call.func, ast.Name)
            and call.func.id == "require_permission"
            and call.args
            and isinstance(call.args[0], ast.Constant)
            and call.args[0].value == "msd.use"
            for call in ast.walk(node)
        )
        if not gated:
            ungated.append(node.name)

    assert routes == 4, f"expected MSD's four endpoints, found {routes}; this test is stale"
    assert not ungated, (
        f"these MSD routes are not gated on msd.use: {ungated}. Reading the "
        "answers is using the assistant, and half a switch is not a switch."
    )


# ---------------------------------------------------------------------------
# What the AgentPrincipal type does and does not prevent — MEASURED
# ---------------------------------------------------------------------------
#
# 🔴 CODEX ENUMERATED FOUR BYPASSES AND ALL FOUR WORKED.
#
# The first version of `principal.py` claimed "you cannot construct one from
# loose values". You could, four ways, and each was reproduced against the
# real code before anything was changed. Three are closed below. The fourth
# cannot be closed in Python and is asserted OPEN on purpose.
#
# ⚠️ A TEST FILE THAT ONLY DEMONSTRATED THE SUCCESSES WOULD REBUILD THE
# OVERCLAIM IT IS HERE TO PREVENT. The last test states the limit as an
# executable fact, so the next reader learns what this type is worth from the
# suite rather than from a docstring that drifted.


def test_of_refuses_an_object_that_merely_looks_like_a_principal() -> None:
    """🔴 `of()` DUCK-TYPED ITS ARGUMENT, SO ANY OBJECT COULD CLAIM ANYTHING.

    Reproduced before the fix: `of(SimpleNamespace(permissions={...}))`
    returned a fully valid `AgentPrincipal` carrying `test.confirm` and
    `analytics.portfolio`. Nothing downstream could have told it apart from a
    real one — the conductor gate would have consulted the forged set and
    opened.
    """
    with pytest.raises(TypeError) as caught:
        AgentPrincipal.of(
            SimpleNamespace(
                organization_id=ORG,
                user_id=USER,
                roles=frozenset({"administrator"}),
                permissions=frozenset({"test.confirm", "analytics.portfolio"}),
            )
        )
    assert "verified Principal" in str(caught.value)


def test_of_refuses_a_principal_subclass() -> None:
    """`type(...) is not Principal`, not `isinstance` — and here is the difference.

    A subclass is where "behaves like a Principal" stops being good enough: it
    passes `isinstance`, and it is the natural place to smuggle in an
    overridden `permissions`. Python happens to block the property form on a
    frozen slots dataclass (`property 'permissions' has no setter`), but that
    is an accident of the base class's shape, not a rule anybody stated — and
    a base class that stopped being `slots=True` would silently reopen it.

    So the exact-type check is what this asserts, on a plain subclass that
    constructs perfectly well and that `isinstance` would have waved through.
    """

    class _Subclass(Principal):
        pass

    impostor = _Subclass(
        user_id=USER,
        organization_id=ORG,
        keycloak_sub="s",
        email="e@example.test",
        display_name="d",
        permissions=frozenset({"test.confirm"}),
    )
    assert isinstance(impostor, Principal), "the premise of this test has gone"

    with pytest.raises(TypeError) as caught:
        AgentPrincipal.of(impostor)
    assert "verified Principal" in str(caught.value)


def test_dataclasses_replace_cannot_widen_a_real_principal() -> None:
    """🔴 THE BYPASS I HAD NOT CONSIDERED, AND THE REASON THE GUARD IS A NONCE.

    `dataclasses.replace` re-invokes `__init__` with the EXISTING field
    values, so the old module-level sentinel was copied straight into the
    forgery: `replace(real_caller, permissions={"test.confirm"})` produced a
    valid object with escalated rights, from a legitimately obtained one.

    A long-lived sentinel is a replayable credential. The guard is minted per
    construction and consumed on use, so a replayed one no longer verifies.
    """
    real = principal("batch.view")
    with pytest.raises(TypeError):
        dataclasses.replace(real, permissions=frozenset({"test.confirm"}))
    # And the original is untouched — a failed forgery must not spend or
    # corrupt the identity it was derived from.
    assert real.permissions == frozenset({"batch.view"})


def test_the_factory_token_is_valid_exactly_once() -> None:
    """The nonce is consumed, so it cannot be captured and reused.

    This is what closes the imported-sentinel bypass too: there is no longer a
    long-lived object to import. Anything a caller manages to get hold of has
    already been spent by the construction that minted it.
    """
    from app.agents import principal as module

    token = module._mint()
    AgentPrincipal(ORG, USER, frozenset(), frozenset({"batch.view"}), False, token)
    with pytest.raises(TypeError):
        AgentPrincipal(ORG, USER, frozenset(), frozenset({"test.confirm"}), False, token)


def test_object_new_still_bypasses_the_guard_and_that_is_documented() -> None:
    """🔴 ASSERTED OPEN, DELIBERATELY. THIS IS NOT A TODO.

    `object.__new__` plus `object.__setattr__` builds any object at all, and
    no Python type can prevent it. Code that can do this could equally call
    `session.execute` and skip the agent tier entirely, so closing it would
    not change what an in-process attacker can reach.

    The test exists so that the module's claim stays honest. `principal.py`
    says this type is a MISUSE BARRIER and not an in-process security
    boundary; if somebody later "fixes" this and upgrades the docstring's
    claim to match, this test fails and makes them say so explicitly.

    🔴 THE REAL REMAINING GAP IS NOT THIS ONE — IT IS I105: `bind()` validates
    identity against PostgreSQL and does NOT validate `permissions`. A forged
    principal using the real session identity passes `bind()` while claiming
    arbitrary authorization. The fix is to derive the permission set from the
    GUC-bound user, and it needs a design (ADR-029 rejected the obvious
    SECURITY DEFINER shape for I82 on measured evidence), not a patch.
    """
    forged = object.__new__(AgentPrincipal)
    object.__setattr__(forged, "organization_id", ORG)
    object.__setattr__(forged, "user_id", USER)
    object.__setattr__(forged, "roles", frozenset())
    object.__setattr__(forged, "permissions", frozenset({"test.confirm"}))
    object.__setattr__(forged, "_guard", None)

    assert forged.has("test.confirm"), (
        "object.__new__ no longer bypasses the guard. If that is deliberate, "
        "update app/agents/principal.py -- its docstring currently states "
        "plainly that this bypass is open and unclosable, and an unstated "
        "improvement is how the next overclaim starts."
    )
    # And it still cannot get past the DATABASE check, which is the half that
    # does not live in Python.
    with pytest.raises(SessionIdentityError):
        forged.authorize(_ProbeSession(user=uuid.uuid4()))


def test_the_analytics_response_reports_the_cap_it_applied() -> None:
    """🔴 THE SCREEN INVENTED THE TRUNCATION LIMIT. Raised by Codex.

    `activity_analytics` omitted `limit` from its response and
    `app/analytics/page.tsx` rendered `capped at {"200"}` — a literal that
    merely happened to match the frontend's own default request. A caller
    asking for `?limit=10` would have received `truncated: true` under a
    notice claiming the cap was 200.

    An invented number is worst precisely here: the truncation notice is the
    one element whose entire job is to say the count is incomplete.
    """
    source = (
        Path(__file__).resolve().parents[1] / "app" / "domains" / "analytics" / "service.py"
    ).read_text(encoding="utf-8")
    assert '"limit": report["limit"]' in source, (
        "analytics no longer reports the cap it applied, so the screen has "
        "nothing truthful to render beside its truncation warning"
    )

    # 🔴 COMMENTS STRIPPED FIRST — A TEST A COMMENT CAN REDDEN IS A TEST
    # NOBODY TRUSTS, and this one failed on its own explanation.
    #
    # The page carries a comment quoting the defect it fixed: *"This read
    # `capped at {"200"}`"*. A naive substring search found that and reported
    # the bug as still present. The inverse — a comment SATISFYING an
    # assertion — is the same failure and is the more dangerous direction,
    # which is why the rule is to read code and not prose.
    page_path = (
        Path(__file__).resolve().parents[3] / "apps" / "web" / "app" / "analytics" / "page.tsx"
    )
    code = "\n".join(
        line
        for line in page_path.read_text(encoding="utf-8").splitlines()
        if not line.lstrip().startswith(("//", "*", "/*"))
    )
    assert 'capped at {"200"}' not in code, "the analytics page hardcodes a truncation limit again"
    assert "capped at {data.testing.limit}" in code, (
        "the analytics page does not render the server's own cap"
    )


# ---------------------------------------------------------------------------
# I105 — the gate consults the database, not the caller
# ---------------------------------------------------------------------------
#
# 🔴 THE HALF I104 LEFT OPEN, IN CODEX'S OWN WORDS:
#
#     bind() validates only organization and user; it never validates roles or
#     permissions. A forged principal using the real session identity
#     therefore passes bind() while claiming arbitrary authorization.
#
# Everything above proves the gate refuses and opens. These prove WHOSE ANSWER
# it is using — which is the only question I105 asked, and the one no test
# here could previously distinguish, because for a legitimate caller the
# claimed set and the real set are identical.


def test_the_gate_ignores_a_claimed_permission_the_database_denies() -> None:
    """🔴 THE I105 REGRESSION TEST. Claim and reality set in opposition.

    The principal claims `report.generate` — the exact escalation that would
    hand somebody the whole test-results report. The session's own GUC grants
    nothing. Before 048 the conductor consulted the claim and opened.
    """
    with pytest.raises(DepartmentDeniedError) as caught:
        analysis_conductor.report(
            _ProbeSession(),  # the database grants NOTHING
            caller=principal(analysis_conductor.REPORT),  # the caller claims it
        )
    assert caught.value.permission == analysis_conductor.REPORT


def test_the_gate_honours_a_permission_the_database_grants_and_the_caller_omits() -> None:
    """The other direction, and it is not symmetric decoration.

    A test that only proved "a claimed permission is ignored" is satisfied by
    a gate that refuses everyone. This one is satisfied only by a gate reading
    the database: the principal claims NOTHING and the session grants
    `report.generate`, so reaching the domain service can have exactly one
    explanation.

    ⚠️ This is also the shape that makes revocation work. A permission set
    computed at the start of a request is a statement about the past;
    `authorize()` re-reads it, which is why `get_principal`'s rule — *"a JWT is
    not a current statement about authorization"* — now holds for permissions
    too.
    """
    with pytest.raises(AssertionError) as reached:
        analysis_conductor.report(
            _ProbeSession(analysis_conductor.REPORT),  # the database grants it
            caller=principal(),  # the caller claims nothing at all
        )
    assert "identity check passed" in str(reached.value)


def test_a_conductor_that_forgets_to_authorize_fails_loudly() -> None:
    """🔴 A MISSING LINE MUST NOT BE SILENTLY EQUIVALENT.

    For a legitimate caller the claimed set and the derived set are identical,
    so a conductor written next month that skipped `authorize()` would pass
    every ordinary test and be wrong only for a forgery — the one case no test
    naturally covers. `require()` therefore refuses an unverified principal
    outright.

    ⚠️ AND IT IS A DIFFERENT ERROR FROM A DENIAL, deliberately. Reporting "you
    forgot to authorize" as "you lack the permission" would send the next
    reader to the role grants to debug a bug in the conductor.
    """
    with pytest.raises(UnverifiedPrincipalError) as caught:
        require(principal("batch.view"), department="laboratory", permission="batch.view")
    assert "authorize" in str(caught.value)

    # ...and the same principal, once authorized, is accepted.
    verified = principal().authorize(_ProbeSession("batch.view"))
    require(verified, department="laboratory", permission="batch.view")


def _call_positions(fn: ast.FunctionDef) -> tuple[int | None, int | None]:
    """Line numbers of the real `caller.authorize(...)` and `require(...)` CALLS.

    🔴 AST NODES, NOT TEXT — AND THE FIRST VERSION OF THIS TEST USED TEXT.

    It searched `ast.dump(node)` for the string "authorize" and compared
    `ast.unparse(node).index(...)` positions. Both include the DOCSTRING, and
    every conductor now discusses `authorize()` prominently in its prose — so
    a function could delete the actual call, or move it after the gate, and
    still satisfy the test through its own documentation. Raised by Codex.

    That is the mirror of the defect found earlier the same day, when a
    comment REDDENED a test. A comment that GREENS one is the more dangerous
    direction, and this file now contains one example of each.
    """
    authorize_at: int | None = None
    require_at: int | None = None
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr == "authorize" and authorize_at is None:
            authorize_at = node.lineno
        if isinstance(func, ast.Name) and func.id == "require" and require_at is None:
            require_at = node.lineno
    return authorize_at, require_at


def test_every_conductor_entry_point_authorizes_before_it_gates() -> None:
    """The order is load-bearing, and it is read from the call graph.

    `require()` refuses an unverified principal, so a conductor that gated
    first could not work at all — the tests above would catch it. What this
    adds is that EVERY gated entry point does it, including any added later,
    and that the authorize call is a real call rather than a mention.
    """
    conductors = sorted(
        (Path(__file__).resolve().parents[1] / "app" / "agents" / "conductors").glob(
            "*_conductor.py"
        )
    )
    assert conductors, "no conductors found; this test is looking in the wrong place"

    checked: list[str] = []
    missing: list[str] = []
    for path in conductors:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef) or node.name.startswith("_"):
                continue
            authorize_at, require_at = _call_positions(node)
            if require_at is None:
                continue  # not a gated entry point
            where = f"{path.name}::{node.name}"
            checked.append(where)
            if authorize_at is None:
                missing.append(f"{where} never calls authorize()")
            elif authorize_at > require_at:
                missing.append(f"{where} gates on line {require_at} before authorizing")

    assert checked, "no gated conductor entry points were found at all"
    assert not missing, (
        "these conductor entry points gate on an authorization set the "
        f"database has not supplied: {missing}"
    )


def test_roles_are_derived_from_the_database_too() -> None:
    """🔴 THE HALF OF I105 THE FIRST FIX MISSED. Raised by Codex.

    Codex's statement of I105 was that `bind()` "never validates ROLES OR
    PERMISSIONS". The first version of migration 048 derived permissions and
    copied `roles` straight through — half of the sentence that was quoted
    back at me.

    Roles are not decorative. `app/domains/tasks/service.py` selects unclaimed
    work with

        t.assigned_user_id IS NULL AND t.assigned_role = ANY(:roles)

    and `msd_conductor` feeds `caller.roles` into it through
    `app/agents/tools/work.py`. So a forged principal carrying the REAL
    session identity and an invented role would have made the assistant
    surface tasks addressed to a role that person does not hold — §7's
    "retrieval filtered by caller-supplied authorization state", which is the
    whole subject of this issue.

    Claim and reality are set in opposition, as with permissions.
    """
    claimed = AgentPrincipal.of(
        Principal(
            user_id=USER,
            organization_id=ORG,
            keycloak_sub=f"sub-{USER}",
            email="caller@example.test",
            display_name="Caller",
            roles=frozenset({"product_development_director", "qa_compliance_officer"}),
            permissions=frozenset(),
        )
    )
    verified = claimed.authorize(_ProbeSession(roles=("laboratory_technician",)))

    assert verified.roles == frozenset({"laboratory_technician"}), (
        f"authorize() produced roles {sorted(verified.roles)} — the caller's claim "
        "survived, so role-addressed work is still selected by caller-supplied state"
    )
    assert "product_development_director" not in verified.roles
