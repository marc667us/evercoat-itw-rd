"""MSD's answers, without a database and without a model.

That both are absent here is the point. `CLAUDE.md` §7 and the seven
non-negotiable rules constrain what MSD may SAY, and those constraints
have to be checkable without standing up a language model — otherwise
they can only be spot-checked by reading output, which is exactly how an
assistant's safety properties rot.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Any

import pytest

from app.agents.conductors.msd_conductor import (
    DISCLAIMER,
    MsdAnswer,
    _compose_comparison,
    _compose_figures,
    _compose_records,
    _compose_safety,
    _compose_usage,
    _compose_work,
    answer,
    classify,
)
from app.agents.ports import NullLanguageModel
from app.agents.principal import AgentPrincipal
from app.agents.tools import explain_the_application
from app.core.security import Principal
from app.domains.msd.retrieval import RetrievedRecord

# ---------------------------------------------------------------------------
# I104 — MSD now takes a verified principal and proves the session is its own
# ---------------------------------------------------------------------------
#
# 🔴 THESE TESTS USED TO PASS `session=None`, AND THAT IS NO LONGER HONEST.
#
# `answer()` took `organization_id`, `user_id`, `role_codes` and `permissions`
# as four ordinary arguments, so a test could state an identity without
# holding one -- which was the defect (I104), visible here as the convenience
# of not needing a session at all when every tool was stubbed.
#
# It now takes an `AgentPrincipal` and calls `caller.bind(session)`, which
# asks PostgreSQL whether `app.current_org` / `app.current_user_id` match.
# So these tests supply a session that answers that probe truthfully. The
# tools are still stubbed and no database is involved: the stub answers the
# identity question and nothing else, which is the whole point -- the boundary
# check is not something a test may opt out of, because the assistant is
# exactly where §7 says it must hold.

ORG = uuid.uuid4()
USER = uuid.uuid4()


def caller(*permissions: str) -> AgentPrincipal:
    """A verified caller holding exactly these permissions."""
    return AgentPrincipal.of(
        Principal(
            user_id=USER,
            organization_id=ORG,
            keycloak_sub=f"sub-{USER}",
            email="caller@example.test",
            display_name="Caller",
            roles=frozenset(),
            permissions=frozenset({"msd.use", *permissions}),
        )
    )


class _ScopedSession:
    """Answers the RLS identity probe as ORG/USER. Touches no database."""

    def execute(self, _statement: object, *args: object, **kwargs: object) -> object:
        row = SimpleNamespace(org=str(ORG), usr=str(USER))
        return SimpleNamespace(one=lambda: row)


class _ShoutyModel:
    """A model that rewords loudly, so its effect is visible."""

    def rephrase(self, *, composed: str, question: str) -> str:
        _ = question
        return composed.upper()


class _LyingModel:
    """A model that ignores what it was given and invents an answer.

    Not a realistic implementation — a deliberate adversary, used to show
    which properties survive a badly-behaved model and which do not.
    """

    def rephrase(self, *, composed: str, question: str) -> str:
        _ = composed, question
        return "Formula FRM-999 is approved for release."


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("What does yellow mean on this test?", "guidance"),
        ("how do I create a formula revision", "guidance"),
        ("what is waiting for me", "pending_work"),
        ("show me my work", "pending_work"),
        ("show me lightweight filler formulas", "find_records"),
        ("", "unsupported"),
        ("   ", "unsupported"),
        # 🔴 CHANGED CONTRACT, NOT A RELAXED TEST. An unrouted question is now
        # SEARCHED before it is refused -- see `classify`'s closing comment.
        # The refusal did not move to a weaker place: it moved DOWNSTREAM, to
        # `answer()`, where it is returned verbatim once the knowledge base has
        # actually been asked. The two tests below hold that line, and one of
        # them proves the other can fail.
        ("thoughts on the weather", "knowledge_search"),
    ],
)
def test_questions_route_to_the_right_capability(question: str, expected: str) -> None:
    assert classify(question) == expected


def test_an_unrouted_question_is_still_refused_when_the_search_finds_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """🔴 THE REFUSAL SURVIVED THE FALLBACK CHANGE.

    Routing everything unmatched into the knowledge base is only safe if
    "I could not find that" still comes out when the base has nothing. The
    failure mode being guarded is an assistant that, having gained a search,
    quietly starts answering questions it has no material for.
    """
    import app.agents.conductors.msd_conductor as conductor

    monkeypatch.setattr(conductor, "search_knowledge", lambda *a, **k: [])

    result = answer(
        session=_ScopedSession(),
        question="thoughts on the weather",
        # Held, so this test exercises the EMPTY SEARCH and not the permission
        # gate below it. Without it the refusal would arrive for the wrong
        # reason and the test would pass while proving nothing.
        caller=caller("knowledge.view"),
    )

    assert result.intent == "unsupported"
    assert result.body.startswith("I cannot answer that yet.")
    # And it must not have invented a destination for a question it refused.
    assert result.href is None


def test_the_refusal_test_can_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    """The falsification of the test above.

    Written because a guard that cannot fail has been this codebase's
    recurring defect -- three times in three days. If `answer()` refused
    unconditionally, the test above would pass for the wrong reason and the
    whole knowledge branch could be dead. Give the same question a passage and
    the intent MUST change.
    """
    import app.agents.conductors.msd_conductor as conductor

    monkeypatch.setattr(
        conductor,
        "search_knowledge",
        lambda *a, **k: [
            {
                "content": "Sanding is done wet, at 400 grit.",
                "title": "Application procedure",
                "source": "procedure",
                "document_id": uuid.uuid4(),
                "ordinal": 1,
                "classification": "INTERNAL",
                "distance": 0.1,
            }
        ],
    )

    result = answer(
        session=_ScopedSession(),
        question="thoughts on the weather",
        caller=caller("knowledge.view"),
    )

    assert result.intent == "knowledge_search"
    assert "400 grit" in result.body


def test_msd_will_not_search_knowledge_without_the_permission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """🔴 §7: MSD MUST NOT BE A PERMISSION-BYPASS CHANNEL.

    `GET /api/knowledge/search` requires `knowledge.view`. Without this gate a
    caller holding `msd.use` and NOT `knowledge.view` -- the Procurement
    Specialist, deliberately excluded in migration 043 -- could ask the
    assistant a knowledge-shaped question and receive the passages the screen
    would have refused them. Codex found it.

    Note what the gap was NOT: every passage returned would still have been
    inside the caller's organization and projects, because RLS never stopped
    applying. The gap is that a PERMISSION governing a surface was enforced on
    the surface and not on the assistant reading the same table.
    """
    import app.agents.conductors.msd_conductor as conductor

    called: list[str] = []

    def _should_not_run(*a: object, **k: object) -> list[dict[str, Any]]:
        called.append("searched")
        return [
            {
                "content": "Sanding is done wet, at 400 grit.",
                "title": "Application procedure",
                "source": "procedure",
                "document_id": uuid.uuid4(),
                "ordinal": 1,
                "classification": "INTERNAL",
                "distance": 0.1,
            }
        ]

    monkeypatch.setattr(conductor, "search_knowledge", _should_not_run)

    result = answer(
        session=_ScopedSession(),
        question="thoughts on the weather",
        # 🔴 NO knowledge.view -- this is the permission gate under test.
        caller=caller(),
    )

    assert not called, (
        "the knowledge base was searched for a caller without knowledge.view; "
        "the passages would have been handed to somebody the screen refuses"
    )
    assert result.intent == "unsupported"
    # And the refusal must not advertise the library it just declined to search.
    assert "knowledge" not in result.body.lower()


def test_guidance_wins_over_record_search() -> None:
    """🔴 THE ORDERING IS A SAFETY PROPERTY, NOT A PREFERENCE.

    "What does yellow mean" contains no search intent, but it does contain
    a word that appears in formula names. Falling through to record
    retrieval would search for "yellow" across the material and formula
    libraries and answer a question about the traffic light with a list of
    pigments — confidently, and completely wrongly.
    """
    assert classify("what does yellow mean on this test?") == "guidance"
    assert classify("what does green mean") == "guidance"


# ---------------------------------------------------------------------------
# What MSD is allowed to say
# ---------------------------------------------------------------------------


def test_every_answer_carries_the_required_label() -> None:
    """§7: AI recommendations are labelled. The database refuses an
    assistant turn without it (`msd_turns_assistant_is_labelled`), and
    this is the application half of the same rule."""
    result = MsdAnswer(body="anything", intent="guidance")
    assert result.disclaimer == DISCLAIMER
    assert "requires technical review" in result.disclaimer


def test_an_empty_search_does_not_claim_the_records_do_not_exist() -> None:
    """🔴 THE MOST IMPORTANT SENTENCE IN THIS MODULE.

    MSD sees only what the asker can read. "There are no formulas like
    that" is therefore a claim it is not entitled to make — the records
    may exist in a project the asker is not a member of, and saying they
    do not exist would both be false and disclose the shape of what does.
    """
    composed = _compose_records([])
    assert "no records you have access to" in composed
    assert "you may not be a member" in composed
    # The forbidden phrasings.
    assert "there are no" not in composed.lower()
    assert "do not exist" not in composed.lower()


def test_an_empty_inbox_is_not_congratulated() -> None:
    """An assistant that says "you are all caught up" over a list it could
    not fill is the same defect as a dashboard rendering an empty
    requirement set as ALL REQUIREMENTS PASSED."""
    composed = _compose_work([])
    assert "Nothing is currently assigned" in composed
    assert "caught up" not in composed.lower()


def test_overdue_work_is_named_as_overdue() -> None:
    tasks = [
        {
            "title": "Review batch LB-014",
            "status": "open",
            "is_overdue": True,
            "project_code": "RDP-2026-014",
            "due_date": "2026-08-01",
        },
        {
            "title": "Approve method",
            "status": "open",
            "is_overdue": False,
            "project_code": None,
            "due_date": None,
        },
    ]
    composed = _compose_work(tasks)
    assert "2 items" in composed
    assert "1 of them is overdue" in composed
    assert "RDP-2026-014" in composed


# ---------------------------------------------------------------------------
# The model may phrase. It may not introduce a fact.
# ---------------------------------------------------------------------------


def test_the_null_model_returns_the_composed_answer_verbatim() -> None:
    """The supported configuration: CI has no Ollama, the deployed site
    has no API, and §7 forbids depending on a paid one."""
    model = NullLanguageModel()
    assert model.rephrase(composed="six batches", question="how many?") == "six batches"


def test_the_model_only_ever_sees_an_already_composed_answer() -> None:
    """🔴 THE PORT HAS NO METHOD THAT TAKES A QUESTION AND RETURNS AN ANSWER.

    This is what makes the evidence list honest. A model can reword; it is
    never asked to produce the content, so there is no seam through which
    it could invent a formula code or a measurement.

    Asserted on the PROTOCOL's shape rather than on behaviour, because it
    is a structural property: adding a `generate(question)` method is the
    change this test exists to make somebody argue for.
    """
    from app.agents.ports import LanguageModelPort

    methods = {name for name in dir(LanguageModelPort) if not name.startswith("_")}
    assert methods == {"rephrase"}, (
        f"the language-model port gained {methods - {'rephrase'}}. A method that "
        "returns content rather than rewording it would let a model introduce "
        "facts nobody checked."
    )


def test_a_lying_model_cannot_corrupt_the_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    """What survives a badly-behaved model, stated honestly.

    A model that ignores its input CAN corrupt the prose — nothing in
    software prevents that, and pretending otherwise would be the kind of
    false assurance this codebase keeps finding. What it cannot do is
    change WHICH RECORDS the answer was built from: the evidence comes
    from the tool, is stored beside the turn, and
    `verify_evidence_within_boundary` can later prove every cited record
    was inside the asker's boundary.

    So the guarantee is precise: MSD's CITATIONS are trustworthy
    independently of the model, and its prose is trustworthy only to the
    extent the model is. That is why the default model is the null one.
    """
    records = [
        RetrievedRecord(
            entity_type="formula",
            entity_id=uuid.uuid4(),
            label="FRM-014 Lightweight Filler",
            excerpt="polyester body filler",
        )
    ]

    import app.agents.conductors.msd_conductor as conductor

    monkeypatch.setattr(conductor, "find_records", lambda *a, **k: records)

    result = answer(
        session=_ScopedSession(),
        caller=caller(),
        question="show me filler formulas",
        model=_LyingModel(),
    )

    # The prose is the model's, and it is wrong.
    assert "FRM-999" in result.body
    # The evidence is the TOOL's, and it is right.
    assert len(result.evidence) == 1
    assert result.evidence[0].label == "FRM-014 Lightweight Filler"
    assert all(r.label != "FRM-999" for r in result.evidence)


def test_a_model_rewords_without_changing_which_tools_ran() -> None:
    entry = explain_the_application("what does yellow mean")
    assert entry is not None

    result = answer(
        session=_ScopedSession(),
        caller=caller(),
        question="what does yellow mean",
        model=_ShoutyModel(),
    )
    assert result.body == entry.body.upper()
    assert result.tool_calls[0]["tool"] == "explain_the_application"


# ---------------------------------------------------------------------------
# Guidance must not drift from the rules it describes
# ---------------------------------------------------------------------------


def test_the_yellow_explanation_states_the_rule_that_matters() -> None:
    """§6/§10: a technically PASSING test stays YELLOW while mandatory
    approvals are incomplete. An explanation that omits that is worse than
    none, because yellow is the state people most want to explain away."""
    entry = explain_the_application("what does yellow mean")
    assert entry is not None
    assert "derived" in entry.body
    assert "approval" in entry.body.lower()
    assert "stays YELLOW" in entry.body


def test_the_green_explanation_refuses_to_be_a_bare_tick() -> None:
    """§10: GREEN is authority-qualified. A screening pass is never
    qualification evidence."""
    entry = explain_the_application("what does green mean")
    assert entry is not None
    assert "screening" in entry.body.lower()
    assert "authority" in entry.body.lower()


def test_guidance_returns_nothing_rather_than_guessing() -> None:
    assert explain_the_application("what is the airspeed of a swallow") is None


def test_every_retrievable_source_can_actually_be_stored_as_evidence() -> None:
    """🔴 THE TWO LITERALS THAT MUST AGREE, AND ALMOST DID NOT.

    `retrieve_for_question` decides which `entity_type` values MSD can
    produce; `ai.msd_evidence` has a CHECK constraint deciding which it
    will store. They are declared in different files, in different
    languages, and nothing connected them.

    If a source is ever added to `_SOURCES` whose name the constraint
    rejects, MSD would answer correctly and then fail at write time — on
    every answer that happened to cite that kind of record, and only
    those. An intermittent 500 that depends on what the search matched is
    about the worst shape a defect can have.

    Caught the near-miss the honest way: a test of mine used `'formula'`
    where the schema says `'formula_version'`, CI refused it, and the
    real question — *does the SERVICE emit valid values?* — turned out to
    be fine. This is that question asked permanently.
    """
    import re
    from pathlib import Path

    api_root = Path(__file__).resolve().parents[1]
    sql = (api_root / "migrations" / "022_messaging_notifications_msd.sql").read_text(
        encoding="utf-8"
    )
    block = sql[sql.index("CREATE TABLE IF NOT EXISTS ai.msd_evidence") :]
    match = re.search(
        r"entity_type\s+TEXT NOT NULL\s*CHECK \(entity_type IN \(([^)]*)\)", block, re.S
    )
    assert match is not None, "the entity_type CHECK constraint has moved or changed shape"
    allowed = set(re.findall(r"'([a-z_]+)'", match.group(1)))

    from app.domains.msd.retrieval import _SOURCES

    emitted = set(_SOURCES)
    assert emitted <= allowed, (
        "MSD can retrieve record kinds that ai.msd_evidence will refuse to "
        f"store: {sorted(emitted - allowed)}. Every answer citing one would "
        "fail at write time. Add them to the CHECK constraint in a migration."
    )


# ---------------------------------------------------------------------------
# Safety and the equations - Concept Note 11, 17 and rule 2
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "question",
    [
        "Show the current SDS for this resin.",
        "Which components in this formula are restricted?",
        "Are any material safety documents missing?",
        "Which formulas contain Material RM-104?",
    ],
)
def test_the_founders_four_safety_questions_reach_the_safety_tool(question: str) -> None:
    """All four are named in the source document, and all four contain search words.

    "which", "show", "contain" - a generic record search would swallow
    every one of them and answer a SAFETY question with a list of names
    carrying no safety state at all. So safety is classified BEFORE
    search, and this is the test that keeps it that way.
    """
    assert classify(question) == "material_safety"


@pytest.mark.parametrize(
    "question",
    [
        "what is the density of FRM-014",
        "what is the VOC content of FRM-014",
        "solids content of FRM-014",
        "calculate the total percentage",
    ],
)
def test_equation_questions_reach_the_calculation_tool(question: str) -> None:
    """Concept Note 17: the engine calculates, MSD interprets and communicates."""
    assert classify(question) == "formula_figures"


def test_msd_does_no_arithmetic_of_its_own() -> None:
    """Rule 2, as a structural check.

    "Python owns deterministic scientific calculation. The LLM may CALL
    calculation tools and EXPLAIN results; it must never perform the
    arithmetic."

    The formulation tool delegates to `evaluate_version`, which runs the
    Hypothesis-tested engine. If arithmetic ever appears in the agent
    tier this fails - a second implementation of "what is this formula's
    density" is the defect.
    """
    import ast
    from pathlib import Path

    agents = Path(__file__).resolve().parents[1] / "app" / "agents"
    offenders: list[str] = []
    for path in sorted(agents.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            # Division and multiplication are how a unit conversion or an
            # average sneaks in. String/list addition is fine, so only
            # these two are policed.
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div | ast.Mult):
                offenders.append(f"{path.name}:{node.lineno}")

    assert not offenders, (
        "arithmetic in the agent tier. Rule 2 gives calculation to "
        f"app/calculations/ and MSD may only explain the result: {offenders}"
    )


def test_a_safety_answer_says_who_decides() -> None:
    """Concept Note 11: MSD must not replace formal Compliance/QA review.

    A chemist who asks an assistant whether a material is safe and gets a
    confident sentence has been handed a regulatory opinion by a text
    generator. Every safety answer states what is ON FILE and names who
    decides.
    """
    composed = _compose_safety(
        [
            {
                "material_code": "RM-104",
                "name": "Polyester resin",
                "status": "approved",
                "restriction_reason": None,
                "hazard_summary": None,
                "requires_sds": True,
                "sds_count": 1,
                "sds_issued_on": "2026-01-04",
            }
        ]
    )
    assert "not a compliance determination" in composed
    assert "Compliance/QA" in composed


def test_a_missing_safety_data_sheet_is_stated_as_a_block() -> None:
    """The one actionable fact in a safety answer.

    Section 8 makes a `requires_sds` material with no SDS on file a hard
    block on submission that cannot be waived. Reporting it softly would
    be "absence presenting as a value" applied to safety.
    """
    composed = _compose_safety(
        [
            {
                "material_code": "RM-999",
                "name": "Unknown hardener",
                "status": "development",
                "restriction_reason": None,
                "hazard_summary": None,
                "requires_sds": True,
                "sds_count": 0,
                "sds_issued_on": None,
            }
        ]
    )
    assert "SAFETY DATA SHEET REQUIRED AND NONE IS ON FILE" in composed
    assert "blocks" in composed


def test_an_empty_usage_answer_does_not_say_nothing_uses_it() -> None:
    """The sentence somebody acts on during a recall.

    "Nothing uses RM-104" is what a person needs when a lot is recalled,
    and MSD cannot know it: a formula in a project the asker is not a
    member of is never returned. The empty case says what was actually
    established and names the reason.
    """
    composed = _compose_usage("RM-104", [])
    assert "no formula versions you have access to" in composed
    assert "not the same as none existing" in composed
    assert "Compliance/QA" in composed
    assert "nothing uses" not in composed.lower()


def test_a_property_that_could_not_be_computed_says_so() -> None:
    """`evaluate_version` returns a value OR a stated reason, never a blank."""
    composed = _compose_figures(
        "FRM-014 v3",
        {
            "component_count": 4,
            "properties": {
                "total_percentage": {"value": "100.00", "unavailable_reason": None},
                "theoretical_density_g_cm3": {
                    "value": None,
                    "unavailable_reason": "density unknown for: RM-FIL-07",
                },
            },
            "submission_blocks": [],
            "submittable": True,
            "version": {"status": "draft"},
        },
    )
    assert "Total percentage: 100.00" in composed
    assert "NOT CALCULATED" in composed
    assert "density unknown for: RM-FIL-07" in composed


def test_cost_is_absent_rather_than_null_without_the_permission() -> None:
    """Asking MSD is not a way around `formula.view_cost`.

    `evaluate_version` omits the KEY when the caller lacks the permission
    - a null would read as "no cost data exists", a different and false
    statement - and the composition must not reintroduce it as
    "cost: not available".
    """
    composed = _compose_figures(
        "FRM-014 v3",
        {
            "component_count": 4,
            "properties": {"total_percentage": {"value": "100.00", "unavailable_reason": None}},
            "submission_blocks": [],
            "submittable": True,
            "version": {"status": "draft"},
        },
    )
    assert "cost" not in composed.lower()


# ---------------------------------------------------------------------------
# Formula comparison - Concept Note section 9
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "question",
    [
        "Compare F005 and F008",
        "compare FRM-014 and FRM-021 on density",
        "difference between F018 and F023",
    ],
)
def test_comparison_questions_reach_the_comparison_tool(question):
    """Checked BEFORE the single-formula equations.

    "compare F018 and F023 on density" names a property, and answering it
    with ONE formula density would be a confident non-answer to the
    question actually asked.
    """
    assert classify(question) == "compare_formulas"


def test_a_comparison_shows_a_pair_of_percentages_never_a_delta():
    """The rule `compare_versions` states and this must not relax.

    "The percentage-point delta on a component is a SUBTRACTION OF TWO
    PERCENTAGES and is therefore arithmetic -- so it is not done here."
    Two such conversions were already caught inside React components on
    this project. A number MSD prints is a number a chemist may quote.
    """
    composed = _compose_comparison(
        "FRM-014 v2",
        "FRM-014 v3",
        {
            "previous": {"status": "approved"},
            "new": {"status": "draft"},
            "change_reason": "reduce density",
            "technical_hypothesis": None,
            "expected_effect": None,
            "observed_effect": None,
            "components": [
                {
                    "material_code": "RM-TAL-01",
                    "material_name": "Talc",
                    "previous_percentage": "12.5000",
                    "new_percentage": "9.0000",
                    "change": "changed",
                },
                {
                    "material_code": "RM-MSP-02",
                    "material_name": "Glass microspheres",
                    "previous_percentage": None,
                    "new_percentage": "4.0000",
                    "change": "added",
                },
            ],
            "previous_properties": {
                "theoretical_density_g_cm3": {"value": "1.5790", "unavailable_reason": None}
            },
            "new_properties": {
                "theoretical_density_g_cm3": {"value": "1.0920", "unavailable_reason": None}
            },
        },
    )
    assert "12.5000% -> 9.0000%" in composed
    assert "ADDED RM-MSP-02" in composed
    assert "1.5790 -> 1.0920" in composed
    # No computed difference anywhere.
    assert "-3.5" not in composed
    assert "3.5000" not in composed
    assert "0.487" not in composed


def test_a_comparison_says_it_is_not_a_performance_comparison():
    """Section 9 also asks for sanding, adhesion, failure history and
    statistical significance. Those need the test records for both
    versions, which this comparison does not read. Silence would let a
    reader take a composition diff for a performance comparison."""
    composed = _compose_comparison(
        "A",
        "B",
        {
            "previous": {},
            "new": {},
            "change_reason": None,
            "technical_hypothesis": None,
            "expected_effect": None,
            "observed_effect": None,
            "components": [],
            "previous_properties": {},
            "new_properties": {},
        },
    )
    assert "does not" in composed
    assert "test performance" in composed
    assert "statistical" in composed


def test_an_untested_revision_says_the_observed_effect_is_not_recorded():
    """Absence stated as absence. `observed_effect` is written only after
    testing, so a blank there is a fact about the version."""
    composed = _compose_comparison(
        "A",
        "B",
        {
            "previous": {},
            "new": {},
            "change_reason": None,
            "technical_hypothesis": None,
            "expected_effect": None,
            "observed_effect": None,
            "components": [],
            "previous_properties": {},
            "new_properties": {},
        },
    )
    assert "not recorded yet" in composed
    assert "has not been tested" in composed
