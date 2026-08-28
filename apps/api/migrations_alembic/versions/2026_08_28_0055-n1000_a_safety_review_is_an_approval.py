"""a safety review is an approval, not a second workflow engine

Revision ID: n1000
Revises: m1000
Created: 2026-08-28

Gives `compliance.review_sds` its FIRST enforcement point.

It has been seeded since 002:127, described as *"Review SDS and safety
documentation"*, granted to `qa_compliance_officer` since 002:275, and read by
nothing in `apps/api/app` -- one of 29 permissions measured in that state. This
migration does not mint `safety.review` beside it, because a synonym for a fact
the catalogue already carries is the defect this project keeps finding.

Two permissions are genuinely new, because two acts have no existing holder:
`safety.approve` and `safety.export_restricted`. Nothing for research,
competitors or experiments -- those belong to the phases that build their
enforcement points, and adding to the orphan pile inside the migration that
starts draining it would be self-defeating.

🔴 SEGREGATION OF DUTIES WAS MEASURED BEFORE IT WAS WRITTEN. Step 2 requires a
decider who did not decide step 1. In the demonstration organization exactly one
user holds `compliance.review_sds`, so granting `safety.approve` to the QA
officer alone would have produced a route nobody could ever clear. It is granted
to the project lead as well -- a different person, measured -- so the rule is
satisfiable.

⚠️ The `entity_type` CHECK at 020:140 is INLINE and UNNAMED. Its generated name
was read from `pg_constraint` (`approval_routes_entity_type_check`), not guessed:
a DROP ... IF EXISTS on a guessed name would leave the old constraint in place
while this migration reported success.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

from migrations_alembic._sql import apply_sql

revision: str = "n1000"
down_revision: str | None = "m1000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    apply_sql("055_a_safety_review_is_an_approval.sql")

    # 🔴 ASSERT THE ROUTE IS ACTUALLY OPENABLE, rather than assuming the seeds
    # landed. A template with no steps, or steps requiring a permission nobody
    # holds, is a Safety Review control that 500s or a queue that never moves --
    # and both look exactly like success at migration time.
    bind = op.get_bind()

    orgs_without_template = bind.execute(
        text(
            """
            SELECT count(*) FROM core.organizations o
             WHERE NOT EXISTS (
                 SELECT 1 FROM workflow.approval_templates t
                  WHERE t.organization_id = o.id
                    AND t.template_code = 'SAFETY_REVIEW'
                    AND t.is_active)
            """
        )
    ).scalar_one()
    if orgs_without_template:
        raise RuntimeError(
            f"{orgs_without_template} organizations have no active SAFETY_REVIEW "
            "template; open_route would refuse a safety review for them"
        )

    # Every step's permission must be held by at least one role, or the rung is
    # undecidable. This checks the CATALOGUE, not one tenant's membership.
    unheld = bind.execute(
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
    if unheld:
        raise RuntimeError(
            f"SAFETY_REVIEW steps require permissions no role holds: {unheld}"
        )


def downgrade() -> None:
    """Remove the safety route and its permissions.

    ⚠️ ORDER MATTERS AND THE CONSTRAINTS ARE NARROWED LAST. Routes must go
    before the `entity_type` value they use is removed, or the narrowed CHECK
    fails to validate against rows that already exist -- which would leave the
    database at a half-applied revision.

    ⚠️ THIS REOPENS THE ORPHAN. `compliance.review_sds` returns to having no
    enforcement point, because `m1000` describes a schema in which it had none.
    A downgrade that quietly kept the fix would make that description false --
    the argument 049, 051, 052 and 053 each make for their own.
    """
    # 🔴 STOP PROVISIONING IT FOR NEW ORGANIZATIONS FIRST. If the trigger still
    # called it, an organization created between these statements would
    # re-create the template this downgrade is removing, and the narrowed
    # authority_level CHECK below would then fail to validate.
    op.execute(
        text(
            """
            CREATE OR REPLACE FUNCTION workflow.provision_templates_on_new_org()
                RETURNS TRIGGER LANGUAGE plpgsql AS $on_new_org$
            BEGIN
                PERFORM workflow.provision_approval_templates(NEW.id);
                RETURN NEW;
            END
            $on_new_org$;
            """
        )
    )
    op.execute(
        text("DROP FUNCTION IF EXISTS workflow.provision_safety_review_template(UUID)")
    )
    op.execute(
        text(
            "DELETE FROM workflow.approval_routes WHERE entity_type = 'safety_review'"
        )
    )
    op.execute(
        text(
            """
            DELETE FROM workflow.approval_template_steps s
             USING workflow.approval_templates t
             WHERE t.id = s.template_id AND t.template_code = 'SAFETY_REVIEW'
            """
        )
    )
    op.execute(
        text("DELETE FROM workflow.approval_templates WHERE template_code = 'SAFETY_REVIEW'")
    )

    op.execute(
        text(
            """
            ALTER TABLE workflow.approval_templates
                DROP CONSTRAINT approval_templates_authority_level_check;
            ALTER TABLE workflow.approval_templates
                ADD CONSTRAINT approval_templates_authority_level_check CHECK (
                    authority_level IS NULL OR authority_level IN
                    ('preliminary','development','controlled','validation',
                     'qualification','release'));
            ALTER TABLE workflow.approval_routes
                DROP CONSTRAINT approval_routes_entity_type_check;
            ALTER TABLE workflow.approval_routes
                ADD CONSTRAINT approval_routes_entity_type_check CHECK (
                    entity_type IN ('test','formula_version','validation',
                                    'pilot','qualification','product_release'));
            """
        )
    )

    op.execute(
        text(
            """
            DELETE FROM core.role_permissions rp
             USING core.permissions p
             WHERE p.id = rp.permission_id
               AND p.code IN ('safety.approve', 'safety.export_restricted')
            """
        )
    )
    op.execute(
        text(
            "DELETE FROM core.permissions "
            "WHERE code IN ('safety.approve', 'safety.export_restricted')"
        )
    )
