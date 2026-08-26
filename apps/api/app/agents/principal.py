"""The identity the agent tier runs as — and why it is a type, not a tuple.

🔴 I104: THE ORCHESTRATOR USED TO TRUST ITS ARGUMENTS.

Every entry point on `root_orchestrator` took `organization_id`, `user_id`
and `permissions` as ordinary keyword arguments. On the HTTP path they came
from a resolved `Principal` and were therefore true. On the path that has no
route — the one the whole tier exists for — nothing checked, and the module
docstring said so in prose:

    "EVERY ARGUMENT HERE COMES FROM A VERIFIED PRINCIPAL, NOT FROM THE
     REQUEST BODY."

That was a **comment asserting a rule the code did not have**, which is this
repository's single most-repeated defect. An in-process caller could pass
`permissions=frozenset({"test.confirm", "report.generate"})` and be believed,
or substitute a colleague's `user_id` and read what is waiting for them. The
conductor gate would then dutifully consult the forged set and let it through
— a gate is only as true as the permissions handed to it.

This module removes the ability to hand them over at all.

---------------------------------------------------------------------------
THREE MECHANISMS, AND ONLY THE FIRST IS TYPE-LEVEL
---------------------------------------------------------------------------

**1. You cannot construct one from loose values.** `AgentPrincipal` refuses
direct construction. `AgentPrincipal.of(principal)` is the only factory and it
demands a `Principal`, whose fields come from a signature-verified token plus
`core.principal_for_subject`. There is no signature anywhere in the tier that
accepts a bare `permissions` set any more, so claiming one is not something a
caller can do by accident or by reading the wrong example.

**2. PostgreSQL is asked whether the session really is this caller's.**
`bind(session)` reads `app.current_org` and `app.current_user_id` — the two
GUCs `app/core/db.py::set_context` sets and every RLS policy consults — and
refuses if they disagree with the principal. 🔴 THIS IS THE ONE MECHANISM A
PYTHON CALLER CANNOT TALK ITS WAY PAST. Substituting a colleague's user id
now means disagreeing with the database's own view of the transaction, not
merely passing a different argument. It also converts three docstrings that
*claimed* "the session must be the caller's own RLS-scoped session" into a
statement something actually checks.

**3. Forging a `Principal` is greppable and tested.**
`tests/test_agent_topology.py` fails the build if any module outside
`app/core/security.py` constructs one. So the remaining path — build a fake
`Principal`, wrap it — cannot be taken quietly.

⚠️ WHAT THIS IS NOT. It is not authentication, and it does not re-derive
permissions from the database. `get_principal` already did that query, and
repeating it per orchestrator call would double the cost of every request to
re-answer a question the request already answered correctly. What it removes
is the *casual* forgery the old signature invited — and mechanism 2 means the
identity half is checked against something outside Python regardless.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Final

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.security import Principal

__all__ = ["AgentPrincipal", "SessionIdentityError"]


class SessionIdentityError(PermissionError):
    """The session handed to the agent tier is not this principal's.

    A `PermissionError`, like `DepartmentDeniedError`, so a caller that
    already handles "not allowed" handles this correctly without importing
    anything new. It is deliberately NOT a subclass of that error: a denied
    department is an authorization answer, and this is a statement that the
    two halves of the call disagree about who is asking — a bug or an
    attempt, never a routine refusal.
    """


# The guard that makes `of()` the only door. A module-private object, so
# passing it requires importing a name that starts with an underscore from
# another module — visible in review and in a grep, rather than a keyword
# somebody could plausibly have typed by accident.
_FACTORY_GUARD: Final = object()


@dataclass(frozen=True, slots=True)
class AgentPrincipal:
    """A verified caller, as the agent tier is allowed to know them.

    Frozen because an identity that could be edited after the gate consulted
    it would make the gate advisory: a conductor checks `permissions`, and a
    mutable set could be widened by anything holding a reference between the
    check and the read.

    Carries no email, no display name and no `keycloak_sub`. The tier needs
    to know who is asking and what they may do; it has never needed to know
    how to contact them, and I81 is the standing reminder that an identifier
    nothing reads is an identifier that should not be handed out.
    """

    organization_id: uuid.UUID
    user_id: uuid.UUID
    roles: frozenset[str]
    permissions: frozenset[str]
    # Not an identity field. It exists so that the generated `__init__`
    # cannot be called successfully without a value only this module holds.
    # Excluded from repr so it never reaches a log line, and from equality
    # so two principals for the same person compare equal.
    _guard: Any = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self._guard is not _FACTORY_GUARD:
            raise TypeError(
                "AgentPrincipal cannot be constructed directly — use "
                "AgentPrincipal.of(principal). I104: the agent tier does not "
                "accept an identity assembled from loose values."
            )

    @classmethod
    def of(cls, principal: Principal) -> AgentPrincipal:
        """The only way to make one.

        Takes the whole `Principal` rather than its fields on purpose. A
        factory with four parameters would be the same hole with a longer
        name — the point is that the caller must already hold a verified
        identity, not that it must type more.
        """
        return cls(
            organization_id=principal.organization_id,
            user_id=principal.user_id,
            roles=frozenset(principal.roles),
            permissions=frozenset(principal.permissions),
            _guard=_FACTORY_GUARD,
        )

    def has(self, permission: str) -> bool:
        """Mirrors `Principal.has`, so the two read the same at call sites."""
        return permission in self.permissions

    def bind(self, session: Session) -> Session:
        """Refuse unless PostgreSQL agrees this session is this caller's.

        🔴 THE CHECK IS AGAINST THE DATABASE, NOT AGAINST AN ARGUMENT.

        `app.current_org` and `app.current_user_id` are set by
        `app/core/db.py::set_context` inside the transaction and are what
        every RLS policy actually reads. If they disagree with this
        principal, then the rows this session can see are not the rows this
        principal may see — which is the precise condition under which a
        conductor's gate would be answering for one person while the query
        answers for another.

        ⚠️ AN ABSENT GUC IS A FAILURE, NOT A PASS. `current_setting(..., true)`
        returns NULL rather than raising when the GUC was never set, and an
        unscoped session is exactly the case this must catch — it is the one
        `unscoped_session_scope()` opens, which sees across tenants. *A guard
        that passes when it cannot see is not a guard.*

        Returns the session so call sites can write
        `laboratory.list_batches(caller.bind(session), ...)` and cannot
        forget the check by forgetting a statement.
        """
        row = session.execute(
            text(
                "SELECT current_setting('app.current_org', true) AS org, "
                "       current_setting('app.current_user_id', true) AS usr"
            )
        ).one()
        return self._verify(session, org=row.org, usr=row.usr)

    def _verify(self, session: Session, *, org: Any, usr: Any) -> Session:
        if not org or not usr:
            raise SessionIdentityError(
                "the agent tier was handed a session with no RLS context "
                "(app.current_org / app.current_user_id unset). An unscoped "
                "session sees across tenants; it is never the caller's own."
            )
        if str(org) != str(self.organization_id):
            raise SessionIdentityError(
                "the session's tenant is not this principal's: the agent tier "
                "would gate on one organization and read another's rows"
            )
        if str(usr) != str(self.user_id):
            raise SessionIdentityError(
                "the session's user is not this principal's: this is the "
                "substitution I104 describes — asking on behalf of somebody "
                "whose authorization was never checked"
            )
        return session
