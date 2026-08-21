"""No function may roll back its caller's transaction. TODO I30.

🔴 THE ABSENCE IS THE MECHANISM, SO THE ABSENCE IS TESTED.

`Session.rollback()` ALWAYS rolls back the **topmost** transaction and
discards any nested ones. It is not scoped to the statement that failed, and
a SAVEPOINT around the call does not protect you from it.

Twenty-one service functions used to call it inside an `IntegrityError`
handler to leave the session usable. That is correct while the function IS
the whole request, and destructive the moment it is not — and §12 pushes this
codebase toward exactly that composition: *"do not rebuild infrastructure per
module, reuse these, always."*

Two had already bitten before the sweep:

* `open_failure`, once `complete_execution` called it to satisfy §10, would
  have discarded a completed test and its audit event over a duplicate
  failure code.
* `record_driver`, once `revise_version` called it to satisfy §29, would have
  discarded a freshly cloned formula version.

**Neither was found by reading the function.** Both were found by a reviewer
looking at the call that introduced the composition — which means the next one
will not be found by reading either. Hence a test rather than a convention.

These take no fixtures: they read source, so they run everywhere, including
where no database is reachable.
"""

from __future__ import annotations

import ast
import pathlib

APP = pathlib.Path(__file__).resolve().parents[1] / "app"

# The ONE legitimate holder. `session_scope` owns the request transaction, so
# it is the only place with the standing to end one. Everything else is a
# participant in somebody else's unit of work.
ALLOWED = {"core/db.py"}


def _python_files() -> list[pathlib.Path]:
    return sorted(p for p in APP.rglob("*.py") if "__pycache__" not in p.parts)


def test_no_service_or_route_calls_session_rollback() -> None:
    """The whole point of I30, as a permanent guard.

    Parsed rather than grepped: a comment mentioning `session.rollback()` is
    fine and common — several now explain why it is absent — and a grep would
    fail on those, which is the fastest way to get a guard deleted.
    """
    offenders: list[str] = []

    for path in _python_files():
        rel = path.relative_to(APP).as_posix()
        if rel in ALLOWED:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if (
                isinstance(func, ast.Attribute)
                and func.attr == "rollback"
                and isinstance(func.value, ast.Name)
                and func.value.id == "session"
            ):
                offenders.append(f"{rel}:{node.lineno}")

    assert not offenders, (
        "session.rollback() rolls back the TOPMOST transaction and discards nested "
        "ones, so calling it inside a service destroys the caller's unit of work. "
        "Use `guarded_write(session)` from app.core.db, which wraps the write in a "
        "SAVEPOINT and lets the caller decide what the failure means. "
        f"Offenders: {offenders}"
    )


def test_every_integrity_error_handler_guards_its_write() -> None:
    """A handler that translates IntegrityError must sit over a guarded write.

    Catching `IntegrityError` means a constraint violation is EXPECTED here.
    PostgreSQL aborts the whole transaction on one, so without a SAVEPOINT the
    handler runs with a dead transaction: every later statement raises
    `InFailedSqlTransaction`, and any work the caller had already done is
    unrecoverable. The savepoint is what makes the refusal survivable.

    Checks that a `with guarded_write(...)` appears inside the `try` that the
    handler belongs to. Deliberately structural, not a spelling check.
    """
    offenders: list[str] = []

    for path in _python_files():
        rel = path.relative_to(APP).as_posix()
        if rel in ALLOWED:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

        for node in ast.walk(tree):
            if not isinstance(node, ast.Try):
                continue
            catches_integrity = any(
                (isinstance(h.type, ast.Name) and h.type.id == "IntegrityError")
                or (
                    isinstance(h.type, ast.Tuple)
                    and any(
                        isinstance(e, ast.Name) and e.id == "IntegrityError" for e in h.type.elts
                    )
                )
                for h in node.handlers
            )
            if not catches_integrity:
                continue

            guarded = any(
                isinstance(inner, ast.With)
                and any(
                    isinstance(item.context_expr, ast.Call)
                    and isinstance(item.context_expr.func, ast.Name)
                    and item.context_expr.func.id == "guarded_write"
                    for item in inner.items
                )
                for stmt in node.body
                for inner in ast.walk(stmt)
            )
            if not guarded:
                offenders.append(f"{rel}:{node.lineno}")

    assert not offenders, (
        "these `try` blocks catch IntegrityError without wrapping their write in "
        "`guarded_write(session)`. PostgreSQL aborts the transaction on a "
        "constraint violation, so the handler runs over a dead transaction and the "
        "caller's earlier work is lost. "
        f"Offenders: {offenders}"
    )
