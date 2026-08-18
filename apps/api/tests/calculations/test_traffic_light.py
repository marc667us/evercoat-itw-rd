"""The fourteen-rule traffic light.

🔴 THE ORDER IS THE SPECIFICATION, SO THE TESTS ASSERT THE ORDER.

`DATA_MODEL.md` §3.2 records that an unordered version of this table
produced two valid colours for the same record. Testing only the outcomes
would not catch a reordering: a state that is both `invalid` and `fail`
is RED either way, and only the LABEL and the rule number reveal which
rule decided. So every ordering test asserts `disposition.rule`.

That is also why `Disposition` carries the rule number at all. A traffic
light nobody can explain is a traffic light nobody trusts.
"""

from __future__ import annotations

import dataclasses
from decimal import Decimal

import pytest

from app.calculations.testing import (
    APPROVAL_STATES,
    AUTHORITY_LEVELS,
    EXECUTION_STATUSES,
    REVIEW_STATES,
    TEST_PURPOSES,
    VALIDITY_STATUSES,
    Disposition,
    DispositionInputs,
    derive_disposition,
    evaluate_against_requirement,
    replicate_statistics,
)


def passing_state(**overrides: object) -> DispositionInputs:
    """A test that has done everything right and been fully approved.

    The baseline is deliberately the GREEN case: every rule below is then
    demonstrated by changing ONE field and showing the light moves. A
    baseline that was already yellow would let a broken rule hide behind
    an earlier one.
    """
    base = {
        "execution_status": "complete",
        "validity_status": "valid",
        "calculated_result": "pass",
        "review_state": "reviewed",
        "approval_state": "approved",
        "test_purpose": "confirmation",
        "authority_level": "controlled",
        "final_confirmed": True,
        "replicates_required": 3,
        "replicates_valid": 3,
        "cv_percent": Decimal("1.0"),
        "cv_limit": Decimal("5.0"),
        "margin_percent": Decimal("40"),
        "warning_threshold": Decimal("10"),
        "trend_alert": False,
    }
    base.update(overrides)
    return DispositionInputs(**base)  # type: ignore[arg-type]


def test_the_baseline_is_green_or_every_other_test_here_is_meaningless() -> None:
    """Verified in the positive direction first.

    If the baseline were yellow for some unrelated reason, each test below
    would pass by accident and the suite would prove nothing.
    """
    d = derive_disposition(passing_state())
    assert d.colour == "green"
    assert d.rule == 14
    assert "CONTROLLED" in d.label


# ---------------------------------------------------------------------------
# Ordering — the part that cannot be checked by outcome alone
# ---------------------------------------------------------------------------


def test_invalid_beats_fail_because_an_invalid_test_has_nothing_to_grade() -> None:
    """🔴 RULE 1 SHORT-CIRCUITS RULE 2 DELIBERATELY (Codex F24).

    Both are RED, so a colour assertion cannot tell them apart. The
    distinction is real: an invalid test was not performed to method, so
    its number is not trustworthy, and reporting REQUIREMENT FAILED would
    assert something the data does not support — and would send somebody
    into a failure investigation for a result that should simply be
    repeated.
    """
    d = derive_disposition(passing_state(validity_status="invalid", calculated_result="fail"))

    assert d.rule == 1
    assert d.label == "INVALID — not graded"
    assert "repeat" in (d.next_action or "")


def test_a_failed_requirement_beats_a_rejection() -> None:
    """Rule 2 before rule 3. The numbers failing is the primary fact; a
    rejection that followed it is a consequence, and reporting REJECTED
    would obscure why."""
    d = derive_disposition(passing_state(calculated_result="fail", approval_state="rejected"))
    assert d.rule == 2
    assert d.label == "REQUIREMENT FAILED"


def test_incomplete_execution_beats_every_yellow_below_it() -> None:
    """Rule 4 before 5-12. Nothing about replicates, variability, review
    or approval is meaningful while the physical work is unfinished."""
    d = derive_disposition(
        passing_state(
            execution_status="in_progress",
            replicates_valid=0,
            approval_state="pending",
            trend_alert=True,
        )
    )
    assert d.rule == 4
    assert d.label == "INCOMPLETE"


def test_missing_replicates_beat_excessive_variability() -> None:
    """Rule 5 before 6. A CV computed from two of five required replicates
    is a statistic about an unfinished test; reporting EXCESSIVE
    VARIABILITY would invite somebody to investigate the method when the
    real answer is "finish the test"."""
    d = derive_disposition(
        passing_state(replicates_valid=2, cv_percent=Decimal("50"), cv_limit=Decimal("5"))
    )
    assert d.rule == 5
    assert "2 valid replicate(s) of 3" in d.reason


def test_a_returned_review_beats_a_recorded_deviation() -> None:
    """Rule 7 before 8. Both are yellow; the actionable one is the review
    state, because somebody is waiting on the submitter."""
    d = derive_disposition(
        passing_state(review_state="returned_for_correction", validity_status="minor_deviation")
    )
    assert d.rule == 7
    assert d.next_action == "correct and resubmit the result"


def test_a_low_margin_beats_a_trend_concern() -> None:
    """Rule 9 before 10."""
    d = derive_disposition(
        passing_state(
            margin_percent=Decimal("2"), warning_threshold=Decimal("10"), trend_alert=True
        )
    )
    assert d.rule == 9
    assert d.label == "PASS WITH LOW MARGIN"


# ---------------------------------------------------------------------------
# Rule 12 — the one the whole product turns on
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("approval_state", ["not_required", "pending"])
def test_a_technically_passing_test_stays_yellow_until_approved(approval_state: str) -> None:
    """🔴 RULE 6 OF THE SEVEN NON-NEGOTIABLES, AND THE MOST IMPORTANT
    ASSERTION IN THIS PRODUCT.

    "Green/Red/Yellow is derived, never user-selected — and a technically
    PASSING test stays YELLOW while mandatory approvals are incomplete."

    Everything about this state is good: complete, valid, passed, all
    replicates, tight CV, wide margin, reviewed, no trend. It is still
    YELLOW, because nobody has approved it. A green tick here would make
    every green tick in the product meaningless.
    """
    d = derive_disposition(passing_state(approval_state=approval_state, next_approver="the Lead"))

    assert d.colour == "yellow"
    assert d.rule == 12
    assert "AWAITING" in d.label
    assert d.next_action is not None


def test_approval_turns_that_same_state_green() -> None:
    """Verified in both directions.

    A rule 12 that fired unconditionally would pass the test above and
    make the product unusable — nothing could ever be green.
    """
    d = derive_disposition(passing_state(approval_state="approved"))
    assert d.colour == "green"


def test_a_conditional_approval_is_yellow_and_keeps_its_limitation() -> None:
    """§9: conditional approval yields YELLOW and the stated limitation is
    preserved. Losing the condition would leave a reader with a yellow
    light and no idea what restricts the result."""
    d = derive_disposition(
        passing_state(
            approval_state="conditionally_approved",
            approval_condition="valid for development comparison only",
        )
    )
    assert d.colour == "yellow"
    assert d.rule == 11
    assert "development comparison only" in d.label


# ---------------------------------------------------------------------------
# Rule 13 — a green that is not a full green
# ---------------------------------------------------------------------------


def test_a_screening_pass_is_green_but_says_it_is_preliminary() -> None:
    """ "A green screening result is never confirmation evidence."

    GREEN is authority-qualified — never a bare tick. Somebody reading
    only the colour would otherwise treat a screening pass as
    qualification evidence, which is exactly what X12 in the plan's
    reconciliation register exists to prevent.
    """
    d = derive_disposition(passing_state(test_purpose="screening", final_confirmed=False))

    assert d.colour == "green"
    assert d.rule == 13
    assert "preliminary" in d.label.lower()
    # Green, and STILL carries a next action — the one green that does.
    assert d.next_action is not None


def test_a_confirmed_test_names_the_authority_it_was_confirmed_at() -> None:
    for level in AUTHORITY_LEVELS:
        d = derive_disposition(passing_state(authority_level=level))
        assert d.colour == "green"
        assert level.upper() in d.label


# ---------------------------------------------------------------------------
# Presentation invariants that are part of the model
# ---------------------------------------------------------------------------


def test_every_yellow_states_why_and_what_happens_next() -> None:
    """§3.3: "A yellow with no explanation is a defect."

    Exhaustive over every yellow-producing state this module can reach,
    so a rule added later without a next action fails here rather than
    reaching a screen.
    """
    yellow_states = [
        passing_state(execution_status="in_progress"),
        passing_state(replicates_valid=1),
        passing_state(cv_percent=Decimal("40"), cv_limit=Decimal("5")),
        passing_state(review_state="returned_for_correction"),
        passing_state(review_state="retest_requested"),
        passing_state(review_state="escalated"),
        passing_state(validity_status="minor_deviation"),
        passing_state(margin_percent=Decimal("1"), warning_threshold=Decimal("10")),
        passing_state(trend_alert=True),
        passing_state(approval_state="conditionally_approved", approval_condition="limited"),
        passing_state(approval_state="pending"),
    ]

    for state in yellow_states:
        d = derive_disposition(state)
        assert d.colour == "yellow", f"expected yellow, got {d.colour} from rule {d.rule}"
        assert d.reason, f"rule {d.rule} produced a yellow with no reason"
        assert d.next_action, f"rule {d.rule} produced a yellow with no next action"


def test_no_state_ever_produces_a_colour_outside_the_three() -> None:
    """Total, by construction: rule 14 is an unconditional fallthrough.

    Swept across every combination of the four axes that drive the
    early rules, so an added value with no matching rule cannot silently
    return something a `StatusBadge` has no rendering for.
    """
    for execution in EXECUTION_STATUSES:
        for validity in VALIDITY_STATUSES:
            for review in REVIEW_STATES:
                for approval in APPROVAL_STATES:
                    d = derive_disposition(
                        passing_state(
                            execution_status=execution,
                            validity_status=validity,
                            review_state=review,
                            approval_state=approval,
                        )
                    )
                    assert d.colour in {"red", "yellow", "green"}
                    assert 1 <= d.rule <= 14
                    assert d.label


def test_a_red_never_carries_a_green_label_and_vice_versa() -> None:
    """Colour and label must agree. They are rendered together — §11
    forbids colour-only status — and a RED labelled CONFIRMED would be
    worse than either alone."""
    for purpose in TEST_PURPOSES:
        red = derive_disposition(passing_state(test_purpose=purpose, validity_status="invalid"))
        assert red.colour == "red"
        assert "CONFIRMED" not in red.label
        assert "PASSED" not in red.label


# ---------------------------------------------------------------------------
# Replicate statistics
# ---------------------------------------------------------------------------


def test_a_single_replicate_has_no_standard_deviation() -> None:
    """`None`, not zero.

    Zero says "perfectly repeatable", which one measurement cannot
    support — and because rule 6 compares CV against a limit, a spurious
    0.0 would silently pass every single-replicate test.
    """
    stats = replicate_statistics([Decimal("5.30")])
    assert stats.mean == Decimal("5.30")
    assert stats.standard_deviation is None
    assert stats.cv_percent is None


def test_the_standard_deviation_is_the_sample_form_not_the_population_form() -> None:
    """n-1, not n.

    Replicates are a sample of the measurement process, not the whole of
    it. The population form understates variability, which would make
    rule 6 fire LESS often than it should — the wrong direction to be
    wrong in on a safety-relevant test.

    For [2, 4, 4, 4, 5, 5, 7, 9]: population sd is exactly 2, sample sd
    is about 2.138. The difference is what this asserts.
    """
    values = [Decimal(n) for n in (2, 4, 4, 4, 5, 5, 7, 9)]
    stats = replicate_statistics(values)

    assert stats.mean == Decimal("5")
    assert stats.standard_deviation is not None
    assert stats.standard_deviation > Decimal("2.1")
    assert stats.standard_deviation < Decimal("2.2")


def test_no_replicates_is_not_a_mean_of_zero() -> None:
    """An empty set has no mean. Reporting 0 would put a fabricated
    measurement on a screen."""
    stats = replicate_statistics([])
    assert stats.count == 0
    assert stats.mean is None
    assert stats.cv_percent is None


def test_a_float_replicate_is_refused() -> None:
    with pytest.raises(TypeError, match="float"):
        replicate_statistics([1.5])  # type: ignore[list-item]


# ---------------------------------------------------------------------------
# Requirement comparison
# ---------------------------------------------------------------------------


def test_a_requirement_with_no_bounds_is_inconclusive_and_never_a_pass() -> None:
    """🔴 ABSENCE MUST NOT PRESENT AS SUCCESS.

    A test with nothing to compare against has not passed; it has
    produced a number. This project has already shipped a screen where an
    empty requirement set rendered "ALL REQUIREMENTS PASSED".
    """
    result = evaluate_against_requirement(Decimal("5.3"))
    assert result.result == "inconclusive"
    assert "cannot be graded" in result.detail


def test_the_margin_is_measured_against_the_nearest_bound() -> None:
    """A value comfortably above the minimum and a hair under the maximum
    is not a comfortable pass.

    Averaging the two margins would report it as one, and rule 9 would
    never fire for it.
    """
    result = evaluate_against_requirement(
        Decimal("99"), minimum=Decimal("10"), maximum=Decimal("100")
    )
    assert result.result == "pass"
    assert result.margin_percent is not None
    assert result.margin_percent < Decimal("2")


@pytest.mark.parametrize(
    ("value", "expected"),
    [("4.9", "fail"), ("5.0", "pass"), ("9.0", "pass"), ("10.0", "pass"), ("10.1", "fail")],
)
def test_the_bounds_are_inclusive(value: str, expected: str) -> None:
    """A requirement of "at least 5.0" is met BY 5.0.

    An exclusive comparison fails a result that exactly meets the
    specification, which is both wrong and the kind of off-by-one nobody
    notices until a batch is rejected.
    """
    result = evaluate_against_requirement(
        Decimal(value), minimum=Decimal("5.0"), maximum=Decimal("10.0")
    )
    assert result.result == expected


def test_an_impossible_requirement_is_refused_rather_than_silently_failing() -> None:
    """min above max grades every measurement as a failure, which looks
    like a product problem rather than a configuration one."""
    with pytest.raises(ValueError, match="above"):
        evaluate_against_requirement(Decimal("5"), minimum=Decimal("10"), maximum=Decimal("1"))


def test_the_disposition_is_frozen() -> None:
    """Server-owned means server-owned. `display_color`, `final_status`
    and `final_confirmed` are never client-settable, and a mutable result
    object invites a caller to 'adjust' one before returning it."""
    d: Disposition = derive_disposition(passing_state())
    # `FrozenInstanceError` specifically, not a blind `Exception`. A bare
    # `raises(Exception)` here would also pass if the attribute did not
    # exist at all -- so the test would keep passing after a rename that
    # removed the field it is guarding.
    with pytest.raises(dataclasses.FrozenInstanceError):
        d.colour = "green"  # type: ignore[misc]
