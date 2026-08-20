"""Application guidance — MSD's Phase 1 capability, and the one with no records.

Concept Note §5 lists the questions this answers: *"How do I create a
formulation revision?"*, *"Where do I enter adhesion test results?"*,
*"What does yellow mean on this test?"*

🔴 THE ANSWERS ARE WRITTEN DOWN, NOT GENERATED.

A model asked "what does yellow mean" will produce something plausible.
Yellow has a SPECIFIC meaning here — §10's ordered, first-match-wins
derivation — and a plausible paraphrase of it is a safety defect: the
whole point of the rule is that a technically passing test stays YELLOW
while approvals are outstanding, and an answer that softens that is worse
than no answer.

So guidance is a lookup table maintained beside the rules it describes.
When §10 changes, this changes, and the test below fails if the
vocabulary drifts.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

__all__ = ["GuidanceEntry", "explain_the_application"]


@dataclass(frozen=True, slots=True)
class GuidanceEntry:
    """One answer, and where in the product it points."""

    topic: str
    body: str
    href: str | None


#: Keyed by the words a chemist actually types, not by internal names.
_GUIDANCE: tuple[tuple[tuple[str, ...], GuidanceEntry], ...] = (
    (
        ("yellow", "amber", "conditional"),
        GuidanceEntry(
            topic="What YELLOW means on a test",
            body=(
                "YELLOW is derived, never chosen. It means the result is not final "
                "yet, and the reason is always stated on the test itself. The most "
                "common cause is that the measurement passed but a required approval "
                "is still outstanding — a technically passing test stays YELLOW "
                "until every mandatory approval is complete. Other causes are "
                "incomplete replicates, variability above the method's limit, a "
                "deviation under review, a pass with a low margin, or a conditional "
                "approval. Open the test to see which rule applied."
            ),
            href="/testing",
        ),
    ),
    (
        ("green",),
        GuidanceEntry(
            topic="What GREEN means on a test",
            body=(
                "GREEN is authority-qualified and never a bare tick. A screening "
                "test that passed reads 'GREEN — Screening Passed (preliminary "
                "authority)', and that is NOT qualification evidence. Check the "
                "authority level beside it before relying on a green result."
            ),
            href="/testing",
        ),
    ),
    (
        ("red", "fail", "failed"),
        GuidanceEntry(
            topic="What RED means on a test",
            body=(
                "RED means the test is invalid, the requirement failed, or an "
                "approval was rejected. A RED confirmation result opens or links a "
                "Failure Investigation — the failure screen is not built yet, so "
                "that link is not clickable today."
            ),
            href="/testing",
        ),
    ),
    (
        ("revision", "revise", "new version", "clone"),
        GuidanceEntry(
            topic="Creating a formula revision",
            body=(
                "An approved formula is never edited in place. Open the formula and "
                "create a new VERSION, which records the parent version, the reason "
                "for the change and the technical hypothesis behind it, and — after "
                "testing — the observed effect. The write path for this is not built "
                "in the browser yet."
            ),
            href="/formulations",
        ),
    ),
    (
        ("batch", "weigh", "weighing", "laboratory", "lab"),
        GuidanceEntry(
            topic="Laboratory batches",
            body=(
                "The Laboratory screen lists batches on the bench, what is still "
                "unweighed, how many samples came off each one and whether any "
                "deviations were recorded. A batch turns an approved formula version "
                "into a physical sample a test can be traced back to."
            ),
            href="/laboratory",
        ),
    ),
    (
        ("test result", "enter result", "adhesion", "replicate"),
        GuidanceEntry(
            topic="Entering test results",
            body=(
                "Results are recorded per REPLICATE, never as an aggregate only, and "
                "the statistics are computed by the server from those raw values. "
                "Result entry is not built in the browser yet; the Testing screen "
                "currently shows the queue and each test's stored axes."
            ),
            href="/testing",
        ),
    ),
    # 🔴 NO ENTRY FOR "what is waiting for me".
    #
    # There was one, and it hijacked the question. Somebody asking what is
    # waiting for them wants THEIR ACTUAL TASKS, not a description of what
    # the My Work screen is — and `pending_work` answers it with real rows
    # read inside their own boundary. An explanation offered in place of
    # the data is a worse answer that looks like a better one.
)


def explain_the_application(question: str) -> GuidanceEntry | None:
    """The written answer for this question, or None.

    Returns None rather than guessing. An assistant that always has
    something to say is one that cannot be trusted when it does.

    🔴 WORD BOUNDARIES, NOT SUBSTRINGS. THIS WAS A REAL BUG.

    The first version used `keyword in question`, and `"weigh" in
    "lightweight"` is TRUE. So *"show me lightweight filler formulas"* —
    a straightforward record search — matched the weighing keyword and
    was answered with an explanation of laboratory batches. Confidently,
    and completely wrongly, which is the worst failure mode an assistant
    has.

    Caught by a routing test rather than by reading, because substring
    collisions are invisible until you try the word.
    """
    lowered = question.lower()
    for keywords, entry in _GUIDANCE:
        for word in keywords:
            # \b on BOTH sides: without them "weigh" matches inside
            # "lightweight"; re.escape keeps multi-word phrases such as
            # "test result" and "new version" literal.
            if re.search(r"\b" + re.escape(word) + r"\b", lowered):
                return entry
    return None
