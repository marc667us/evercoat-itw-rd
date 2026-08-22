"""MSD's two word lists are one decision, and they must not drift apart.

🔴 A HALF-WORKING PATH IS WORSE THAN A CLOSED ONE.

`classify()` decides WHICH capability a question needs. `_subject_of()` decides
WHAT the question is about, by stripping question words. They are two
expressions of one judgement -- "these words are the ask, not the subject" --
and nothing connected them.

Measured against the running application on 2026-08-22:

  * Before: "is RM-ADD-01 safe to use?" classified as `unsupported`, because
    the classifier knew "safety" and not "safe". The user got "I cannot answer
    that yet", which is at least honest about being a limitation.

  * After widening the classifier ALONE: the same question routed correctly to
    material_safety and then searched for `%rm-add-01 safe to use%`, matching
    nothing, and answered **"I found no materials you have access to matching
    that"** -- about a material that plainly exists.

That second state is the worse one. It sounds like a FINDING about the
material rather than a limitation of the assistant, and on a safety question
that is exactly the wrong way to be wrong. It was introduced by fixing half of
a pair.

So the pair is now asserted. If a future word is added to the classifier's
safety vocabulary and not to the subject extractor's noise, this fails.
"""

from __future__ import annotations

import pytest

from app.agents.conductors.msd_conductor import _subject_of, classify

# The words that route a question to `material_safety`. Kept here as the
# statement of intent; the test proves the extractor strips every one.
SAFETY_VOCABULARY = (
    "sds",
    "safety",
    "safe",
    "hazard",
    "hazardous",
    "restricted",
    "contain",
    "contains",
    "used in",
)


@pytest.mark.parametrize("word", [w for w in SAFETY_VOCABULARY if " " not in w])
def test_every_safety_word_is_stripped_from_the_subject(word: str) -> None:
    """A word that ROUTES a question must not also be searched for.

    `_subject_of` is what the lookup receives, so any routing word left in it
    becomes part of an ILIKE pattern and guarantees no match.
    """
    subject = _subject_of(f"is RM-ADD-01 {word}?")
    assert word not in subject.split(), (
        f"{word!r} routes a question to material_safety and is still present "
        f"in the extracted subject {subject!r}. The lookup will search for it "
        "as part of the material name and find nothing -- which reads as a "
        "finding about the material rather than a limitation of the search."
    )


@pytest.mark.parametrize(
    "question",
    [
        "is RM-ADD-01 safe to use?",
        "is RM-ADD-01 hazardous?",
        "safety of RM-ADD-01",
        "does RM-ADD-01 have an SDS?",
        "which formulas contain RM-ADD-01?",
        "is RM-ADD-01 restricted?",
    ],
)
def test_a_safety_question_reduces_to_the_material_code(question: str) -> None:
    """🔴 Both halves, on the phrasings a chemist actually uses.

    Routing alone is not enough and extraction alone is not enough. This
    asserts the pair: the question reaches `material_safety` AND reduces to
    something the database can match.
    """
    assert classify(question) == "material_safety", (
        f"{question!r} does not reach the material-safety capability"
    )
    assert _subject_of(question) == "rm-add-01", (
        f"{question!r} reduced to {_subject_of(question)!r} rather than the "
        "material code, so the lookup searches for the question and matches "
        "nothing"
    )


def test_guidance_still_wins_over_a_record_search() -> None:
    """The ordering the classifier's own docstring argues for.

    "What does yellow mean" must be answered from written guidance, not
    matched against formula names -- where "yellow" would return confident
    nonsense. Widening the safety vocabulary must not have disturbed that.
    """
    assert classify("what does yellow mean?") == "guidance"
    assert classify("what is a conditional approval?") == "guidance"


def test_the_other_intents_still_route() -> None:
    """A widened noise list is a chance to break every other capability."""
    assert classify("what is waiting for me?") == "pending_work"
    assert classify("compare FRM-009 and FRM-014") == "compare_formulas"
    assert classify("what is the density of FRM-014") == "formula_figures"
    assert _subject_of("what is the density of FRM-014") == "frm-014"
