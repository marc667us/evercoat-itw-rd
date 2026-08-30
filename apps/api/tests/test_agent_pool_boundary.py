"""The agent tier must write on the AGENT connection, or 060 is decoration.

🔴 THIS IS THE TEST THREE COMMENTS PROMISE.

`app/agents/tools/market_intelligence.py`, the market-intelligence conductor
and `app/core/config.py` all say the draft-only boundary is a property of the
connection and point here. If this file is deleted, those become claims about a
guard that does not exist.

What it guards: migration 060 refuses a non-draft write from `evercoat_agent`,
keyed on `session_user`. Run the same tool code on the runtime pool and the
trigger never fires — the writes succeed, an agent can publish, and NOTHING IN
THE CODE LOOKS DIFFERENT. There is no exception, no failing assertion, and no
log line. That failure is invisible by construction, which is exactly the kind
this repository has shipped before ("a gate on an unused path is decoration").

So this reads the source. It is a structural test, and it says so: it proves
the conductor NAMES the agent scope and does not name the runtime one. That is
weaker than driving a real write — which `tests/db/test_060_agent_boundary.py`
does against PostgreSQL — and the two are complementary. This one catches a
future edit that swaps the scope; that one catches a trigger that stopped
refusing.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "app"
CONDUCTOR = APP / "agents" / "conductors" / "market_intelligence_conductor.py"
TOOLS = APP / "agents" / "tools" / "market_intelligence.py"


def _names_called(path: Path) -> set[str]:
    """Every function name called anywhere in the module."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    called: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                called.add(func.id)
            elif isinstance(func, ast.Attribute):
                called.add(func.attr)
    return called


def test_the_conductor_opens_the_agent_scope() -> None:
    called = _names_called(CONDUCTOR)
    assert "agent_session_scope" in called, (
        "the market-intelligence conductor no longer opens agent_session_scope. "
        "Its writes would run on whatever session it was handed, migration "
        "060's trigger reads session_user and would never fire, and an agent "
        "could publish to the public catalogue."
    )


def test_the_conductor_never_opens_the_runtime_or_public_scope() -> None:
    called = _names_called(CONDUCTOR)
    for forbidden in ("session_scope", "unscoped_session_scope", "public_session_scope"):
        assert forbidden not in called, (
            f"the conductor calls {forbidden}(). The agent tier must write on "
            "the agent connection: on any other, the draft-only boundary is "
            "silently absent."
        )


def test_the_conductor_still_authorizes_on_the_callers_session() -> None:
    """Two sessions, and the caller's is not optional either.

    `authorize()` replaces the claimed permission set with one read from
    `core.authorization_for_current_session()`, keyed on the tenant GUC. The
    agent connection has no GUC and no privilege on `core`, so this can only
    happen on the caller's session — and without it `require()` would gate on
    a set the caller supplied (I105).
    """
    called = _names_called(CONDUCTOR)
    assert "authorize" in called
    assert "require" in called


@pytest.mark.parametrize("entry", ["propose_catalogue_entry", "read_review_queue"])
def test_every_entry_point_takes_the_callers_session_first(entry: str) -> None:
    """The caller's session is the first positional argument, as elsewhere.

    Not cosmetic: every other conductor in this application takes `session`
    first, and a signature that broke the pattern here is one an orchestrator
    edit could fill with the WRONG session without a type error, because both
    are `Session`.
    """
    tree = ast.parse(CONDUCTOR.read_text(encoding="utf-8"))
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    assert entry in functions, f"{entry} is gone from the conductor"
    args = functions[entry].args.args
    assert args, f"{entry} takes no positional arguments"
    assert args[0].arg == "session", f"{entry}'s first argument is {args[0].arg!r}, not 'session'"


def test_the_tools_never_open_a_session_of_their_own() -> None:
    """Tools receive a session; they do not choose one.

    A tool that opened its own scope would decide the connection — and
    therefore decide whether the boundary applies — from inside the layer that
    is supposed to be pure. It would also be invisible at the conductor, which
    is where a reader looks to answer "which connection does this write use?".
    """
    called = _names_called(TOOLS)
    for forbidden in (
        "agent_session_scope",
        "session_scope",
        "unscoped_session_scope",
        "public_session_scope",
    ):
        assert forbidden not in called, f"{TOOLS.name} opens {forbidden}() itself"


def test_the_tools_never_write_a_publication_status_other_than_draft() -> None:
    """A read of the source, and deliberately a crude one.

    The database is what refuses a published write. This only catches the
    tools ASKING for one — which would be a defect even though 060 would stop
    it, because a tool that tries is a tool somebody meant to publish with.
    """
    source = TOOLS.read_text(encoding="utf-8")

    # 🔴 THE FIRST VERSION OF THIS ASSERTION ENDED `or True` AND COULD NOT
    # FAIL. Caught while writing it, which is the only reason it is not in the
    # repository. Falsify a guard before trusting it, every time.
    #
    # Strings only, not comments: the module's own docstring discusses
    # publication at length and would match a naive substring search, which is
    # how a guard ends up passing for the wrong reason.
    tree = ast.parse(source)
    literals = {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    sql = " ".join(text for text in literals if "INSERT INTO public_intel." in text)

    assert "INSERT INTO public_intel." in sql, "the tools no longer insert anything"
    for forbidden in ("'published'", "'withdrawn'"):
        assert forbidden not in sql, (
            f"a tool's SQL names {forbidden}. Only a human publishes; the "
            "database would refuse this, but a tool that ASKS is one somebody "
            "meant to publish with."
        )
    inserts = sql.count("INSERT INTO public_intel.")
    drafts = sql.count("'draft'")
    assert drafts >= inserts, (
        f"{inserts} INSERT statements but only {drafts} literal 'draft' values; "
        "an insert that does not name draft relies on a column default, and a "
        "migration could change a default without anything here failing"
    )
