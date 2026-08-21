"""Every organization gets the approval engine. TODO I32.

🔴 A SHIPPED DEFAULT THAT SHIPS ONCE IS NOT A DEFAULT.

Migration 020 seeded §9's five approval templates with a one-time
``FOR org IN SELECT id FROM core.organizations LOOP``. That is every
organization *that existed when 020 ran*. There was no trigger, and nothing
else writes ``workflow.approval_templates``.

So every organization created afterwards had an approval engine with nothing
in it: ``open_route`` looks its template up by ``authority_level``, finds
none, and refuses — **no approval could be routed at all for a new tenant**.
§9's "one shared approval engine, never re-implemented per module" was
unreachable for exactly the customers who arrive after deployment.

It went unnoticed because nothing asked. The tables existed, the engine's
code was correct and tested, and the only symptom was a refusal in a code
path no test had reached with a fresh organization.

Migration 030 makes it a trigger plus a backfill. These tests are what stop
it regressing into a one-time loop again.
"""

from __future__ import annotations

import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session

# §9's five, by name. Written out rather than counted: a count passes when
# five WRONG templates exist, and the whole defect class here is "something
# plausible is present but is not what the rule says".
EXPECTED_TEMPLATES = {
    "SCREENING_SIMPLE",
    "OVERSIGHT_STANDARD",
    "VALIDATION_CONFIRMATION",
    "QUALIFICATION_CONFIRMATION",
    "RELEASE_CRITICAL",
}


def _new_org(session: Session) -> uuid.UUID:
    return session.execute(
        text("INSERT INTO core.organizations (code, name) VALUES (:c, :n) RETURNING id"),
        {"c": f"APRV-{uuid.uuid4().hex[:8]}", "n": "Approval provisioning org"},
    ).scalar_one()


def _template_codes(session: Session, org: uuid.UUID) -> set[str]:
    return {
        r[0]
        for r in session.execute(
            text(
                "SELECT template_code FROM workflow.approval_templates WHERE organization_id = :o"
            ),
            {"o": org},
        )
    }


def test_a_newly_created_organization_gets_the_five_templates(
    owner_session: Session,
) -> None:
    """🔴 THE DEFECT, DIRECTLY. This returned ZERO before migration 030."""
    org = _new_org(owner_session)
    owner_session.flush()

    assert _template_codes(owner_session, org) == EXPECTED_TEMPLATES, (
        "a new organization did not receive §9's approval templates, so no approval "
        "can be routed for it and the shared approval engine is unreachable"
    )


def test_every_provisioned_template_has_its_steps(owner_session: Session) -> None:
    """A template with no steps routes to nobody.

    The templates and their steps are two INSERTs, and the second is inside an
    `IF tpl IS NOT NULL` branch — so a template row without its steps is a
    reachable state, and it would look provisioned while approving nothing.
    """
    org = _new_org(owner_session)
    owner_session.flush()

    stepless = [
        r[0]
        for r in owner_session.execute(
            text(
                """
                SELECT t.template_code
                FROM workflow.approval_templates t
                WHERE t.organization_id = :o
                  AND NOT EXISTS (
                      SELECT 1 FROM workflow.approval_template_steps s
                      WHERE s.template_id = t.id
                  )
                """
            ),
            {"o": org},
        )
    ]

    assert not stepless, f"these templates have no steps and would approve nothing: {stepless}"


def test_qualification_requires_an_independent_qa_step(owner_session: Session) -> None:
    """ADR-019 carried as DATA, not as code.

    The QA step on QUALIFICATION_CONFIRMATION must declare
    `must_differ_from_group`, or independent QA approval could be supplied by
    somebody who already gave a development-side approval — a two-signature
    control collapsing into one person signing twice.

    Asserted on a freshly provisioned organization specifically: the whole
    point of 030 is that a new tenant gets the same guarantees as an old one,
    and a backfill that dropped this column would be invisible otherwise.
    """
    org = _new_org(owner_session)
    owner_session.flush()

    row = (
        owner_session.execute(
            text(
                """
                SELECT s.must_differ_from_group
                FROM workflow.approval_template_steps s
                JOIN workflow.approval_templates t ON t.id = s.template_id
                WHERE t.organization_id = :o
                  AND t.template_code = 'QUALIFICATION_CONFIRMATION'
                  AND s.permission_required = 'test.approve_qa'
                """
            ),
            {"o": org},
        )
        .mappings()
        .one()
    )

    assert row["must_differ_from_group"] is not None, (
        "the independent QA step does not declare must_differ_from_group, so ADR-019's "
        "segregation of duties is not enforced by the route"
    )


def test_no_organization_anywhere_is_missing_its_templates(owner_session: Session) -> None:
    """The backfill, asserted against the whole table.

    A trigger fixes the future; this is what says the past was repaired. A
    migration's own `RAISE NOTICE` is not evidence — it reports what it did,
    not what is true afterwards.
    """
    orphans = [
        str(r[0])
        for r in owner_session.execute(
            text(
                """
                SELECT o.id FROM core.organizations o
                WHERE NOT EXISTS (
                    SELECT 1 FROM workflow.approval_templates t
                    WHERE t.organization_id = o.id
                )
                """
            )
        )
    ]

    assert not orphans, f"{len(orphans)} organization(s) have no approval templates: {orphans[:5]}"
