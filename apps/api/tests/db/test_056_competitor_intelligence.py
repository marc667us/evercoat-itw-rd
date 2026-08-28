"""Migration 056 — the competitor register and the Composition Evidence Matrix.

🔴 WRITTEN BECAUSE `4e32a54` CLAIMED THREE HOLES CLOSED AND ASSERTED NONE OF THEM.

The commit message states that the review found, before any of it was written:

  1. `supersedes_id` constrained the tenant but not the OWNER, so a competitor
     label could supersede a material's Safety Data Sheet — removing that SDS
     from `materials.usable_documents`, which decides whether a formula may be
     submitted.
  2. The write-once set protected the BYTES but not the OWNER, so an approved,
     scan-clean label could be re-pointed at a different product and carry its
     clean verdict there.
  3. The product-bound composite foreign key on evidence needed a unique key
     that did not exist, without which a label for product A could back a claim
     about product B.

All three were fixed in the migration. None was exercised by a test, so all
three were claims rather than measurements. This project's standing lesson is
that **a test which has only ever PASSED has not been shown to detect
anything**, so every guard below is exercised in BOTH directions: the legal
case must succeed and the illegal case must be refused, for the stated reason.

⚠️ THE LEGAL CASES ARE NOT DECORATION. Without them a refusal proves only that
something failed — a fixture that never produced a valid row would make every
`pytest.raises` below pass while measuring nothing at all. That precise trap
already caught this suite once: `test_054`'s first non-SDS refusal matched zero
rows and reported a clean `INSERT 0 0` that looked exactly like a pass.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

pytestmark = pytest.mark.db


# ---------------------------------------------------------------------------
# Fixture — one organization, one material with an approved SDS, and two
# competitor products, so "the other product" is a real row and not a UUID
# that simply does not exist.
# ---------------------------------------------------------------------------


@pytest.fixture
def competitor_fixture(owner_session: Session) -> Iterator[dict[str, uuid.UUID]]:
    suffix = uuid.uuid4().hex[:8]

    org_id = owner_session.execute(
        text("INSERT INTO core.organizations (code, name) VALUES (:c, :n) RETURNING id"),
        {"c": f"COMP-{suffix}", "n": "Competitor Test Org"},
    ).scalar_one()

    user_id = owner_session.execute(
        text(
            "INSERT INTO core.users (keycloak_sub, email, display_name) "
            "VALUES (:s, :e, :n) RETURNING id"
        ),
        {"s": f"comp-{suffix}", "e": f"comp-{suffix}@example.test", "n": "Competitor Tester"},
    ).scalar_one()
    member_id = owner_session.execute(
        text(
            "INSERT INTO core.organization_members "
            "(organization_id, user_id, status, email, display_name) "
            "VALUES (:o, :u, 'active', :e, :n) RETURNING id"
        ),
        {
            "o": org_id,
            "u": user_id,
            "e": f"comp-{suffix}@example.test",
            "n": "Competitor Tester",
        },
    ).scalar_one()

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

    project_id = owner_session.execute(
        text(
            "INSERT INTO projects.projects (organization_id, project_code, name) "
            "VALUES (:o, :c, 'Benchmark project') RETURNING id"
        ),
        {"o": org_id, "c": f"PRJ-{suffix}"},
    ).scalar_one()

    # FORCE RLS binds the table owner too, so even this session must declare
    # its tenant. Without it the INSERTs below fail with "new row violates
    # row-level security policy" -- the guard working, not a defect.
    owner_session.execute(
        text("SELECT set_config('app.current_org', :o, true)"), {"o": str(org_id)}
    )
    owner_session.execute(
        text("SELECT set_config('app.current_user_id', :u, true)"), {"u": str(user_id)}
    )

    product_a = _make_product(owner_session, org_id, user_id, f"A-{suffix}")
    product_b = _make_product(owner_session, org_id, user_id, f"B-{suffix}")

    sds_id = _make_document(owner_session, org_id, user_id, suffix, "SDS", material_id=material_id)
    label_a = _make_document(
        owner_session, org_id, user_id, suffix, "label", competitor_product_id=product_a
    )

    # 🔴 ONE ROW IN EVERY COMPETITOR TABLE, NOT ONLY IN `products`.
    #
    # The cross-tenant test loops over all four tables. With rows in `products`
    # alone, the other three counted zero because there was NOTHING TO SEE --
    # a guard that passes when it cannot see, which is worse than one that
    # cannot fail. Codex P2, 2026-08-28, and it is right: the loop would have
    # reported green over three tables whose policies could expose every row.
    sample_id = owner_session.execute(
        text(
            "INSERT INTO competitors.samples "
            "(organization_id, competitor_product_id, sample_reference, registered_by) "
            "VALUES (:o, :p, :ref, :u) RETURNING id"
        ),
        {"o": org_id, "p": product_a, "ref": f"SAMP-{suffix}", "u": user_id},
    ).scalar_one()
    owner_session.execute(
        text(
            """
            INSERT INTO competitors.composition_evidence
                (organization_id, competitor_product_id, component_name,
                 evidence_source, evidence_grade, source_document_id,
                 source_locator, recorded_by)
            VALUES (:o, :p, 'Filler', 'document', 'B', :d, 'Section 3', :u)
            """
        ),
        {"o": org_id, "p": product_a, "d": label_a, "u": user_id},
    )
    owner_session.execute(
        text(
            """
            INSERT INTO competitors.benchmarks
                (organization_id, competitor_product_id, project_id, attribute,
                 gap_summary, recorded_by)
            VALUES (:o, :p, :prj, 'Sand-through time',
                    'Theirs sands about four minutes sooner at 20 C.', :u)
            """
        ),
        {"o": org_id, "p": product_a, "prj": project_id, "u": user_id},
    )
    owner_session.flush()

    yield {
        "sample_id": sample_id,
        "org_id": org_id,
        "user_id": user_id,
        "member_id": member_id,
        "material_id": material_id,
        "project_id": project_id,
        "product_a": product_a,
        "product_b": product_b,
        "sds_id": sds_id,
        "label_a": label_a,
    }

    # 🔴 EXPLICIT TEARDOWN, BECAUSE TWO TESTS BELOW COMMIT.
    #
    # `owner_session`'s rollback cannot undo a commit, and a committed fixture
    # row is permanent. CI counts `materials.materials` GLOBALLY after seeding
    # twice and compares it with `demo-data.json`, so every leaked material
    # makes the seed look non-idempotent -- which is exactly how this was
    # found: the suite was green locally on a database that had quietly
    # accumulated dozens of these orgs.
    #
    # Children before parents: every FK in the digital thread is RESTRICT by
    # design (CLAUDE.md §5), so the order below is not cosmetic. The GUC is
    # re-set because the competitor and safety tables FORCE row-level
    # security, which binds the owner too -- without it these DELETEs match
    # nothing and report success.
    owner_session.rollback()
    owner_session.begin()
    owner_session.execute(
        text("SELECT set_config('app.current_org', :o, true)"), {"o": str(org_id)}
    )
    for statement in (
        "DELETE FROM competitors.composition_evidence WHERE organization_id = :o",
        "DELETE FROM competitors.benchmarks WHERE organization_id = :o",
        "DELETE FROM competitors.samples WHERE organization_id = :o",
        # 🔴 DOCUMENTS BEFORE PRODUCTS. `material_documents_competitor_fk` is
        # RESTRICT, so a competitor label pins the product it belongs to. I got
        # this order wrong first time and the foreign key said so immediately --
        # which is the constraint doing precisely the job it exists for.
        "DELETE FROM materials.material_documents WHERE organization_id = :o",
        "DELETE FROM competitors.products WHERE organization_id = :o",
        "DELETE FROM materials.materials WHERE organization_id = :o",
        "DELETE FROM projects.projects WHERE organization_id = :o",
        "DELETE FROM core.member_roles WHERE member_id = :m",
        "DELETE FROM core.organization_members WHERE organization_id = :o",
        "DELETE FROM core.users WHERE id = :u",
        "DELETE FROM core.organizations WHERE id = :o",
    ):
        owner_session.execute(text(statement), {"o": org_id, "u": user_id, "m": member_id})
    owner_session.commit()


def _make_product(session: Session, org_id: uuid.UUID, user_id: uuid.UUID, name: str) -> uuid.UUID:
    return session.execute(  # type: ignore[no-any-return]
        text(
            "INSERT INTO competitors.products "
            "(organization_id, manufacturer, product_name, registered_by) "
            "VALUES (:o, 'Rival Chemicals', :n, :u) RETURNING id"
        ),
        {"o": org_id, "n": name, "u": user_id},
    ).scalar_one()


def _make_document(
    session: Session,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    suffix: str,
    document_type: str,
    *,
    material_id: uuid.UUID | None = None,
    competitor_product_id: uuid.UUID | None = None,
    supersedes_id: uuid.UUID | None = None,
) -> uuid.UUID:
    """An APPROVED, scan-clean, unexpired document owned by exactly one thing.

    Every column 036's `material_documents_approved_has_evidence` demands is
    supplied, so the row genuinely appears in `materials.usable_documents`.
    A quarantined fixture row would make the refusals pass for the wrong reason.
    """
    return session.execute(  # type: ignore[no-any-return]
        text(
            """
            INSERT INTO materials.material_documents
                (organization_id, material_id, competitor_product_id, document_type,
                 title, storage_key, content_type, byte_size, checksum_sha256,
                 status, scan_status, scanner_name, scanner_version, scanned_at,
                 supersedes_id, uploaded_by)
            VALUES (:o, :m, :cp, :dt, :title, :key, 'application/pdf', 2048,
                    :checksum, 'approved', 'clean', 'test-scanner', '1.0', now(),
                    :sup, :u)
            RETURNING id
            """
        ),
        {
            "o": org_id,
            "m": material_id,
            "cp": competitor_product_id,
            "dt": document_type,
            "title": f"{document_type} for testing",
            "key": f"test/{document_type}-{suffix}-{uuid.uuid4().hex[:6]}",
            "checksum": uuid.uuid4().hex + uuid.uuid4().hex,
            "sup": supersedes_id,
            "u": user_id,
        },
    ).scalar_one()


def _claim(session: Session, fx: dict[str, uuid.UUID], **overrides: object) -> uuid.UUID:
    """A document-sourced claim on product A, which is the legal shape."""
    params: dict[str, object] = {
        "o": fx["org_id"],
        "p": overrides.get("competitor_product_id", fx["product_a"]),
        "d": overrides.get("source_document_id", fx["label_a"]),
        "src": overrides.get("evidence_source", "document"),
        "conf": overrides.get("confidence", "possible"),
        "vby": overrides.get("verified_by"),
        "vat": overrides.get("verified_at"),
        "u": fx["user_id"],
        "name": overrides.get("component_name", "Styrene"),
    }
    return session.execute(  # type: ignore[no-any-return]
        text(
            """
            INSERT INTO competitors.composition_evidence
                (organization_id, competitor_product_id, component_name,
                 evidence_source, evidence_grade, confidence, source_document_id,
                 source_locator, verified_by, verified_at, recorded_by)
            VALUES (:o, :p, :name, :src, 'A', :conf, :d,
                    'Section 3, ingredient table', :vby, CAST(:vat AS TIMESTAMPTZ), :u)
            RETURNING id
            """
        ),
        params,
    ).scalar_one()


def _grant_review_sds(session: Session, fx: dict[str, uuid.UUID]) -> None:
    """Give the fixture's member a role actually carrying `compliance.review_sds`.

    Built rather than looked up: a test that depended on a seeded role holding
    the permission would silently stop exercising the trigger the day the seed
    changed, and would report green.
    """
    # ⚠️ `core.roles` HAS NO `organization_id`. A role is a platform-level
    # definition and the MEMBERSHIP is what binds it to a tenant -- which is
    # also why the trigger joins through `core.organization_members` rather
    # than looking for a tenant column on the role.
    role_id = session.execute(
        text("INSERT INTO core.roles (code, name) VALUES (:c, 'SDS Reviewer') RETURNING id"),
        {"c": f"sds-reviewer-{uuid.uuid4().hex[:6]}"},
    ).scalar_one()
    permission_id = session.execute(
        text("SELECT id FROM core.permissions WHERE code = 'compliance.review_sds'")
    ).scalar_one()
    session.execute(
        text("INSERT INTO core.role_permissions (role_id, permission_id) VALUES (:r, :p)"),
        {"r": role_id, "p": permission_id},
    )
    session.execute(
        text("INSERT INTO core.member_roles (member_id, role_id) VALUES (:m, :r)"),
        {"m": fx["member_id"], "r": role_id},
    )
    session.flush()


# ---------------------------------------------------------------------------
# HOLE 1 — supersession stays with one owner
# ---------------------------------------------------------------------------


def test_a_document_may_supersede_one_with_the_same_owner(
    owner_session: Session, competitor_fixture
) -> None:
    """The legal case. Without it the refusal below proves only that something broke."""
    fx = competitor_fixture
    revision = _make_document(
        owner_session,
        fx["org_id"],
        fx["user_id"],
        "rev",
        "label",
        competitor_product_id=fx["product_a"],
        supersedes_id=fx["label_a"],
    )
    assert revision is not None


def test_a_competitor_label_cannot_supersede_a_materials_sds(
    owner_session: Session, competitor_fixture
) -> None:
    """🔴 THE HOLE THAT REACHED THE FORMULA-SUBMISSION GATE.

    `materials.usable_documents` excludes a document a newer approved revision
    supersedes, and the formula-submission gate reads that view. So superseding
    ACROSS owners would have let an upload against a competitor product remove a
    material's SDS from the view -- changing whether a formula may be submitted,
    on the strength of an unrelated file.
    """
    fx = competitor_fixture
    with pytest.raises(DBAPIError) as caught:
        _make_document(
            owner_session,
            fx["org_id"],
            fx["user_id"],
            "cross",
            "label",
            competitor_product_id=fx["product_a"],
            supersedes_id=fx["sds_id"],  # a MATERIAL's document
        )
    assert "SAME owner" in str(caught.value)


def test_the_superseded_sds_is_still_usable_after_the_refusal(
    owner_session: Session, competitor_fixture
) -> None:
    """🔴 THE POINT OF THE GUARD, ASSERTED AS AN OUTCOME RATHER THAN A MESSAGE.

    Checking only that an exception was raised would leave the actual claim --
    that the SDS remains submittable -- unmeasured. This asserts the CONSEQUENCE.
    """
    fx = competitor_fixture
    owner_session.execute(text("SAVEPOINT before_cross_owner"))
    with pytest.raises(DBAPIError):
        _make_document(
            owner_session,
            fx["org_id"],
            fx["user_id"],
            "cross2",
            "label",
            competitor_product_id=fx["product_a"],
            supersedes_id=fx["sds_id"],
        )
    owner_session.execute(text("ROLLBACK TO SAVEPOINT before_cross_owner"))

    still_usable = owner_session.execute(
        text("SELECT count(*) FROM materials.usable_documents WHERE id = :d"),
        {"d": fx["sds_id"]},
    ).scalar_one()
    assert still_usable == 1, "the SDS left usable_documents despite the refusal"


# ---------------------------------------------------------------------------
# HOLE 2 — the owner is write-once
# ---------------------------------------------------------------------------


def test_a_scanned_label_cannot_be_re_pointed_at_another_product(
    owner_session: Session, competitor_fixture
) -> None:
    """An approved, scan-clean label must not carry its verdict to a different product."""
    fx = competitor_fixture
    with pytest.raises(DBAPIError) as caught:
        owner_session.execute(
            text(
                "UPDATE materials.material_documents SET competitor_product_id = :b WHERE id = :d"
            ),
            {"b": fx["product_b"], "d": fx["label_a"]},
        )
    assert "write-once" in str(caught.value)


def test_a_document_cannot_be_re_owned_from_a_competitor_to_a_material(
    owner_session: Session, competitor_fixture
) -> None:
    """The other half of the rule — and 🔴 A DIFFERENT TRIGGER ENFORCES IT.

    MEASURED, not assumed. Triggers fire in NAME order, and
    `material_documents_evidence_write_once` (038) sorts before
    `material_documents_owner_write_once` (056). 038 already refuses a move to
    another material, so on this path it fires first and 056's `material_id`
    branch never executes — it is unreachable defence-in-depth.

    056's `competitor_product_id` branch IS load-bearing: 038 checks material,
    organization and document type only, so nothing but 056 stops a label being
    re-pointed at another product. The preceding test is the one that measures
    the new guard; this one measures that the OUTCOME holds either way.

    Asserting the refusal message here would tie the test to whichever trigger
    happens to sort first, so it asserts the consequence: the document still
    belongs to the product it was uploaded for.
    """
    fx = competitor_fixture
    # A SAVEPOINT, not a rollback: rolling the whole transaction back would
    # discard the fixture too, and the row would then be absent rather than
    # unchanged -- an assertion that passes for the wrong reason.
    owner_session.execute(text("SAVEPOINT before_reown"))
    with pytest.raises(DBAPIError):
        owner_session.execute(
            text(
                "UPDATE materials.material_documents "
                "SET material_id = :m, competitor_product_id = NULL WHERE id = :d"
            ),
            {"m": fx["material_id"], "d": fx["label_a"]},
        )
    owner_session.execute(text("ROLLBACK TO SAVEPOINT before_reown"))
    owner = owner_session.execute(
        text("SELECT competitor_product_id FROM materials.material_documents WHERE id = :d"),
        {"d": fx["label_a"]},
    ).scalar_one_or_none()
    assert owner == fx["product_a"], "the label changed owner despite the refusal"


def test_a_harmless_update_to_the_same_document_still_succeeds(
    owner_session: Session, competitor_fixture
) -> None:
    """🔴 A GUARD THAT REFUSES EVERYTHING IS NOT A GUARD, IT IS AN OUTAGE.

    The trigger fires `BEFORE UPDATE` on every column, so this asserts it lets
    an unrelated edit through rather than blocking all writes to the table.
    """
    fx = competitor_fixture
    owner_session.execute(
        text("UPDATE materials.material_documents SET title = :t WHERE id = :d"),
        {"t": "Label, 1L tin, 2026 packaging", "d": fx["label_a"]},
    )
    title = owner_session.execute(
        text("SELECT title FROM materials.material_documents WHERE id = :d"),
        {"d": fx["label_a"]},
    ).scalar_one()
    assert title == "Label, 1L tin, 2026 packaging"


# ---------------------------------------------------------------------------
# HOLE 3 — a document backs a claim only about ITS OWN product  (T2b)
# ---------------------------------------------------------------------------


def test_a_document_can_back_a_claim_about_its_own_product(
    owner_session: Session, competitor_fixture
) -> None:
    """The legal case for the composite foreign key."""
    fx = competitor_fixture
    assert _claim(owner_session, fx) is not None


def test_a_label_for_product_a_cannot_back_a_claim_about_product_b(
    owner_session: Session, competitor_fixture
) -> None:
    """🔴 T2b. The composite FK is the mechanism; every other constraint holds."""
    fx = competitor_fixture
    with pytest.raises(IntegrityError) as caught:
        _claim(owner_session, fx, competitor_product_id=fx["product_b"])
    assert "composition_evidence_document_fk" in str(caught.value)


def test_a_sample_of_product_a_cannot_back_a_claim_about_product_b(
    owner_session: Session, competitor_fixture
) -> None:
    """🔴 MIGRATION 057 — THE HOLE THE DOCUMENT KEY CLOSED AND THE SAMPLE KEY DID NOT.

    056 bound `source_document_id` to the product and left
    `composition_evidence_sample_fk` tenant-scoped, so product A's tin could be
    recorded as the physical source of a claim about product B. It was latent
    only because no client had ever sent `sample_id`; adding the sample picker
    made it reachable from a browser, which is what turned a dormant schema gap
    into a live one.
    """
    fx = competitor_fixture
    with pytest.raises(IntegrityError) as caught:
        owner_session.execute(
            text(
                """
                INSERT INTO competitors.composition_evidence
                    (organization_id, competitor_product_id, component_name,
                     evidence_source, evidence_grade, sample_id, recorded_by)
                VALUES (:o, :b, 'Talc', 'laboratory', 'A', :s, :u)
                """
            ),
            {"o": fx["org_id"], "b": fx["product_b"], "s": fx["sample_id"], "u": fx["user_id"]},
        )
    assert "composition_evidence_sample_fk" in str(caught.value)


def test_the_sample_foreign_key_constrains_the_product(owner_session: Session) -> None:
    """🔴 ASSERT THE RESULTING PRIVILEGE, NEVER THE STATEMENT.

    A two-column key would leave the cross-product citation open while the
    migration log read exactly like a fix. This reads the constraint back out
    of `pg_constraint`.
    """
    definition = owner_session.execute(
        text(
            "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
            " WHERE conrelid = 'competitors.composition_evidence'::regclass "
            "   AND conname = 'composition_evidence_sample_fk'"
        )
    ).scalar_one_or_none()
    assert definition is not None, "composition_evidence_sample_fk is missing"
    assert "competitor_product_id" in definition, (
        f"the sample foreign key does not constrain the product: {definition}"
    )


def test_the_unique_key_the_composite_foreign_key_needs_exists(
    owner_session: Session, competitor_fixture
) -> None:
    """🔴 ASSERT THE THING EXISTS BEFORE TRUSTING A PROPERTY OF IT.

    The FK above is only expressible because 056 added
    `material_documents_id_competitor_org_key`. Reading it from `pg_constraint`
    rather than from the migration text: the file existing is not the schema.
    """
    kind = owner_session.execute(
        text(
            "SELECT contype FROM pg_constraint "
            "WHERE conname = 'material_documents_id_competitor_org_key'"
        )
    ).scalar_one_or_none()
    assert kind == "u", "the unique key the evidence FK depends on is missing"


# ---------------------------------------------------------------------------
# T2a / T2c — `verified` is not something a writer may assert about itself
# ---------------------------------------------------------------------------


def test_verified_requires_both_a_verifier_and_a_time(
    owner_session: Session, competitor_fixture
) -> None:
    """T2c. `verified_by` alone is not verification, and neither is a bare flag.

    🔴 THE PERMISSION MUST BE GRANTED FIRST TO REACH THE CONSTRAINT AT ALL.
    A `BEFORE INSERT` trigger runs before row constraints are evaluated, so
    without the grant this refusal comes from `verification_names_a_reviewer`
    and the CHECK is never exercised — the test would pass while measuring a
    different mechanism entirely.
    """
    fx = competitor_fixture
    _grant_review_sds(owner_session, fx)
    with pytest.raises(IntegrityError) as caught:
        _claim(owner_session, fx, confidence="verified", verified_by=fx["user_id"])
    assert "composition_evidence_verification_complete" in str(caught.value)


def test_a_verifier_and_a_time_without_verified_is_also_refused(
    owner_session: Session, competitor_fixture
) -> None:
    """🔴 BOTH DIRECTIONS. The constraint is an equivalence, not an implication.

    A row carrying a verifier and a timestamp while claiming `possible` would
    read, to anybody scanning the table, as a verified claim that had been
    quietly downgraded.
    """
    fx = competitor_fixture
    with pytest.raises(IntegrityError) as caught:
        _claim(
            owner_session,
            fx,
            confidence="possible",
            verified_by=fx["user_id"],
            verified_at="2026-08-28T00:00:00Z",
        )
    assert "composition_evidence_verification_complete" in str(caught.value)


def test_an_observation_can_never_be_verified(owner_session: Session, competitor_fixture) -> None:
    """T2a. There is nothing anybody else can re-check, so the grade is unearnable.

    A person reading the back of a tin is making an honest observation. What
    they cannot do is certify it, and the database — not the screen — is what
    says so.
    """
    fx = competitor_fixture
    _grant_review_sds(owner_session, fx)
    with pytest.raises(IntegrityError) as caught:
        owner_session.execute(
            text(
                """
                INSERT INTO competitors.composition_evidence
                    (organization_id, competitor_product_id, component_name,
                     evidence_source, evidence_grade, confidence, rationale,
                     observed_by, verified_by, verified_at, recorded_by)
                VALUES (:o, :p, 'Talc', 'manual_observation', 'C', 'verified',
                        'Read from the back of the tin', :u, :u, now(), :u)
                """
            ),
            {"o": fx["org_id"], "p": fx["product_a"], "u": fx["user_id"]},
        )
    assert "composition_evidence_verifiable_source" in str(caught.value)


def test_a_laboratory_claim_must_cite_a_sample_or_a_test(
    owner_session: Session, competitor_fixture
) -> None:
    """🔴 THE SHAPE THAT MADE A MENU OPTION UNWRITABLE.

    `composition_evidence_laboratory_shape` requires a sample or a test on
    every `laboratory` row. The screen offered "Our own laboratory result"
    while sending neither, so every such submission was refused by the
    database -- an option nobody could use, and nothing measured it.

    Codex read this as "an uncited laboratory claim can be created and later
    verified". Measured, it is the opposite: the row cannot be created at all.
    The finding was right that the path was broken and wrong about which way.
    """
    fx = competitor_fixture
    with pytest.raises(IntegrityError) as caught:
        owner_session.execute(
            text(
                """
                INSERT INTO competitors.composition_evidence
                    (organization_id, competitor_product_id, component_name,
                     evidence_source, evidence_grade, recorded_by)
                VALUES (:o, :p, 'Talc', 'laboratory', 'A', :u)
                """
            ),
            {"o": fx["org_id"], "p": fx["product_a"], "u": fx["user_id"]},
        )
    assert "composition_evidence_laboratory_shape" in str(caught.value)


def test_a_laboratory_claim_citing_a_sample_is_accepted(
    owner_session: Session, competitor_fixture
) -> None:
    """The other direction: with the sample the screen now sends, it is legal."""
    fx = competitor_fixture
    claim_id = owner_session.execute(
        text(
            """
            INSERT INTO competitors.composition_evidence
                (organization_id, competitor_product_id, component_name,
                 evidence_source, evidence_grade, sample_id, recorded_by)
            VALUES (:o, :p, 'Talc', 'laboratory', 'A', :s, :u)
            RETURNING id
            """
        ),
        {"o": fx["org_id"], "p": fx["product_a"], "s": fx["sample_id"], "u": fx["user_id"]},
    ).scalar_one()
    assert claim_id is not None


def test_the_named_verifier_must_actually_hold_the_permission(
    owner_session: Session, competitor_fixture
) -> None:
    """🔴 THE TRIGGER, AND IT IS A MISUSE BARRIER RATHER THAN A BOUNDARY.

    Anybody who can already run SQL as this role can grant themselves the role
    first. What it stops is a verified claim naming somebody who never held
    `compliance.review_sds` — which is the shape a mistake takes, and the shape
    an audit reads.
    """
    fx = competitor_fixture
    with pytest.raises(DBAPIError) as caught:
        _claim(
            owner_session,
            fx,
            confidence="verified",
            verified_by=fx["user_id"],
            verified_at="2026-08-28T00:00:00Z",
        )
    assert "compliance.review_sds" in str(caught.value)


def test_a_holder_of_review_sds_can_verify(owner_session: Session, competitor_fixture) -> None:
    """🔴 FALSIFIES THE TRIGGER THE OTHER WAY.

    Without this the refusal above would also pass if the trigger refused
    EVERYONE — a guard that cannot succeed proves nothing about who may.
    """
    fx = competitor_fixture
    _grant_review_sds(owner_session, fx)
    claim_id = _claim(
        owner_session,
        fx,
        confidence="verified",
        verified_by=fx["user_id"],
        verified_at="2026-08-28T00:00:00Z",
    )
    assert claim_id is not None


# ---------------------------------------------------------------------------
# T3a / T8 — reach, counted as what a user can reach
# ---------------------------------------------------------------------------


def test_every_competitor_table_forces_row_level_security(owner_session: Session) -> None:
    """T8. FORCE from birth: the policies bind the table OWNER too.

    Read from `pg_class`, not from the migration text — the database in front
    of you is not the schema, and a migration is not applied because a file
    exists.
    """
    rows = owner_session.execute(
        text(
            "SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity "
            "  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            " WHERE n.nspname = 'competitors' AND c.relkind = 'r' ORDER BY c.relname"
        )
    ).all()
    assert len(rows) == 4, f"expected four competitor tables, found {len(rows)}"
    unforced = [r[0] for r in rows if not (r[1] and r[2])]
    assert not unforced, f"these competitor tables are not FORCE RLS: {unforced}"


def test_another_organization_reaches_none_of_it(
    owner_session: Session, app_session: Session, competitor_fixture
) -> None:
    """🔴 T3a — COUNTED AS WHAT A USER CAN REACH, NOT BY READING A POLICY.

    A policy can be present and still not apply. This asks the runtime role,
    under a different tenant, how many rows it can actually see.
    """
    fx = competitor_fixture
    owner_session.commit()

    other_org = uuid.uuid4()
    app_session.execute(
        text("SELECT set_config('app.current_org', :o, true)"), {"o": str(other_org)}
    )

    for table in (
        "competitors.products",
        "competitors.samples",
        "competitors.composition_evidence",
        "competitors.benchmarks",
    ):
        reachable = app_session.execute(
            # Suppressed deliberately: `table` comes from the tuple literal
            # above, never from input, and an identifier cannot be bound.
            text(f"SELECT count(*) FROM {table} WHERE organization_id = :o"),  # noqa: S608
            {"o": fx["org_id"]},
        ).scalar_one()
        assert reachable == 0, f"another organization reached {reachable} rows of {table}"


def test_the_owning_organization_does_reach_its_own_product(
    owner_session: Session, app_session: Session, competitor_fixture
) -> None:
    """🔴 THE OTHER DIRECTION OF T3a.

    Without it, the zeros above would also be produced by a policy that hides
    the table from everybody — or by a fixture that never committed a row.
    """
    fx = competitor_fixture
    owner_session.commit()

    app_session.execute(
        text("SELECT set_config('app.current_org', :o, true)"), {"o": str(fx["org_id"])}
    )
    app_session.execute(
        text("SELECT set_config('app.current_user_id', :u, true)"), {"u": str(fx["user_id"])}
    )
    # 🔴 EVERY TABLE THE NEGATIVE TEST LOOPS OVER, OR THE ZEROS THERE PROVE
    # NOTHING. Checking only `products` left three tables whose zero could
    # equally have meant "empty" as "correctly hidden".
    expected = {
        "competitors.products": 2,
        "competitors.samples": 1,
        "competitors.composition_evidence": 1,
        "competitors.benchmarks": 1,
    }
    for table, count in expected.items():
        reachable = app_session.execute(
            text(f"SELECT count(*) FROM {table} WHERE organization_id = :o"),  # noqa: S608
            {"o": fx["org_id"]},
        ).scalar_one()
        assert reachable == count, (
            f"the owning organization reached {reachable} of its {count} rows in {table}"
        )


# ---------------------------------------------------------------------------
# The register was EXTENDED, not forked — §14
# ---------------------------------------------------------------------------


def test_there_is_no_second_document_table(owner_session: Session) -> None:
    """§14: *"do not build a second document repository"*, asserted rather than intended."""
    forked = owner_session.execute(
        text(
            "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            " WHERE n.nspname = 'competitors' AND c.relkind = 'r' "
            "   AND c.relname LIKE '%document%'"
        )
    ).scalar_one()
    assert forked == 0, "a second document repository exists in the competitors schema"


def test_usable_documents_kept_security_invoker(owner_session: Session) -> None:
    """⚠️ 056 RECREATED THE VIEW THE FORMULA-SUBMISSION GATE READS.

    `security_invoker = true` is what makes the view honour the CALLER's RLS.
    Recreating a view silently drops its options, and the loss would be
    invisible: every query would keep working, and would return more rows.
    """
    options = owner_session.execute(
        text(
            "SELECT c.reloptions FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            " WHERE n.nspname = 'materials' AND c.relname = 'usable_documents'"
        )
    ).scalar_one()
    # Existence first, then the property of it: asserting a property of a
    # missing thing reports the wrong failure.
    assert options is not None, "usable_documents has no reloptions at all"
    assert any("security_invoker=true" in str(opt) for opt in options), (
        f"usable_documents lost security_invoker; reloptions = {options}"
    )
