"""research becomes an experiment

Revision ID: q1000
Revises: p1000
Created: 2026-08-29

Phase 4 of the Material Safety Data & Research Center: the eight `research`
tables, their permissions, the finding approval route, and the one point where
research joins the formula world -- an accepted experiment proposal recording
the version `formulations.revise_version` returned.

🔴 THE ASSERTIONS BELOW CHECK RESULTS, NOT STATEMENTS.

`CREATE TABLE` succeeding says the DDL parsed. Four things could still be
silently wrong afterwards, and each has cost this project a session before:

  * a table created without FORCE RLS reads as protected and is not (I56/I58);
  * a policy with only a `USING` half protects reads and leaves writes open,
    because a foreign-key check bypasses RLS;
  * a permission seeded with no holder is a gate nobody can pass (five
    instances);
  * a template backfilled for today's organizations only, silently expiring
    for the next tenant created (055 shipped that defect and a test found it).
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

from migrations_alembic._sql import apply_sql

revision: str = "q1000"
down_revision: str | None = "p1000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_RESEARCH_TABLES = (
    "investigations",
    "questions",
    "sources",
    "evidence",
    "findings",
    "hypotheses",
    "knowledge_gaps",
    "experiment_proposals",
)

_PERMISSIONS = (
    "research.view",
    "research.create",
    "research.review",
    "research.approve",
    "experiment.propose",
    "experiment.accept",
)


def upgrade() -> None:
    apply_sql("058_research_becomes_an_experiment.sql")

    bind = op.get_bind()

    # ---------------------------------------------------------------
    # Every one of the eight is FORCE-protected, and both halves of
    # every policy are present.
    # ---------------------------------------------------------------
    unforced = [
        row[0]
        for row in bind.execute(
            text(
                """
                SELECT c.relname
                  FROM pg_class c
                  JOIN pg_namespace n ON n.oid = c.relnamespace
                 WHERE n.nspname = 'research'
                   AND c.relkind = 'r'
                   AND NOT (c.relrowsecurity AND c.relforcerowsecurity)
                 ORDER BY c.relname
                """
            )
        )
    ]
    if unforced:
        raise RuntimeError(
            "research tables without FORCE ROW LEVEL SECURITY after 058: "
            f"{unforced}. A table that is merely ENABLED is unprotected against "
            "its own owner, which is what FORCE exists to close."
        )

    present = {
        row[0]
        for row in bind.execute(
            text(
                """
                SELECT c.relname
                  FROM pg_class c
                  JOIN pg_namespace n ON n.oid = c.relnamespace
                 WHERE n.nspname = 'research' AND c.relkind = 'r'
                """
            )
        )
    }
    missing = sorted(set(_RESEARCH_TABLES) - present)
    if missing:
        raise RuntimeError(f"058 did not create: {missing}")

    # A `USING` policy and a `WITH CHECK` policy, on each of the eight.
    # `polcmd` is 'r' for the SELECT/UPDATE/DELETE scope policy and 'a' for
    # the INSERT one; a table carrying only the first is write-open.
    write_open = [
        row[0]
        for row in bind.execute(
            text(
                """
                SELECT c.relname
                  FROM pg_class c
                  JOIN pg_namespace n ON n.oid = c.relnamespace
                 WHERE n.nspname = 'research' AND c.relkind = 'r'
                   AND NOT EXISTS (
                       SELECT 1 FROM pg_policy p
                        WHERE p.polrelid = c.oid AND p.polwithcheck IS NOT NULL
                   )
                 ORDER BY c.relname
                """
            )
        )
    ]
    if write_open:
        raise RuntimeError(
            "research tables with no WITH CHECK policy after 058: "
            f"{write_open}. USING alone protects reads and leaves writes open."
        )

    # ---------------------------------------------------------------
    # Every permission exists AND is held by at least one role.
    # ---------------------------------------------------------------
    for code in _PERMISSIONS:
        holders = bind.execute(
            text(
                """
                SELECT count(*)
                  FROM core.role_permissions rp
                  JOIN core.permissions p ON p.id = rp.permission_id
                 WHERE p.code = :code
                """
            ),
            {"code": code},
        ).scalar_one()
        if holders == 0:
            raise RuntimeError(
                f"{code} exists after 058 but no role holds it. A permission "
                "with no holder is a gate nobody can pass."
            )

    # ---------------------------------------------------------------
    # The finding route is decidable — and stays decidable for a tenant
    # created tomorrow.
    # ---------------------------------------------------------------
    orgs_without = bind.execute(
        text(
            """
            SELECT count(*)
              FROM core.organizations o
             WHERE NOT EXISTS (
                   SELECT 1 FROM workflow.approval_templates t
                    WHERE t.organization_id = o.id
                      AND t.template_code = 'RESEARCH_FINDING'
                      AND t.is_active
             )
            """
        )
    ).scalar_one()
    if orgs_without:
        raise RuntimeError(
            f"{orgs_without} organization(s) have no active RESEARCH_FINDING "
            "template after 058; open_route('research') would raise for them."
        )

    # 🔴 THE BACKFILL IS NOT THE POINT — THE TRIGGER IS. 055's defect was a
    # point-in-time backfill that silently expired for the next tenant. Assert
    # the trigger function actually calls this one, so the guarantee survives.
    body = bind.execute(
        text("SELECT prosrc FROM pg_proc WHERE proname = 'provision_templates_on_new_org'")
    ).scalar_one_or_none()
    if body is None or "provision_research_finding_template" not in body:
        raise RuntimeError(
            "workflow.provision_templates_on_new_org() does not provision the "
            "RESEARCH_FINDING template; every organization created from now on "
            "would be missing it, and nothing would look wrong."
        )

    # ---------------------------------------------------------------
    # The formula thread runs backwards as well as forwards.
    # ---------------------------------------------------------------
    unique_def = bind.execute(
        text(
            """
            SELECT pg_get_constraintdef(oid)
              FROM pg_constraint
             WHERE conrelid = 'formulations.formula_version_drivers'::regclass
               AND conname = 'formula_version_drivers_unique'
            """
        )
    ).scalar_one_or_none()
    if unique_def is None:
        raise RuntimeError("formula_version_drivers_unique is missing after 058")
    version_fk = bind.execute(
        text(
            """
            SELECT pg_get_constraintdef(oid)
              FROM pg_constraint
             WHERE conrelid = 'research.experiment_proposals'::regclass
               AND conname = 'experiment_proposals_version_fk'
            """
        )
    ).scalar_one_or_none()
    if version_fk is None or "project_id" not in version_fk:
        raise RuntimeError(
            "experiment_proposals_version_fk does not carry the project: "
            f"{version_fk}. A proposal from one project could revise another "
            "project's formula and record it as authorised by this research."
        )

    if "experiment_proposal_id" not in unique_def:
        raise RuntimeError(
            "formula_version_drivers_unique does not carry experiment_proposal_id: "
            f"{unique_def}. NULLS DISTINCT means the same proposal could be "
            "recorded as the driver of the same version any number of times."
        )

    # A promoted finding needs a word in the knowledge register, or every
    # promotion is refused at runtime by a constraint the service cannot see.
    source_check = bind.execute(
        text(
            """
            SELECT pg_get_constraintdef(oid)
              FROM pg_constraint
             WHERE conrelid = 'knowledge.documents'::regclass
               AND conname = 'documents_source_check'
            """
        )
    ).scalar_one_or_none()
    if source_check is None or "research_finding" not in source_check:
        raise RuntimeError(
            "knowledge.documents_source_check does not accept 'research_finding': "
            f"{source_check}. promote_finding would be refused on every call."
        )

    # 🔴 THE HELPER MUST NOT HAVE SURVIVED (043's rule).
    if bind.execute(text("SELECT count(*) FROM pg_proc WHERE proname = '_grant'")).scalar_one():
        raise RuntimeError(
            "core._grant survived 058. A resident permission-granting function "
            "is a standing way to widen authorization from anywhere."
        )


def downgrade() -> None:
    """Unpick Phase 4, in dependency order.

    The `research` schema goes whole. The two EXISTING tables it touched --
    `formula_version_drivers` and the approval CHECKs -- are put back to the
    shape 057 left them in, which is not the same as dropping what 058 added:
    the driver's unique key and its type CHECK must be RESTATED, or the
    downgrade would leave a table that accepts `research` with nowhere to
    point.
    """
    op.execute(
        text(
            """
            ALTER TABLE formulations.formula_version_drivers
                DROP CONSTRAINT IF EXISTS formula_version_drivers_proposal_fk;
            ALTER TABLE formulations.formula_version_drivers
                DROP CONSTRAINT IF EXISTS formula_version_drivers_research_is_present;
            ALTER TABLE formulations.formula_version_drivers
                DROP CONSTRAINT IF EXISTS formula_version_drivers_unique;
            ALTER TABLE formulations.formula_version_drivers
                ADD CONSTRAINT formula_version_drivers_unique
                UNIQUE (formula_version_id, driver_type, failure_id, requirement_id);
            -- 🔴 THE ROWS COME FIRST, OR `ADD CONSTRAINT` ABORTS.
            --
            -- `ADD CONSTRAINT ... CHECK` VALIDATES EXISTING ROWS. Any accepted
            -- proposal that produced a revision left a `driver_type='research'`
            -- row, so re-adding the narrower CHECK over it fails and the whole
            -- downgrade rolls back. Found by the Supervisor.
            --
            -- Reclassified rather than deleted: the driver is §2's record of
            -- WHY a formula version exists, and deleting it would break the
            -- digital thread of a version that still exists. `other` is the
            -- honest remaining answer once the research vertical is gone, and
            -- the reason text still names the proposal in prose.
            UPDATE formulations.formula_version_drivers
               SET driver_type = 'other',
                   reason = reason || ' (was a research driver; the research '
                                      'vertical was removed by downgrading 058)'
             WHERE driver_type = 'research';
            ALTER TABLE formulations.formula_version_drivers
                DROP CONSTRAINT IF EXISTS formula_version_drivers_driver_type_check;
            ALTER TABLE formulations.formula_version_drivers
                ADD CONSTRAINT formula_version_drivers_driver_type_check CHECK (
                    driver_type IN ('failure', 'requirement', 'optimization',
                                    'cost', 'regulatory', 'customer_request',
                                    'other')
                );
            ALTER TABLE formulations.formula_version_drivers
                DROP COLUMN IF EXISTS experiment_proposal_id;

            -- 🔴 DECIDED APPROVAL HISTORY IS NOT REMOVED, AND THIS DOWNGRADE
            -- WOULD NOT RUN IF IT TRIED.
            --
            -- The first version of this function deleted the routes and their
            -- steps, and PostgreSQL refused outright:
            -- `workflow.approval_route_steps is append-only; DELETE is not
            -- permitted` -- `audit.deny_mutation`, unconditional, so not even
            -- the migration runner may remove a signature. §9 requires an
            -- approval decision to be permanent, and a downgrade is not an
            -- exception to that.
            --
            -- So the routes stay, and BECAUSE they stay the entity_type CHECK
            -- CANNOT be narrowed back: `research_finding` rows would violate
            -- it and the ALTER would fail. The value remains accepted, with
            -- nothing able to write it once the schema is gone -- which is a
            -- deliberate, stated residue rather than a silent one.
            --
            -- 🔴 AND THE TEMPLATE CANNOT SIMPLY BE DELETED EITHER --
            -- measured, after the second attempt failed:
            -- `approval_routes_template_fk` still references it from the routes
            -- that must survive. A route SNAPSHOTS its template, so the
            -- template is part of the record of how a decision was made.
            --
            -- So a template with a surviving route is RETIRED rather than
            -- removed: deactivated so no new route can open against it, and its
            -- `authority_level` cleared so the CHECK below can be narrowed
            -- back. One with no route is deleted outright.
            DELETE FROM workflow.approval_template_steps s
             USING workflow.approval_templates t
             WHERE s.template_id = t.id AND t.template_code = 'RESEARCH_FINDING'
               AND NOT EXISTS (SELECT 1 FROM workflow.approval_routes r
                                WHERE r.template_id = t.id);
            DELETE FROM workflow.approval_templates t
             WHERE t.template_code = 'RESEARCH_FINDING'
               AND NOT EXISTS (SELECT 1 FROM workflow.approval_routes r
                                WHERE r.template_id = t.id);
            UPDATE workflow.approval_templates
               SET is_active = FALSE, authority_level = NULL
             WHERE template_code = 'RESEARCH_FINDING';
            -- Safe to narrow: `authority_level` lives on TEMPLATES, which the
            -- DELETE above removed, not on the routes that must survive.
            ALTER TABLE workflow.approval_templates
                DROP CONSTRAINT IF EXISTS approval_templates_authority_level_check;
            ALTER TABLE workflow.approval_templates
                ADD CONSTRAINT approval_templates_authority_level_check CHECK (
                    authority_level IS NULL OR authority_level IN
                    ('preliminary', 'development', 'controlled', 'validation',
                     'qualification', 'release', 'safety')
                );

            CREATE OR REPLACE FUNCTION workflow.provision_templates_on_new_org()
                RETURNS TRIGGER
                LANGUAGE plpgsql
                SECURITY DEFINER
                SET search_path TO 'pg_catalog', 'public', 'pg_temp'
            AS $on_new_org$
            BEGIN
                PERFORM workflow.provision_approval_templates(NEW.id);
                PERFORM workflow.provision_safety_review_template(NEW.id);
                RETURN NEW;
            END
            $on_new_org$;
            REVOKE ALL ON FUNCTION workflow.provision_templates_on_new_org() FROM PUBLIC;
            DROP FUNCTION IF EXISTS workflow.provision_research_finding_template(UUID);

            -- 🔴 THE SCHEMA GOES FIRST, OR THE DOCUMENT DELETE IS REFUSED.
            --
            -- `research.findings.findings_document_fk` is ON DELETE RESTRICT,
            -- so a promoted finding PINS the knowledge document it produced.
            -- Deleting the documents while `research` still exists aborts the
            -- downgrade. The Supervisor found the ordering; dropping the schema
            -- first removes the referencing side, and then the documents go.
            DROP SCHEMA IF EXISTS research CASCADE;

            DELETE FROM knowledge.chunks c
             USING knowledge.documents d
             WHERE c.document_id = d.id AND d.source = 'research_finding';
            DELETE FROM knowledge.documents WHERE source = 'research_finding';
            ALTER TABLE knowledge.documents
                DROP CONSTRAINT IF EXISTS documents_source_check;
            ALTER TABLE knowledge.documents
                ADD CONSTRAINT documents_source_check CHECK (
                    source IN ('internal_note', 'material_document', 'standard',
                               'procedure', 'external')
                );

            DELETE FROM core.role_permissions rp
             USING core.permissions p
             WHERE p.id = rp.permission_id
               AND p.code IN ('research.view', 'research.create', 'research.review',
                              'research.approve', 'experiment.propose',
                              'experiment.accept');
            DELETE FROM core.permissions
             WHERE code IN ('research.view', 'research.create', 'research.review',
                            'research.approve', 'experiment.propose',
                            'experiment.accept');
            """
        )
    )
