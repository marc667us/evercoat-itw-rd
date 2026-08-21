"""No function may roll back its caller's transaction. TODO I30.

🔴 THE ABSENCE IS THE MECHANISM, SO THE ABSENCE IS TESTED.

`Session.rollback()` ALWAYS rolls back the **topmost** transaction and
discards any nested ones. It is not scoped to the statement that failed, and
a SAVEPOINT around the call does not protect you from it.

Twenty-three service functions and routes used to call it inside an
`IntegrityError` handler to leave the session usable. That is correct while
the function IS the whole request, and destructive the moment it is not — and
§12 pushes this codebase toward exactly that composition: *"do not rebuild
infrastructure per module, reuse these, always."*

Two had already bitten before the sweep:

* `open_failure`, once `complete_execution` called it to satisfy §10, would
  have discarded a completed test and its audit event over a duplicate
  failure code.
* `record_driver`, once `revise_version` called it to satisfy §29, would have
  discarded a freshly cloned formula version.

**Neither was found by reading the function.** Both were found by a reviewer
looking at the call that introduced the composition — which means the next one
will not be found by reading either. Hence a test rather than a convention.

🔴 AND THE FIRST VERSION OF THIS FILE COULD FALSE-PASS, which Codex caught.
It asked only whether the `try` contained *some* `guarded_write` anywhere,
so an unguarded `session.execute` sitting beside a guarded one satisfied it —
a guard against unprotected writes that did not notice an unprotected write.
It now requires **every** `session.execute` in the block to be lexically
inside a guard.

These take no fixtures: they read source, so they run everywhere, including
where no database is reachable.
"""

from __future__ import annotations

import ast
import pathlib

APP = pathlib.Path(__file__).resolve().parents[1] / "app"

# `session_scope` and `unscoped_session_scope` OWN the request transaction, so
# they are the only functions with the standing to end one. Named individually
# rather than exempting the whole module: a future helper added beside them
# must not inherit the exemption by living in the same file. Raised by Codex.
ROLLBACK_ALLOWED: dict[str, set[str]] = {
    "core/db.py": {"session_scope", "unscoped_session_scope"},
}

# Nodes that open a new scope. `ast.walk` crosses these happily, which would
# let a `guarded_write` inside an unrelated nested function satisfy an outer
# handler. Raised by Codex.
_SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)


def _python_files() -> list[pathlib.Path]:
    return sorted(p for p in APP.rglob("*.py") if "__pycache__" not in p.parts)


def _walk_same_scope(node: ast.AST) -> list[ast.AST]:
    """Every descendant of `node` that shares its scope.

    Stops at nested function, class and lambda boundaries.
    """
    found: list[ast.AST] = []
    stack: list[ast.AST] = list(ast.iter_child_nodes(node))
    while stack:
        current = stack.pop()
        found.append(current)
        if isinstance(current, _SCOPES):
            continue
        stack.extend(ast.iter_child_nodes(current))
    return found


def _is_integrity_error(node: ast.expr | None) -> bool:
    """`IntegrityError`, `exc.IntegrityError`, or either inside a tuple."""
    if node is None:
        return False
    if isinstance(node, ast.Name):
        return node.id == "IntegrityError"
    if isinstance(node, ast.Attribute):
        return node.attr == "IntegrityError"
    if isinstance(node, ast.Tuple):
        return any(_is_integrity_error(e) for e in node.elts)
    return False


def _is_guard(node: ast.AST) -> bool:
    """A `with guarded_write(...)` — plain or attribute-qualified."""
    if not isinstance(node, ast.With):
        return False
    for item in node.items:
        call = item.context_expr
        if not isinstance(call, ast.Call):
            continue
        func = call.func
        if isinstance(func, ast.Name) and func.id == "guarded_write":
            return True
        if isinstance(func, ast.Attribute) and func.attr == "guarded_write":
            return True
    return False


def _is_db_write(node: ast.AST) -> bool:
    """A `<something>.execute(...)` call — the only way this app writes."""
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"execute", "flush"}
    )


def test_no_service_or_route_calls_session_rollback() -> None:
    """The whole point of I30, as a permanent guard.

    Parsed rather than grepped: a comment mentioning `session.rollback()` is
    fine and common — several now explain why it is absent — and a grep would
    fail on those, which is the fastest way to get a guard deleted.

    Matches `.rollback()` on ANY receiver, not just a variable literally named
    `session`. `db.rollback()` and `self.session.rollback()` do the identical
    damage. Raised by Codex.
    """
    offenders: list[str] = []

    for path in _python_files():
        rel = path.relative_to(APP).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        allowed_here = ROLLBACK_ALLOWED.get(rel, set())

        for func in ast.walk(tree):
            if not isinstance(func, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            if func.name in allowed_here:
                continue
            for node in _walk_same_scope(func):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "rollback"
                    # A SAVEPOINT's own rollback is scoped and legitimate.
                    and not (
                        isinstance(node.func.value, ast.Name)
                        and node.func.value.id in {"savepoint", "nested", "sp"}
                    )
                ):
                    offenders.append(f"{rel}:{node.lineno} in {func.name}()")

    assert not offenders, (
        "rollback() on a session rolls back the TOPMOST transaction and discards "
        "nested ones, so calling it inside a service destroys the caller's unit of "
        "work. Use `guarded_write(session)` from app.core.db, which wraps the write "
        "in a SAVEPOINT and lets the caller decide what the failure means. "
        f"Offenders: {offenders}"
    )


def test_every_write_under_an_integrity_error_handler_is_guarded() -> None:
    """Every write in a `try` that expects IntegrityError must be guarded.

    Catching `IntegrityError` means a constraint violation is EXPECTED here.
    PostgreSQL aborts the whole transaction on one, so without a SAVEPOINT the
    handler runs with a dead transaction: every later statement raises
    `InFailedSqlTransaction`, and any work the caller had already done is
    unrecoverable. The savepoint is what makes the refusal survivable.

    🔴 CONTAINMENT, not presence. The first version asked only whether the
    block contained a `guarded_write` somewhere, so this passed:

        try:
            with guarded_write(session):
                pass
            session.execute(text("INSERT ..."))   # unprotected
        except IntegrityError:
            ...

    Every `.execute()` and `.flush()` in the block must now be lexically
    inside a guard. Raised by Codex.
    """
    offenders: list[str] = []

    for path in _python_files():
        rel = path.relative_to(APP).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

        for node in ast.walk(tree):
            if not isinstance(node, ast.Try):
                continue
            if not any(_is_integrity_error(h.type) for h in node.handlers):
                continue

            # Writes that ARE inside a guard, collected first.
            protected: set[int] = set()
            for stmt in node.body:
                for inner in [stmt, *_walk_same_scope(stmt)]:
                    if _is_guard(inner):
                        for guarded in _walk_same_scope(inner):
                            if _is_db_write(guarded):
                                protected.add(id(guarded))

            for stmt in node.body:
                for inner in [stmt, *_walk_same_scope(stmt)]:
                    if _is_db_write(inner) and id(inner) not in protected:
                        offenders.append(f"{rel}:{inner.lineno}")

    assert not offenders, (
        "these writes sit in a `try` that catches IntegrityError but are NOT inside "
        "`guarded_write(session)`. PostgreSQL aborts the transaction on a constraint "
        "violation, so the handler would run over a dead transaction and the caller's "
        "earlier work would be lost. "
        f"Offenders: {offenders}"
    )
