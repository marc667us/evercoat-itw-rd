"""Opportunities — the head of the digital thread, and its gate.

The assertions that matter most here are the ones about what is REFUSED.
A gate that can be walked around is not a gate, and every refusal below
corresponds to a state the digital thread could not explain:

  * a project whose originating opportunity was never approved
  * two projects claiming the same opportunity
  * a decision that silently overwrote an earlier one
  * an opportunity parked in on_hold that nothing could ever move
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.domains.opportunities.service import (
    OpportunityDecision,
    OpportunityInput,
    OpportunityNotFoundError,
    OpportunityStateError,
    convert_to_project,
    create_opportunity,
    decide_opportunity,
    list_opportunities,
    opportunity_detail,
)


@pytest.fixture
def opp_world(owner_session):
    suffix = uuid.uuid4().hex[:8]

    org = owner_session.execute(
        text("INSERT INTO core.organizations (code, name) VALUES (:c, :n) RETURNING id"),
        {"c": f"OPP-{suffix}", "n": "Opportunity Test Org"},
    ).scalar_one()

    director = owner_session.execute(
        text(
            """
            INSERT INTO core.users (keycloak_sub, email, display_name)
            VALUES (:s, :e, 'Director') RETURNING id
            """
        ),
        {"s": str(uuid.uuid4()), "e": f"director-{suffix}@example.test"},
    ).scalar_one()
    owner_session.execute(
        text(
            """
            INSERT INTO core.organization_members (organization_id, user_id, status)
            VALUES (:o, :u, 'active')
            """
        ),
        {"o": org, "u": director},
    )
    owner_session.flush()
    return {"org": org, "director": director, "suffix": suffix}


def _make(owner_session, world, *, code_suffix="001", status_to=None):
    opportunity_id = create_opportunity(
        owner_session,
        data=OpportunityInput(
            opportunity_code=f"OPP-{world['suffix']}-{code_suffix}",
            title="Faster-curing polyester filler",
            market_need="Body shops lose throughput waiting for cure",
            product_family="polyester_filler",
            priority="high",
        ),
        actor_id=world["director"],
        organization_id=world["org"],
    )
    if status_to:
        owner_session.execute(
            text(
                """
                UPDATE innovation.opportunities SET status = :s
                WHERE id = :i AND organization_id = :o
                """
            ),
            {"s": status_to, "i": opportunity_id, "o": world["org"]},
        )
    owner_session.flush()
    return opportunity_id


def test_a_draft_cannot_be_decided(owner_session, opp_world):
    """Deciding a draft is deciding on an idea nobody has assessed."""
    opportunity_id = _make(owner_session, opp_world)

    with pytest.raises(OpportunityStateError, match="cannot be decided"):
        decide_opportunity(
            owner_session,
            opportunity_id=opportunity_id,
            decision=OpportunityDecision("approve", "looks good"),
            actor_id=opp_world["director"],
            organization_id=opp_world["org"],
        )


def test_a_decision_requires_a_rationale(owner_session, opp_world):
    opportunity_id = _make(owner_session, opp_world, status_to="awaiting_decision")

    with pytest.raises(OpportunityStateError, match="rationale is required"):
        decide_opportunity(
            owner_session,
            opportunity_id=opportunity_id,
            decision=OpportunityDecision("reject", "  "),
            actor_id=opp_world["director"],
            organization_id=opp_world["org"],
        )


def test_decision_writes_all_three_columns_together(owner_session, opp_world):
    """opportunities_decision_complete permits no partial decision."""
    opportunity_id = _make(owner_session, opp_world, status_to="awaiting_decision")

    new_status = decide_opportunity(
        owner_session,
        opportunity_id=opportunity_id,
        decision=OpportunityDecision("approve", "Market data supports the volume case"),
        actor_id=opp_world["director"],
        organization_id=opp_world["org"],
    )
    owner_session.flush()

    assert new_status == "approved"
    row = (
        owner_session.execute(
            text(
                """
                SELECT status, decision, decided_by, decided_at, decision_rationale
                FROM innovation.opportunities WHERE id = :i AND organization_id = :o
                """
            ),
            {"i": opportunity_id, "o": opp_world["org"]},
        )
        .mappings()
        .one()
    )
    assert row["status"] == "approved"
    assert row["decision"] == "approve"
    assert row["decided_by"] == opp_world["director"]
    assert row["decided_at"] is not None
    assert "volume case" in row["decision_rationale"]


def test_a_second_decision_is_refused_not_overwritten(owner_session, opp_world):
    """'Rejected in March, approved in April' is history an audit asks for."""
    opportunity_id = _make(owner_session, opp_world, status_to="awaiting_decision")

    decide_opportunity(
        owner_session,
        opportunity_id=opportunity_id,
        decision=OpportunityDecision("reject", "No commercial case"),
        actor_id=opp_world["director"],
        organization_id=opp_world["org"],
    )
    owner_session.flush()

    with pytest.raises(OpportunityStateError, match="cannot be decided"):
        decide_opportunity(
            owner_session,
            opportunity_id=opportunity_id,
            decision=OpportunityDecision("approve", "changed my mind"),
            actor_id=opp_world["director"],
            organization_id=opp_world["org"],
        )


def test_on_hold_is_not_a_one_way_door(owner_session, opp_world):
    """Migration 008's second defect.

    'on_hold' existed in the table from migration 003 and the service
    could only decide {feasibility, awaiting_decision} -- so 'revisit next
    quarter' meant 'never'. Nothing type-checks that gap.
    """
    opportunity_id = _make(owner_session, opp_world, status_to="awaiting_decision")

    held = decide_opportunity(
        owner_session,
        opportunity_id=opportunity_id,
        decision=OpportunityDecision("hold", "Revisit when the resin price settles"),
        actor_id=opp_world["director"],
        organization_id=opp_world["org"],
    )
    owner_session.flush()
    assert held == "on_hold"

    # The point of the test: it can be decided again.
    resumed = decide_opportunity(
        owner_session,
        opportunity_id=opportunity_id,
        decision=OpportunityDecision("approve", "Resin price settled"),
        actor_id=opp_world["director"],
        organization_id=opp_world["org"],
    )
    owner_session.flush()
    assert resumed == "approved"


def test_only_an_approved_opportunity_becomes_a_project(owner_session, opp_world):
    opportunity_id = _make(owner_session, opp_world, status_to="awaiting_decision")
    decide_opportunity(
        owner_session,
        opportunity_id=opportunity_id,
        decision=OpportunityDecision("reject", "No case"),
        actor_id=opp_world["director"],
        organization_id=opp_world["org"],
    )
    owner_session.flush()

    with pytest.raises(OpportunityStateError, match="only an approved opportunity"):
        convert_to_project(
            owner_session,
            opportunity_id=opportunity_id,
            project_code=f"RDP-{opp_world['suffix']}",
            name="Should not exist",
            lead_user_id=opp_world["director"],
            actor_id=opp_world["director"],
            organization_id=opp_world["org"],
        )


def test_conversion_keeps_the_thread_and_enrols_the_lead(owner_session, opp_world):
    """The link back is the whole reason this module exists (CLAUDE.md §2)."""
    opportunity_id = _make(owner_session, opp_world, status_to="awaiting_decision")
    decide_opportunity(
        owner_session,
        opportunity_id=opportunity_id,
        decision=OpportunityDecision("approve", "Approved at the January gate"),
        actor_id=opp_world["director"],
        organization_id=opp_world["org"],
    )
    owner_session.flush()

    project_id = convert_to_project(
        owner_session,
        opportunity_id=opportunity_id,
        project_code=f"RDP-{opp_world['suffix']}",
        name="Fast-cure filler development",
        lead_user_id=opp_world["director"],
        actor_id=opp_world["director"],
        organization_id=opp_world["org"],
        confidentiality="restricted",
    )
    owner_session.flush()

    row = (
        owner_session.execute(
            text(
                """
                SELECT p.opportunity_id, p.product_family, p.priority, o.status
                FROM projects.projects p
                JOIN innovation.opportunities o ON o.id = p.opportunity_id
                WHERE p.id = :p AND p.organization_id = :o
                """
            ),
            {"p": project_id, "o": opp_world["org"]},
        )
        .mappings()
        .one()
    )
    assert row["opportunity_id"] == opportunity_id
    # Carried across, not retyped by the user.
    assert row["product_family"] == "polyester_filler"
    assert row["priority"] == "high"
    assert row["status"] == "converted"

    # The lead is a member. Without this a restricted project is invisible
    # to its own lead on the next request -- RLS behaving correctly,
    # looking exactly like a failed save.
    is_member = owner_session.execute(
        text(
            """
            SELECT EXISTS (
                SELECT 1 FROM projects.project_members
                WHERE project_id = :p AND user_id = :u AND organization_id = :o
            )
            """
        ),
        {"p": project_id, "u": opp_world["director"], "o": opp_world["org"]},
    ).scalar_one()
    assert is_member is True


def test_one_project_per_opportunity_is_enforced_by_the_database(owner_session, opp_world):
    """The service checks it, but a service check is advisory.

    Migration 008 adds a partial unique index, because the service is not
    the only thing that will ever write projects -- a background job, a
    data fix or a later module reaching the table directly is governed
    only by the database.
    """
    opportunity_id = _make(owner_session, opp_world, status_to="awaiting_decision")
    decide_opportunity(
        owner_session,
        opportunity_id=opportunity_id,
        decision=OpportunityDecision("approve", "Approved"),
        actor_id=opp_world["director"],
        organization_id=opp_world["org"],
    )
    owner_session.flush()
    convert_to_project(
        owner_session,
        opportunity_id=opportunity_id,
        project_code=f"RDP-{opp_world['suffix']}-A",
        name="First",
        lead_user_id=opp_world["director"],
        actor_id=opp_world["director"],
        organization_id=opp_world["org"],
    )
    owner_session.flush()

    # Bypass the service entirely -- this is the path the index exists for.
    with pytest.raises(IntegrityError):
        owner_session.execute(
            text(
                """
                INSERT INTO projects.projects
                    (organization_id, project_code, name, opportunity_id)
                VALUES (:o, :c, 'Sibling', :opp)
                """
            ),
            {"o": opp_world["org"], "c": f"RDP-{opp_world['suffix']}-B", "opp": opportunity_id},
        )
        owner_session.flush()


def test_projects_without_an_opportunity_do_not_collide(owner_session, opp_world):
    """The unique index is PARTIAL. NULL opportunity_id must be unlimited.

    A non-partial index would let exactly one project per organization
    exist without an originating opportunity, which is not a rule anybody
    stated and would block the ordinary 'raise a project directly' path.
    """
    for label in ("A", "B", "C"):
        owner_session.execute(
            text(
                """
                INSERT INTO projects.projects
                    (organization_id, project_code, name)
                VALUES (:o, :c, :n)
                """
            ),
            {
                "o": opp_world["org"],
                "c": f"RDP-{opp_world['suffix']}-DIRECT-{label}",
                "n": f"Direct {label}",
            },
        )
    owner_session.flush()

    count = owner_session.execute(
        text(
            """
            SELECT COUNT(*) FROM projects.projects
            WHERE organization_id = :o AND opportunity_id IS NULL
            """
        ),
        {"o": opp_world["org"]},
    ).scalar_one()
    assert count == 3


def test_duplicate_opportunity_code_is_refused_per_organization(owner_session, opp_world):
    _make(owner_session, opp_world, code_suffix="DUP")
    with pytest.raises(OpportunityStateError, match="already exists"):
        _make(owner_session, opp_world, code_suffix="DUP")


def test_detail_and_funnel_report_the_conversion(owner_session, opp_world):
    opportunity_id = _make(owner_session, opp_world, status_to="awaiting_decision")
    decide_opportunity(
        owner_session,
        opportunity_id=opportunity_id,
        decision=OpportunityDecision("approve", "Approved"),
        actor_id=opp_world["director"],
        organization_id=opp_world["org"],
    )
    owner_session.flush()
    convert_to_project(
        owner_session,
        opportunity_id=opportunity_id,
        project_code=f"RDP-{opp_world['suffix']}-F",
        name="Funnel project",
        lead_user_id=opp_world["director"],
        actor_id=opp_world["director"],
        organization_id=opp_world["org"],
    )
    owner_session.flush()

    detail = opportunity_detail(
        owner_session, opportunity_id=opportunity_id, organization_id=opp_world["org"]
    )
    assert detail["project_code"] == f"RDP-{opp_world['suffix']}-F"
    assert detail["decided_by_name"] == "Director"

    funnel = list_opportunities(owner_session, organization_id=opp_world["org"])
    assert len(funnel) == 1
    assert funnel[0]["status"] == "converted"
    assert funnel[0]["project_code"] == f"RDP-{opp_world['suffix']}-F"


def test_a_missing_opportunity_is_not_found(owner_session, opp_world):
    with pytest.raises(OpportunityNotFoundError):
        opportunity_detail(
            owner_session,
            opportunity_id=uuid.uuid4(),
            organization_id=opp_world["org"],
        )
