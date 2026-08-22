"""§0.2 is a structure, and a structure needs an instrument.

Root `CLAUDE.md` §0.2 states four rules about the agent tier:

    Root Orchestrator at app/agents/orchestrators/root_orchestrator.py
    Department Conductors at app/agents/conductors/<dept>_conductor.py
    Specialists never call other agents.
    API routes never call specialists directly.

Every one of them is a claim about IMPORTS, which means every one of them
can be checked. Left as prose they are a convention, and this repository's
own history is a catalogue of conventions that lapsed — a comment
promising the metrics label was a route template while the code used the
raw path; a comment saying direct messages were governed by channel
membership while nothing enforced it; a `CURRENT_SLICE` comment asking
the next person to remember to build the pages.

So this reads the source. It needs no database, no network and no model.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
AGENTS = API_ROOT / "app" / "agents"
API_DIR = API_ROOT / "app" / "api"

ORCHESTRATOR = "app.agents.orchestrators.root_orchestrator"


def _imports(path: Path) -> set[str]:
    """Every module this file imports, as dotted names."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found


def test_the_root_orchestrator_exists_where_the_rule_says() -> None:
    assert (AGENTS / "orchestrators" / "root_orchestrator.py").is_file(), (
        "§0.2 fixes this path exactly; a differently-named entry point is how "
        "a second one gets added later"
    )


def test_conductors_are_named_by_their_department() -> None:
    conductors = sorted(
        p.name for p in (AGENTS / "conductors").glob("*.py") if p.name != "__init__.py"
    )
    assert conductors, "no conductors at all"
    for name in conductors:
        assert name.endswith("_conductor.py"), (
            f"{name} is in conductors/ but is not named <dept>_conductor.py"
        )


def test_no_api_route_reaches_past_the_orchestrator() -> None:
    """🔴 THE RULE WITH TEETH: routes never call specialists directly.

    An API module may import the root orchestrator. It may not import a
    conductor, and it may not import a tool — those are the imports that
    quietly turn a governed entry point into one of several.
    """
    offenders: list[str] = []
    for path in sorted(API_DIR.glob("*.py")):
        for module in _imports(path):
            if module.startswith("app.agents.conductors") or module.startswith("app.agents.tools"):
                offenders.append(f"{path.name} imports {module}")

    assert not offenders, (
        "§0.2: API routes never call specialists directly, and MSD is reached "
        "through the orchestrator. These imports bypass it:\n  " + "\n  ".join(offenders)
    )


def test_the_msd_route_does_reach_the_orchestrator() -> None:
    """The positive case.

    Without it, deleting the import entirely would satisfy the test above
    while leaving MSD unreachable — a rule that passes hardest when the
    feature is gone is not a rule.
    """
    assert ORCHESTRATOR in _imports(API_DIR / "msd.py"), (
        "app/api/msd.py no longer reaches MSD through the root orchestrator"
    )


def test_specialists_never_call_other_agents() -> None:
    """A tool may not import a conductor or another orchestrator.

    Tools are leaves. A tool that reaches back up is how a call graph
    becomes a cycle nobody can reason about, and it is the specific thing
    §0.2 forbids.
    """
    offenders: list[str] = []
    for path in sorted((AGENTS / "tools").glob("*.py")):
        for module in _imports(path):
            if "conductors" in module or "orchestrators" in module:
                offenders.append(f"tools/{path.name} imports {module}")

    assert not offenders, "specialists must never call other agents:\n  " + "\n  ".join(offenders)


def test_no_orchestration_framework_leaks_outside_graphs() -> None:
    """ADR-002 selects LangGraph; §4 confines it to `app/agents/graphs/`.

    There is no `graphs/` package yet — MVP-1's MSD is structured
    tool-calls (ADR-013), so importing a framework to run a `match`
    statement would be the leak rather than the architecture. This test
    holds either way: if `graphs/` appears, the import may live there and
    nowhere else.
    """
    banned = ("langgraph", "langchain", "crewai", "autogen", "semantic_kernel")
    offenders: list[str] = []
    for path in sorted(AGENTS.rglob("*.py")):
        if "graphs" in path.parts:
            continue
        for module in _imports(path):
            root = module.split(".")[0]
            if root in banned:
                offenders.append(f"{path.relative_to(API_ROOT)} imports {module}")

    assert not offenders, (
        "the orchestration framework must stay inside app/agents/graphs/:\n  "
        + "\n  ".join(offenders)
    )


def test_no_paid_ai_sdk_is_imported_anywhere() -> None:
    """§7's zero-cost rule, as a check rather than a promise.

    "No essential dependency on an external AI API — proprietary
    formulations never leave the organization's infrastructure. This is a
    security property first and a cost property second."
    """
    banned = ("openai", "anthropic", "google", "cohere", "mistralai", "boto3")

    # 🔴 ONE NAMED EXCEPTION, AND IT IS NARROWED RATHER THAN WAIVED.
    #
    # `boto3` is the AWS SDK, so it was banned outright -- Bedrock is paid AI
    # and AWS S3 is on §E's forbidden list. But boto3 is also the ordinary
    # client for the S3 PROTOCOL, which is what Garage and Oracle Object
    # Storage speak, and ADR-004 chose an S3-compatible store precisely so the
    # same adapter serves both.
    #
    # So the rule this test means is not "boto3 is absent". It is "no data
    # leaves the organization's infrastructure". The thing that decides which
    # of those is true is `endpoint_url`: WITHOUT it, boto3 resolves to AWS.
    # A ban on the name would have been satisfied by importing `botocore`
    # instead, while an adapter that forgot `endpoint_url` would ship
    # formulation documents to Amazon and pass.
    #
    # The exception is therefore one file, and that file is then held to two
    # assertions the blanket ban never made.
    s3_adapter = API_ROOT / "app" / "core" / "object_storage.py"

    offenders: list[str] = []
    for path in sorted((API_ROOT / "app").rglob("*.py")):
        for module in _imports(path):
            if module.split(".")[0] not in banned:
                continue
            if module.split(".")[0] == "boto3" and path == s3_adapter:
                continue
            offenders.append(f"{path.relative_to(API_ROOT)} imports {module}")

    assert not offenders, (
        "a paid/hosted AI SDK is imported; formulation data must not leave "
        "the organization's infrastructure:\n  " + "\n  ".join(offenders)
    )

    source = s3_adapter.read_text(encoding="utf-8")

    # Every client must be pinned to our own endpoint. This is the assertion
    # that actually enforces the rule; the import location above is only what
    # keeps the surface to one reviewable file.
    for call in re.finditer(r"boto3\.client\(", source):
        tail = source[call.end() : call.end() + 400]
        assert "endpoint_url" in tail, (
            "a boto3 client is constructed without an explicit endpoint_url in "
            "app/core/object_storage.py. Without one, boto3 resolves to AWS "
            "and proprietary formulation documents would be uploaded to a "
            "commercial provider on §E's forbidden list."
        )

    # And nothing in that file may reach an AI service. boto3 is one import
    # away from Bedrock, which is exactly what the blanket ban was protecting
    # against.
    for forbidden_service in ("bedrock", "comprehend", "textract", "rekognition"):
        assert forbidden_service not in source.lower(), (
            f"app/core/object_storage.py references {forbidden_service!r}. The "
            "boto3 exception is for S3-compatible OBJECT STORAGE only; a paid "
            "AI or document service is precisely what §7 forbids."
        )
