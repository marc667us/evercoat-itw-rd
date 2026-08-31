"""The Research Center: workspaces, evidence, the findings register, and proposals.

🔴 THE LOOP THIS MODULE CLOSES

Specification §19, "Research-to-Experiment Workflow":

    Research Question -> Investigation -> Evidence -> Finding -> Hypothesis
    -> Experiment Proposal -> Chemist Review -> Formula Candidate -> Lab Batch
    -> Test -> Analysis -> Finding Updated

Everything from "Formula Candidate" rightwards already exists and is owned by
other modules. This one owns the left half, and joins the two at EXACTLY ONE
POINT: `accept_experiment_proposal` calls `formulations.revise_version` and
records the id it returns. Nothing here inserts a formula version, a lab batch
or a test, and there is no second path that does.

🔴 A PROPOSAL IS INERT UNTIL A PERSON ACCEPTS IT

§20 ends: *"Status: MSD PROPOSAL - NOT APPROVED. The Chemist decides whether it
becomes an actual experiment."* That is `CLAUDE.md` §7's boundary in this
module's own terms -- the assistant may propose, a human decides -- and it is
why acceptance is gated on a permission a person holds rather than on a status
a proposal can reach by itself.

🔴 AND ACCEPTANCE DOES NOT SMUGGLE ANYBODY PAST THE FORMULA GATE

Revising a formula version through `/formulations` requires `formula.clone` AND
`formula.modify_draft`. Accepting a proposal produces the same thing by the same
service, so the route requires those two permissions ALONGSIDE
`experiment.accept`. A route that reaches a privileged act without its gate is
this project's most-repeated defect class; it is not being introduced here to
save a click.

⚠️ TWO CONFIDENCE SCALES, ON PURPOSE. `research.findings.confidence` is §29's
high / moderate / low / unknown and answers *how strong is this conclusion?*.
`competitors.composition_evidence.confidence` is verified / supported /
probable / possible / unknown and answers *how well do we know this claim about
somebody else's recipe?*. The specification defines both, for these two objects.
Do not harmonize them.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.core.audit import AuditEvent, write_audit
from app.core.db import guarded_write
from app.core.embedding import EmbeddingPort
from app.core.notifications import notify
from app.core.tenancy import require_active_member
from app.domains.approvals.service import ApprovalError, open_route, route_for_entity
from app.domains.formulations.service import RevisionInput, revise_version
from app.domains.knowledge.service import ingest_document

__all__ = [
    "EvidenceInput",
    "FindingInput",
    "InvestigationInput",
    "ProposalInput",
    "ResearchError",
    "ResearchNotFoundError",
    "ResearchStateError",
    "SourceInput",
    "accept_experiment_proposal",
    "close_investigation",
    "decide_hypothesis",
    "finding_approval_status",
    "list_evidence",
    "list_findings",
    "list_hypotheses",
    "list_investigations",
    "list_knowledge_gaps",
    "list_proposals",
    "list_questions",
    "list_sources",
    "open_investigation",
    "promote_finding",
    "propose_experiment",
    "record_evidence",
    "record_finding",
    "record_hypothesis",
    "record_knowledge_gap",
    "record_question",
    "record_source",
    "reject_experiment_proposal",
    "resolve_knowledge_gap",
    "settle_question",
    "submit_finding",
]


class ResearchError(RuntimeError):
    """A research record could not be written as asked."""


class ResearchNotFoundError(ResearchError):
    """It does not exist, or the caller cannot reach it."""


class ResearchStateError(ResearchError):
    """It exists but is not in a state that allows this."""


@dataclass(frozen=True, slots=True)
class InvestigationInput:
    title: str
    research_question: str
    project_id: uuid.UUID | None = None
    search_strategy: str | None = None
    formula_version_id: uuid.UUID | None = None
    material_id: uuid.UUID | None = None
    test_id: uuid.UUID | None = None
    failure_id: uuid.UUID | None = None
    owner_user_id: uuid.UUID | None = None


@dataclass(frozen=True, slots=True)
class SourceInput:
    source_kind: str
    evidence_grade: str
    title: str
    source_locator: str | None = None
    document_id: uuid.UUID | None = None


@dataclass(frozen=True, slots=True)
class EvidenceInput:
    summary: str
    stance: str = "supports"
    question_id: uuid.UUID | None = None
    source_id: uuid.UUID | None = None
    formula_version_id: uuid.UUID | None = None
    test_id: uuid.UUID | None = None
    failure_id: uuid.UUID | None = None


@dataclass(frozen=True, slots=True)
class FindingInput:
    subject: str
    statement: str
    applicability: str
    confidence: str
    limitations: str | None = None


@dataclass(frozen=True, slots=True)
class ProposalInput:
    objective: str
    basis: str
    variables: str
    expected_direction: str
    required_tests: str
    confidence: str
    controlled_variables: str | None = None
    risks: str | None = None
    hypothesis_id: uuid.UUID | None = None


def _translate(exc: DBAPIError) -> ResearchError:
    """A PostgreSQL refusal, as an answer a client can act on.

    🔴 THE FALL-THROUGH IS THE DANGEROUS PART. Phase 3 shipped four
    constraints that reached the generic branch, which returns the raw
    PostgreSQL message -- schema, table and constraint expression -- as the
    response body. Every constraint this module can provoke is named here, and
    `test_every_constraint_has_a_message` walks `pg_constraint` to prove it.
    """
    detail = str(getattr(exc, "orig", exc))

    if "investigations_org_code_key" in detail:
        return ResearchStateError("that investigation code is already used in this organization")
    if "findings_org_code_key" in detail:
        return ResearchStateError("that finding code is already used in this organization")
    if "experiment_proposals_org_code_key" in detail:
        return ResearchStateError("that proposal code is already used in this organization")
    if "questions_order_key" in detail:
        return ResearchStateError(
            "that question number is already taken in this workspace; the next "
            "free number is allocated automatically, so this means two writes "
            "raced -- try again"
        )
    if "evidence_cites_something" in detail:
        return ResearchError(
            "an evidence card must cite something: a source, a formula version, "
            "a test or a failure. A card that cites nothing is an opinion."
        )
    if "evidence_question_fk" in detail:
        return ResearchStateError(
            "that question belongs to a different investigation. Evidence cannot "
            "attach one workspace's reasoning to another's conclusion."
        )
    if "evidence_source_fk" in detail:
        return ResearchStateError("that source belongs to a different investigation")
    if "hypotheses_finding_fk" in detail:
        return ResearchStateError("that finding belongs to a different investigation")
    if "experiment_proposals_hypothesis_fk" in detail:
        return ResearchStateError("that hypothesis belongs to a different investigation")
    if "sources_document_shape" in detail:
        return ResearchError("a document source must name the document it cites")
    if "has no approved approval route" in detail:
        return ResearchStateError(
            "only an approved finding may be promoted into the knowledge register. "
            "§9: approved findings are prioritized when answering future technical "
            "questions, so promoting an unreviewed conclusion would make it "
            "authoritative."
        )
    if "findings_promotion_complete" in detail:
        return ResearchError("a promotion needs both a document and a time")
    if "experiment_proposals_acceptance_produced_a_version" in detail:
        return ResearchStateError(
            "an accepted proposal must record the formula version it produced, and "
            "a proposal that was not accepted may not carry one"
        )
    if "experiment_proposals_decision_complete" in detail:
        return ResearchError("a decision needs both a named decider and a time")
    if "investigations_closure_complete" in detail:
        return ResearchError("a closed workspace is closed at a time; an open one is not")
    if "knowledge_gaps_question_fk" in detail:
        return ResearchStateError(
            "that question belongs to a different investigation, so a gap here cannot point at it"
        )
    if "experiment_proposals_version_fk" in detail:
        return ResearchStateError(
            "that formula version does not belong to this investigation's "
            "project. Research scoped to one project revises that project's "
            "formulas; organization-wide research may revise any you can reach."
        )
    # \U0001f534 EVERY `*_investigation_fk`, NOT THE TWO I HAPPENED TO WRITE.
    # Codex found `knowledge_gaps_question_fk` unnamed while the module's own
    # header claimed every provocable constraint was named. Matching the
    # SUFFIX covers the five siblings that were missing for the same reason,
    # and `test_every_constraint_has_a_message` walks `pg_constraint` so a
    # ninth table cannot reintroduce the gap.
    if "_investigation_fk" in detail:
        return ResearchNotFoundError("no such investigation in this organization")
    if "investigations_project_fk" in detail:
        return ResearchNotFoundError("no such project in this organization")
    if "investigations_version_fk" in detail or "evidence_version_fk" in detail:
        return ResearchNotFoundError("no such formula version in this organization")
    if "investigations_material_fk" in detail:
        return ResearchNotFoundError("no such material in this organization")
    if "investigations_test_fk" in detail or "evidence_test_fk" in detail:
        return ResearchNotFoundError("no such test in this organization")
    if "investigations_failure_fk" in detail or "evidence_failure_fk" in detail:
        return ResearchNotFoundError("no such failure in this organization")
    if "sources_document_fk" in detail or "findings_document_fk" in detail:
        return ResearchNotFoundError("no such document in this organization")
    if "row-level security" in detail:
        return ResearchStateError("this record names a project you cannot reach")
    return ResearchError("that research record could not be written as asked")


def _load_investigation(
    session: Session, *, investigation_id: uuid.UUID, organization_id: uuid.UUID
) -> dict[str, Any]:
    """The workspace, or a refusal that does not say whether it exists.

    RLS decides reachability, so a workspace in a restricted project the
    caller is not a member of returns exactly the same answer as one that was
    never created. That is deliberate: distinguishing the two is an oracle.
    """
    row = (
        session.execute(
            text(
                """
                SELECT id, organization_id, project_id, investigation_code, title,
                       research_question, status, owner_user_id
                  FROM research.investigations
                 WHERE id = :iid AND organization_id = :org
                """
            ),
            {"iid": investigation_id, "org": organization_id},
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise ResearchNotFoundError("no such investigation in this organization")
    return dict(row)


# ---------------------------------------------------------------------------
# The workspace
# ---------------------------------------------------------------------------


def open_investigation(
    session: Session,
    *,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    spec: InvestigationInput,
) -> dict[str, Any]:
    """Open a Research Workspace (§7).

    🔴 `lpad` TRUNCATES ON THE RIGHT, WHICH IS WHY THE WIDTH IS A `GREATEST`.

    `lpad('1000', 3, '0')` is `'100'` -- measured, not reasoned about. A fixed
    width does not merely stop padding once the number outgrows it: it returns
    a DIFFERENT number, colliding with one already issued, and the unique
    constraint then refuses every later attempt for that organization and year.
    Codes would become permanently un-allocatable and nothing about the code
    would look wrong. Found by the Supervisor reviewing this commit.

    🔴 THE CODE IS ALLOCATED INSIDE THE INSERT, NOT READ AND THEN WRITTEN.

    `RES-2026-0041` is per organization and per year. Selecting the maximum
    first and inserting afterwards is a read-then-write race: two chemists
    opening a workspace in the same second would both read 40 and both try 41.
    Taken inside the statement, the loser hits `investigations_org_code_key`
    and gets a refusal -- a correct refusal reached by a race rather than by a
    check, which is `revise_version`'s reasoning for issue numbers.

    `project_id` is optional. §1.2: an investigation into a chemistry rather
    than into a project belongs to the organization, and NULL says so.
    """
    owner = spec.owner_user_id or actor_id
    # \U0001f534 A NAMED OWNER IS CHECKED; THE CALLER IS NOT.
    #
    # `owner_user_id` comes straight off the request body and
    # `research.investigations.owner_user_id` is a plain
    # `REFERENCES core.users (id)` -- NOT tenant-scoped, because referential
    # integrity bypasses RLS even under FORCE. Without this, a caller could
    # name a user from ANOTHER organization as the owner and `notify()` below
    # would then address a notification to them. That is the C1/C2 defect
    # `app/core/tenancy.py` exists for, and the Supervisor found it here.
    #
    # The tell was already in the route: `post_investigation` catches
    # `CrossTenantReferenceError` and nothing in the call path could raise it
    # -- a handler for an exception that could not occur, standing in for the
    # check that was missing.
    if spec.owner_user_id is not None and spec.owner_user_id != actor_id:
        require_active_member(
            session,
            user_id=spec.owner_user_id,
            organization_id=organization_id,
            role_description="research owner",
        )
    try:
        with guarded_write(session):
            row = (
                session.execute(
                    text(
                        """
                        INSERT INTO research.investigations
                            (organization_id, project_id, investigation_code, title,
                             research_question, search_strategy, formula_version_id,
                             material_id, test_id, failure_id, owner_user_id, opened_by)
                        SELECT :org, :project,
                               'RES-' || to_char(clock_timestamp(), 'YYYY') || '-' ||
                               lpad(seq.n::TEXT, GREATEST(4, length(seq.n::TEXT)), '0'),
                               :title, :question, :strategy, :version, :material,
                               :test, :failure, :owner, :actor
                          FROM (
                                   SELECT COALESCE(max(
                                       NULLIF(regexp_replace(i.investigation_code,
                                                             '^RES-\\d{4}-', ''), '')::INT
                                   ), 0) + 1 AS n
                                     FROM research.investigations i
                                    WHERE i.organization_id = :org
                                      AND i.investigation_code LIKE
                                          'RES-' || to_char(clock_timestamp(), 'YYYY') || '-%'
                               ) AS seq
                        RETURNING id, investigation_code
                        """
                    ),
                    {
                        "org": organization_id,
                        "project": spec.project_id,
                        "title": spec.title,
                        "question": spec.research_question,
                        "strategy": spec.search_strategy,
                        "version": spec.formula_version_id,
                        "material": spec.material_id,
                        "test": spec.test_id,
                        "failure": spec.failure_id,
                        "owner": owner,
                        "actor": actor_id,
                    },
                )
                .mappings()
                .one()
            )
    except DBAPIError as exc:
        raise _translate(exc) from exc

    write_audit(
        session,
        AuditEvent(
            action="RESEARCH_INVESTIGATION_OPENED",
            entity_type="research_investigation",
            entity_id=str(row["id"]),
            organization_id=organization_id,
            user_id=actor_id,
            new_state={"code": row["investigation_code"], "title": spec.title},
        ),
    )
    # The owner is told, unless they opened it themselves -- a notification
    # telling somebody about their own action is noise, and §11 counts
    # actionable items rather than events.
    if owner != actor_id:
        notify(
            session,
            organization_id=organization_id,
            recipient_id=owner,
            notification_type="research.assigned",
            title=f"{row['investigation_code']}: {spec.title}",
            body="You have been made the owner of a research workspace.",
            entity_type="research_investigation",
            entity_id=row["id"],
            is_actionable=True,
        )
    return {"id": row["id"], "investigation_code": row["investigation_code"]}


def list_investigations(
    session: Session,
    *,
    organization_id: uuid.UUID,
    status: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """Workspaces this caller can reach.

    RLS applies the project predicate, so a workspace opened against a
    restricted project is invisible to a non-member -- the count of what the
    caller can reach, never a count of rows filtered afterwards.

    The four counts come with it because a workspace with no questions and no
    evidence is one somebody started and abandoned, and the screen should be
    able to say so rather than making every card a round trip.

    🔴 AND IT NOW SAYS WHAT MOTIVATED IT -- SPEC §25.

    `research.investigations` has carried `material_id`, `formula_version_id`,
    `test_id` and `failure_id` since migration 058, and the create route has
    always accepted all four. This SELECT projected NONE of them, so the
    Research Center could not say which material, test or failure an
    investigation was opened from, and §25's "reaching an investigation from
    the record that motivated it" had no data to work with in either direction.

    That is the same defect shape as the dates one closed on 2026-08-30: the
    column was never missing, the projection was. The lesson there was that
    every layer silently undoes the next, so the readable CODE is projected
    beside each id -- an id alone renders as a UUID nobody can act on, which is
    how a link ends up looking like it works while telling the reader nothing.
    """
    return [
        dict(r)
        for r in session.execute(
            text(
                """
                SELECT i.id, i.investigation_code, i.title, i.research_question,
                       i.status, i.project_id, i.owner_user_id, i.created_at,
                       p.project_code,
                       -- §25. The record that motivated this workspace, with
                       -- the code a person reads rather than the id alone.
                       -- LEFT JOINs, and every one tenant-qualified: RLS is a
                       -- backstop, not the boundary, and a join that omits the
                       -- organization is how a reference crosses a tenant.
                       i.material_id, m.material_code, m.name AS material_name,
                       i.formula_version_id, fv.version_code,
                       i.test_id, t.test_number,
                       i.failure_id, fl.failure_code, fl.title AS failure_title,
                       (SELECT count(*) FROM research.questions q
                         WHERE q.investigation_id = i.id
                           AND q.organization_id = i.organization_id) AS question_count,
                       (SELECT count(*) FROM research.evidence e
                         WHERE e.investigation_id = i.id
                           AND e.organization_id = i.organization_id) AS evidence_count,
                       (SELECT count(*) FROM research.findings f
                         WHERE f.investigation_id = i.id
                           AND f.organization_id = i.organization_id) AS finding_count,
                       (SELECT count(*) FROM research.experiment_proposals x
                         WHERE x.investigation_id = i.id
                           AND x.organization_id = i.organization_id) AS proposal_count
                  FROM research.investigations i
                  LEFT JOIN projects.projects p
                         ON p.id = i.project_id AND p.organization_id = i.organization_id
                  LEFT JOIN materials.materials m
                         ON m.id = i.material_id AND m.organization_id = i.organization_id
                  LEFT JOIN formulations.formula_versions fv
                         ON fv.id = i.formula_version_id
                        AND fv.organization_id = i.organization_id
                  LEFT JOIN testing.tests t
                         ON t.id = i.test_id AND t.organization_id = i.organization_id
                  LEFT JOIN quality.failures fl
                         ON fl.id = i.failure_id AND fl.organization_id = i.organization_id
                 WHERE i.organization_id = :org
                   AND (CAST(:status AS TEXT) IS NULL OR i.status = :status)
                 ORDER BY i.created_at DESC
                 LIMIT :limit
                """
            ),
            {"org": organization_id, "status": status, "limit": limit},
        ).mappings()
    ]


def close_investigation(
    session: Session,
    *,
    investigation_id: uuid.UUID,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
) -> dict[str, Any]:
    """Close a workspace. Nothing in it is deleted, ever (§5)."""
    investigation = _load_investigation(
        session, investigation_id=investigation_id, organization_id=organization_id
    )
    if investigation["status"] == "closed":
        raise ResearchStateError("that workspace is already closed")

    try:
        with guarded_write(session):
            session.execute(
                text(
                    """
                    UPDATE research.investigations
                       SET status = 'closed', closed_at = clock_timestamp()
                     WHERE id = :iid AND organization_id = :org
                    """
                ),
                {"iid": investigation_id, "org": organization_id},
            )
    except DBAPIError as exc:
        raise _translate(exc) from exc

    write_audit(
        session,
        AuditEvent(
            action="RESEARCH_INVESTIGATION_CLOSED",
            entity_type="research_investigation",
            entity_id=str(investigation_id),
            organization_id=organization_id,
            user_id=actor_id,
            previous_state={"status": investigation["status"]},
            new_state={"status": "closed"},
        ),
    )
    return {"id": investigation_id, "status": "closed"}


# ---------------------------------------------------------------------------
# Questions, sources and evidence
# ---------------------------------------------------------------------------


def record_question(
    session: Session,
    *,
    investigation_id: uuid.UUID,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    question: str,
) -> dict[str, Any]:
    """Add an answerable sub-question to a workspace.

    The number is taken inside the INSERT, for the reason the investigation
    code is. `questions_order_key` refuses a loser rather than silently
    renumbering somebody else's question.
    """
    _load_investigation(session, investigation_id=investigation_id, organization_id=organization_id)
    try:
        with guarded_write(session):
            row = (
                session.execute(
                    text(
                        """
                        INSERT INTO research.questions
                            (organization_id, investigation_id, sequence_number,
                             question, asked_by)
                        SELECT :org, :iid,
                               (SELECT COALESCE(max(q.sequence_number), 0) + 1
                                  FROM research.questions q
                                 WHERE q.investigation_id = :iid
                                   AND q.organization_id = :org),
                               :question, :actor
                        RETURNING id, sequence_number
                        """
                    ),
                    {
                        "org": organization_id,
                        "iid": investigation_id,
                        "question": question,
                        "actor": actor_id,
                    },
                )
                .mappings()
                .one()
            )
    except DBAPIError as exc:
        raise _translate(exc) from exc
    return {"id": row["id"], "sequence_number": row["sequence_number"]}


def list_questions(
    session: Session, *, investigation_id: uuid.UUID, organization_id: uuid.UUID
) -> list[dict[str, Any]]:
    """The questions in a workspace, in the order they were asked."""
    _load_investigation(session, investigation_id=investigation_id, organization_id=organization_id)
    return [
        dict(r)
        for r in session.execute(
            text(
                """
                SELECT q.id, q.sequence_number, q.question, q.status, q.created_at,
                       (SELECT count(*) FROM research.evidence e
                         WHERE e.question_id = q.id
                           AND e.organization_id = q.organization_id) AS evidence_count
                  FROM research.questions q
                 WHERE q.investigation_id = :iid AND q.organization_id = :org
                 ORDER BY q.sequence_number
                """
            ),
            {"iid": investigation_id, "org": organization_id},
        ).mappings()
    ]


def settle_question(
    session: Session,
    *,
    question_id: uuid.UUID,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    status: str,
) -> dict[str, Any]:
    """Mark a question answered, or record that it cannot be answered.

    `unanswerable` is not a failure state. §7 asks a workspace to record
    Knowledge Gaps, and a gap is traceable precisely when the question that
    hit it says so.
    """
    if status not in {"answered", "unanswerable"}:
        raise ResearchStateError(
            "a question is settled as 'answered' or 'unanswerable'; reopening one "
            "is not a transition this register supports"
        )
    try:
        with guarded_write(session):
            updated = session.execute(
                text(
                    """
                    UPDATE research.questions
                       SET status = :status
                     WHERE id = :qid AND organization_id = :org AND status = 'open'
                    RETURNING id
                    """
                ),
                {"qid": question_id, "org": organization_id, "status": status},
            ).scalar_one_or_none()
    except DBAPIError as exc:
        raise _translate(exc) from exc
    if updated is None:
        # One answer for "no such question" and "already settled" would hide a
        # real conflict, so they are separated -- but only after RLS has
        # already decided reachability, so neither leaks across a tenant.
        raise ResearchStateError(
            "no open question with that id here; it may already have been settled"
        )

    write_audit(
        session,
        AuditEvent(
            action="RESEARCH_QUESTION_SETTLED",
            entity_type="research_question",
            entity_id=str(question_id),
            organization_id=organization_id,
            user_id=actor_id,
            new_state={"status": status},
        ),
    )
    return {"id": question_id, "status": status}


def record_source(
    session: Session,
    *,
    investigation_id: uuid.UUID,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    spec: SourceInput,
) -> dict[str, Any]:
    """Register a source and grade it (§6).

    The grade describes the SOURCE, not the conclusion: an A-grade standard
    can be cited by evidence that contradicts a finding. §6's ranking is
    stored verbatim -- A internal validated / standard / manufacturer, B
    peer-reviewed / patent / institution, C supplier literature / conference,
    D general web, X unverified.
    """
    _load_investigation(session, investigation_id=investigation_id, organization_id=organization_id)
    try:
        with guarded_write(session):
            source_id = session.execute(
                text(
                    """
                    INSERT INTO research.sources
                        (organization_id, investigation_id, source_kind, evidence_grade,
                         title, source_locator, document_id, recorded_by)
                    VALUES (:org, :iid, :kind, :grade, :title, :locator, :doc, :actor)
                    RETURNING id
                    """
                ),
                {
                    "org": organization_id,
                    "iid": investigation_id,
                    "kind": spec.source_kind,
                    "grade": spec.evidence_grade,
                    "title": spec.title,
                    "locator": spec.source_locator,
                    "doc": spec.document_id,
                    "actor": actor_id,
                },
            ).scalar_one()
    except DBAPIError as exc:
        raise _translate(exc) from exc
    return {"id": source_id}


def list_sources(
    session: Session, *, investigation_id: uuid.UUID, organization_id: uuid.UUID
) -> list[dict[str, Any]]:
    """Sources on file for a workspace, best-graded first."""
    _load_investigation(session, investigation_id=investigation_id, organization_id=organization_id)
    return [
        dict(r)
        for r in session.execute(
            text(
                """
                SELECT id, source_kind, evidence_grade, title, source_locator,
                       document_id, created_at
                  FROM research.sources
                 WHERE investigation_id = :iid AND organization_id = :org
                 ORDER BY evidence_grade, created_at
                """
            ),
            {"iid": investigation_id, "org": organization_id},
        ).mappings()
    ]


def record_evidence(
    session: Session,
    *,
    investigation_id: uuid.UUID,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    spec: EvidenceInput,
) -> dict[str, Any]:
    """Record one evidence card (§28).

    §28's example marks some citations ✓ and others ○. `stance` stores that,
    plus the case the example does not draw and honest research needs:
    `contradicts`. A register that can only record agreement is a register of
    conclusions, not of evidence.
    """
    _load_investigation(session, investigation_id=investigation_id, organization_id=organization_id)
    try:
        with guarded_write(session):
            evidence_id = session.execute(
                text(
                    """
                    INSERT INTO research.evidence
                        (organization_id, investigation_id, question_id, source_id,
                         formula_version_id, test_id, failure_id, stance, summary,
                         recorded_by)
                    VALUES (:org, :iid, :question, :source, :version, :test, :failure,
                            :stance, :summary, :actor)
                    RETURNING id
                    """
                ),
                {
                    "org": organization_id,
                    "iid": investigation_id,
                    "question": spec.question_id,
                    "source": spec.source_id,
                    "version": spec.formula_version_id,
                    "test": spec.test_id,
                    "failure": spec.failure_id,
                    "stance": spec.stance,
                    "summary": spec.summary,
                    "actor": actor_id,
                },
            ).scalar_one()
    except DBAPIError as exc:
        raise _translate(exc) from exc
    return {"id": evidence_id}


def list_evidence(
    session: Session, *, investigation_id: uuid.UUID, organization_id: uuid.UUID
) -> list[dict[str, Any]]:
    """The evidence cards, with the grade of whatever each one cites."""
    _load_investigation(session, investigation_id=investigation_id, organization_id=organization_id)
    return [
        dict(r)
        for r in session.execute(
            text(
                """
                SELECT e.id, e.question_id, e.source_id, e.formula_version_id,
                       e.test_id, e.failure_id, e.stance, e.summary, e.created_at,
                       s.title AS source_title, s.evidence_grade, s.source_kind,
                       q.sequence_number AS question_number,
                       v.version_code, t.test_number, fl.failure_code
                  FROM research.evidence e
                  LEFT JOIN research.sources s
                         ON s.id = e.source_id AND s.organization_id = e.organization_id
                  LEFT JOIN research.questions q
                         ON q.id = e.question_id AND q.organization_id = e.organization_id
                  LEFT JOIN formulations.formula_versions v
                         ON v.id = e.formula_version_id
                        AND v.organization_id = e.organization_id
                  LEFT JOIN testing.tests t
                         ON t.id = e.test_id AND t.organization_id = e.organization_id
                  LEFT JOIN quality.failures fl
                         ON fl.id = e.failure_id AND fl.organization_id = e.organization_id
                 WHERE e.investigation_id = :iid AND e.organization_id = :org
                 ORDER BY e.created_at
                """
            ),
            {"iid": investigation_id, "org": organization_id},
        ).mappings()
    ]


# ---------------------------------------------------------------------------
# The findings register (§9)
# ---------------------------------------------------------------------------


def record_finding(
    session: Session,
    *,
    investigation_id: uuid.UUID,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    spec: FindingInput,
) -> dict[str, Any]:
    """Draft a finding. It is not in the register until it is approved."""
    _load_investigation(session, investigation_id=investigation_id, organization_id=organization_id)
    try:
        with guarded_write(session):
            row = (
                session.execute(
                    text(
                        """
                        INSERT INTO research.findings
                            (organization_id, investigation_id, finding_code, subject,
                             statement, applicability, limitations, confidence, author_id)
                        SELECT :org, :iid,
                               'RF-' || lpad(seq.n::TEXT,
                                             GREATEST(4, length(seq.n::TEXT)), '0'),
                               :subject, :statement, :applicability, :limitations,
                               :confidence, :actor
                          FROM (
                                   SELECT COALESCE(max(
                                       NULLIF(regexp_replace(f.finding_code, '^RF-', ''),
                                              '')::INT
                                   ), 0) + 1 AS n
                                     FROM research.findings f
                                    WHERE f.organization_id = :org
                               ) AS seq
                        RETURNING id, finding_code
                        """
                    ),
                    {
                        "org": organization_id,
                        "iid": investigation_id,
                        "subject": spec.subject,
                        "statement": spec.statement,
                        "applicability": spec.applicability,
                        "limitations": spec.limitations,
                        "confidence": spec.confidence,
                        "actor": actor_id,
                    },
                )
                .mappings()
                .one()
            )
    except DBAPIError as exc:
        raise _translate(exc) from exc

    write_audit(
        session,
        AuditEvent(
            action="RESEARCH_FINDING_DRAFTED",
            entity_type="research_finding",
            entity_id=str(row["id"]),
            organization_id=organization_id,
            user_id=actor_id,
            new_state={"code": row["finding_code"], "confidence": spec.confidence},
        ),
    )
    return {"id": row["id"], "finding_code": row["finding_code"], "status": "draft"}


def list_findings(
    session: Session,
    *,
    organization_id: uuid.UUID,
    investigation_id: uuid.UUID | None = None,
    status: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """The register, or one workspace's part of it."""
    return [
        dict(r)
        for r in session.execute(
            text(
                """
                SELECT f.id, f.finding_code, f.subject, f.statement, f.applicability,
                       f.limitations, f.confidence, f.status, f.author_id,
                       f.promoted_document_id, f.promoted_at, f.created_at,
                       f.investigation_id, i.investigation_code, i.project_id,
                       -- 🔴 THE APPROVAL OUTCOME IS THE ROUTE'S, NOT A COLUMN
                       -- HERE. `safety_review_status` reads it the same way and
                       -- for the same reason: a stored copy would be a status
                       -- nothing maintains. NULL means never submitted.
                       r.status AS approval_status
                  FROM research.findings f
                  JOIN research.investigations i
                    ON i.id = f.investigation_id AND i.organization_id = f.organization_id
                  LEFT JOIN workflow.approval_routes r
                         ON r.entity_type = 'research_finding'
                        AND r.entity_id = f.id
                        AND r.organization_id = f.organization_id
                 WHERE f.organization_id = :org
                   AND (CAST(:iid AS UUID) IS NULL OR f.investigation_id = :iid)
                   AND (CAST(:status AS TEXT) IS NULL OR f.status = :status)
                 ORDER BY f.created_at DESC
                 LIMIT :limit
                """
            ),
            {
                "org": organization_id,
                "iid": investigation_id,
                "status": status,
                "limit": limit,
            },
        ).mappings()
    ]


def submit_finding(
    session: Session,
    *,
    finding_id: uuid.UUID,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
) -> dict[str, Any]:
    """Submit a finding, opening its approval route.

    🔴 IT CALLS `approvals.open_route`. There is no second approval engine and
    no second notion of "signed off" -- `CLAUDE.md` §12 forbids one, and
    `/approvals` already renders the queue this route joins.

    ⚠️ AND IT REFUSES A FINDING ON AN ORGANIZATION-WIDE WORKSPACE, WITH A
    REASON. `open_route` takes `project_id` as a NOT NULL argument
    (`approvals/service.py:103`), and §1.2 deliberately allows an
    investigation to have none. Rather than forbid organization-wide research
    -- which the specification asks for -- or invent a null project that the
    approval queue would then render, the refusal says exactly what to do:
    move the workspace to a project, or keep the finding as a draft.
    """
    finding = (
        session.execute(
            text(
                """
                SELECT f.id, f.finding_code, f.subject, f.status, f.investigation_id,
                       i.project_id, i.investigation_code, i.owner_user_id
                  FROM research.findings f
                  JOIN research.investigations i
                    ON i.id = f.investigation_id AND i.organization_id = f.organization_id
                 WHERE f.id = :fid AND f.organization_id = :org
                """
            ),
            {"fid": finding_id, "org": organization_id},
        )
        .mappings()
        .one_or_none()
    )
    if finding is None:
        raise ResearchNotFoundError("no such finding in this organization")
    if finding["status"] != "draft":
        raise ResearchStateError(
            f"that finding is {finding['status']}; only a draft can be submitted"
        )
    if finding["project_id"] is None:
        raise ResearchStateError(
            "this finding belongs to an organization-wide investigation, and an "
            "approval route needs a project: each project's lead approves for "
            "their own work. Move the investigation to a project, or keep the "
            "finding as a draft."
        )

    try:
        with guarded_write(session):
            session.execute(
                text(
                    """
                    UPDATE research.findings
                       SET status = 'submitted'
                     WHERE id = :fid AND organization_id = :org
                    """
                ),
                {"fid": finding_id, "org": organization_id},
            )
    except DBAPIError as exc:
        raise _translate(exc) from exc

    try:
        route = open_route(
            session,
            organization_id=organization_id,
            project_id=finding["project_id"],
            entity_type="research_finding",
            entity_id=finding_id,
            authority_level="research",
            actor_id=actor_id,
        )
    except ApprovalError as exc:
        # The route is the point of submitting. Left in `submitted` with no
        # route, the finding would sit in a queue that does not exist -- the
        # "gate on an unused path" defect, arrived at by accident.
        raise ResearchStateError(f"the finding could not be routed for approval: {exc}") from exc

    write_audit(
        session,
        AuditEvent(
            action="RESEARCH_FINDING_SUBMITTED",
            entity_type="research_finding",
            entity_id=str(finding_id),
            organization_id=organization_id,
            user_id=actor_id,
            previous_state={"status": "draft"},
            new_state={"status": "submitted", "route_id": str(route["route_id"])},
        ),
    )
    return {"id": finding_id, "status": "submitted", "route": route}


def finding_approval_status(
    session: Session, *, finding_id: uuid.UUID, organization_id: uuid.UUID
) -> dict[str, Any] | None:
    """The route and its steps, or None if the finding was never submitted."""
    return route_for_entity(
        session,
        organization_id=organization_id,
        entity_type="research_finding",
        entity_id=finding_id,
    )


def promote_finding(
    session: Session,
    *,
    finding_id: uuid.UUID,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    embedder: EmbeddingPort,
) -> dict[str, Any]:
    """Promote an approved finding into the Knowledge Library.

    🔴 THIS IS `knowledge.promote`'s FIRST ENFORCEMENT POINT. The permission
    has been seeded since migration 002 and held by three roles, and until now
    nothing in the product read it -- one of the 29 orphans. The route that
    calls this is where it starts meaning something.

    🔴 AND IT CALLS `knowledge.ingest_document`, THE ONE INGEST PATH. §14 and
    §15: there is one knowledge register, and a finding entering it gets the
    same chunking, embedding and classification as anything else. Nothing here
    writes `knowledge.documents` directly.

    ⚠️ ONLY AN APPROVED FINDING. Checked here so the refusal explains itself,
    AND enforced by `findings_only_approved_are_promoted` so a direct SQL
    write cannot walk past it. §9: approved findings are prioritized when
    answering future technical questions, so promoting a draft would make an
    unreviewed conclusion authoritative -- exactly what §7 of `CLAUDE.md`
    forbids ("informal chat never becomes authoritative knowledge
    automatically").
    """
    finding = (
        session.execute(
            text(
                """
                SELECT f.id, f.finding_code, f.subject, f.statement, f.applicability,
                       f.limitations, f.confidence, f.status, f.promoted_document_id,
                       i.project_id, i.investigation_code,
                       r.status AS approval_status
                  FROM research.findings f
                  JOIN research.investigations i
                    ON i.id = f.investigation_id AND i.organization_id = f.organization_id
                  LEFT JOIN workflow.approval_routes r
                         ON r.entity_type = 'research_finding'
                        AND r.entity_id = f.id
                        AND r.organization_id = f.organization_id
                 WHERE f.id = :fid AND f.organization_id = :org
                """
            ),
            {"fid": finding_id, "org": organization_id},
        )
        .mappings()
        .one_or_none()
    )
    if finding is None:
        raise ResearchNotFoundError("no such finding in this organization")
    if finding["approval_status"] != "approved":
        raise ResearchStateError(
            "that finding has not been approved"
            + (
                " — it has never been submitted for approval"
                if finding["approval_status"] is None
                else f" — its approval route is {finding['approval_status']}"
            )
            + ". §9 prioritizes approved findings when answering future technical "
            "questions, so promoting an unreviewed one would make it authoritative."
        )
    if finding["promoted_document_id"] is not None:
        raise ResearchStateError("that finding is already in the knowledge register")

    body = "\n\n".join(
        part
        for part in (
            f"Finding {finding['finding_code']} — {finding['subject']}",
            finding["statement"],
            f"Applicability: {finding['applicability']}",
            f"Limitations: {finding['limitations']}" if finding["limitations"] else "",
            f"Confidence: {finding['confidence']}",
            f"Source investigation: {finding['investigation_code']}",
        )
        if part
    )

    document = ingest_document(
        session,
        organization_id=organization_id,
        actor_id=actor_id,
        title=f"{finding['finding_code']}: {finding['subject']}",
        body=body,
        source="research_finding",
        embedder=embedder,
        project_id=finding["project_id"],
    )

    try:
        with guarded_write(session):
            session.execute(
                text(
                    """
                    UPDATE research.findings
                       SET promoted_document_id = :doc, promoted_at = clock_timestamp()
                     WHERE id = :fid AND organization_id = :org
                    """
                ),
                {"doc": document["document_id"], "fid": finding_id, "org": organization_id},
            )
    except DBAPIError as exc:
        raise _translate(exc) from exc

    write_audit(
        session,
        AuditEvent(
            action="RESEARCH_FINDING_PROMOTED",
            entity_type="research_finding",
            entity_id=str(finding_id),
            organization_id=organization_id,
            user_id=actor_id,
            new_state={
                "code": finding["finding_code"],
                "document_id": str(document["document_id"]),
            },
        ),
    )
    return {"id": finding_id, "document_id": document["document_id"]}


# ---------------------------------------------------------------------------
# Hypotheses and knowledge gaps
# ---------------------------------------------------------------------------


def record_hypothesis(
    session: Session,
    *,
    investigation_id: uuid.UUID,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    statement: str,
    rationale: str | None = None,
    finding_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """State something an experiment could support or refute."""
    _load_investigation(session, investigation_id=investigation_id, organization_id=organization_id)
    try:
        with guarded_write(session):
            hypothesis_id = session.execute(
                text(
                    """
                    INSERT INTO research.hypotheses
                        (organization_id, investigation_id, finding_id, statement,
                         rationale, proposed_by)
                    VALUES (:org, :iid, :fid, :statement, :rationale, :actor)
                    RETURNING id
                    """
                ),
                {
                    "org": organization_id,
                    "iid": investigation_id,
                    "fid": finding_id,
                    "statement": statement,
                    "rationale": rationale,
                    "actor": actor_id,
                },
            ).scalar_one()
    except DBAPIError as exc:
        raise _translate(exc) from exc
    return {"id": hypothesis_id}


def decide_hypothesis(
    session: Session,
    *,
    hypothesis_id: uuid.UUID,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    status: str,
) -> dict[str, Any]:
    """Record what the evidence did to a hypothesis.

    `refuted` is a first-class outcome, not an error. §4 of the revised
    specification puts failure investigations and historical formulas in the
    internal evidence base precisely so that what did NOT work is retrievable.
    """
    if status not in {"supported", "refuted", "withdrawn"}:
        raise ResearchStateError("a hypothesis is settled as 'supported', 'refuted' or 'withdrawn'")
    try:
        with guarded_write(session):
            updated = session.execute(
                text(
                    """
                    UPDATE research.hypotheses
                       SET status = :status
                     WHERE id = :hid AND organization_id = :org AND status = 'open'
                    RETURNING id
                    """
                ),
                {"hid": hypothesis_id, "org": organization_id, "status": status},
            ).scalar_one_or_none()
    except DBAPIError as exc:
        raise _translate(exc) from exc
    if updated is None:
        raise ResearchStateError(
            "no open hypothesis with that id here; it may already have been settled"
        )

    write_audit(
        session,
        AuditEvent(
            action="RESEARCH_HYPOTHESIS_SETTLED",
            entity_type="research_hypothesis",
            entity_id=str(hypothesis_id),
            organization_id=organization_id,
            user_id=actor_id,
            new_state={"status": status},
        ),
    )
    return {"id": hypothesis_id, "status": status}


def list_hypotheses(
    session: Session, *, investigation_id: uuid.UUID, organization_id: uuid.UUID
) -> list[dict[str, Any]]:
    """The hypotheses in a workspace, open ones first.

    🔴 THIS READER EXISTS BECAUSE THE WRITER DID FIRST, AND THAT WAS A DEFECT.

    `record_hypothesis` and `decide_hypothesis` were written before anything
    could list what they wrote — a table with a writer, no reader and no
    control, which is the same defect as a route with no caller wearing a
    different hat. Found while building the screen, which is exactly why §10
    requires the writer and its control to ship in the same phase.
    """
    _load_investigation(session, investigation_id=investigation_id, organization_id=organization_id)
    return [
        dict(r)
        for r in session.execute(
            text(
                """
                SELECT h.id, h.statement, h.rationale, h.status, h.finding_id,
                       h.created_at, f.finding_code,
                       (SELECT count(*) FROM research.experiment_proposals x
                         WHERE x.hypothesis_id = h.id
                           AND x.organization_id = h.organization_id) AS proposal_count
                  FROM research.hypotheses h
                  LEFT JOIN research.findings f
                         ON f.id = h.finding_id AND f.organization_id = h.organization_id
                 WHERE h.investigation_id = :iid AND h.organization_id = :org
                 ORDER BY CASE h.status WHEN 'open' THEN 0 ELSE 1 END, h.created_at
                """
            ),
            {"iid": investigation_id, "org": organization_id},
        ).mappings()
    ]


def record_knowledge_gap(
    session: Session,
    *,
    investigation_id: uuid.UUID,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    description: str,
    impact: str = "moderate",
    question_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """Record what the work could not establish."""
    _load_investigation(session, investigation_id=investigation_id, organization_id=organization_id)
    try:
        with guarded_write(session):
            gap_id = session.execute(
                text(
                    """
                    INSERT INTO research.knowledge_gaps
                        (organization_id, investigation_id, question_id, description,
                         impact, identified_by)
                    VALUES (:org, :iid, :qid, :description, :impact, :actor)
                    RETURNING id
                    """
                ),
                {
                    "org": organization_id,
                    "iid": investigation_id,
                    "qid": question_id,
                    "description": description,
                    "impact": impact,
                    "actor": actor_id,
                },
            ).scalar_one()
    except DBAPIError as exc:
        raise _translate(exc) from exc
    return {"id": gap_id}


def resolve_knowledge_gap(
    session: Session,
    *,
    gap_id: uuid.UUID,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
) -> dict[str, Any]:
    """Close a gap once it has been filled."""
    try:
        with guarded_write(session):
            updated = session.execute(
                text(
                    """
                    UPDATE research.knowledge_gaps
                       SET status = 'closed'
                     WHERE id = :gid AND organization_id = :org AND status = 'open'
                    RETURNING id
                    """
                ),
                {"gid": gap_id, "org": organization_id},
            ).scalar_one_or_none()
    except DBAPIError as exc:
        raise _translate(exc) from exc
    if updated is None:
        raise ResearchStateError("no open knowledge gap with that id here")

    write_audit(
        session,
        AuditEvent(
            action="RESEARCH_GAP_CLOSED",
            entity_type="research_knowledge_gap",
            entity_id=str(gap_id),
            organization_id=organization_id,
            user_id=actor_id,
            new_state={"status": "closed"},
        ),
    )
    return {"id": gap_id, "status": "closed"}


def list_knowledge_gaps(
    session: Session, *, investigation_id: uuid.UUID, organization_id: uuid.UUID
) -> list[dict[str, Any]]:
    """The gaps in a workspace, worst impact first."""
    _load_investigation(session, investigation_id=investigation_id, organization_id=organization_id)
    return [
        dict(r)
        for r in session.execute(
            text(
                """
                SELECT g.id, g.description, g.impact, g.status, g.question_id,
                       g.created_at, q.sequence_number AS question_number
                  FROM research.knowledge_gaps g
                  LEFT JOIN research.questions q
                         ON q.id = g.question_id AND q.organization_id = g.organization_id
                 WHERE g.investigation_id = :iid AND g.organization_id = :org
                 ORDER BY CASE g.impact WHEN 'high' THEN 0 WHEN 'moderate' THEN 1
                                        ELSE 2 END,
                          g.created_at
                """
            ),
            {"iid": investigation_id, "org": organization_id},
        ).mappings()
    ]


# ---------------------------------------------------------------------------
# Experiment proposals (§20) — and the one join to the formula world
# ---------------------------------------------------------------------------


def propose_experiment(
    session: Session,
    *,
    investigation_id: uuid.UUID,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    spec: ProposalInput,
) -> dict[str, Any]:
    """Write §20's structured proposal. It changes nothing until accepted."""
    _load_investigation(session, investigation_id=investigation_id, organization_id=organization_id)
    try:
        with guarded_write(session):
            row = (
                session.execute(
                    text(
                        """
                        INSERT INTO research.experiment_proposals
                            (organization_id, investigation_id, hypothesis_id,
                             proposal_code, objective, basis, variables,
                             controlled_variables, expected_direction, required_tests,
                             risks, confidence, proposed_by)
                        SELECT :org, :iid, :hypothesis,
                               'EXP-' || to_char(clock_timestamp(), 'YYYY') || '-' ||
                               lpad(seq.n::TEXT, GREATEST(3, length(seq.n::TEXT)), '0'),
                               :objective, :basis, :variables, :controlled,
                               :direction, :tests, :risks, :confidence, :actor
                          FROM (
                                   SELECT COALESCE(max(
                                       NULLIF(regexp_replace(x.proposal_code,
                                                             '^EXP-\\d{4}-', ''), '')::INT
                                   ), 0) + 1 AS n
                                     FROM research.experiment_proposals x
                                    WHERE x.organization_id = :org
                                      AND x.proposal_code LIKE
                                          'EXP-' || to_char(clock_timestamp(), 'YYYY') || '-%'
                               ) AS seq
                        RETURNING id, proposal_code
                        """
                    ),
                    {
                        "org": organization_id,
                        "iid": investigation_id,
                        "hypothesis": spec.hypothesis_id,
                        "objective": spec.objective,
                        "basis": spec.basis,
                        "variables": spec.variables,
                        "controlled": spec.controlled_variables,
                        "direction": spec.expected_direction,
                        "tests": spec.required_tests,
                        "risks": spec.risks,
                        "confidence": spec.confidence,
                        "actor": actor_id,
                    },
                )
                .mappings()
                .one()
            )
    except DBAPIError as exc:
        raise _translate(exc) from exc

    write_audit(
        session,
        AuditEvent(
            action="EXPERIMENT_PROPOSED",
            entity_type="experiment_proposal",
            entity_id=str(row["id"]),
            organization_id=organization_id,
            user_id=actor_id,
            new_state={"code": row["proposal_code"], "objective": spec.objective},
        ),
    )
    return {
        "id": row["id"],
        "proposal_code": row["proposal_code"],
        "status": "proposed",
    }


def list_proposals(
    session: Session,
    *,
    organization_id: uuid.UUID,
    investigation_id: uuid.UUID | None = None,
    status: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """Proposals this caller can reach."""
    return [
        dict(r)
        for r in session.execute(
            text(
                """
                SELECT x.id, x.proposal_code, x.objective, x.basis, x.variables,
                       x.controlled_variables, x.expected_direction, x.required_tests,
                       x.risks, x.confidence, x.status, x.hypothesis_id,
                       x.resulting_formula_version_id, x.decided_by, x.decided_at,
                       x.decision_note, x.created_at, x.investigation_id,
                       i.investigation_code, v.version_code AS resulting_version_code
                  FROM research.experiment_proposals x
                  JOIN research.investigations i
                    ON i.id = x.investigation_id AND i.organization_id = x.organization_id
                  LEFT JOIN formulations.formula_versions v
                         ON v.id = x.resulting_formula_version_id
                        AND v.organization_id = x.organization_id
                 WHERE x.organization_id = :org
                   AND (CAST(:iid AS UUID) IS NULL OR x.investigation_id = :iid)
                   AND (CAST(:status AS TEXT) IS NULL OR x.status = :status)
                 ORDER BY x.created_at DESC
                 LIMIT :limit
                """
            ),
            {
                "org": organization_id,
                "iid": investigation_id,
                "status": status,
                "limit": limit,
            },
        ).mappings()
    ]


def _load_open_proposal(
    session: Session, *, proposal_id: uuid.UUID, organization_id: uuid.UUID
) -> dict[str, Any]:
    """The proposal, LOCKED, or a refusal.

    \U0001f534 `FOR UPDATE OF x` IS THE POINT OF THIS FUNCTION, NOT THE SELECT.

    Codex P1 against the first version: the read checked `status = 'proposed'`
    and the write later said `WHERE status = 'proposed'` without checking how
    many rows it touched. Two chemists accepting the same proposal at once
    would each have passed the read, each have called `revise_version` -- so
    TWO formula versions exist, both claiming this proposal as their driver --
    and only one UPDATE would land. The loser still wrote an audit event, still
    notified, and still returned success for a revision the proposal does not
    record.

    A row lock makes the second caller wait and then read `accepted`, so the
    refusal happens BEFORE anything is cloned. `OF x` locks the proposal only:
    locking the joined investigation as well would serialise every acceptance
    in a workspace against every other.
    """
    row = (
        session.execute(
            text(
                """
                SELECT x.id, x.proposal_code, x.objective, x.expected_direction,
                       x.status, x.proposed_by, x.investigation_id, x.project_id,
                       i.investigation_code
                  FROM research.experiment_proposals x
                  JOIN research.investigations i
                    ON i.id = x.investigation_id AND i.organization_id = x.organization_id
                 WHERE x.id = :pid AND x.organization_id = :org
                   FOR UPDATE OF x
                """
            ),
            {"pid": proposal_id, "org": organization_id},
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise ResearchNotFoundError("no such experiment proposal in this organization")
    if row["status"] != "proposed":
        raise ResearchStateError(
            f"that proposal is already {row['status']}; a decision is taken once"
        )
    return dict(row)


def accept_experiment_proposal(
    session: Session,
    *,
    proposal_id: uuid.UUID,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    version_id: uuid.UUID,
    change_reason: str,
    technical_hypothesis: str,
    decision_note: str | None = None,
) -> dict[str, Any]:
    """Accept a proposal, revising the named formula version.

    🔴 IT CALLS `formulations.revise_version` AND STORES WHAT THAT RETURNS.

    This function inserts no formula row. §8: a formula changes by being
    cloned into a new draft, and `revise_version` is the only thing that does
    it -- which is also why the caller must supply `change_reason` and
    `technical_hypothesis`: the database requires both of every version after
    the first, and a proposal's objective is not a substitute for a chemist
    saying what they expect this specific revision to do.

    🔴 AND THE REVISION RECORDS THAT RESEARCH DROVE IT. `driver_type='research'`
    with the proposal's id, so §2's thread is traversable in BOTH directions:
    forward from the proposal to the version, and backward from the version to
    the investigation. Migration 058 refuses a `research` driver that names no
    proposal, so this cannot silently degrade into an unlinked category.
    """
    proposal = _load_open_proposal(
        session, proposal_id=proposal_id, organization_id=organization_id
    )

    # 🔴 REFUSE BEFORE CLONING, NOT AFTER.
    #
    # `experiment_proposals_version_fk` already refuses a version outside the
    # proposal's project — but it fires on the UPDATE below, which is AFTER
    # `revise_version` has cloned a formula version. The clone is then undone
    # only by the caller's rollback, and the message a client reads describes a
    # constraint rather than the decision.
    #
    # The Supervisor's re-review of `ef160b3` found `project_id` being selected
    # and read by nothing — a value computed and carried but never used, which
    # is this project's own name for a capability the comments claim and the
    # code lacks. This is that value doing its job.
    #
    # ⚠️ NULL means the investigation is organization-wide, and then there is no
    # project to be outside of: §1.2's deliberate case, and the database agrees
    # because MATCH SIMPLE skips the three-column key when the column is NULL.
    if proposal["project_id"] is not None:
        version_project = session.execute(
            text(
                """
                SELECT project_id FROM formulations.formula_versions
                 WHERE id = :vid AND organization_id = :org
                """
            ),
            {"vid": version_id, "org": organization_id},
        ).scalar_one_or_none()
        if version_project is None:
            raise ResearchNotFoundError("no such formula version in this organization")
        if version_project != proposal["project_id"]:
            raise ResearchStateError(
                "that formula version belongs to a different project. Research "
                "scoped to one project revises that project's formulas; only "
                "organization-wide research may revise any you can reach."
            )

    revision = revise_version(
        session,
        version_id=version_id,
        organization_id=organization_id,
        actor_id=actor_id,
        spec=RevisionInput(
            change_reason=change_reason,
            technical_hypothesis=technical_hypothesis,
            driver_type="research",
            driver_experiment_proposal_id=proposal_id,
        ),
    )

    try:
        with guarded_write(session):
            decided = session.execute(
                text(
                    """
                    UPDATE research.experiment_proposals
                       SET status = 'accepted',
                           resulting_formula_version_id = :version,
                           decided_by = :actor,
                           decided_at = clock_timestamp(),
                           decision_note = :note
                     WHERE id = :pid AND organization_id = :org AND status = 'proposed'
                    RETURNING id
                    """
                ),
                {
                    "version": revision["version_id"],
                    "actor": actor_id,
                    "note": decision_note,
                    "pid": proposal_id,
                    "org": organization_id,
                },
            ).scalar_one_or_none()
    except DBAPIError as exc:
        raise _translate(exc) from exc
    # \U0001f534 A CONDITIONAL UPDATE THAT MATCHES NOTHING REPORTS SUCCESS.
    # The row lock above should make this unreachable; asserting it anyway is
    # what turns "should" into "did", and a silent no-op here would leave a
    # formula version cloned with no proposal recording it.
    if decided is None:
        raise ResearchStateError(
            "that proposal was decided by somebody else while this acceptance "
            "was in flight; nothing has been recorded against it"
        )

    write_audit(
        session,
        AuditEvent(
            action="EXPERIMENT_PROPOSAL_ACCEPTED",
            entity_type="experiment_proposal",
            entity_id=str(proposal_id),
            organization_id=organization_id,
            user_id=actor_id,
            previous_state={"status": "proposed"},
            new_state={
                "status": "accepted",
                "formula_version_id": str(revision["version_id"]),
                "version_code": revision["version_code"],
            },
        ),
    )
    if proposal["proposed_by"] != actor_id:
        notify(
            session,
            organization_id=organization_id,
            recipient_id=proposal["proposed_by"],
            notification_type="experiment.accepted",
            title=f"{proposal['proposal_code']} accepted",
            body=f"Formula version {revision['version_code']} was created from it.",
            entity_type="experiment_proposal",
            entity_id=proposal_id,
        )
    return {
        "id": proposal_id,
        "status": "accepted",
        "formula_version_id": revision["version_id"],
        "version_code": revision["version_code"],
    }


def reject_experiment_proposal(
    session: Session,
    *,
    proposal_id: uuid.UUID,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    decision_note: str,
) -> dict[str, Any]:
    """Decline a proposal, with a reason.

    The reason is REQUIRED. §4 of the revised specification puts what did not
    work into the evidence base on purpose; a rejection with no stated reason
    teaches the next person nothing and invites the same proposal again.
    """
    if not decision_note.strip():
        raise ResearchStateError("a rejected proposal must say why it was rejected")
    _load_open_proposal(session, proposal_id=proposal_id, organization_id=organization_id)

    try:
        with guarded_write(session):
            decided = session.execute(
                text(
                    """
                    UPDATE research.experiment_proposals
                       SET status = 'rejected',
                           decided_by = :actor,
                           decided_at = clock_timestamp(),
                           decision_note = :note
                     WHERE id = :pid AND organization_id = :org AND status = 'proposed'
                    RETURNING id
                    """
                ),
                {
                    "actor": actor_id,
                    "note": decision_note,
                    "pid": proposal_id,
                    "org": organization_id,
                },
            ).scalar_one_or_none()
    except DBAPIError as exc:
        raise _translate(exc) from exc
    if decided is None:
        raise ResearchStateError(
            "that proposal was decided by somebody else while this rejection was in flight"
        )

    write_audit(
        session,
        AuditEvent(
            action="EXPERIMENT_PROPOSAL_REJECTED",
            entity_type="experiment_proposal",
            entity_id=str(proposal_id),
            organization_id=organization_id,
            user_id=actor_id,
            previous_state={"status": "proposed"},
            new_state={"status": "rejected"},
            reason=decision_note,
        ),
    )
    return {"id": proposal_id, "status": "rejected"}
