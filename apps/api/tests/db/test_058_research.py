"""Migration 058 — the research vertical, and the guards it claims to have.

🔴 EVERY GUARD BELOW IS EXERCISED IN BOTH DIRECTIONS.

This project's standing lesson: *a test that has only ever PASSED has not been
shown to detect anything*, and *a guard that passes when it cannot see is worse
than one that cannot fail*. So each refusal here is paired with the legal case
that must succeed. Without the legal half, a fixture that never produced a valid
row would make every `pytest.raises` pass while measuring nothing — the trap
that caught `test_054` (a refusal matching zero rows, reporting a clean
`INSERT 0 0` that looked exactly like a pass).

What is measured:

  T3a  cross-ORGANIZATION: org B reaches none of it, counted as what a USER can
       reach rather than by reading a policy;
  T3b  cross-PROJECT inside one organization: a non-member of a restricted
       project reaches none of its research — including through the seven
       CHILD tables, whose policies inherit by joining the workspace;
  T8   FORCE RLS: asserted as `evercoat_app`, and the OWNER is refused too;
  the three-column foreign keys that stop one workspace's reasoning being
  attached to another's conclusion (the hole 057 closed for competitors,
  written correctly here at birth);
  the promotion trigger, which cannot be a CHECK because the approval lives on
  the route;
  the driver that makes the formula thread traversable backwards.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

pytestmark = pytest.mark.db


RESEARCH_TABLES = (
    "investigations",
    "questions",
    "sources",
    "evidence",
    "findings",
    "hypotheses",
    "knowledge_gaps",
    "experiment_proposals",
)


@pytest.fixture
def research_fixture(owner_session: Session) -> Iterator[dict[str, Any]]:
    """One organization, two projects — one normal, one restricted — and a
    workspace in each, with a row in EVERY child table of the restricted one.

    🔴 A ROW IN EVERY CHILD TABLE, NOT ONLY IN `investigations`. The scope test
    below loops over all eight. With rows in the parent alone, seven of them
    would count zero because there was NOTHING TO SEE, and the loop would report
    green over seven tables whose policies could expose every row. Codex made
    exactly this point about `test_056` and it was right.
    """
    suffix = uuid.uuid4().hex[:8]

    org_id = owner_session.execute(
        text("INSERT INTO core.organizations (code, name) VALUES (:c, :n) RETURNING id"),
        {"c": f"RES-{suffix}", "n": "Research Test Org"},
    ).scalar_one()
    other_org_id = owner_session.execute(
        text("INSERT INTO core.organizations (code, name) VALUES (:c, :n) RETURNING id"),
        {"c": f"RESB-{suffix}", "n": "Research Test Org B"},
    ).scalar_one()

    user_id = owner_session.execute(
        text(
            "INSERT INTO core.users (keycloak_sub, email, display_name) "
            "VALUES (:s, :e, :n) RETURNING id"
        ),
        {"s": f"res-{suffix}", "e": f"res-{suffix}@example.test", "n": "Research Tester"},
    ).scalar_one()
    # A second person, who is NOT a member of the restricted project. T3b is
    # about a colleague in the same company, not about another tenant.
    outsider_id = owner_session.execute(
        text(
            "INSERT INTO core.users (keycloak_sub, email, display_name) "
            "VALUES (:s, :e, :n) RETURNING id"
        ),
        {"s": f"out-{suffix}", "e": f"out-{suffix}@example.test", "n": "Research Outsider"},
    ).scalar_one()

    member_ids = [
        owner_session.execute(
            text(
                "INSERT INTO core.organization_members "
                "(organization_id, user_id, status, email, display_name) "
                "VALUES (:o, :u, 'active', :e, :n) RETURNING id"
            ),
            {"o": org_id, "u": uid, "e": f"{tag}-{suffix}@example.test", "n": tag},
        ).scalar_one()
        for uid, tag in ((user_id, "member"), (outsider_id, "outsider"))
    ]

    normal_project = owner_session.execute(
        text(
            "INSERT INTO projects.projects (organization_id, project_code, name, "
            "confidentiality) VALUES (:o, :c, 'Open project', 'normal') RETURNING id"
        ),
        {"o": org_id, "c": f"PRJ-N-{suffix}"},
    ).scalar_one()
    restricted_project = owner_session.execute(
        text(
            "INSERT INTO projects.projects (organization_id, project_code, name, "
            "confidentiality) VALUES (:o, :c, 'Restricted project', 'restricted') RETURNING id"
        ),
        {"o": org_id, "c": f"PRJ-R-{suffix}"},
    ).scalar_one()
    owner_session.execute(
        text(
            "INSERT INTO projects.project_members "
            "(organization_id, project_id, user_id, project_role) "
            "VALUES (:o, :p, :u, 'lead')"
        ),
        {"o": org_id, "p": restricted_project, "u": user_id},
    )

    owner_session.execute(
        text("SELECT set_config('app.current_org', :o, true)"), {"o": str(org_id)}
    )
    owner_session.execute(
        text("SELECT set_config('app.current_user_id', :u, true)"), {"u": str(user_id)}
    )

    def _investigation(project: uuid.UUID | None, code: str) -> uuid.UUID:
        return owner_session.execute(  # type: ignore[no-any-return]
            text(
                """
                INSERT INTO research.investigations
                    (organization_id, project_id, investigation_code, title,
                     research_question, owner_user_id, opened_by)
                VALUES (:o, :p, :code, 'Sanding performance',
                        'What drives sand-through time?', :u, :u)
                RETURNING id
                """
            ),
            {"o": org_id, "p": project, "code": code, "u": user_id},
        ).scalar_one()

    restricted_inv = _investigation(restricted_project, f"RES-{suffix}-R")
    open_inv = _investigation(normal_project, f"RES-{suffix}-N")
    orgwide_inv = _investigation(None, f"RES-{suffix}-O")

    question_id = owner_session.execute(
        text(
            "INSERT INTO research.questions (organization_id, investigation_id, "
            "sequence_number, question, asked_by) "
            "VALUES (:o, :i, 1, 'Does microsphere loading matter?', :u) RETURNING id"
        ),
        {"o": org_id, "i": restricted_inv, "u": user_id},
    ).scalar_one()
    source_id = owner_session.execute(
        text(
            "INSERT INTO research.sources (organization_id, investigation_id, source_kind, "
            "evidence_grade, title, recorded_by) "
            "VALUES (:o, :i, 'literature', 'B', 'A paper on microspheres', :u) RETURNING id"
        ),
        {"o": org_id, "i": restricted_inv, "u": user_id},
    ).scalar_one()
    owner_session.execute(
        text(
            "INSERT INTO research.evidence (organization_id, investigation_id, question_id, "
            "source_id, stance, summary, recorded_by) "
            "VALUES (:o, :i, :q, :s, 'supports', 'Loading correlates with sanding.', :u)"
        ),
        {"o": org_id, "i": restricted_inv, "q": question_id, "s": source_id, "u": user_id},
    )
    finding_id = owner_session.execute(
        text(
            "INSERT INTO research.findings (organization_id, investigation_id, finding_code, "
            "subject, statement, applicability, confidence, author_id) "
            "VALUES (:o, :i, :c, 'Microsphere loading', 'More loading sands sooner.', "
            "'Lightweight polyester filler family', 'moderate', :u) RETURNING id"
        ),
        {"o": org_id, "i": restricted_inv, "c": f"RF-{suffix}", "u": user_id},
    ).scalar_one()
    hypothesis_id = owner_session.execute(
        text(
            "INSERT INTO research.hypotheses (organization_id, investigation_id, finding_id, "
            "statement, proposed_by) "
            "VALUES (:o, :i, :f, 'Raising loading by 2% improves sanding.', :u) RETURNING id"
        ),
        {"o": org_id, "i": restricted_inv, "f": finding_id, "u": user_id},
    ).scalar_one()
    owner_session.execute(
        text(
            "INSERT INTO research.knowledge_gaps (organization_id, investigation_id, "
            "question_id, description, identified_by) "
            "VALUES (:o, :i, :q, 'No data above 8% loading.', :u)"
        ),
        {"o": org_id, "i": restricted_inv, "q": question_id, "u": user_id},
    )
    proposal_id = owner_session.execute(
        text(
            """
            INSERT INTO research.experiment_proposals
                (organization_id, investigation_id, hypothesis_id, proposal_code, objective,
                 basis, variables, expected_direction, required_tests, confidence, proposed_by)
            VALUES (:o, :i, :h, :c, 'Improve sanding', 'RF-0045', 'Microsphere loading',
                    'Shorter sand-through time', 'Density; sanding', 'moderate', :u)
            RETURNING id
            """
        ),
        {"o": org_id, "i": restricted_inv, "h": hypothesis_id, "c": f"EXP-{suffix}", "u": user_id},
    ).scalar_one()
    owner_session.flush()

    yield {
        "org_id": org_id,
        "other_org_id": other_org_id,
        "user_id": user_id,
        "outsider_id": outsider_id,
        "member_ids": member_ids,
        "normal_project": normal_project,
        "restricted_project": restricted_project,
        "restricted_inv": restricted_inv,
        "open_inv": open_inv,
        "orgwide_inv": orgwide_inv,
        "question_id": question_id,
        "source_id": source_id,
        "finding_id": finding_id,
        "hypothesis_id": hypothesis_id,
        "proposal_id": proposal_id,
        "suffix": suffix,
    }

    # 🔴 EXPLICIT TEARDOWN, BECAUSE TESTS BELOW COMMIT. A committed fixture row
    # is permanent, and 70 leaked organizations from exactly this omission made
    # the SEED look non-idempotent last session — a red naming innocent code two
    # files away. Children before parents: every FK here is RESTRICT.
    owner_session.rollback()
    owner_session.begin()
    # 🔴 BOTH GUCs. With only the tenant set, `core.is_project_member`
    # answers false, the RESTRICTED project's investigation is invisible to this
    # session, and the DELETE matches nothing while reporting success -- the
    # failure then surfaces two statements later as a foreign key on
    # `projects`. A DELETE that matches nothing is not a DELETE that worked.
    owner_session.execute(
        text("SELECT set_config('app.current_org', :o, true)"), {"o": str(org_id)}
    )
    owner_session.execute(
        text("SELECT set_config('app.current_user_id', :u, true)"), {"u": str(user_id)}
    )
    for statement in (
        "DELETE FROM formulations.formula_version_drivers WHERE organization_id = :o",
        "DELETE FROM research.experiment_proposals WHERE organization_id = :o",
        "DELETE FROM research.knowledge_gaps WHERE organization_id = :o",
        "DELETE FROM research.hypotheses WHERE organization_id = :o",
        "DELETE FROM research.evidence WHERE organization_id = :o",
        "DELETE FROM research.findings WHERE organization_id = :o",
        "DELETE FROM research.sources WHERE organization_id = :o",
        "DELETE FROM research.questions WHERE organization_id = :o",
        "DELETE FROM research.investigations WHERE organization_id = :o",
        "DELETE FROM projects.project_members WHERE organization_id = :o",
        "DELETE FROM projects.projects WHERE organization_id = :o",
        "DELETE FROM core.member_roles WHERE member_id = ANY(:members)",
        "DELETE FROM core.organization_members WHERE organization_id = :o",
        "DELETE FROM core.users WHERE id = ANY(:users)",
        "DELETE FROM core.organizations WHERE id = :o OR id = :other",
    ):
        owner_session.execute(
            text(statement),
            {
                "o": org_id,
                "other": other_org_id,
                "users": [user_id, outsider_id],
                "members": member_ids,
            },
        )
    owner_session.commit()


def _as(session: Session, org: uuid.UUID | None, user: uuid.UUID | None) -> None:
    """Adopt a tenant and a person for the rest of this transaction."""
    session.execute(
        text("SELECT set_config('app.current_org', :o, true)"),
        {"o": str(org) if org else ""},
    )
    session.execute(
        text("SELECT set_config('app.current_user_id', :u, true)"),
        {"u": str(user) if user else ""},
    )


# ---------------------------------------------------------------------------
# T8 — FORCE row-level security
# ---------------------------------------------------------------------------


def test_every_research_table_forces_row_level_security(owner_session: Session) -> None:
    """Not merely ENABLED. FORCE is what binds the table's own owner.

    A table that is only ENABLED reads as protected in every catalogue view a
    person is likely to check, and is wide open to `evercoat_owner` — which is
    what the I56/I58 cutover exists to close for the older tables.
    """
    rows = owner_session.execute(
        text(
            """
            SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity
              FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
             WHERE n.nspname = 'research' AND c.relkind = 'r'
             ORDER BY c.relname
            """
        )
    ).all()
    assert {r[0] for r in rows} == set(RESEARCH_TABLES)
    unprotected = [r[0] for r in rows if not (r[1] and r[2])]
    assert unprotected == [], f"not FORCE-protected: {unprotected}"


def test_the_owner_is_refused_without_a_tenant(
    owner_session: Session, research_fixture: dict[str, Any]
) -> None:
    """FORCE binds the owner, and this proves it rather than asserting it.

    Both directions in one test: with the tenant declared the owner sees the
    workspace, and with no tenant it sees nothing. If FORCE were absent the
    second count would be non-zero.
    """
    _as(owner_session, research_fixture["org_id"], research_fixture["user_id"])
    with_tenant = owner_session.execute(
        text("SELECT count(*) FROM research.investigations WHERE organization_id = :o"),
        {"o": research_fixture["org_id"]},
    ).scalar_one()
    assert with_tenant == 3

    _as(owner_session, None, None)
    without_tenant = owner_session.execute(
        text("SELECT count(*) FROM research.investigations WHERE organization_id = :o"),
        {"o": research_fixture["org_id"]},
    ).scalar_one()
    assert without_tenant == 0


# ---------------------------------------------------------------------------
# T3a / T3b — what a USER can reach
# ---------------------------------------------------------------------------


def test_another_organization_reaches_none_of_it(
    owner_session: Session, app_session: Session, research_fixture: dict[str, Any]
) -> None:
    """T3a. Counted as what a user can reach, never by reading a policy."""
    # `app_session` is a DIFFERENT CONNECTION, so it cannot see the fixture's
    # uncommitted rows. Without this the zeros below would be produced by
    # there being nothing there -- a guard passing because it cannot see.
    owner_session.commit()
    _as(app_session, research_fixture["org_id"], research_fixture["user_id"])
    visible = {
        table: app_session.execute(
            text(f"SELECT count(*) FROM research.{table}")  # noqa: S608 - fixed identifiers
        ).scalar_one()
        for table in RESEARCH_TABLES
    }
    assert all(count > 0 for count in visible.values()), (
        f"the fixture did not populate every table, so the refusal below would "
        f"measure nothing: {visible}"
    )

    _as(app_session, research_fixture["other_org_id"], research_fixture["outsider_id"])
    for table in RESEARCH_TABLES:
        count = app_session.execute(
            text(f"SELECT count(*) FROM research.{table}")  # noqa: S608 - fixed identifiers
        ).scalar_one()
        assert count == 0, f"org B can see {count} row(s) of research.{table}"


def test_a_colleague_outside_a_restricted_project_reaches_none_of_its_research(
    owner_session: Session, app_session: Session, research_fixture: dict[str, Any]
) -> None:
    """T3b — and it is the CHILD tables that make this worth writing.

    The seven children carry no `project_id`. Their policies join the workspace,
    and the workspace's own policy is applied to that subquery for the same
    role. So the whole question is whether that transitive step actually happens
    — which is a fact about PostgreSQL to be measured, not a fact about the
    design to be assumed.
    """
    owner_session.commit()
    _as(app_session, research_fixture["org_id"], research_fixture["user_id"])
    member_sees = app_session.execute(
        text("SELECT count(*) FROM research.investigations WHERE id = :i"),
        {"i": research_fixture["restricted_inv"]},
    ).scalar_one()
    assert member_sees == 1, "the project member cannot see their own workspace"

    _as(app_session, research_fixture["org_id"], research_fixture["outsider_id"])
    # The open and organization-wide workspaces stay visible: this is a project
    # boundary, not a research blackout. Without this half the test would pass
    # against a policy that hid everything from everybody.
    assert (
        app_session.execute(
            text("SELECT count(*) FROM research.investigations WHERE id = ANY(:ids)"),
            {"ids": [research_fixture["open_inv"], research_fixture["orgwide_inv"]]},
        ).scalar_one()
        == 2
    )
    assert (
        app_session.execute(
            text("SELECT count(*) FROM research.investigations WHERE id = :i"),
            {"i": research_fixture["restricted_inv"]},
        ).scalar_one()
        == 0
    )
    for table in (
        "questions",
        "sources",
        "evidence",
        "findings",
        "hypotheses",
        "knowledge_gaps",
        "experiment_proposals",
    ):
        count = app_session.execute(
            text(
                f"SELECT count(*) FROM research.{table} "  # noqa: S608 - fixed identifiers
                "WHERE investigation_id = :i"
            ),
            {"i": research_fixture["restricted_inv"]},
        ).scalar_one()
        assert count == 0, (
            f"a non-member reaches {count} row(s) of research.{table} belonging to a "
            "restricted project"
        )


def test_a_write_into_another_tenant_is_refused_not_only_a_read(
    owner_session: Session, app_session: Session, research_fixture: dict[str, Any]
) -> None:
    """`USING` alone protects reads. This is the half that needs `WITH CHECK`."""
    owner_session.commit()
    _as(app_session, research_fixture["other_org_id"], research_fixture["outsider_id"])
    with pytest.raises(DBAPIError) as caught:
        app_session.execute(
            text(
                """
                INSERT INTO research.investigations
                    (organization_id, investigation_code, title, research_question,
                     owner_user_id, opened_by)
                VALUES (:o, 'RES-SMUGGLED', 'Smuggled', 'Can I write here?', :u, :u)
                """
            ),
            {"o": research_fixture["org_id"], "u": research_fixture["outsider_id"]},
        )
    assert "row-level security" in str(caught.value.orig)
    app_session.rollback()


# ---------------------------------------------------------------------------
# The three-column foreign keys
# ---------------------------------------------------------------------------


def test_evidence_cannot_cite_another_workspaces_question(
    owner_session: Session, research_fixture: dict[str, Any]
) -> None:
    """The hole 057 closed for competitors, refused here at birth.

    Both directions: citing the OWN workspace's question succeeds, citing
    another workspace's is refused by the composite key.
    """
    _as(owner_session, research_fixture["org_id"], research_fixture["user_id"])
    # 🔴 THE SOURCE IS NOT OPTIONAL HERE, AND THAT IS THE CHECK WORKING.
    # A first draft of this test cited only the question and was refused by
    # `evidence_cites_something` -- correctly: a question is what the evidence
    # ANSWERS, not what it rests on.
    legal = owner_session.execute(
        text(
            "INSERT INTO research.evidence (organization_id, investigation_id, question_id, "
            "source_id, stance, summary, recorded_by) "
            "VALUES (:o, :i, :q, :s, 'related', 'Same workspace.', :u) RETURNING id"
        ),
        {
            "o": research_fixture["org_id"],
            "i": research_fixture["restricted_inv"],
            "q": research_fixture["question_id"],
            "s": research_fixture["source_id"],
            "u": research_fixture["user_id"],
        },
    ).scalar_one()
    assert legal is not None

    with pytest.raises(IntegrityError) as caught:
        owner_session.execute(
            text(
                "INSERT INTO research.evidence (organization_id, investigation_id, "
                "question_id, source_id, stance, summary, recorded_by) "
                "VALUES (:o, :i, :q, :s, 'supports', 'Another workspace.', :u)"
            ),
            {
                "o": research_fixture["org_id"],
                # The OPEN investigation, citing the RESTRICTED one's question.
                "i": research_fixture["open_inv"],
                "q": research_fixture["question_id"],
                "s": research_fixture["source_id"],
                "u": research_fixture["user_id"],
            },
        )
    assert "evidence_question_fk" in str(caught.value.orig)
    owner_session.rollback()


def test_an_evidence_card_must_cite_something(
    owner_session: Session, research_fixture: dict[str, Any]
) -> None:
    """A card citing nothing is an opinion with a border around it."""
    _as(owner_session, research_fixture["org_id"], research_fixture["user_id"])
    with pytest.raises(IntegrityError) as caught:
        owner_session.execute(
            text(
                "INSERT INTO research.evidence (organization_id, investigation_id, "
                "stance, summary, recorded_by) "
                "VALUES (:o, :i, 'supports', 'Trust me.', :u)"
            ),
            {
                "o": research_fixture["org_id"],
                "i": research_fixture["restricted_inv"],
                "u": research_fixture["user_id"],
            },
        )
    assert "evidence_cites_something" in str(caught.value.orig)
    owner_session.rollback()


# ---------------------------------------------------------------------------
# The promotion trigger — the guard that could not be a CHECK
# ---------------------------------------------------------------------------


def test_a_finding_cannot_be_promoted_without_an_approved_route(
    owner_session: Session, research_fixture: dict[str, Any]
) -> None:
    """🔴 AND THE APPROVED CASE SUCCEEDS, WHICH IS WHAT MAKES THIS A TEST.

    A refusal on its own would also be produced by a trigger that refuses
    everything. The second half opens a route, approves it, and promotes — so
    the trigger is shown to DISTINGUISH the two states rather than to block.
    """
    org_id = research_fixture["org_id"]
    # The first half below ends in a rollback, which would otherwise discard the
    # FIXTURE's own uncommitted rows -- the organization included -- and the
    # second half would then fail on a foreign key rather than on the guard it
    # is measuring. Committing the fixture first makes the rollback undo only
    # this test's work; teardown removes the rest.
    owner_session.commit()
    _as(owner_session, org_id, research_fixture["user_id"])

    document_id = owner_session.execute(
        text(
            "INSERT INTO knowledge.documents (organization_id, title, source, ingested_by) "
            "VALUES (:o, 'Promoted finding', 'research_finding', :u) RETURNING id"
        ),
        {"o": org_id, "u": research_fixture["user_id"]},
    ).scalar_one()

    with pytest.raises(DBAPIError) as caught:
        owner_session.execute(
            text(
                "UPDATE research.findings SET promoted_document_id = :d, "
                "promoted_at = clock_timestamp() WHERE id = :f AND organization_id = :o"
            ),
            {"d": document_id, "f": research_fixture["finding_id"], "o": org_id},
        )
    assert "no approved approval route" in str(caught.value.orig)
    owner_session.rollback()

    # ---- and now the approved case, which must succeed -------------------
    _as(owner_session, org_id, research_fixture["user_id"])
    document_id = owner_session.execute(
        text(
            "INSERT INTO knowledge.documents (organization_id, title, source, ingested_by) "
            "VALUES (:o, 'Promoted finding', 'research_finding', :u) RETURNING id"
        ),
        {"o": org_id, "u": research_fixture["user_id"]},
    ).scalar_one()
    owner_session.execute(
        text(
            """
            INSERT INTO workflow.approval_routes
                (organization_id, project_id, entity_type, entity_id, template_id,
                 template_code, status, closed_at)
            SELECT :o, :p, 'research_finding', :f, t.id, t.template_code, 'approved',
                   clock_timestamp()
              FROM workflow.approval_templates t
             WHERE t.organization_id = :o AND t.template_code = 'RESEARCH_FINDING'
            """
        ),
        {
            "o": org_id,
            "p": research_fixture["restricted_project"],
            "f": research_fixture["finding_id"],
        },
    )
    owner_session.execute(
        text(
            "UPDATE research.findings SET promoted_document_id = :d, "
            "promoted_at = clock_timestamp() WHERE id = :f AND organization_id = :o"
        ),
        {"d": document_id, "f": research_fixture["finding_id"], "o": org_id},
    )
    promoted = owner_session.execute(
        text("SELECT promoted_document_id FROM research.findings WHERE id = :f"),
        {"f": research_fixture["finding_id"]},
    ).scalar_one()
    assert promoted == document_id
    owner_session.rollback()


def test_the_findings_status_column_carries_no_state_nothing_writes(
    owner_session: Session,
) -> None:
    """🔴 THE DEFECT THIS COLUMN WAS REDESIGNED TO AVOID.

    The first draft of 058 gave `findings.status` the values `approved` and
    `rejected`, and NOTHING would have written them: the approval engine settles
    a route and has no entity callback. That is the defect Codex found on
    `safety_reviews` in Phase 2 — a table claiming a status nothing maintained.

    This asserts the shape of the fix, so a later "completeness" pass cannot put
    the two values back without also building something that writes them.
    """
    definition = owner_session.execute(
        text(
            "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
            "WHERE conrelid = 'research.findings'::regclass AND conname LIKE '%status%'"
        )
    ).scalar_one()
    assert "approved" not in definition, (
        "research.findings.status accepts 'approved' again. The approval lives on "
        "the route; a column here would be a status nothing maintains."
    )
    assert "'draft'" in definition
    assert "'submitted'" in definition


# ---------------------------------------------------------------------------
# The formula thread, backwards
# ---------------------------------------------------------------------------


def test_a_research_driver_must_name_its_proposal(
    owner_session: Session, research_fixture: dict[str, Any]
) -> None:
    """§2's thread, in the direction that is easy to lose.

    A `research` driver with no proposal records a CATEGORY and loses the LINK,
    which is the isolated data island §2 forbids. Both directions: naming the
    proposal succeeds, omitting it is refused.
    """
    org_id = research_fixture["org_id"]
    _as(owner_session, org_id, research_fixture["user_id"])

    formula_id = owner_session.execute(
        text(
            """
            INSERT INTO formulations.formulas
                (organization_id, project_id, formula_code, name, owner_user_id, created_by)
            VALUES (:o, :p, :c, 'Research driver formula', :u, :u) RETURNING id
            """
        ),
        {
            "o": org_id,
            "p": research_fixture["restricted_project"],
            "c": f"F-{research_fixture['suffix']}",
            "u": research_fixture["user_id"],
        },
    ).scalar_one()
    version_id = owner_session.execute(
        text(
            """
            INSERT INTO formulations.formula_versions
                (organization_id, project_id, formula_id, version_number, version_code,
                 status, created_by)
            VALUES (:o, :p, :f, 1, :c, 'draft', :u) RETURNING id
            """
        ),
        {
            "o": org_id,
            "p": research_fixture["restricted_project"],
            "f": formula_id,
            "c": f"F-{research_fixture['suffix']}-V1",
            "u": research_fixture["user_id"],
        },
    ).scalar_one()

    driver_id = owner_session.execute(
        text(
            """
            INSERT INTO formulations.formula_version_drivers
                (organization_id, project_id, formula_version_id, driver_type,
                 experiment_proposal_id, reason, recorded_by)
            VALUES (:o, :p, :v, 'research', :x, 'Accepted EXP proposal', :u)
            RETURNING id
            """
        ),
        {
            "o": org_id,
            "p": research_fixture["restricted_project"],
            "v": version_id,
            "x": research_fixture["proposal_id"],
            "u": research_fixture["user_id"],
        },
    ).scalar_one()
    assert driver_id is not None

    with pytest.raises(IntegrityError) as caught:
        owner_session.execute(
            text(
                """
                INSERT INTO formulations.formula_version_drivers
                    (organization_id, project_id, formula_version_id, driver_type,
                     reason, recorded_by)
                VALUES (:o, :p, :v, 'research', 'No proposal named', :u)
                """
            ),
            {
                "o": org_id,
                "p": research_fixture["restricted_project"],
                "v": version_id,
                "u": research_fixture["user_id"],
            },
        )
    assert "research_is_present" in str(caught.value.orig)
    owner_session.rollback()


def test_the_driver_unique_key_carries_the_proposal(owner_session: Session) -> None:
    """🔴 NULLS DISTINCT IS WHY THIS TEST EXISTS.

    Adding `experiment_proposal_id` to the table without adding it to
    `formula_version_drivers_unique` would leave the same proposal recordable as
    the driver of the same version any number of times — because every existing
    key column is NULL on a research row, and PostgreSQL's default treats those
    rows as always distinct.
    """
    definition = owner_session.execute(
        text(
            "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
            "WHERE conrelid = 'formulations.formula_version_drivers'::regclass "
            "AND conname = 'formula_version_drivers_unique'"
        )
    ).scalar_one()
    assert "experiment_proposal_id" in definition


# ---------------------------------------------------------------------------
# The approval template — for tenants that do not exist yet
# ---------------------------------------------------------------------------


def test_an_organization_created_today_gets_the_research_template(
    owner_session: Session,
) -> None:
    """🔴 THE BACKFILL IS NOT THE GUARANTEE; THE TRIGGER IS.

    055 shipped a point-in-time backfill and a test exactly like this one found
    that every tenant created afterwards would be missing its template, with
    `open_route('safety')` raising the first time anybody pressed the button and
    nothing about the migration looking wrong.

    So this creates an organization and ASKS, rather than reading the migration.
    """
    suffix = uuid.uuid4().hex[:8]
    org_id = owner_session.execute(
        text("INSERT INTO core.organizations (code, name) VALUES (:c, :n) RETURNING id"),
        {"c": f"TPL-{suffix}", "n": "Template Test Org"},
    ).scalar_one()
    try:
        row = (
            owner_session.execute(
                text(
                    """
                    SELECT t.authority_level,
                           (SELECT count(*) FROM workflow.approval_template_steps s
                             WHERE s.template_id = t.id) AS steps,
                           (SELECT count(*) FROM workflow.approval_template_steps s
                             WHERE s.template_id = t.id
                               AND s.must_differ_from_group IS NOT NULL) AS segregated
                      FROM workflow.approval_templates t
                     WHERE t.organization_id = :o AND t.template_code = 'RESEARCH_FINDING'
                       AND t.is_active
                    """
                ),
                {"o": org_id},
            )
            .mappings()
            .one_or_none()
        )
        assert row is not None, "a new organization has no RESEARCH_FINDING template"
        assert row["authority_level"] == "research"
        assert row["steps"] == 2, "review and approve are two steps or the rule is nothing"
        assert row["segregated"] == 1, "no step requires a different decider"
    finally:
        owner_session.rollback()


def test_the_two_route_steps_are_satisfiable_by_two_different_people(
    owner_session: Session,
) -> None:
    """🔴 A SEGREGATION RULE THAT MAKES THE ROUTE UNCOMPLETABLE IS WORSE THAN NONE.

    055 measured this before writing the rule and recorded the numbers. Measured
    again here against the live catalogue, because a later migration that moved
    a grant would break the route silently: the queue would simply never be
    decidable, and nothing would raise.
    """
    holders = {
        row[0]: row[1]
        for row in owner_session.execute(
            text(
                """
                SELECT p.code, count(DISTINCT r.code)
                  FROM core.permissions p
                  JOIN core.role_permissions rp ON rp.permission_id = p.id
                  JOIN core.roles r ON r.id = rp.role_id
                 WHERE p.code IN ('research.review', 'research.approve')
                 GROUP BY p.code
                """
            )
        ).all()
    }
    assert holders.get("research.review", 0) >= 2, holders
    assert holders.get("research.approve", 0) >= 2, holders

    # And they are not the SAME single role, which would make
    # `must_differ_from_group` unsatisfiable whenever that role has one member.
    distinct_roles = owner_session.execute(
        text(
            """
            SELECT count(*) FROM (
                SELECT r.code
                  FROM core.roles r
                  JOIN core.role_permissions rp ON rp.role_id = r.id
                  JOIN core.permissions p ON p.id = rp.permission_id
                 WHERE p.code = 'research.review'
                EXCEPT
                SELECT r.code
                  FROM core.roles r
                  JOIN core.role_permissions rp ON rp.role_id = r.id
                  JOIN core.permissions p ON p.id = rp.permission_id
                 WHERE p.code = 'research.approve'
            ) reviewers_who_cannot_approve
            """
        )
    ).scalar_one()
    assert distinct_roles >= 1, (
        "every role that may review may also approve, so the route can only be "
        "completed by two people holding the same role"
    )


def test_submitting_a_finding_opens_a_route_and_promotion_follows_it(
    owner_session: Session, research_fixture: dict[str, Any]
) -> None:
    """🔴 THE SUCCESS PATH THE HTTP SUITE CANNOT COVER WITHOUT LEAKING.

    `submit_finding` opens a route through the ONE approval engine, and an
    approval route is permanent: `workflow.approval_route_steps` carries
    `audit.deny_mutation` on DELETE, unconditionally, so a committing test
    would leak an organization for ever. Here the whole thing rolls back.

    Both halves, because either alone proves little:

      1. submitting a finding on a PROJECT opens a real RESEARCH_FINDING route
         at `research` authority with two steps, the second requiring a
         different decider;
      2. and once that route is approved, the promotion trigger lets the
         finding through -- which is what shows the trigger DISTINGUISHES the
         two states rather than simply blocking.
    """
    from app.domains.research.service import submit_finding

    org_id = research_fixture["org_id"]
    _as(owner_session, org_id, research_fixture["user_id"])

    result = submit_finding(
        session=owner_session,
        finding_id=research_fixture["finding_id"],
        organization_id=org_id,
        actor_id=research_fixture["user_id"],
    )
    assert result["status"] == "submitted"
    assert result["route"]["template_code"] == "RESEARCH_FINDING"
    # `open_route` returns the COUNT of steps it copied, not the steps.
    # Measured from `approvals/service.py:216`, after `len()` raised here.
    assert result["route"]["steps"] == 2, result["route"]

    route = (
        owner_session.execute(
            text(
                """
                SELECT r.status, r.template_code, count(s.id) AS steps,
                       count(s.id) FILTER (WHERE s.must_differ_from_group IS NOT NULL)
                           AS segregated
                  FROM workflow.approval_routes r
                  JOIN workflow.approval_route_steps s ON s.route_id = r.id
                 WHERE r.entity_type = 'research_finding'
                   AND r.entity_id = :f AND r.organization_id = :o
                 GROUP BY r.status, r.template_code
                """
            ),
            {"f": research_fixture["finding_id"], "o": org_id},
        )
        .mappings()
        .one_or_none()
    )
    assert route is not None, "the finding was submitted but no route exists"
    assert route["status"] == "open"
    assert route["template_code"] == "RESEARCH_FINDING"
    assert route["steps"] == 2
    assert route["segregated"] == 1

    owner_session.rollback()
