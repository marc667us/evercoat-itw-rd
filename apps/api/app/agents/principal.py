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

**1. No signature in the tier accepts a permission set.** `AgentPrincipal`
refuses direct construction, refuses `dataclasses.replace`, and
`AgentPrincipal.of(principal)` — the only factory — demands the exact
`Principal` type, whose fields come from a signature-verified token plus
`core.principal_for_subject`. Claiming a permission set is therefore not
something a caller can do by accident, by convenience, or by copying the
wrong example.

🔴 AND HERE IS WHAT IT IS *NOT*, STATED PLAINLY, BECAUSE THE FIRST VERSION OF
THIS PARAGRAPH OVERCLAIMED AND CODEX CALLED IT.

It said "you cannot construct one from loose values". You could: four
bypasses were enumerated and all four reproduced against this code —
duck-typed `of()`, `dataclasses.replace` replaying the guard, `object.__new__`
with `object.__setattr__`, and importing the private sentinel. Three are
closed. **`object.__new__` cannot be closed in Python and is not claimed to
be.**

So this is a MISUSE BARRIER, not an in-process security boundary. Code running
inside this process that wants to forge authorization can do so — it could
equally call `session.execute` and skip the agent tier entirely, which no type
in Python prevents either. What the type buys is that forging is now a
deliberate, greppable, unmistakable act rather than the path of least
resistance that a four-argument signature made it.

✅ **I105 IS CLOSED, AND IT WAS THE REAL GAP.** `bind()` validated identity and
not authorization, so a forged principal carrying the real session identity
passed it while claiming anything. `authorize()` below now REPLACES both
`roles` and `permissions` with what
`core.authorization_for_current_session()` returns for the session's own GUC
(migration 048). The gate and the rows are derived from the same two GUCs and
can no longer disagree about who is asking.

⚠️ That function is NOT the design ADR-029 rejected for I82. That rejection
was about a definer that WRITES — the write fires ADR-028's address guards,
which inside a definer run as the table owner and reopen I83's oracle. This
one is `STABLE` and takes ZERO ARGUMENTS, so it has neither the write that
starts that chain nor the parameter that makes a lookup an oracle.

**2. PostgreSQL is asked whether the session really is this caller's.**
`bind(session)` reads `app.current_org` and `app.current_user_id` — the two
GUCs `app/core/db.py::set_context` sets and every RLS policy consults — and
refuses if they disagree with the principal. 🔴 THIS IS THE ONE MECHANISM A
PYTHON CALLER CANNOT TALK ITS WAY PAST. Substituting a colleague's user id
now means disagreeing with the database's own view of the transaction, not
merely passing a different argument. It also converts three docstrings that
*claimed* "the session must be the caller's own RLS-scoped session" into a
statement something actually checks.

**3. The remaining path is loud.** Forging now means constructing a real
`Principal` — which has a public constructor at `app/core/security.py` — or
reaching for `object.__new__`. Both are unmistakable in a diff and in a grep,
which is the whole of what mechanism 1 claims.

`tests/test_conductor_boundary.py` pins the closed bypasses AND records the
open one, so the limits of this type are measured rather than assumed. A test
suite that only demonstrated the successes would leave the next reader with
exactly the overclaim this docstring had.
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


# 🔴 A ONE-SHOT NONCE, NOT A LONG-LIVED SENTINEL — AND CODEX IS WHY.
#
# The first version held a module-level `_FACTORY_GUARD = object()` and
# checked identity against it. Codex enumerated four bypasses and ALL FOUR
# were reproduced against the real code before this was changed:
#
#   1. `AgentPrincipal.of(SimpleNamespace(permissions={"test.confirm"}, ...))`
#      — `of()` duck-typed its argument and never checked it was a Principal.
#   2. `dataclasses.replace(real_caller, permissions=forged)` — `replace`
#      re-invokes `__init__` with the EXISTING field values, so it carried the
#      valid guard straight into the forgery. This one I had not considered.
#   3. `object.__new__` + `object.__setattr__` — skips `__init__` entirely.
#   4. `from app.agents.principal import _FACTORY_GUARD` — an underscore is a
#      convention, not an access control, which the old comment admitted.
#
# A nonce that is CONSUMED on use closes 1, 2 and 4: each mint is unique and
# valid exactly once, so a replayed guard — which is what `replace` does, and
# what an imported sentinel would be — no longer verifies. `of()` now also
# demands the exact `Principal` type.
#
# ⚠️ 3 REMAINS OPEN AND CANNOT BE CLOSED IN PYTHON. Anything that can call
# `object.__setattr__` can build any object it likes; it could equally call
# `session.execute` directly and skip this tier altogether. See the module
# docstring for what this type therefore does and does not claim.
_MINTED: Final[set[int]] = set()


def _mint() -> object:
    """A token valid for exactly one construction."""
    token = object()
    _MINTED.add(id(token))
    return token


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
    # 🔴 WHETHER THE DATABASE HAS AGREED TO `permissions` (I105).
    #
    # False from `of()`: those permissions came from the request's own
    # `Principal`, which is true for a legitimate caller and is still only
    # Python. True from `authorize()`, which replaces the set with one read
    # from `core.permissions_for_current_session()`.
    #
    # `app/agents/boundary.py::require` REFUSES an unverified principal. That
    # is what stops a conductor written next month from gating on a claimed
    # set by simply forgetting a line — the failure is loud instead of silent,
    # which is the difference between this and the docstring I104 replaced.
    #
    # ⚠️ A MISUSE DETECTOR, NOT AN UNFORGEABLE PROPERTY. It is an ordinary
    # boolean, and `object.__setattr__` can set it exactly as it can set
    # `permissions` — see the module docstring's open bypass. The boundary is
    # that every conductor calls `authorize()`, asserted from the call graph.
    verified: bool = False
    # Not an identity field. It exists so that the generated `__init__`
    # cannot be called successfully without a value only this module holds.
    # Excluded from repr so it never reaches a log line, and from equality
    # so two principals for the same person compare equal.
    _guard: Any = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        # `discard` after a membership test, so the token is spent whether or
        # not it was valid. A guard that could be replayed is not a guard —
        # which is exactly what `dataclasses.replace` was doing with the old
        # long-lived sentinel.
        if id(self._guard) not in _MINTED:
            raise TypeError(
                "AgentPrincipal cannot be constructed directly, replaced, or "
                "copied — use AgentPrincipal.of(principal). I104: the agent "
                "tier does not accept an identity assembled from loose values."
            )
        _MINTED.discard(id(self._guard))

    @classmethod
    def of(cls, principal: Principal) -> AgentPrincipal:
        """The only way to make one.

        Takes the whole `Principal` rather than its fields on purpose. A
        factory with four parameters would be the same hole with a longer
        name — the point is that the caller must already hold a verified
        identity, not that it must type more.

        🔴 AND IT CHECKS THE EXACT TYPE, BECAUSE IT USED TO DUCK-TYPE.

        This read `principal.permissions` and friends off whatever it was
        given, so `of(SimpleNamespace(permissions={"test.confirm"}, ...))`
        produced a fully valid `AgentPrincipal` claiming anything at all —
        reproduced against this code, not theorised. Raised by Codex.

        `type(...) is not Principal` rather than `isinstance`: a subclass
        could override `permissions` as a property returning whatever it
        liked, and this is the one place where "behaves like a Principal" is
        not good enough.
        """
        if type(principal) is not Principal:
            raise TypeError(
                f"AgentPrincipal.of requires a verified Principal, not "
                f"{type(principal).__name__}. An object that merely has the "
                "right attributes is an identity nobody checked."
            )
        return cls(
            organization_id=principal.organization_id,
            user_id=principal.user_id,
            roles=frozenset(principal.roles),
            permissions=frozenset(principal.permissions),
            verified=False,
            _guard=_mint(),
        )

    def has(self, permission: str) -> bool:
        """Mirrors `Principal.has`, so the two read the same at call sites."""
        return permission in self.permissions

    def authorize(self, session: Session) -> AgentPrincipal:
        """Refuse unless PostgreSQL agrees, and take the permissions FROM it.

        🔴 THIS IS I105, AND IT IS THE HALF I104 LEFT OPEN.

        I104 made the identity checkable: the two GUCs `app/core/db.py` sets
        and every RLS policy reads must agree with this principal, so
        substituting a colleague means disagreeing with the database rather
        than passing a different argument.

        It did not check PERMISSIONS. Codex said so exactly — *"a forged
        principal using the real session identity therefore passes bind()
        while claiming arbitrary authorization"* — and the conductor gate then
        consulted the forged set. So this no longer VALIDATES the set it was
        given; it REPLACES it with one read from
        `core.permissions_for_current_session()`, keyed on the same GUC.

        ⚠️ DERIVE, NOT COMPARE. Comparing the claimed set against the database
        would also refuse a forgery, and it would additionally refuse a
        LEGITIMATE caller whose membership changed mid-request — reading it as
        an attack. Deriving makes revocation take effect instead, which is
        what `get_principal` already says it wants: *"A JWT is a statement
        about identity; it is not a current statement about authorization."*
        The same is true of a permission set computed a few milliseconds ago.

        ⚠️ AN ABSENT GUC IS A FAILURE, NOT A PASS. `current_setting(..., true)`
        returns NULL rather than raising when the GUC was never set, and an
        unscoped session — the one `unscoped_session_scope()` opens, which
        sees across tenants — is exactly the case this must catch. *A guard
        that passes when it cannot see is not a guard.* The SQL function fails
        closed on the same condition independently.

        Returns a NEW principal marked `verified`, because
        `app/agents/boundary.py::require` refuses one that is not. A conductor
        that forgets this line cannot silently fall back to the claimed set —
        it raises.

        ⚠️ ONE EXTRA ROUND TRIP PER AGENT-TIER ENTRY, on the connection the
        caller already holds. That is the price of the gate and the rows
        answering for the same person, and it is worth it.
        """
        row = session.execute(
            text(
                "SELECT current_setting('app.current_org', true)     AS org, "
                "       current_setting('app.current_user_id', true) AS usr, "
                "       a.roles                                      AS roles, "
                "       a.permissions                                AS perms "
                "FROM core.authorization_for_current_session() a"
            )
        ).one()
        self._check_identity(org=row.org, usr=row.usr)

        return AgentPrincipal(
            organization_id=self.organization_id,
            user_id=self.user_id,
            # 🔴 ROLES ARE DERIVED TOO, AND THE FIRST VERSION OF THIS COPIED
            # `self.roles` STRAIGHT THROUGH. Raised by Codex, and it is not a
            # tidiness point: `app/domains/tasks/service.py` matches unclaimed
            # work with `t.assigned_role = ANY(:roles)`, and `msd_conductor`
            # feeds the caller's role codes into it. A forged principal with
            # the real session identity and invented roles would have made the
            # assistant surface tasks addressed to roles that person does not
            # hold — retrieval filtered by caller-supplied authorization state,
            # which is exactly the §7 defect I105 is about.
            roles=frozenset(row.roles or ()),
            # 🔴 THE DATABASE'S ANSWER, NOT THE CALLER'S. Both are TEXT[] and
            # psycopg returns them as lists; `None` would mean the function
            # returned NULL, which its COALESCE prevents — treated as empty
            # rather than trusted, because an authorization set that is
            # "unknown" must grant nothing.
            permissions=frozenset(row.perms or ()),
            verified=True,
            _guard=_mint(),
        )

    def _check_identity(self, *, org: Any, usr: Any) -> None:
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
