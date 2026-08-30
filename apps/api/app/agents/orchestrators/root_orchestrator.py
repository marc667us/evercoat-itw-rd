"""Root Orchestrator — the only door into the agent tier.

🔴 §0.2, LITERALLY: *"API routes never call specialists directly. MSD is
reached through the orchestrator."*

Today it routes one department, and that is not an argument for skipping
it. The rule earns its keep at the second department, when a route that
had learned to import a conductor directly would keep doing so — and the
orchestrator is also the single place where cross-cutting obligations
belong: the authorization boundary is asserted here for every request,
whatever department serves it.

`tests/test_agent_topology.py` enforces the structure rather than trusting
it: no module under `app/api/` may import a conductor or a tool.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.agents.conductors import (
    analysis_conductor,
    formulations_conductor,
    innovation_conductor,
    knowledge_conductor,
    laboratory_conductor,
    market_intelligence_conductor,
    materials_conductor,
    msd_conductor,
    quality_conductor,
    testing_conductor,
)
from app.agents.conductors.analysis_conductor import UnknownDashboardError
from app.agents.conductors.msd_conductor import MsdAnswer
from app.agents.ports import LanguageModelPort
from app.agents.principal import AgentPrincipal

__all__ = [
    "AgentPrincipal",
    "UnknownDashboardError",
    "analysis_analytics",
    "analysis_dashboard",
    "analysis_report",
    "answer_question",
    "formulations_classifications",
    "formulations_comparison",
    "formulations_evaluation",
    "formulations_formulas",
    "formulations_version",
    "innovation_opportunities",
    "innovation_opportunity",
    "knowledge_documents",
    "knowledge_search",
    "laboratory_batch",
    "laboratory_batches",
    "market_intelligence_propose",
    "market_intelligence_review_queue",
    "materials_documents",
    "materials_material",
    "materials_materials",
    "materials_suppliers",
    "materials_usage",
    "msd_threads",
    "msd_turns",
    "quality_failure",
    "quality_failures",
    "testing_methods",
    "testing_test",
    "testing_tests",
]

# 🔴 RE-EXPORTED ON PURPOSE, AND IT IS NOT A CONVENIENCE.
#
# A route must build an `AgentPrincipal` to call anything here, and
# `tests/test_agent_topology.py` forbids an API module importing anything
# under `app.agents.conductors` or `app.agents.tools`. Without this
# re-export the rule would push routes toward importing
# `app.agents.principal` directly — a second agent-tier import path, which
# is the shape §0.2 exists to prevent. One door means one import.


def answer_question(
    session: Session,
    *,
    caller: AgentPrincipal,
    question: str,
    project_id: uuid.UUID | None = None,
    model: LanguageModelPort | None = None,
) -> MsdAnswer:
    """Answer a question as the given principal.

    🔴 THIS DOCSTRING USED TO BE THE ONLY THING ENFORCING I104.

    It said, correctly and uselessly: *"EVERY ARGUMENT HERE COMES FROM A
    VERIFIED PRINCIPAL, NOT FROM THE REQUEST BODY."* The signature was
    `organization_id`, `user_id`, `role_codes` and `permissions` — four
    ordinary keyword arguments — so the sentence was a request to the next
    caller, not a property of the function. Codex raised it; it was true.
    An in-process caller could name a colleague's `user_id` and ask MSD
    what was waiting for them, or hand in a permission set the conductor
    would then faithfully consult.

    There is now one argument, and it cannot be assembled from values:
    `AgentPrincipal.of(principal)` is the only factory and it demands the
    `Principal` the route resolved from a signature-verified token plus a
    database lookup. See `app/agents/principal.py`.

    `session` must be the caller's own RLS-scoped session — the mechanism §7
    relies on, so retrieval returns what this person can open and filtering
    happens BEFORE anything reasons over it. The conductor now proves that
    against PostgreSQL's own GUCs rather than trusting it.
    """
    return msd_conductor.answer(
        session,
        caller=caller,
        question=question,
        project_id=project_id,
        model=model,
    )


# ---------------------------------------------------------------------------
# The other three departments.
#
# 🔴 THE RULE EARNS ITS KEEP HERE, AND THIS IS THE MOMENT IT PREDICTED.
#
# The module docstring above was written when there was exactly one
# department, and said so: *"Today it routes one department, and that is not
# an argument for skipping it. The rule earns its keep at the second
# department, when a route that had learned to import a conductor directly
# would keep doing so."* There are four now. Every one of them is reached
# through this module, and `tests/test_agent_topology.py` fails the build if
# an API module imports a conductor instead.
#
# These are STRUCTURAL entry points: they apply the department's permission
# gate (see `app/agents/boundary.py`) and dispatch to the domain service that
# owns the rules. None of them reasons, and none of them writes.
#
# ⚠️ THEY ARE READ-ONLY ON PURPOSE, AND THAT IS §4 RATHER THAN CAUTION.
# Humans approve. AI must not approve a test, change a controlled formula,
# move a result from YELLOW to GREEN, confirm a root cause or release a
# product. So no write-side service function is reachable from here at all --
# not `confirm_test`, not `approve`, not `authorize_batch`. A proposal an
# agent makes reaches a human through the approval engine, never through this
# door.
# ---------------------------------------------------------------------------


def laboratory_batches(
    session: Session,
    *,
    caller: AgentPrincipal,
    project_id: uuid.UUID | None = None,
    status: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """Lab batches, through the laboratory conductor."""
    return laboratory_conductor.batches(
        session,
        caller=caller,
        project_id=project_id,
        status=status,
        limit=limit,
    )


def laboratory_batch(
    session: Session,
    *,
    batch_id: uuid.UUID,
    caller: AgentPrincipal,
) -> dict[str, Any]:
    """One lab batch, through the laboratory conductor."""
    return laboratory_conductor.batch(
        session,
        batch_id=batch_id,
        caller=caller,
    )


def testing_tests(
    session: Session,
    *,
    caller: AgentPrincipal,
    project_id: uuid.UUID | None = None,
    review_state: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """The test queue, through the testing conductor."""
    return testing_conductor.tests(
        session,
        caller=caller,
        project_id=project_id,
        review_state=review_state,
        limit=limit,
    )


def testing_test(
    session: Session,
    *,
    test_id: uuid.UUID,
    caller: AgentPrincipal,
) -> dict[str, Any]:
    """One test and its derived disposition, through the testing conductor."""
    return testing_conductor.test(
        session,
        test_id=test_id,
        caller=caller,
    )


def testing_methods(
    session: Session,
    *,
    caller: AgentPrincipal,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """Test methods, through the testing conductor."""
    return testing_conductor.methods(
        session,
        caller=caller,
        limit=limit,
    )


def analysis_dashboard(
    session: Session,
    *,
    name: str,
    caller: AgentPrincipal,
) -> dict[str, Any]:
    """One dashboard, through the analysis conductor."""
    return analysis_conductor.dashboard(session, name=name, caller=caller)


def analysis_report(
    session: Session,
    *,
    caller: AgentPrincipal,
    project_id: uuid.UUID | None = None,
    limit: int = 200,
) -> dict[str, Any]:
    """The test-results report, through the analysis conductor."""
    return analysis_conductor.report(
        session,
        caller=caller,
        project_id=project_id,
        limit=limit,
    )


def analysis_analytics(
    session: Session,
    *,
    caller: AgentPrincipal,
    project_id: uuid.UUID | None = None,
    limit: int = 200,
) -> dict[str, Any]:
    """Testing and laboratory activity, counted — through the analysis conductor.

    Gated on `analytics.view`, with the organization-wide `by_project`
    breakdown gated separately on `analytics.portfolio`. Those two
    permissions are held by nine and two of the ten seeded roles and, until
    this entry point, were read by no line of application code.
    """
    return analysis_conductor.analytics(session, caller=caller, project_id=project_id, limit=limit)


# ---------------------------------------------------------------------------
# MSD's conversation surface.
#
# 🔴 THE DEPARTMENT §0.2 NAMES BY NAME NOW HAS ONE DOOR INSTEAD OF FOUR.
#
# *"API routes never call specialists directly. MSD is reached through the
# orchestrator."* Three of MSD's four endpoints imported
# `app.domains.msd.service` and called it — governed asking, ungoverned
# reading. See `msd_conductor`'s conversation section for what that meant in
# practice and for the measurement of who the `msd.use` gate newly refuses.
#
# ⚠️ READS ONLY. `open_thread` and `record_exchange` stay on the route, like
# every other write in this tier (§4).
# ---------------------------------------------------------------------------


def msd_threads(
    session: Session, *, caller: AgentPrincipal, limit: int = 50
) -> list[dict[str, Any]]:
    """The caller's own MSD conversations, through the MSD conductor."""
    return msd_conductor.threads(session, caller=caller, limit=limit)


def msd_turns(
    session: Session, *, caller: AgentPrincipal, thread_id: uuid.UUID, limit: int = 200
) -> list[dict[str, Any]]:
    """One conversation and its evidence, through the MSD conductor."""
    return msd_conductor.turns(session, caller=caller, thread_id=thread_id, limit=limit)


# ---------------------------------------------------------------------------
# Five more departments — formulations, materials, innovation, quality,
# knowledge.
#
# 🔴 EVERY ONE OF THESE HAD A ROUTE AND NO DOOR, WHICH IS THE SAME DEFECT AS A
# CONDUCTOR WITH NO CALLERS.
#
# Before this, eight of nineteen API modules never touched the orchestrator at
# all. The four wired departments were the ones an agent happened to need, so
# §0.2's topology described a quarter of the product and the rest was a
# convention that had not been tested. A question put to MSD about a raw
# material, a formula's genealogy, an open failure investigation or the
# opportunity pipeline had NOWHERE to be answered from except a domain service
# with no permission gate on the non-HTTP path.
#
# ⚠️ THEY ARE READ-ONLY, LIKE THE OTHERS, AND FOR THE SAME REASON. §4: humans
# approve. No `submit_version`, no `accept_root_cause`, no `create_material`, no
# `ingest_document` is reachable from this module. `export_version` is absent
# too, and that one is a read — it WRITES an export audit event naming the
# actor, and §4 keeps the audited act of taking proprietary composition out of
# the building on the human path.
#
# ⚠️ AND THE GATE IS THE CONDUCTOR'S, NOT THIS FILE'S. Nothing here checks a
# permission. Each function below is a dispatch; the department owns its own
# requirement, which is what stops this module becoming a second, competing
# statement of the authorization model.
# ---------------------------------------------------------------------------


def formulations_formulas(
    session: Session,
    *,
    caller: AgentPrincipal,
    project_id: uuid.UUID | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """Formulas, through the formulations conductor."""
    return formulations_conductor.formulas(
        session, caller=caller, project_id=project_id, limit=limit
    )


def formulations_version(
    session: Session, *, version_id: uuid.UUID, caller: AgentPrincipal
) -> dict[str, Any]:
    """One formula version — cost included only if the caller holds it."""
    return formulations_conductor.version(session, version_id=version_id, caller=caller)


def formulations_evaluation(
    session: Session, *, version_id: uuid.UUID, caller: AgentPrincipal
) -> dict[str, Any]:
    """The version's computed evaluation, through the formulations conductor."""
    return formulations_conductor.evaluation(session, version_id=version_id, caller=caller)


def formulations_comparison(
    session: Session,
    *,
    left_version_id: uuid.UUID,
    right_version_id: uuid.UUID,
    caller: AgentPrincipal,
) -> dict[str, Any]:
    """Two versions against each other, through the formulations conductor."""
    return formulations_conductor.comparison(
        session,
        left_version_id=left_version_id,
        right_version_id=right_version_id,
        caller=caller,
    )


def formulations_classifications(
    session: Session, *, caller: AgentPrincipal
) -> list[dict[str, Any]]:
    """The confidentiality lattice, through the formulations conductor."""
    return formulations_conductor.classifications(session, caller=caller)


def materials_materials(
    session: Session,
    *,
    caller: AgentPrincipal,
    status: str | None = None,
    role: str | None = None,
    search: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """Raw materials, through the materials conductor."""
    return materials_conductor.materials(
        session, caller=caller, status=status, role=role, search=search, limit=limit
    )


def materials_material(
    session: Session, *, material_id: uuid.UUID, caller: AgentPrincipal
) -> dict[str, Any]:
    """One raw material, through the materials conductor."""
    return materials_conductor.material(session, material_id=material_id, caller=caller)


def materials_usage(
    session: Session, *, material_id: uuid.UUID, caller: AgentPrincipal
) -> list[dict[str, Any]]:
    """Where a material is used — needs `formula.view` as well as `material.view`."""
    return materials_conductor.usage(session, material_id=material_id, caller=caller)


def materials_documents(
    session: Session, *, material_id: uuid.UUID, caller: AgentPrincipal
) -> list[dict[str, Any]]:
    """A material's documents, through the materials conductor."""
    return materials_conductor.documents(session, material_id=material_id, caller=caller)


def materials_suppliers(
    session: Session,
    *,
    caller: AgentPrincipal,
    status: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """Suppliers, through the materials conductor — they share its permission."""
    return materials_conductor.suppliers(session, caller=caller, status=status, limit=limit)


def innovation_opportunities(
    session: Session,
    *,
    caller: AgentPrincipal,
    status: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """The opportunity pipeline, through the innovation conductor."""
    return innovation_conductor.opportunities(session, caller=caller, status=status, limit=limit)


def innovation_opportunity(
    session: Session, *, opportunity_id: uuid.UUID, caller: AgentPrincipal
) -> dict[str, Any]:
    """One opportunity, through the innovation conductor."""
    return innovation_conductor.opportunity(session, opportunity_id=opportunity_id, caller=caller)


def quality_failures(
    session: Session,
    *,
    caller: AgentPrincipal,
    project_id: uuid.UUID | None = None,
    status: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """Failure investigations, through the quality conductor."""
    return quality_conductor.failures(
        session, caller=caller, project_id=project_id, status=status, limit=limit
    )


def quality_failure(
    session: Session, *, failure_id: uuid.UUID, caller: AgentPrincipal
) -> dict[str, Any]:
    """One investigation and its hypotheses — whose status only a human moves."""
    return quality_conductor.failure(session, failure_id=failure_id, caller=caller)


def knowledge_documents(
    session: Session, *, caller: AgentPrincipal, limit: int = 100
) -> dict[str, Any]:
    """The library, through the knowledge conductor."""
    return knowledge_conductor.documents(session, caller=caller, limit=limit)


def knowledge_search(
    session: Session,
    *,
    caller: AgentPrincipal,
    question: str,
    limit: int = knowledge_conductor.MAX_SEARCH_RESULTS,
) -> list[dict[str, Any]]:
    """Ranked passages for a PERSON — no relevance cut, unlike MSD's tool."""
    return knowledge_conductor.search(session, caller=caller, question=question, limit=limit)


# ---------------------------------------------------------------------------
# Market intelligence — the department that curates the PUBLIC catalogue.
#
# 🔴 THE ONLY DEPARTMENT WHOSE WRITES LEAVE THE TENANT.
#
# Everything else here reads and writes records belonging to the caller's
# organization. This one proposes into `public_intel`, which has no tenant and
# is served to anonymous readers. That is why its conductor takes two sessions
# and why migration 060 exists: the caller's session answers "may this person
# do this", and the agent connection answers "may this write be published" --
# with the answer to the second being always no.
# ---------------------------------------------------------------------------


def market_intelligence_propose(
    session: Session,
    *,
    caller: AgentPrincipal,
    manufacturer_name: str,
    product_name: str | None = None,
    category: str | None = None,
    source_url: str | None = None,
) -> market_intelligence_conductor.CurationResult:
    """Propose a competitor product into the public catalogue, as a DRAFT.

    Nothing this returns is public. `CurationResult.published` is the honest
    answer to "did this reach anybody", and it is False.
    """
    return market_intelligence_conductor.propose_catalogue_entry(
        session,
        caller,
        manufacturer_name=manufacturer_name,
        product_name=product_name,
        category=category,
        source_url=source_url,
    )


def market_intelligence_review_queue(
    session: Session, *, caller: AgentPrincipal, limit: int = 50
) -> list[dict[str, Any]]:
    """What the agent tier has proposed and no human has decided on."""
    return market_intelligence_conductor.read_review_queue(session, caller, limit=limit)
