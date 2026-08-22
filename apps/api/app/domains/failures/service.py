"""Failure investigation, and the link from a failure to the revision it
caused.

🔴 A HYPOTHESIS IS NOT A ROOT CAUSE.

`CLAUDE.md` §7 draws the line and this module keeps it: `accept_root_cause`
is the ONLY path from `proposed`/`under_review` to `accepted`, it requires
`failure.accept_root_cause` (held by the Lead alone), and it writes the
accepting human's id into the row. There is no system actor, and no code
path here that can accept a hypothesis on anybody's behalf — which
matters because MSD will propose hypotheses in Slice 7 and must never be
able to conclude one.

**Evidence can contradict.** `link_evidence` takes a relationship, and
`contradicts` is as ordinary as `supports`. An investigation that could
only record confirming evidence is one that cannot rule anything out —
which is precisely how a plausible first hypothesis becomes an accepted
root cause.

**Why a formula version exists.** `record_driver` writes
`formula_version_drivers`, so §29's question — "why was F008 created?" —
has an answer, and can have several: a revision may answer a failure AND
chase a requirement at once.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.audit import AuditEvent, write_audit
from app.core.db import guarded_write

# Cross-domain, and it cannot cycle: `messaging` imports only `app.core.*`.
from app.core.notifications import notify
from app.core.tenancy import require_active_member

__all__ = [
    "ActionInput",
    "DriverInput",
    "EvidenceInput",
    "FailureError",
    "FailureInput",
    "FailureNotFoundError",
    "FailureStateError",
    "HypothesisInput",
    "accept_root_cause",
    "close_failure",
    "get_failure",
    "link_evidence",
    "list_failures",
    "open_failure",
    "open_failure_for_failed_test",
    "raise_action",
    "record_driver",
    "record_evidence",
    "record_hypothesis",
    "reject_hypothesis",
]


class FailureError(RuntimeError):
    """Base for refusals that are business rules, not bugs."""


class FailureNotFoundError(FailureError):
    pass


class FailureStateError(FailureError):
    pass


@dataclass(frozen=True, slots=True)
class FailureInput:
    failure_code: str
    title: str
    description: str | None = None
    severity: str = "major"
    test_id: uuid.UUID | None = None
    formula_version_id: uuid.UUID | None = None
    batch_id: uuid.UUID | None = None


@dataclass(frozen=True, slots=True)
class HypothesisInput:
    possible_cause: str
    mechanism: str | None = None
    confidence: str = "medium"
    source: str | None = None
    # `human` unless a caller says otherwise, and MSD says otherwise.
    # Defaulting the other way would let an unlabelled AI suggestion pass
    # as somebody's judgement.
    origin: str = "human"


@dataclass(frozen=True, slots=True)
class EvidenceInput:
    evidence_type: str
    summary: str
    detail: str | None = None
    referenced_entity_type: str | None = None
    referenced_entity_id: uuid.UUID | None = None
    source_reference: str | None = None
    origin: str = "human"


@dataclass(frozen=True, slots=True)
class ActionInput:
    action_type: str
    description: str
    assigned_to: uuid.UUID | None = None
    due_date: Any = None


@dataclass(frozen=True, slots=True)
class DriverInput:
    driver_type: str
    reason: str
    failure_id: uuid.UUID | None = None
    requirement_id: uuid.UUID | None = None


# ---------------------------------------------------------------------------
# Opening
# ---------------------------------------------------------------------------


def open_failure(
    session: Session,
    *,
    project_id: uuid.UUID,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    spec: FailureInput,
) -> dict[str, Any]:
    """Open an investigation."""
    require_active_member(
        session, user_id=actor_id, organization_id=organization_id, role_description="author"
    )

    # `guarded_write` (a SAVEPOINT) rather than a bare try: a duplicate failure
    # code must refuse THIS insert, not destroy the caller's transaction --
    # `complete_execution` calls this to satisfy §10 and has already written a
    # completion and an audit event by the time it gets here. Full reasoning on
    # the helper (TODO I30).
    try:
        with guarded_write(session):
            row = (
                session.execute(
                    text(
                        """
                        INSERT INTO quality.failures
                            (organization_id, project_id, failure_code, title, description,
                             severity, test_id, formula_version_id, batch_id, opened_by)
                        SELECT :org, p.id, :code, :title, :description, :severity,
                               :test, :version, :batch, :actor
                        FROM projects.projects p
                        WHERE p.id = :pid AND p.organization_id = :org
                          AND (p.confidentiality = 'normal' OR core.is_project_member(p.id))
                        RETURNING id, failure_code, status
                        """
                    ),
                    {
                        "org": organization_id,
                        "pid": project_id,
                        "code": spec.failure_code,
                        "title": spec.title,
                        "description": spec.description,
                        "severity": spec.severity,
                        "test": spec.test_id,
                        "version": spec.formula_version_id,
                        "batch": spec.batch_id,
                        "actor": actor_id,
                    },
                )
                .mappings()
                .one_or_none()
            )
    except IntegrityError as exc:
        # No `session.rollback()`: the SAVEPOINT above has already been rolled
        # back by leaving the `with` block, and the caller's transaction is
        # intact. Rolling back here would destroy it.
        if "failures_org_code_key" in str(exc.orig):
            raise FailureError(
                f"failure code '{spec.failure_code}' is already used in this organization"
            ) from exc
        raise FailureError(str(exc.orig)) from exc

    if row is None:
        # Same predicate the RLS USING clause applies, for the reason
        # `create_formula` uses it: WITH CHECK is organization-only, so an
        # INSERT naming a restricted project would otherwise succeed and
        # merely become invisible to its author.
        raise FailureNotFoundError("no such project in this organization")

    write_audit(
        session,
        AuditEvent(
            action="failure.opened",
            entity_type="failure",
            entity_id=str(row["id"]),
            organization_id=organization_id,
            user_id=actor_id,
            new_state={"failure_code": spec.failure_code, "severity": spec.severity},
            reason=spec.title,
        ),
    )

    # 🔴 I8 -- AN INVESTIGATION NOBODY IS TOLD ABOUT INVESTIGATES NOTHING.
    #
    # This matters more than the task case, because §10 opens investigations
    # AUTOMATICALLY when a confirmation test fails. Without this, the system
    # silently creates a failure investigation that nobody is informed of and
    # nobody owns -- the most consequential record in the product, appearing
    # in a queue no one is prompted to look at.
    #
    # THE PROJECT LEAD, and only the lead. §11 sidebar counts are actionable
    # items, so fanning this out to every project member would put one
    # investigation into everybody's action count and make the badge useless.
    # The lead is the one role §9 makes responsible for the project's gates.
    #
    # 🔴 AND THE LEAD IS THE SAFE RECIPIENT. §7: a notification must not
    # disclose what the recipient cannot see. `projects.projects.lead_user_id`
    # is what migration 006 already uses to grant read access to a RESTRICTED
    # project, so a lead can by construction read the failure this names --
    # which is not true of an arbitrary organization member.
    lead = session.execute(
        text(
            "SELECT lead_user_id FROM projects.projects WHERE id = :pid AND organization_id = :org"
        ),
        {"pid": project_id, "org": organization_id},
    ).scalar_one_or_none()

    if lead is not None and lead != actor_id:
        notify(
            session,
            organization_id=organization_id,
            recipient_id=lead,
            notification_type="failure_opened",
            title=f"{spec.failure_code}: {spec.title}",
            body=spec.description,
            entity_type="failure",
            entity_id=row["id"],
            is_actionable=True,
        )

    return dict(row)


def _free_failure_code(session: Session, *, organization_id: uuid.UUID, base: str) -> str:
    """Return `base`, or the first free `base-2`, `base-3`, ... suffix.

    🔴 WHY THIS EXISTS. Raised by the Supervisor: the automatic investigation
    generates `FI-<test_number>`, and `test_number` is caller-supplied. If
    anything already holds that code — a human investigation for a DIFFERENT
    test, say — `failures_org_code_key` refuses the INSERT, and because §10's
    open is deliberately not swallowed, **that test could never be completed,
    permanently.** `failure_code` has no rename path, so there was no recovery
    that did not involve a database edit.

    A suffix is preferable to widening the generated code for everyone: the
    common case stays the readable `FI-T-1234`, and the collision case stays
    possible instead of fatal.

    Bounded at ten attempts. An eleventh collision means something is wrong
    that a loop should not paper over, and the caller then gets the ordinary
    duplicate-code refusal — now a 409 rather than a 500.

    Not a substitute for the unique index: this closes the RACE-FREE case
    inside one transaction. Two concurrent transactions can still pick the
    same suffix, and the constraint is what refuses the loser. That refusal is
    correct and recoverable — a retry finds the next free suffix.
    """
    for attempt in range(1, 11):
        candidate = base if attempt == 1 else f"{base}-{attempt}"
        taken = session.execute(
            text(
                "SELECT 1 FROM quality.failures "
                "WHERE organization_id = :org AND failure_code = :code"
            ),
            {"org": organization_id, "code": candidate},
        ).first()
        if taken is None:
            return candidate
    return base


def open_failure_for_failed_test(
    session: Session,
    *,
    test_id: uuid.UUID,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
) -> dict[str, Any] | None:
    """§10: "A RED confirmation result automatically opens or links a
    Failure Investigation."

    **Automatically, and idempotently.** Returns the existing
    investigation if one already points at this test rather than opening
    a second — X11 in the plan's reconciliation register settles that a
    RED result "opens OR LINKS", and two investigations of one failure is
    two half-answers.

    **Only for a CONFIRMATION.** A failed SCREENING test is information,
    not a failure of the product: screening is preliminary authority and
    is never confirmation evidence, so opening an investigation for one
    would fill the queue with results nobody intended as verdicts. The
    plan's X11 says the same — there is no single global RED rule.
    """
    test = (
        session.execute(
            text(
                """
                SELECT t.id, t.project_id, t.test_number, t.calculated_result,
                       t.validity_status, t.test_purpose, t.sample_id,
                       b.id AS batch_id, b.formula_version_id
                FROM testing.tests t
                JOIN laboratory.samples s
                  ON s.id = t.sample_id AND s.organization_id = t.organization_id
                JOIN laboratory.batches b
                  ON b.id = s.batch_id AND b.organization_id = s.organization_id
                WHERE t.id = :tid AND t.organization_id = :org
                """
            ),
            {"tid": test_id, "org": organization_id},
        )
        .mappings()
        .one_or_none()
    )
    if test is None:
        raise FailureNotFoundError("no such test in this organization")

    if test["test_purpose"] != "confirmation":
        return None
    if test["calculated_result"] != "fail":
        return None

    # 🔴 `.first()`, NOT `.one_or_none()`. Raised by the Supervisor.
    #
    # Migration 029 adds a partial UNIQUE index on `(organization_id, test_id)`
    # so at most one investigation can name a test — which is what "opens OR
    # LINKS" has always claimed. But this code must not DEPEND on that index
    # being present: against a database migrated only to 028, two rows are
    # legal, and `.one_or_none()` would raise `MultipleResultsFound` — which is
    # not caught anywhere, so the test could never be completed AGAIN. A
    # permanent lockout on a safety-critical path, reachable by two engineers
    # legitimately opening an investigation for the same test.
    #
    # Ordered so the answer is stable rather than whichever row the heap
    # returns first.
    existing = (
        session.execute(
            text(
                """
                SELECT id, failure_code, status FROM quality.failures
                WHERE test_id = :tid AND organization_id = :org
                ORDER BY opened_at, id
                LIMIT 1
                """
            ),
            {"tid": test_id, "org": organization_id},
        )
        .mappings()
        .first()
    )
    if existing is not None:
        return dict(existing)

    return open_failure(
        session,
        project_id=test["project_id"],
        organization_id=organization_id,
        actor_id=actor_id,
        spec=FailureInput(
            failure_code=_free_failure_code(
                session, organization_id=organization_id, base=f"FI-{test['test_number']}"
            ),
            title=f"Confirmation test {test['test_number']} failed its requirement",
            description=(
                "Opened automatically because a confirmation test returned a failing "
                "result (CLAUDE.md §10)."
            ),
            severity="major",
            test_id=test_id,
            formula_version_id=test["formula_version_id"],
            batch_id=test["batch_id"],
        ),
    )


# ---------------------------------------------------------------------------
# Hypotheses and evidence
# ---------------------------------------------------------------------------


def record_hypothesis(
    session: Session,
    *,
    failure_id: uuid.UUID,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    spec: HypothesisInput,
) -> uuid.UUID:
    """Propose a possible cause.

    Always `proposed`. There is no argument that could create one already
    accepted, because accepting is a separate act requiring a separate
    permission the proposer may not hold — and `failure.investigate` (the
    Chemist and Engineer) is deliberately not `failure.accept_root_cause`
    (the Lead).
    """
    failure = _failure_row(session, failure_id=failure_id, organization_id=organization_id)
    if failure["status"] in {"closed", "cancelled"}:
        raise FailureStateError(
            f"investigation {failure['failure_code']} is {failure['status']}; reopen it "
            "before adding to it"
        )

    hypothesis_id: uuid.UUID = session.execute(
        text(
            """
            INSERT INTO quality.failure_hypotheses
                (organization_id, project_id, failure_id, possible_cause, mechanism,
                 confidence, source, origin, proposed_by)
            VALUES (:org, :pid, :fid, :cause, :mechanism, :confidence, :source,
                    :origin, :actor)
            RETURNING id
            """
        ),
        {
            "org": organization_id,
            "pid": failure["project_id"],
            "fid": failure_id,
            "cause": spec.possible_cause,
            "mechanism": spec.mechanism,
            "confidence": spec.confidence,
            "source": spec.source,
            "origin": spec.origin,
            "actor": actor_id,
        },
    ).scalar_one()

    # Opening a hypothesis moves the investigation forward, but only from
    # `open`: a failure already at `root_cause_accepted` must not be
    # dragged backwards by somebody adding a late idea.
    session.execute(
        text(
            """
            UPDATE quality.failures SET status = 'investigating', updated_at = now()
            WHERE id = :fid AND organization_id = :org AND status = 'open'
            """
        ),
        {"fid": failure_id, "org": organization_id},
    )

    write_audit(
        session,
        AuditEvent(
            action="failure.hypothesis_proposed",
            entity_type="failure",
            entity_id=str(failure_id),
            organization_id=organization_id,
            user_id=actor_id,
            new_state={"origin": spec.origin, "confidence": spec.confidence},
            reason=spec.possible_cause[:200],
        ),
    )
    return hypothesis_id


def record_evidence(
    session: Session,
    *,
    failure_id: uuid.UUID,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    spec: EvidenceInput,
) -> uuid.UUID:
    """Record an observation. Not attached to a hypothesis yet — §27 makes
    that many-to-many, because one observation can bear on several."""
    failure = _failure_row(session, failure_id=failure_id, organization_id=organization_id)

    evidence_id: uuid.UUID = session.execute(
        text(
            """
            INSERT INTO quality.failure_evidence
                (organization_id, project_id, failure_id, evidence_type, summary,
                 detail, referenced_entity_type, referenced_entity_id,
                 source_reference, origin, recorded_by)
            VALUES (:org, :pid, :fid, :etype, :summary, :detail, :rtype, :rid,
                    :reference, :origin, :actor)
            RETURNING id
            """
        ),
        {
            "org": organization_id,
            "pid": failure["project_id"],
            "fid": failure_id,
            "etype": spec.evidence_type,
            "summary": spec.summary,
            "detail": spec.detail,
            "rtype": spec.referenced_entity_type,
            "rid": spec.referenced_entity_id,
            "reference": spec.source_reference,
            "origin": spec.origin,
            "actor": actor_id,
        },
    ).scalar_one()

    write_audit(
        session,
        AuditEvent(
            action="failure.evidence_recorded",
            entity_type="failure",
            entity_id=str(failure_id),
            organization_id=organization_id,
            user_id=actor_id,
            new_state={"evidence_type": spec.evidence_type, "origin": spec.origin},
            reason=spec.summary[:200],
        ),
    )
    return evidence_id


def link_evidence(
    session: Session,
    *,
    hypothesis_id: uuid.UUID,
    evidence_id: uuid.UUID,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    relationship: str = "supports",
    note: str | None = None,
) -> uuid.UUID:
    """Attach an observation to a hypothesis, saying HOW it bears on it.

    `contradicts` is as ordinary a value as `supports`. An investigation
    that can only record confirming evidence cannot rule anything out,
    and that is the mechanism by which a plausible first idea becomes an
    accepted root cause.
    """
    if relationship not in {"supports", "contradicts", "inconclusive"}:
        raise FailureError(f"'{relationship}' is not a relationship")

    try:
        with guarded_write(session):
            link_id: uuid.UUID = session.execute(
                text(
                    """
                    INSERT INTO quality.hypothesis_evidence
                        (organization_id, hypothesis_id, evidence_id, relationship,
                         note, linked_by)
                    VALUES (:org, :hid, :eid, :rel, :note, :actor)
                    RETURNING id
                    """
                ),
                {
                    "org": organization_id,
                    "hid": hypothesis_id,
                    "eid": evidence_id,
                    "rel": relationship,
                    "note": note,
                    "actor": actor_id,
                },
            ).scalar_one()
    except IntegrityError as exc:
        detail = str(exc.orig)
        if "hypothesis_evidence_pair_key" in detail:
            raise FailureError("this evidence is already linked to that hypothesis") from exc
        raise FailureNotFoundError("no such hypothesis or evidence here") from exc

    return link_id


def accept_root_cause(
    session: Session,
    *,
    failure_id: uuid.UUID,
    hypothesis_id: uuid.UUID,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    rationale: str,
) -> dict[str, Any]:
    """Promote ONE hypothesis to the accepted root cause.

    🔴 THE ONLY PATH TO `accepted`, AND IT NAMES A HUMAN.

    §7: "only a human moves it to `accepted`". The route requires
    `failure.accept_root_cause`, which the Lead alone holds — not the
    Chemist or Engineer who investigate, and deliberately not the
    administrator.

    At most one accepted hypothesis per failure, enforced by a partial
    unique index. The refusal is translated here into a message that says
    which one already holds the position, because "duplicate key" tells a
    Lead nothing about what to do.
    """
    if not rationale:
        raise FailureError(
            "accepting a root cause is a technical decision; it must state the "
            "reasoning that justified it"
        )

    try:
        with guarded_write(session):
            row = (
                session.execute(
                    text(
                        """
                        UPDATE quality.failure_hypotheses
                        SET status = 'accepted',
                            accepted_by = :actor,
                            accepted_at = now(),
                            updated_at = now()
                        WHERE id = :hid
                          AND failure_id = :fid
                          AND organization_id = :org
                          AND status IN ('proposed','under_review')
                        RETURNING id, possible_cause, origin
                        """
                    ),
                    {
                        "hid": hypothesis_id,
                        "fid": failure_id,
                        "org": organization_id,
                        "actor": actor_id,
                    },
                )
                .mappings()
                .one_or_none()
            )
    except IntegrityError as exc:
        if "one_accepted" in str(exc.orig):
            existing = session.execute(
                text(
                    """
                    SELECT possible_cause FROM quality.failure_hypotheses
                    WHERE failure_id = :fid AND status = 'accepted'
                    """
                ),
                {"fid": failure_id},
            ).scalar_one_or_none()
            raise FailureStateError(
                "this investigation already has an accepted root cause "
                f"({existing!r}). Two accepted causes is not a stronger conclusion; "
                "reject the standing one first if it is wrong."
            ) from exc
        raise FailureError(str(exc.orig)) from exc

    if row is None:
        raise FailureStateError(
            "that hypothesis is not open for acceptance — it may already be accepted or rejected"
        )

    session.execute(
        text(
            """
            UPDATE quality.failures
            SET status = 'root_cause_accepted', updated_at = now()
            WHERE id = :fid AND organization_id = :org
              AND status IN ('open','investigating')
            """
        ),
        {"fid": failure_id, "org": organization_id},
    )

    write_audit(
        session,
        AuditEvent(
            action="failure.root_cause_accepted",
            entity_type="failure",
            entity_id=str(failure_id),
            organization_id=organization_id,
            user_id=actor_id,
            new_state={
                "hypothesis_id": str(hypothesis_id),
                # Recorded because it matters that a human accepted an AI
                # suggestion, as opposed to accepting their own.
                "hypothesis_origin": row["origin"],
            },
            reason=rationale,
        ),
    )
    return dict(row)


def reject_hypothesis(
    session: Session,
    *,
    hypothesis_id: uuid.UUID,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    reason: str,
) -> dict[str, Any]:
    """Rule a hypothesis out, with the reason.

    The next investigator needs to know what was already considered and
    on what basis; a hypothesis that simply disappears invites the same
    idea again in six months.
    """
    if not reason:
        raise FailureError("a rejected hypothesis must say why it was ruled out")

    row = (
        session.execute(
            text(
                """
                UPDATE quality.failure_hypotheses
                SET status = 'rejected', rejection_reason = :reason, updated_at = now()
                WHERE id = :hid AND organization_id = :org
                  AND status IN ('proposed','under_review')
                RETURNING id, possible_cause, failure_id
                """
            ),
            {"hid": hypothesis_id, "org": organization_id, "reason": reason},
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise FailureStateError(
            "that hypothesis is not open — an accepted root cause cannot be silently "
            "rejected; reopen the investigation instead"
        )

    write_audit(
        session,
        AuditEvent(
            action="failure.hypothesis_rejected",
            entity_type="failure",
            entity_id=str(row["failure_id"]),
            organization_id=organization_id,
            user_id=actor_id,
            new_state={"hypothesis_id": str(hypothesis_id)},
            reason=reason,
        ),
    )
    return dict(row)


# ---------------------------------------------------------------------------
# Actions, closure, and the driver bridge
# ---------------------------------------------------------------------------


def raise_action(
    session: Session,
    *,
    failure_id: uuid.UUID,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    spec: ActionInput,
) -> uuid.UUID:
    """Raise a corrective action. §28's five types, plus `other`."""
    failure = _failure_row(session, failure_id=failure_id, organization_id=organization_id)
    if spec.assigned_to is not None:
        require_active_member(
            session,
            user_id=spec.assigned_to,
            organization_id=organization_id,
            role_description="assignee",
        )

    action_id: uuid.UUID = session.execute(
        text(
            """
            INSERT INTO quality.failure_actions
                (organization_id, project_id, failure_id, action_type, description,
                 assigned_to, due_date, raised_by)
            VALUES (:org, :pid, :fid, :atype, :description, :assignee,
                    CAST(:due AS DATE), :actor)
            RETURNING id
            """
        ),
        {
            "org": organization_id,
            "pid": failure["project_id"],
            "fid": failure_id,
            "atype": spec.action_type,
            "description": spec.description,
            "assignee": spec.assigned_to,
            "due": spec.due_date,
            "actor": actor_id,
        },
    ).scalar_one()

    write_audit(
        session,
        AuditEvent(
            action="failure.action_raised",
            entity_type="failure",
            entity_id=str(failure_id),
            organization_id=organization_id,
            user_id=actor_id,
            new_state={"action_type": spec.action_type},
            reason=spec.description[:200],
        ),
    )
    return action_id


def record_driver(
    session: Session,
    *,
    formula_version_id: uuid.UUID,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    spec: DriverInput,
) -> uuid.UUID:
    """Record WHY a formula version exists. §29.

    Several drivers per version are expected, not exceptional: a revision
    may answer a failure and chase a requirement at once, and a single
    column would force somebody to pick one and lose the rest.
    """
    version = (
        session.execute(
            text(
                """
                SELECT project_id, version_code FROM formulations.formula_versions
                WHERE id = :vid AND organization_id = :org
                """
            ),
            {"vid": formula_version_id, "org": organization_id},
        )
        .mappings()
        .one_or_none()
    )
    if version is None:
        raise FailureNotFoundError("no such formula version in this organization")

    # `guarded_write` for the same reason as `open_failure` above:
    # `revise_version` calls this to satisfy §2's "a new formula revision must
    # show exactly which failure or improvement objective caused it", so a
    # constraint violation here must refuse the driver, not roll back the
    # version that was just cloned. Full reasoning on the helper (TODO I30).
    try:
        with guarded_write(session):
            driver_id: uuid.UUID = session.execute(
                text(
                    """
                    INSERT INTO formulations.formula_version_drivers
                        (organization_id, project_id, formula_version_id, driver_type,
                         failure_id, requirement_id, reason, recorded_by)
                    VALUES (:org, :pid, :vid, :dtype, :fid, :rid, :reason, :actor)
                    RETURNING id
                    """
                ),
                {
                    "org": organization_id,
                    "pid": version["project_id"],
                    "vid": formula_version_id,
                    "dtype": spec.driver_type,
                    "fid": spec.failure_id,
                    "rid": spec.requirement_id,
                    "reason": spec.reason,
                    "actor": actor_id,
                },
            ).scalar_one()
    except IntegrityError as exc:
        detail = str(exc.orig)
        if "failure_is_present" in detail or "requirement_is_present" in detail:
            raise FailureError(
                f"a driver of type '{spec.driver_type}' must name the {spec.driver_type} "
                "it refers to; otherwise it answers 'why does this version exist?' with "
                "a category and nothing else"
            ) from exc
        if "drivers_unique" in detail:
            raise FailureError("that driver is already recorded for this version") from exc
        raise FailureError(detail) from exc

    write_audit(
        session,
        AuditEvent(
            action="formula_version.driver_recorded",
            entity_type="formula_version",
            entity_id=str(formula_version_id),
            organization_id=organization_id,
            user_id=actor_id,
            new_state={"driver_type": spec.driver_type},
            reason=spec.reason,
        ),
    )
    return driver_id


def close_failure(
    session: Session,
    *,
    failure_id: uuid.UUID,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    summary: str,
) -> dict[str, Any]:
    """Close the investigation, with its conclusion.

    Refused while any corrective action is still outstanding. An
    investigation closed over unfinished actions is a conclusion nobody
    acted on — and the actions would then sit in a closed record where
    no queue would surface them again.
    """
    if not summary:
        raise FailureError(
            "a closed investigation must state its conclusion; the next person to hit "
            "this failure reads exactly that field"
        )

    outstanding = session.execute(
        text(
            """
            SELECT count(*) FROM quality.failure_actions
            WHERE failure_id = :fid AND organization_id = :org
              AND status IN ('proposed','approved','in_progress')
            """
        ),
        {"fid": failure_id, "org": organization_id},
    ).scalar_one()
    if outstanding:
        raise FailureStateError(
            f"{outstanding} corrective action(s) are still outstanding; closing now "
            "would leave them where no queue will surface them again"
        )

    row = (
        session.execute(
            text(
                """
                UPDATE quality.failures
                SET status = 'closed', closed_by = :actor, closed_at = now(),
                    closure_summary = :summary, updated_at = now()
                WHERE id = :fid AND organization_id = :org
                  AND status NOT IN ('closed','cancelled')
                RETURNING id, failure_code, status
                """
            ),
            {"fid": failure_id, "org": organization_id, "actor": actor_id, "summary": summary},
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        current = _failure_row(session, failure_id=failure_id, organization_id=organization_id)
        raise FailureStateError(
            f"investigation {current['failure_code']} is already {current['status']}"
        )

    write_audit(
        session,
        AuditEvent(
            action="failure.closed",
            entity_type="failure",
            entity_id=str(failure_id),
            organization_id=organization_id,
            user_id=actor_id,
            new_state={"status": "closed"},
            reason=summary,
        ),
    )
    return dict(row)


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------


def list_failures(
    session: Session,
    *,
    organization_id: uuid.UUID,
    project_id: uuid.UUID | None = None,
    status: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    rows = session.execute(
        text(
            """
            SELECT f.id, f.failure_code, f.title, f.severity, f.status, f.project_id,
                   f.test_id, f.formula_version_id, f.opened_at, f.closed_at,
                   (SELECT count(*) FROM quality.failure_hypotheses h
                     WHERE h.failure_id = f.id) AS hypothesis_count,
                   (SELECT count(*) FROM quality.failure_hypotheses h
                     WHERE h.failure_id = f.id AND h.status = 'accepted')
                     AS has_root_cause,
                   (SELECT count(*) FROM quality.failure_actions a
                     WHERE a.failure_id = f.id
                       AND a.status IN ('proposed','approved','in_progress'))
                     AS open_actions
            FROM quality.failures f
            WHERE f.organization_id = :org
              AND (CAST(:pid AS UUID) IS NULL OR f.project_id = CAST(:pid AS UUID))
              AND (CAST(:status AS TEXT) IS NULL OR f.status = CAST(:status AS TEXT))
            ORDER BY f.opened_at DESC
            LIMIT :limit
            """
        ),
        {"org": organization_id, "pid": project_id, "status": status, "limit": limit},
    ).mappings()
    return [dict(r) for r in rows]


def get_failure(
    session: Session, *, failure_id: uuid.UUID, organization_id: uuid.UUID
) -> dict[str, Any]:
    """One investigation, with its hypotheses, evidence and actions.

    Each hypothesis carries the evidence linked to it AND how that
    evidence bears on it. A screen showing only supporting evidence would
    make every hypothesis look well-founded.
    """
    failure = _failure_row(session, failure_id=failure_id, organization_id=organization_id)

    hypotheses = [
        dict(r)
        for r in session.execute(
            text(
                """
                SELECT id, possible_cause, mechanism, confidence, source, origin,
                       status, accepted_by, accepted_at, rejection_reason,
                       proposed_by, created_at
                FROM quality.failure_hypotheses
                WHERE failure_id = :fid AND organization_id = :org
                ORDER BY created_at
                """
            ),
            {"fid": failure_id, "org": organization_id},
        ).mappings()
    ]

    links = [
        dict(r)
        for r in session.execute(
            text(
                """
                SELECT l.hypothesis_id, l.evidence_id, l.relationship, l.note,
                       e.evidence_type, e.summary, e.origin
                FROM quality.hypothesis_evidence l
                JOIN quality.failure_evidence e
                  ON e.id = l.evidence_id AND e.organization_id = l.organization_id
                WHERE e.failure_id = :fid AND l.organization_id = :org
                """
            ),
            {"fid": failure_id, "org": organization_id},
        ).mappings()
    ]

    by_hypothesis: dict[uuid.UUID, list[dict[str, Any]]] = {}
    for link in links:
        by_hypothesis.setdefault(link["hypothesis_id"], []).append(link)
    for hypothesis in hypotheses:
        hypothesis["evidence"] = by_hypothesis.get(hypothesis["id"], [])

    failure["hypotheses"] = hypotheses
    failure["accepted_root_cause"] = next(
        (h for h in hypotheses if h["status"] == "accepted"), None
    )
    failure["evidence"] = [
        dict(r)
        for r in session.execute(
            text(
                """
                SELECT id, evidence_type, summary, detail, referenced_entity_type,
                       referenced_entity_id, source_reference, origin, recorded_at
                FROM quality.failure_evidence
                WHERE failure_id = :fid AND organization_id = :org
                ORDER BY recorded_at
                """
            ),
            {"fid": failure_id, "org": organization_id},
        ).mappings()
    ]
    failure["actions"] = [
        dict(r)
        for r in session.execute(
            text(
                """
                SELECT id, action_type, description, status, assigned_to, due_date,
                       completed_at, outcome
                FROM quality.failure_actions
                WHERE failure_id = :fid AND organization_id = :org
                ORDER BY created_at
                """
            ),
            {"fid": failure_id, "org": organization_id},
        ).mappings()
    ]
    return failure


def _failure_row(
    session: Session, *, failure_id: uuid.UUID, organization_id: uuid.UUID
) -> dict[str, Any]:
    row = (
        session.execute(
            text(
                """
                SELECT id, organization_id, project_id, failure_code, title, description,
                       severity, status, test_id, formula_version_id, batch_id,
                       opened_by, opened_at, closed_by, closed_at, closure_summary
                FROM quality.failures
                WHERE id = :fid AND organization_id = :org
                """
            ),
            {"fid": failure_id, "org": organization_id},
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise FailureNotFoundError("no such failure investigation in this organization")
    return dict(row)
