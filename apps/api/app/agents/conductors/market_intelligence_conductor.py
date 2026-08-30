"""Market intelligence — the department that curates the public catalogue.

The owner's instruction: "the global competitor product marketplace must be
managed by agents". This is that department.

🔴 IT PROPOSES. IT DOES NOT PUBLISH, AND THAT IS NOT ENFORCED IN THIS FILE.

Everything this conductor writes lands as a draft, and a human decides whether
it becomes public. That is rule 4 ("Humans approve") and it is the
specification's own words: a detected product "creates a reviewable draft
rather than automatically publishing an unverified product record".

The mechanism is migration 060: a trigger keyed on `session_user` that refuses
a non-draft write from `evercoat_agent`. It is a property of the CONNECTION.

🔴 SO THIS CONDUCTOR USES **TWO** SESSIONS, AND BOTH ARE LOAD-BEARING.

An earlier draft of this file took no session at all and opened only the agent
one. `test_every_conductor_entry_point_authorizes_before_it_gates` refused it,
correctly, and the refusal is the I105 lesson: `require()` gates on a
permission set, and a set that did not come from the database is one the caller
supplied. `AgentPrincipal.authorize()` REPLACES the claimed set with one read
from `core.authorization_for_current_session()` — which is keyed on the tenant
GUC and therefore needs the CALLER'S OWN RLS-SCOPED SESSION.

The agent connection cannot serve that: it has no tenant GUC and no privilege
on `core` at all. So:

    session       -- the caller's. Answers "may this person do this?"
    agent_session -- the agent's.  Answers "may this WRITE be published?"

Neither substitutes for the other. Authorize on the agent session and the gate
consults nothing; write on the caller's session and the draft-only trigger
never fires, because it reads `session_user`. The second failure is the
dangerous one: everything would succeed, and an agent could publish invented
claims to anonymous readers with nothing in the code looking different.
`tests/test_agent_pool_boundary.py` asserts the writes go through the agent
pool.

⚠️ The catalogue is GLOBAL and has no tenant, so no tenant filtering is lost by
writing outside the caller's session — the caller's session is here for
authority, not for scoping rows.

🔴 SPECIALISTS NEVER CALL OTHER AGENTS (§0.2). This conductor calls TOOLS. It
does not call another conductor and it is not called by a route;
`root_orchestrator` is the only caller and `tests/test_agent_topology.py`
enforces both directions.
"""

from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from app.agents.boundary import require
from app.agents.principal import AgentPrincipal
from app.agents.tools import market_intelligence
from app.core.db import agent_session_scope
from app.domains.opportunities.service import (
    OpportunityInput,
    OpportunityStateError,
    create_opportunity,
)

__all__ = [
    "CurationResult",
    "propose_catalogue_entry",
    "propose_opportunities_from_marketplace",
    "read_review_queue",
]

# The department's gate. `material.view` is the permission that already governs
# competitor intelligence internally (`/api/competitors` requires it), so the
# same authority governs proposing into the public catalogue rather than a new
# permission nobody grants.
DEPARTMENT = "market_intelligence"
PERMISSION = "material.view"


@dataclass(frozen=True, slots=True)
class CurationResult:
    """What was proposed, and the fact that nothing was published."""

    manufacturer_id: uuid.UUID
    product_id: uuid.UUID | None
    news_id: uuid.UUID | None
    publication_status: str

    @property
    def published(self) -> bool:
        """Always False, and asserted rather than assumed.

        A caller that wants to know whether this reached the public catalogue
        should be able to ask, and get the honest answer every time.
        """
        return self.publication_status == "published"


def propose_catalogue_entry(
    session: Session,
    caller: AgentPrincipal,
    *,
    manufacturer_name: str,
    product_name: str | None = None,
    category: str | None = None,
    chemistry: str | None = None,
    region: str | None = None,
    description: str | None = None,
    price_amount: Decimal | None = None,
    price_currency: str | None = None,
    price_as_of: str | None = None,
    source_url: str | None = None,
    generated_by: str = "market_intelligence_conductor",
) -> CurationResult:
    """Propose a manufacturer, and optionally a product, into the catalogue.

    `session` is the CALLER'S, and it is used for authorization only. The
    writes go to `agent_session` — see the module header for why the two
    cannot be collapsed.
    """
    caller = caller.authorize(session)
    require(caller, department=DEPARTMENT, permission=PERMISSION)

    with agent_session_scope() as agent_session:
        manufacturer_id = market_intelligence.draft_manufacturer(
            agent_session,
            name=manufacturer_name,
            source_url=source_url,
            generated_by=generated_by,
        )

        product_id: uuid.UUID | None = None
        status = "draft"
        if product_name is not None:
            drafted = market_intelligence.draft_product(
                agent_session,
                manufacturer_id=manufacturer_id,
                product_name=product_name,
                category=category,
                chemistry=chemistry,
                region=region,
                description=description,
                price_amount=price_amount,
                price_currency=price_currency,
                price_as_of=price_as_of,
                source_url=source_url,
                generated_by=generated_by,
            )
            product_id = drafted.product_id
            # Read back from the row rather than asserting "draft" as a
            # literal. If the boundary ever stopped holding, this reports it
            # instead of restating the intention.
            status = drafted.publication_status

    return CurationResult(
        manufacturer_id=manufacturer_id,
        product_id=product_id,
        news_id=None,
        publication_status=status,
    )


def read_review_queue(
    session: Session, caller: AgentPrincipal, *, limit: int = 50
) -> list[dict[str, object]]:
    """What the agent tier has proposed and no human has decided on.

    The queue is the handover. A tier that proposed into something nobody could
    read would produce output that never reached a person, which is the same
    defect as a route with no caller.
    """
    caller = caller.authorize(session)
    require(caller, department=DEPARTMENT, permission=PERMISSION)
    with agent_session_scope() as agent_session:
        return market_intelligence.review_queue(agent_session, limit=limit)


def propose_opportunities_from_marketplace(
    session: Session, caller: AgentPrincipal, *, limit: int = 5
) -> list[dict[str, object]]:
    """Review the public catalogue and raise Innovation opportunities as DRAFTS.

    Owner instruction: *"opportunities must be identified by agent who reviews
    and analyses the products and uploads the opportunities to innovations."*

    🔴 WHAT THE AGENT ACTUALLY KNOWS, AND WHAT IT DOES NOT.

    It knows two facts, both counted from the database: how many products the
    public catalogue publishes in a category, and how many of them THIS
    organization has adopted into its own pipeline. A category with many of the
    first and none of the second is a coverage gap — a real, checkable
    statement about this application's own records.

    It does NOT know that the gap is commercially attractive, that the category
    is growing, or that Evercoat should enter it. Those are market judgements,
    and an agent asserting them would be producing a prediction shaped like a
    measurement — which rule 3 forbids and §7 forbids again.

    So the opportunity it writes SAYS what it is built from, in the record
    itself. A reader who disagrees can see exactly which two numbers produced
    it.

    🔴 EVERY ONE IS A DRAFT, AND THAT IS THE EXISTING WORKFLOW, NOT A NEW ONE.

    `create_opportunity` writes `status='draft'`, and only `submit_opportunity`
    — a human action — moves it to a decidable state. Rule 4: humans approve.
    The specification says the same: the news module "should create an
    Opportunity Candidate that an authorized user reviews before entering the
    existing development workflow."

    ⚠️ THE CALLER'S SESSION, NOT THE AGENT POOL. Opportunities are TENANT data
    and the gap analysis reads this tenant's adoptions through RLS. The agent
    connection has no tenant and could not scope either. The draft-only trigger
    is a `public_intel` control; nothing here writes to `public_intel`.
    """
    caller = caller.authorize(session)
    require(caller, department=DEPARTMENT, permission="opportunity.create")

    gaps = market_intelligence.category_gaps(session, limit=limit)
    raised: list[dict[str, object]] = []
    year = dt.date.today().year

    for index, gap in enumerate(gaps, start=1):
        if gap.adopted:
            # Not a gap. Skipping rather than raising a weaker opportunity
            # keeps the queue meaningful — a reviewer who finds obvious noise
            # in it stops reading the queue.
            continue
        code = f"OPP-{year}-MKT{index:02d}"
        try:
            opportunity_id = create_opportunity(
                session,
                data=OpportunityInput(
                    opportunity_code=code,
                    title=f"No competitor coverage adopted in {gap.category}",
                    market_need=(
                        f"The public competitor catalogue publishes "
                        f"{gap.competitor_products} product(s) in "
                        f"{gap.category} from {gap.manufacturers} "
                        f"manufacturer(s). This organization has adopted none "
                        f"into its pipeline, so no benchmark or composition "
                        f"evidence exists for the category."
                    ),
                    product_family=gap.category,
                    technical_concept=(
                        "Raised automatically from a coverage count, not from a "
                        "market assessment. It states what the catalogue holds "
                        "and what this organization has looked at — nothing "
                        "about demand, margin or fit. A human decides whether "
                        "it is worth pursuing."
                    ),
                    priority="medium",
                ),
                actor_id=caller.user_id,
                organization_id=caller.organization_id,
            )
        except OpportunityStateError:
            # Almost always the code already exists from an earlier run. A
            # re-run must not fail the whole sweep over one duplicate.
            continue
        raised.append(
            {
                "opportunity_id": str(opportunity_id),
                "opportunity_code": code,
                "category": gap.category,
                "competitor_products": gap.competitor_products,
                "adopted": gap.adopted,
                "status": "draft",
            }
        )

    return raised
