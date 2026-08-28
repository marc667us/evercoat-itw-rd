"""Migration 054/055 — the Material Safety Data schema, falsified.

🔴 EVERY GUARD HERE IS BROKEN ON PURPOSE BEFORE IT IS TRUSTED.

This project's recurring lesson is that a test which has only ever PASSED has
not been shown to detect anything. So each rule below is exercised in both
directions: the legal case must succeed, and the illegal case must be REFUSED
for the stated reason.

That mattered immediately. Writing these by hand against the development
database, the first attempt at `test_a_non_sds_document_is_refused` matched
ZERO ROWS -- the database holds only SDS documents -- and reported a clean
`INSERT 0 0`. It looked exactly like a pass. The test now BUILDS the document
it needs, so the guard actually executes.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

pytestmark = pytest.mark.db


# ---------------------------------------------------------------------------
# Fixtures — one organization, one material, one usable SDS
# ---------------------------------------------------------------------------


@pytest.fixture
def safety_fixture(owner_session: Session) -> dict[str, uuid.UUID]:
    """An organization with a material and one approved, scan-clean SDS."""
    suffix = uuid.uuid4().hex[:8]

    org_id = owner_session.execute(
        text(
            "INSERT INTO core.organizations (code, name) VALUES (:c, :n) RETURNING id"
        ),
        {"c": f"SAFE-{suffix}", "n": "Safety Test Org"},
    ).scalar_one()

    # `keycloak_sub`, `email`, `display_name` -- all NOT NULL. There is no
    # `subject` column: 047 and 052 established that an authentication
    # identifier is not a readable attribute of a tenant-visible row.
    user_id = owner_session.execute(
        text(
            "INSERT INTO core.users (keycloak_sub, email, display_name) "
            "VALUES (:s, :e, :n) RETURNING id"
        ),
        {"s": f"safety-{suffix}", "e": f"safety-{suffix}@example.test", "n": "Safety Tester"},
    ).scalar_one()
    # 🔴 THE MEMBERSHIP CARRIES THE NAME AND THE ADDRESS, NOT THE IDENTITY.
    # Migration 052: an identity has no tenant attributes. `email` and
    # `display_name` are NOT NULL *here*, which is why `list_messages` reads
    # attribution from `core.organization_members` rather than `core.users`.
    owner_session.execute(
        text(
            "INSERT INTO core.organization_members "
            "(organization_id, user_id, status, email, display_name) "
            "VALUES (:o, :u, 'active', :e, :n)"
        ),
        {
            "o": org_id,
            "u": user_id,
            "e": f"safety-{suffix}@example.test",
            "n": "Safety Tester",
        },
    )

    material_id = owner_session.execute(
        text(
            """
            INSERT INTO materials.materials
                (organization_id, material_code, name, category, role, status, created_by)
            VALUES (:o, :code, 'Test resin', 'Resin', 'resin', 'approved', :u)
            RETURNING id
            """
        ),
        {"o": org_id, "code": f"RM-{suffix}", "u": user_id},
    ).scalar_one()

    document_id = _make_document(owner_session, org_id, material_id, user_id, suffix, "SDS")
    owner_session.flush()

    # 🔴 EVEN THE OWNER MUST DECLARE A TENANT HERE, AND THAT IS NEW.
    #
    # `safety.*` is the first schema in this codebase created with FORCE ROW
    # LEVEL SECURITY, so its policies bind the table owner as well as
    # `evercoat_app`. Every other `owner_session` fixture in this suite writes
    # freely because the older tables are not forced -- which is exactly the
    # gap I56/I58 exists to close.
    #
    # Without this line the INSERTs below fail with "new row violates row-level
    # security policy", which is the guard doing its job, not a defect.
    owner_session.execute(
        text("SELECT set_config('app.current_org', :o, true)"), {"o": str(org_id)}
    )

    return {
        "org_id": org_id,
        "user_id": user_id,
        "material_id": material_id,
        "document_id": document_id,
    }


def _make_document(
    session: Session,
    org_id: uuid.UUID,
    material_id: uuid.UUID,
    user_id: uuid.UUID,
    suffix: str,
    document_type: str,
    status: str = "approved",
) -> uuid.UUID:
    """An APPROVED, scan-clean, unexpired, unsuperseded document.

    Every column 036's `material_documents_approved_has_evidence` demands is
    supplied, so the row genuinely appears in `materials.usable_documents`.
    A fixture that produced a quarantined row would make every refusal below
    pass for the wrong reason.
    """
    return session.execute(  # type: ignore[no-any-return]
        text(
            """
            INSERT INTO materials.material_documents
                (organization_id, material_id, document_type, title, storage_key,
                 content_type, byte_size, checksum_sha256, status, scan_status,
                 scanner_name, scanner_version, scanned_at, uploaded_by)
            VALUES (:o, :m, :dt, :title, :key, 'application/pdf', 2048,
                    :checksum, :status, 'clean', 'test-scanner', '1.0', now(), :u)
            RETURNING id
            """
        ),
        {
            "o": org_id,
            "m": material_id,
            "dt": document_type,
            "title": f"{document_type} for testing",
            "key": f"test/{document_type}-{suffix}-{uuid.uuid4().hex[:6]}",
            "checksum": uuid.uuid4().hex + uuid.uuid4().hex,
            "status": status,
            "u": user_id,
        },
    ).scalar_one()


def _interpret(session: Session, fixture: dict[str, uuid.UUID], **overrides: object) -> uuid.UUID:
    params = {
        "o": fixture["org_id"],
        "d": overrides.get("document_id", fixture["document_id"]),
        "m": overrides.get("material_id", fixture["material_id"]),
        "u": fixture["user_id"],
    }
    return session.execute(  # type: ignore[no-any-return]
        text(
            """
            INSERT INTO safety.sds_versions
                (organization_id, document_id, material_id, interpreted_by)
            VALUES (:o, :d, :m, :u) RETURNING id
            """
        ),
        params,
    ).scalar_one()


# ---------------------------------------------------------------------------
# S1a — creation requires a USABLE document. Four refusals, one success.
# ---------------------------------------------------------------------------


def test_a_usable_sds_can_be_interpreted(owner_session: Session, safety_fixture) -> None:
    """The legal case. Without this, the four refusals below prove nothing:
    a trigger that refuses everything would pass them all."""
    version_id = _interpret(owner_session, safety_fixture)
    assert version_id is not None


def test_an_unusable_document_is_refused(owner_session: Session, safety_fixture) -> None:
    """A quarantined document is not evidence."""
    # 🔴 CREATED QUARANTINED, NOT APPROVED-THEN-DOWNGRADED.
    #
    # The first version of this test approved a document and then UPDATEd its
    # status, and migration 038's write-once trigger refused: *"a verdict is
    # safety evidence: supersede it with a new row rather than rewriting this
    # one."* That refusal is correct and the test was wrong -- and had it been
    # written the other way round, it would have passed on 038's error message
    # while proving nothing at all about 054's trigger.
    doc = _make_document(
        owner_session,
        safety_fixture["org_id"],
        safety_fixture["material_id"],
        safety_fixture["user_id"],
        "quar",
        "SDS",
        status="quarantined",
    )
    owner_session.flush()

    assert (
        owner_session.execute(
            text("SELECT count(*) FROM materials.usable_documents WHERE id = :d"), {"d": doc}
        ).scalar_one()
        == 0
    ), "the quarantined document is somehow usable; this test would prove nothing"

    with pytest.raises(DBAPIError, match="not a usable document"):
        _interpret(owner_session, safety_fixture, document_id=doc)


def test_a_non_sds_document_is_refused(owner_session: Session, safety_fixture) -> None:
    """🔴 THE TEST THAT SILENTLY MATCHED ZERO ROWS ON THE FIRST ATTEMPT.

    The development database holds only SDS documents, so a test that selected
    an existing non-SDS row inserted nothing and reported success. The TDS is
    built here, and its presence in `usable_documents` is asserted FIRST, so
    the refusal that follows can only be about the document TYPE.
    """
    tds = _make_document(
        owner_session,
        safety_fixture["org_id"],
        safety_fixture["material_id"],
        safety_fixture["user_id"],
        "tds",
        "TDS",
    )
    owner_session.flush()

    usable = owner_session.execute(
        text("SELECT count(*) FROM materials.usable_documents WHERE id = :d"), {"d": tds}
    ).scalar_one()
    assert usable == 1, (
        "the TDS is not usable, so a refusal below would be about usability "
        "and this test would prove nothing about document type"
    )

    with pytest.raises(DBAPIError, match="is a TDS, not an SDS"):
        _interpret(owner_session, safety_fixture, document_id=tds)


def test_a_document_material_mismatch_is_refused(owner_session: Session, safety_fixture) -> None:
    """Two composite FKs both hold even when these point at different materials."""
    other_material = owner_session.execute(
        text(
            """
            INSERT INTO materials.materials
                (organization_id, material_code, name, category, role, status, created_by)
            VALUES (:o, :c, 'Another', 'Filler', 'filler', 'approved', :u) RETURNING id
            """
        ),
        {"o": safety_fixture["org_id"], "c": f"RM-OTHER-{uuid.uuid4().hex[:6]}", "u": safety_fixture["user_id"]},
    ).scalar_one()
    with pytest.raises(DBAPIError, match="belongs to material"):
        _interpret(owner_session, safety_fixture, material_id=other_material)


def test_one_interpretation_per_document(owner_session: Session, safety_fixture) -> None:
    """A second reading of the same sheet would leave two answers on file."""
    _interpret(owner_session, safety_fixture)
    owner_session.flush()
    with pytest.raises(IntegrityError):
        _interpret(owner_session, safety_fixture)
        owner_session.flush()


# ---------------------------------------------------------------------------
# S1b / S1c — history survives supersession; currency is derived
# ---------------------------------------------------------------------------


def test_an_interpretation_survives_its_document_being_superseded(
    owner_session: Session, safety_fixture
) -> None:
    """🔴 THE TRAP THIS SCHEMA WAS REDESIGNED AROUND.

    `materials.usable_documents` excludes a document that a newer APPROVED
    revision supersedes (037:79-84). A rule of "interpretations only exist for
    usable documents" would therefore have destroyed revision comparison at
    exactly the moment it became possible -- comparison needs the previous
    revision, which is superseded by definition.

    So: the interpretation must STILL BE READABLE (S1b), while the current
    position must NOT return it (S1c). Both halves asserted, because either
    one alone is satisfiable by a broken implementation.
    """
    old_version = _interpret(owner_session, safety_fixture)
    owner_session.flush()

    # A newer approved revision supersedes it.
    newer = _make_document(
        owner_session,
        safety_fixture["org_id"],
        safety_fixture["material_id"],
        safety_fixture["user_id"],
        "rev2",
        "SDS",
    )
    owner_session.execute(
        text("UPDATE materials.material_documents SET supersedes_id = :old WHERE id = :new"),
        {"old": safety_fixture["document_id"], "new": newer},
    )
    owner_session.flush()

    # Precondition: the old document really has left the view.
    still_usable = owner_session.execute(
        text("SELECT count(*) FROM materials.usable_documents WHERE id = :d"),
        {"d": safety_fixture["document_id"]},
    ).scalar_one()
    assert still_usable == 0, "the old document is still usable; this test proves nothing"

    # S1b — the interpretation is history, and history is kept.
    survives = owner_session.execute(
        text("SELECT count(*) FROM safety.sds_versions WHERE id = :v"), {"v": old_version}
    ).scalar_one()
    assert survives == 1, (
        "the interpretation vanished when its document was superseded; "
        "compare_revisions can no longer answer what changed"
    )

    # S1c — but it is not the current position, because that joins the view.
    current = owner_session.execute(
        text(
            """
            SELECT count(*) FROM safety.sds_versions v
              JOIN materials.usable_documents d
                ON d.id = v.document_id AND d.organization_id = v.organization_id
             WHERE v.id = :v
            """
        ),
        {"v": old_version},
    ).scalar_one()
    assert current == 0, (
        "a superseded revision is still being reported as the current safety "
        "position; S1c is not being applied by this query"
    )


# ---------------------------------------------------------------------------
# FORCE RLS — counted as what a connection can REACH
# ---------------------------------------------------------------------------


def test_force_rls_is_enabled_on_every_safety_table(owner_session: Session) -> None:
    """A missing FORCE is completely invisible: every query still works and the
    owner simply reads across tenants."""
    unforced = owner_session.execute(
        text(
            """
            SELECT string_agg(c.relname, ', ' ORDER BY c.relname)
              FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
             WHERE n.nspname = 'safety' AND c.relkind = 'r'
               AND NOT (c.relrowsecurity AND c.relforcerowsecurity)
            """
        )
    ).scalar()
    assert unforced is None, f"safety tables without FORCE ROW LEVEL SECURITY: {unforced}"


def test_another_organization_reaches_no_interpretations(
    owner_session: Session, app_session: Session, safety_fixture
) -> None:
    """Counted from the runtime role, not read off a policy."""
    _interpret(owner_session, safety_fixture)
    owner_session.commit()

    try:
        app_session.execute(
            text("SELECT set_config('app.current_org', :o, true)"),
            {"o": str(safety_fixture["org_id"])},
        )
        mine = app_session.execute(text("SELECT count(*) FROM safety.sds_versions")).scalar_one()
        assert mine >= 1, "the owning organization cannot see its own row; RLS is too tight"

        app_session.execute(
            text("SELECT set_config('app.current_org', :o, true)"),
            {"o": str(uuid.uuid4())},
        )
        theirs = app_session.execute(text("SELECT count(*) FROM safety.sds_versions")).scalar_one()
        assert theirs == 0, "another organization can read these safety interpretations"

        # Fail closed: no organization set means nothing, not everything.
        app_session.execute(text("SELECT set_config('app.current_org', '', true)"))
        anonymous = app_session.execute(
            text("SELECT count(*) FROM safety.sds_versions")
        ).scalar_one()
        assert anonymous == 0, "safety data is readable with no organization context"
    finally:
        owner_session.execute(
            text("DELETE FROM safety.sds_versions WHERE organization_id = :o"),
            {"o": safety_fixture["org_id"]},
        )
        owner_session.commit()


# ---------------------------------------------------------------------------
# 055 — the approval route exists and is decidable
# ---------------------------------------------------------------------------


def test_the_approval_engine_accepts_a_safety_review(owner_session: Session) -> None:
    accepts = owner_session.execute(
        text(
            "SELECT pg_get_constraintdef(oid) LIKE '%safety_review%' "
            "FROM pg_constraint WHERE conname = 'approval_routes_entity_type_check'"
        )
    ).scalar_one()
    assert accepts, "workflow.approval_routes will not accept entity_type='safety_review'"


def test_every_organization_has_a_decidable_safety_template(owner_session: Session) -> None:
    """🔴 A TEMPLATE WHOSE STEPS NOBODY CAN SATISFY IS A QUEUE THAT NEVER MOVES.

    Both halves matter: the template must exist for every tenant (or
    `open_route` refuses), and each step's permission must be held by some
    role (or the rung is undecidable and the review can never close).
    """
    missing = owner_session.execute(
        text(
            """
            SELECT count(*) FROM core.organizations o
             WHERE NOT EXISTS (
                 SELECT 1 FROM workflow.approval_templates t
                  WHERE t.organization_id = o.id
                    AND t.template_code = 'SAFETY_REVIEW' AND t.is_active)
            """
        )
    ).scalar_one()
    assert missing == 0, f"{missing} organizations have no active SAFETY_REVIEW template"

    unheld = owner_session.execute(
        text(
            """
            SELECT string_agg(DISTINCT s.permission_required, ', ')
              FROM workflow.approval_template_steps s
              JOIN workflow.approval_templates t
                ON t.id = s.template_id AND t.organization_id = s.organization_id
             WHERE t.template_code = 'SAFETY_REVIEW'
               AND NOT EXISTS (
                   SELECT 1 FROM core.permissions p
                     JOIN core.role_permissions rp ON rp.permission_id = p.id
                    WHERE p.code = s.permission_required)
            """
        )
    ).scalar()
    assert unheld is None, f"SAFETY_REVIEW steps require permissions no role holds: {unheld}"


def test_segregation_of_duties_is_satisfiable(owner_session: Session) -> None:
    """🔴 THE RULE THAT WOULD HAVE MADE THE ROUTE UNCOMPLETABLE.

    Step 2 must be decided by somebody who did not decide step 1. If both
    steps' permissions reached only ONE role, no route could ever close --
    and nothing about the seed would have looked wrong.
    """
    roles_per_step = owner_session.execute(
        text(
            """
            SELECT s.step_number, count(DISTINCT rp.role_id) AS roles
              FROM workflow.approval_template_steps s
              JOIN workflow.approval_templates t
                ON t.id = s.template_id AND t.organization_id = s.organization_id
              JOIN core.permissions p ON p.code = s.permission_required
              JOIN core.role_permissions rp ON rp.permission_id = p.id
             WHERE t.template_code = 'SAFETY_REVIEW'
             GROUP BY s.step_number ORDER BY s.step_number
            """
        )
    ).all()
    by_step = {row.step_number: row.roles for row in roles_per_step}
    assert by_step, "the SAFETY_REVIEW template has no steps"
    assert by_step.get(2, 0) >= 2, (
        "step 2 of SAFETY_REVIEW is reachable by fewer than two roles, so "
        "must_differ_from_group makes it undecidable whenever the same person "
        "holds both -- a safety review that can be opened and never closed"
    )


def test_the_new_permissions_have_holders(owner_session: Session) -> None:
    """A permission nobody holds gates a feature nobody can use -- this project
    has caught that five times, and 29 such permissions still exist."""
    for code in ("safety.approve", "safety.export_restricted"):
        holders = owner_session.execute(
            text(
                """
                SELECT count(*) FROM core.permissions p
                  JOIN core.role_permissions rp ON rp.permission_id = p.id
                 WHERE p.code = :code
                """
            ),
            {"code": code},
        ).scalar_one()
        assert holders > 0, f"{code} is granted to no role"


def test_export_is_not_granted_to_the_director(owner_session: Session) -> None:
    """039 established the asymmetry for `formula.export` on the security
    source's §31: seniority is not a need to remove controlled data from the
    building. It applies at least as hard to a hazard dossier."""
    director = owner_session.execute(
        text(
            """
            SELECT count(*) FROM core.permissions p
              JOIN core.role_permissions rp ON rp.permission_id = p.id
              JOIN core.roles r ON r.id = rp.role_id
             WHERE p.code = 'safety.export_restricted'
               AND r.code = 'product_development_director'
            """
        )
    ).scalar_one()
    assert director == 0, (
        "the director holds safety.export_restricted; 039 deliberately withheld "
        "the equivalent formula.export grant for the same reason"
    )


# ---------------------------------------------------------------------------
# T3b — SAME-ORGANIZATION, restricted-project isolation
#
# 🔴 CODEX RAISED THIS AS THE GAP THAT MATTERED. The suite above proves org A
# cannot read org B. It did NOT prove that a colleague INSIDE the organization,
# who is not a member of a restricted project, is kept out of that project's
# safety alerts and reviews. Permission and resource scope are separate gates
# (SECURITY.md §3) and holding `compliance.review_sds` is not membership.
#
# And it tests the WRITE side too, which is where the real hole was: FOREIGN
# KEY checks bypass RLS, so a `WITH CHECK` of `organization_id` alone would let
# a non-member INSERT a row naming a project they cannot read.
# ---------------------------------------------------------------------------


def test_a_non_member_cannot_read_or_write_a_restricted_projects_safety_records(
    owner_session: Session, app_session: Session, safety_fixture
) -> None:
    org_id = safety_fixture["org_id"]
    restricted = owner_session.execute(
        text(
            """
            INSERT INTO projects.projects
                (organization_id, project_code, name, confidentiality)
            VALUES (:o, :c, 'Restricted work', 'restricted')
            RETURNING id
            """
        ),
        {"o": org_id, "c": f"RDP-R-{uuid.uuid4().hex[:6]}"},
    ).scalar_one()

    # 🔴 EVEN THE SETUP MUST BE A PROJECT MEMBER NOW, AND THAT IS THE FIX
    # WORKING. The `WITH CHECK` on `safety_alerts` carries the project
    # predicate, and FORCE RLS binds the owner too -- so writing an alert onto
    # a restricted project requires membership of it, exactly as it should.
    owner_session.execute(
        text(
            """
            INSERT INTO projects.project_members
                (organization_id, project_id, user_id, project_role, status)
            VALUES (:o, :p, :u, 'lead', 'active')
            """
        ),
        {"o": org_id, "p": restricted, "u": safety_fixture["user_id"]},
    )
    owner_session.execute(
        text("SELECT set_config('app.current_user_id', :u, true)"),
        {"u": str(safety_fixture["user_id"])},
    )

    version_id = _interpret(owner_session, safety_fixture)
    owner_session.flush()

    alert_id = owner_session.execute(
        text(
            """
            INSERT INTO safety.safety_alerts
                (organization_id, sds_version_id, project_id, material_id,
                 severity, change_summary)
            VALUES (:o, :v, :p, :m, 'critical', '1 hazard classification(s) added')
            RETURNING id
            """
        ),
        {"o": org_id, "v": version_id, "p": restricted, "m": safety_fixture["material_id"]},
    ).scalar_one()
    assert alert_id is not None
    owner_session.commit()

    try:
        # A colleague in the SAME organization who is not a project member.
        app_session.execute(
            text("SELECT set_config('app.current_org', :o, true)"), {"o": str(org_id)}
        )
        app_session.execute(
            text("SELECT set_config('app.current_user_id', :u, true)"), {"u": str(uuid.uuid4())}
        )

        visible = app_session.execute(
            text("SELECT count(*) FROM safety.safety_alerts WHERE project_id = :p"),
            {"p": restricted},
        ).scalar_one()
        assert visible == 0, (
            "a non-member of a restricted project can read its safety alerts; "
            "the project predicate is not being applied"
        )

        # 🔴 AND THE WRITE SIDE. This is the half that was actually broken:
        # `USING` protected the read while `WITH CHECK` allowed the insert.
        with pytest.raises(DBAPIError, match="row-level security"):
            app_session.execute(
                text(
                    """
                    INSERT INTO safety.safety_alerts
                        (organization_id, sds_version_id, project_id, material_id,
                         severity, change_summary)
                    VALUES (:o, :v, :p, :m, 'high', 'written by a non-member')
                    """
                ),
                {
                    "o": org_id,
                    "v": version_id,
                    "p": restricted,
                    "m": safety_fixture["material_id"],
                },
            )
    finally:
        app_session.rollback()
        owner_session.execute(
            text("SELECT set_config('app.current_org', :o, true)"), {"o": str(org_id)}
        )
        owner_session.execute(
            text("SELECT set_config('app.current_user_id', :u, true)"),
            {"u": str(safety_fixture["user_id"])},
        )
        owner_session.execute(
            text("DELETE FROM safety.safety_alerts WHERE organization_id = :o"), {"o": org_id}
        )
        owner_session.execute(
            text("DELETE FROM safety.sds_versions WHERE organization_id = :o"), {"o": org_id}
        )
        owner_session.commit()


def test_a_safety_review_has_no_status_of_its_own(owner_session: Session) -> None:
    """🔴 THE SECOND NOTION OF "SIGNED OFF", REMOVED AND KEPT REMOVED.

    The first version of this schema gave `safety_reviews` its own
    `review_state` and closure columns that NOTHING EVER UPDATED, so the
    approval route could be approved while the review sat at `open` for ever.
    A safety review IS its approval route, and its status is read through
    `approvals.route_for_entity`.

    Asserted against the catalogue rather than trusted to a comment, because a
    future migration adding the column back would otherwise reintroduce the
    defect silently.
    """
    stateful = owner_session.execute(
        text(
            """
            SELECT string_agg(column_name, ', ' ORDER BY column_name)
              FROM information_schema.columns
             WHERE table_schema = 'safety' AND table_name = 'safety_reviews'
               AND column_name IN ('review_state', 'status', 'outcome',
                                   'closed_at', 'closed_by')
            """
        )
    ).scalar()
    assert stateful is None, (
        f"safety_reviews has grown its own closure state ({stateful}). The "
        "approval route is the only record of whether a safety review has been "
        "signed off; a second one drifts out of step and nothing fails."
    )


# ---------------------------------------------------------------------------
# The two defects Codex found in the FIXES, asserted so they cannot come back
# ---------------------------------------------------------------------------


def test_an_alert_carries_the_revision_a_review_is_opened_against(
    owner_session: Session, safety_fixture
) -> None:
    """🔴 THE CONTROL SENT THE WRONG ID AND NOTHING WOULD HAVE CAUGHT IT.

    "Open a safety review" is opened against the INTERPRETATION. The browser
    read the alert's own `id` and sent that, because `list_alerts` did not
    return `sds_version_id` at all -- so every press would have failed the
    foreign key, and no test looked at the field because the field was absent.

    This asserts the contract the control depends on: the alert names the
    revision, and that revision is a real interpretation.
    """
    from app.domains.material_safety.service import list_alerts

    project_id = owner_session.execute(
        text(
            """
            INSERT INTO projects.projects (organization_id, project_code, name, confidentiality)
            VALUES (:o, :c, 'Alert project', 'normal') RETURNING id
            """
        ),
        {"o": safety_fixture["org_id"], "c": f"RDP-A-{uuid.uuid4().hex[:6]}"},
    ).scalar_one()

    version_id = _interpret(owner_session, safety_fixture)
    owner_session.execute(
        text(
            """
            INSERT INTO safety.safety_alerts
                (organization_id, sds_version_id, project_id, material_id,
                 severity, change_summary)
            VALUES (:o, :v, :p, :m, 'high', '1 component(s) added')
            """
        ),
        {
            "o": safety_fixture["org_id"],
            "v": version_id,
            "p": project_id,
            "m": safety_fixture["material_id"],
        },
    )
    owner_session.flush()

    rows = list_alerts(owner_session, organization_id=safety_fixture["org_id"])
    mine = [r for r in rows if r["project_id"] == project_id]
    assert mine, "the alert was not returned"
    assert "sds_version_id" in mine[0], (
        "list_alerts does not return sds_version_id, so the 'open a safety "
        "review' control has no correct value to send"
    )
    assert mine[0]["sds_version_id"] == version_id


def test_an_open_batch_on_a_retired_version_still_raises_an_alert(
    owner_session: Session, safety_fixture
) -> None:
    """🔴 CODEX ARGUED THE OPPOSITE CASE AND WON IT.

    An earlier fix filtered formula versions to the active ones BEFORE asking
    which laboratory batches were open. But a `superseded` version can still
    have an `authorized` or `in_progress` batch: somebody is physically making
    that material right now. Retiring a RECIPE is not proof that PHYSICAL WORK
    stopped, and hiding that batch is precisely the exposure a safety alert
    exists to surface.

    So the version filter applies to the "which formulas" answer, and the batch
    lookup runs across every version. This test fails if that is ever undone.
    """
    from app.domains.material_safety.service import impact_of_revision

    org = safety_fixture["org_id"]
    user = safety_fixture["user_id"]
    suffix = uuid.uuid4().hex[:6]

    project_id = owner_session.execute(
        text(
            """
            INSERT INTO projects.projects (organization_id, project_code, name, confidentiality)
            VALUES (:o, :c, 'Retired recipe project', 'normal') RETURNING id
            """
        ),
        {"o": org, "c": f"RDP-S-{suffix}"},
    ).scalar_one()

    formula_id = owner_session.execute(
        text(
            """
            INSERT INTO formulations.formulas
                (organization_id, project_id, formula_code, name, owner_user_id, created_by)
            VALUES (:o, :p, :c, 'Retired formula', :u, :u) RETURNING id
            """
        ),
        {"o": org, "p": project_id, "c": f"FRM-{suffix}", "u": user},
    ).scalar_one()

    # 🔴 CREATED AS A DRAFT, THEN RETIRED. CLAUDE.md §8 freezes the
    # composition of a non-draft version -- "the composition of version X is
    # frozen (status superseded); clone it to a new draft version" -- so the
    # component has to go in before the status moves. The end state is what
    # this test is about: a SUPERSEDED version that still contains the
    # material.
    version_id = owner_session.execute(
        text(
            """
            INSERT INTO formulations.formula_versions
                (organization_id, project_id, formula_id, version_number, version_code,
                 status, created_by)
            VALUES (:o, :p, :f, 1, :vc, 'draft', :u) RETURNING id
            """
        ),
        {"o": org, "p": project_id, "f": formula_id, "vc": f"{suffix}-v1", "u": user},
    ).scalar_one()

    owner_session.execute(
        text(
            """
            INSERT INTO formulations.formula_components
                (organization_id, project_id, formula_version_id, material_id,
                 percentage, display_order)
            VALUES (:o, :p, :v, :m, 10.0, 1)
            """
        ),
        {"o": org, "p": project_id, "v": version_id, "m": safety_fixture["material_id"]},
    )

    # NOW retire it. The recipe is history; the batch below is not.
    owner_session.execute(
        text(
            "UPDATE formulations.formula_versions SET status = 'superseded' WHERE id = :v"
        ),
        {"v": version_id},
    )

    # ...and a batch that is still being made.
    owner_session.execute(
        text(
            """
            INSERT INTO laboratory.batches
                (organization_id, project_id, formula_version_id, batch_number,
                 planned_quantity_kg, status, authorized_by, authorized_at, created_by)
            VALUES (:o, :p, :v, :b, 5.0, 'in_progress', :u, now(), :u)
            """
        ),
        {"o": org, "p": project_id, "v": version_id, "b": f"LB-{suffix}", "u": user},
    )

    sds_version = _interpret(owner_session, safety_fixture)
    owner_session.flush()

    impact = impact_of_revision(
        owner_session, organization_id=org, sds_version_id=sds_version
    )

    assert any(b["formula_version_id"] == version_id for b in impact["open_batches"]), (
        "an in-progress batch on a superseded formula version is not reported. "
        "Somebody is physically making that material and would not be told the "
        "safety data sheet changed."
    )
    assert project_id in impact["projects"], (
        "the project with the live batch is not in the alert set, so no alert "
        "would be raised for it"
    )
