"""MSD's answers, without a database and without a model.

That both are absent here is the point. `CLAUDE.md` §7 and the seven
non-negotiable rules constrain what MSD may SAY, and those constraints
have to be checkable without standing up a language model — otherwise
they can only be spot-checked by reading output, which is exactly how an
assistant's safety properties rot.
"""

from __future__ import annotations

import uuid

import pytest

from app.agents.conductors.msd_conductor import (
    DISCLAIMER,
    MsdAnswer,
    _compose_records,
    _compose_work,
    answer,
    classify,
)
from app.agents.ports import NullLanguageModel
from app.agents.tools import explain_the_application
from app.domains.msd.retrieval import RetrievedRecord


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
        ("thoughts on the weather", "unsupported"),
    ],
)
def test_questions_route_to_the_right_capability(question: str, expected: str) -> None:
    assert classify(question) == expected


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
        session=None,  # type: ignore[arg-type] - find_records is stubbed
        organization_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        role_codes=frozenset(),
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
        session=None,  # type: ignore[arg-type] - guidance touches no database
        organization_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        role_codes=frozenset(),
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
