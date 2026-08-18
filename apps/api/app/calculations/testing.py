"""Test evaluation: replicate statistics, requirement comparison, and the
traffic light.

🔴 THE TRAFFIC LIGHT IS AN ALGORITHM, NOT A LOOKUP TABLE.

`DATA_MODEL.md` §3.2 records why: an unordered table produced two valid
colours for the same record, and the Supervisor caught it (S3). The rules
below are evaluated IN ORDER and the FIRST MATCH WINS. Reordering them is
a behavioural change, not a tidy-up, and the tests assert the order
directly rather than only the outcomes.

Rule 6 of the seven non-negotiables lives here: *Green/Red/Yellow is
derived, never user-selected — and a technically PASSING test stays
YELLOW while mandatory approvals are incomplete.* That is rule 12 in the
list, and it is the single most important assertion in the eventual
golden end-to-end scenario.

WHY THIS IS A PURE MODULE WITH NO I/O
-------------------------------------
Rule 2 of the seven: Python owns deterministic scientific calculation and
the LLM never does the arithmetic. The same reasoning applies to the
database: a `CASE` expression in SQL computing `display_color` would be a
second implementation of this algorithm that nothing could check against
the first, and this repository's most repeated defect is exactly that —
two literals in two files that nothing compares.

So the derivation exists once, here, and `testing.tests.display_color` is
never a stored column. Screens ask for it; they are not told it.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

__all__ = [
    "Disposition",
    "DispositionInputs",
    "MeasurementEvaluation",
    "ReplicateStatistics",
    "derive_disposition",
    "evaluate_against_requirement",
    "replicate_statistics",
]

HUNDRED = Decimal("100")
ZERO = Decimal("0")

# The vocabularies, exactly as DATA_MODEL.md §3.1 fixes them. Duplicated
# nowhere else in Python: the database CHECK constraints are compared
# against these by a test, so the two cannot drift.
EXECUTION_STATUSES = ("not_started", "in_progress", "complete", "abandoned")
VALIDITY_STATUSES = ("valid", "minor_deviation", "invalid")
CALCULATED_RESULTS = (
    "pass",
    "fail",
    "inconclusive",
    "improved",
    "no_significant_change",
    "worsened",
)
REVIEW_STATES = (
    "awaiting_review",
    "under_review",
    "returned_for_correction",
    "retest_requested",
    "escalated",
    "reviewed",
)
APPROVAL_STATES = (
    "not_required",
    "pending",
    "conditionally_approved",
    "approved",
    "rejected",
)
TEST_PURPOSES = ("screening", "oversight", "confirmation", "improvement")
AUTHORITY_LEVELS = (
    "preliminary",
    "development",
    "controlled",
    "validation",
    "qualification",
    "release",
)


def _dec(value: object, field: str) -> Decimal:
    """Accept Decimal, int or str. Refuse float, loudly.

    The same boundary the formulation engine enforces, for the same
    reason: a measured value is a controlled quantity, and a coefficient
    of variation computed through binary floating point is a number
    nobody can reproduce exactly from the raw replicates.
    """
    if isinstance(value, float):
        raise TypeError(
            f"{field} was a float. Measured values are Decimal (CLAUDE.md §5) — "
            f"pass Decimal('{value}') or a string."
        )
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, str)):
        try:
            return Decimal(value)
        except InvalidOperation as exc:
            raise ValueError(f"{field} is not a number: {value!r}") from exc
    raise TypeError(f"{field} must be Decimal, int or str, not {type(value).__name__}")


# ---------------------------------------------------------------- statistics


@dataclass(frozen=True, slots=True)
class ReplicateStatistics:
    """What a set of replicate measurements says.

    `valid_count` is separate from `count` because an excluded replicate
    is not a missing one: it was performed, it is on the record, and it
    was set aside for a stated reason. Rule 5 compares `valid_count`
    against the method's requirement, so collapsing the two would let a
    test with three excluded replicates read as complete.
    """

    count: int
    valid_count: int
    mean: Decimal | None
    standard_deviation: Decimal | None
    cv_percent: Decimal | None


def replicate_statistics(
    values: list[Decimal | int | str],
    *,
    places: Decimal = Decimal("0.000001"),
) -> ReplicateStatistics:
    """Mean, sample standard deviation and coefficient of variation.

    SAMPLE standard deviation (n-1), not population (n). Replicates are a
    sample of the measurement process, not the whole of it, and the
    population form understates variability — which would make rule 6
    (EXCESSIVE VARIABILITY) fire less often than it should. Understating
    variability on a safety-relevant test is the wrong direction to be
    wrong in.

    A single replicate has a mean and NO standard deviation. `None`, not
    zero: zero says "perfectly repeatable", which is a claim one
    measurement cannot support. This distinction matters because rule 6
    compares `cv` against a limit, and a spurious 0.0 would silently pass
    every single-replicate test.

    `cv` is undefined when the mean is zero, and is reported as `None`
    rather than as a division by zero — a legitimate case for a
    measurement centred on zero (a delta, a drift).
    """
    if not values:
        return ReplicateStatistics(0, 0, None, None, None)

    numbers = [_dec(v, "replicate") for v in values]
    count = len(numbers)
    total = sum(numbers, start=ZERO)
    mean = total / count

    if count < 2:
        return ReplicateStatistics(count, count, mean, None, None)

    variance = sum(((n - mean) ** 2 for n in numbers), start=ZERO) / (count - 1)
    # `Decimal.sqrt` is correctly rounded to the current context, which is
    # the closest thing to exact available for an irrational result. The
    # quantize keeps the reported figure stable across contexts so two
    # runs of the same data cannot disagree in the last digit.
    sd = variance.sqrt().quantize(places)

    cv = None if mean == ZERO else (sd / mean * HUNDRED).copy_abs().quantize(places)

    return ReplicateStatistics(
        count=count,
        valid_count=count,
        mean=mean,
        standard_deviation=sd,
        cv_percent=cv,
    )


# ------------------------------------------------------- requirement check


@dataclass(frozen=True, slots=True)
class MeasurementEvaluation:
    """What the numbers said, before anybody looked at them.

    `margin` is how far inside the requirement the value sits, as a
    percentage of the limit it is nearest to. Rule 9 turns a small margin
    into PASS WITH LOW MARGIN — a pass that is one bad batch from a
    failure, which a bare `pass` conceals.

    `None` margin means there was no bound to measure against, not that
    the margin was zero.
    """

    result: str
    margin_percent: Decimal | None
    detail: str


def evaluate_against_requirement(
    value: Decimal | int | str,
    *,
    target: Decimal | int | str | None = None,
    minimum: Decimal | int | str | None = None,
    maximum: Decimal | int | str | None = None,
) -> MeasurementEvaluation:
    """Compare a measured value against a structured requirement.

    The requirement model is target / min / max, from Slice 2 — a
    requirement of "adhesion should be good" cannot be compared against
    5.3 MPa, which is why that structure exists.

    WITH NO BOUNDS THE RESULT IS `inconclusive`, NOT `pass`. A test with
    nothing to compare against has not passed; it has produced a number.
    Defaulting to `pass` is the shape of defect this project has hit
    repeatedly — an empty requirement set once rendered "ALL REQUIREMENTS
    PASSED".
    """
    measured = _dec(value, "value")
    low = None if minimum is None else _dec(minimum, "minimum")
    high = None if maximum is None else _dec(maximum, "maximum")
    aim = None if target is None else _dec(target, "target")

    if low is not None and high is not None and low > high:
        raise ValueError(f"minimum {low} is above maximum {high}")

    if low is None and high is None:
        return MeasurementEvaluation(
            result="inconclusive",
            margin_percent=None,
            detail=(
                "the requirement states no minimum and no maximum, so this "
                "measurement cannot be graded"
                + (f" (target {aim} is advisory)" if aim is not None else "")
            ),
        )

    if low is not None and measured < low:
        return MeasurementEvaluation(
            result="fail",
            margin_percent=None,
            detail=f"{measured} is below the minimum of {low}",
        )
    if high is not None and measured > high:
        return MeasurementEvaluation(
            result="fail",
            margin_percent=None,
            detail=f"{measured} is above the maximum of {high}",
        )

    # Inside the bounds. How comfortably?
    margins: list[Decimal] = []
    if low is not None and low != ZERO:
        margins.append((measured - low) / low.copy_abs() * HUNDRED)
    if high is not None and high != ZERO:
        margins.append((high - measured) / high.copy_abs() * HUNDRED)

    # The NEAREST bound governs. A value comfortably above the minimum and
    # a hair under the maximum is not a comfortable pass, and averaging
    # the two margins would report it as one.
    margin = min(margins) if margins else None

    return MeasurementEvaluation(
        result="pass",
        margin_percent=margin,
        detail=f"{measured} is within the requirement",
    )


# ------------------------------------------------------------- the traffic light


@dataclass(frozen=True, slots=True)
class DispositionInputs:
    """Everything the derivation reads. Nothing it does not.

    Named `DispositionInputs` and not `TestState`: pytest collects any
    class whose name begins with `Test`, so the obvious name made the
    suite emit a collection warning on every run. Noise in a test report
    is not harmless -- it is where a real warning goes to hide.

    A single frozen input makes the algorithm total and testable: every
    rule's trigger is a field here, so a rule cannot come to depend on
    something a caller forgot to supply.
    """

    execution_status: str
    validity_status: str
    calculated_result: str | None
    review_state: str
    approval_state: str
    test_purpose: str
    authority_level: str
    final_confirmed: bool = False
    replicates_required: int = 1
    replicates_valid: int = 0
    cv_percent: Decimal | None = None
    cv_limit: Decimal | None = None
    margin_percent: Decimal | None = None
    warning_threshold: Decimal | None = None
    trend_alert: bool = False
    approval_condition: str | None = None
    next_approver: str | None = None


@dataclass(frozen=True, slots=True)
class Disposition:
    """The final disposition, and why.

    `rule` is the number of the rule that fired. It is returned, not
    hidden, because a traffic light nobody can explain is a traffic light
    nobody trusts — and because it makes the ordering directly
    assertable: a test can demand that a given state fires rule 1 and not
    rule 2, which is what stops a reordering slipping through.

    `next_action` is non-empty for every YELLOW. `DATA_MODEL.md` §3.3:
    "Every YELLOW states why AND what the next required action is. A
    yellow with no explanation is a defect."
    """

    colour: str
    label: str
    reason: str
    next_action: str | None
    rule: int


def derive_disposition(state: DispositionInputs) -> Disposition:
    """The fourteen rules, in order, first match wins.

    🔴 THE ORDER IS THE SPECIFICATION. Rule 1 short-circuits before rule 2
    deliberately: "technically invalid" is a RED cause distinct from
    failure, because an invalid test has no trustworthy number to grade
    and grading it would assert something the data does not support
    (Codex F24).
    """
    # 1 — invalid, and therefore not graded at all.
    if state.validity_status == "invalid":
        return Disposition(
            "red",
            "INVALID — not graded",
            "the test was not performed to method, so its result cannot be trusted",
            "repeat the test to method",
            1,
        )

    # 2 — the numbers say it failed.
    if state.calculated_result == "fail":
        return Disposition(
            "red",
            "REQUIREMENT FAILED",
            "the measured result is outside the requirement",
            "open or link a failure investigation",
            2,
        )

    # 3 — an approver refused it.
    if state.approval_state == "rejected":
        return Disposition(
            "red",
            "REJECTED",
            "an approver rejected this result",
            "address the rejection and retest",
            3,
        )

    # 4 — the physical work is not finished.
    if state.execution_status != "complete":
        return Disposition(
            "yellow",
            "INCOMPLETE",
            f"execution is {state.execution_status.replace('_', ' ')}",
            "complete the test execution",
            4,
        )

    # 5 — not enough valid replicates.
    if state.replicates_valid < state.replicates_required:
        return Disposition(
            "yellow",
            "INCOMPLETE REPLICATES",
            f"{state.replicates_valid} valid replicate(s) of {state.replicates_required} required",
            "perform the remaining replicates",
            5,
        )

    # 6 — the replicates disagree with each other too much.
    if (
        state.cv_percent is not None
        and state.cv_limit is not None
        and state.cv_percent > state.cv_limit
    ):
        return Disposition(
            "yellow",
            "EXCESSIVE VARIABILITY",
            f"coefficient of variation {state.cv_percent}% exceeds the method "
            f"limit of {state.cv_limit}%",
            "investigate the method or repeat the replicates",
            6,
        )

    # 7 — review sent it back.
    if state.review_state in {"returned_for_correction", "retest_requested", "escalated"}:
        spoken = state.review_state.replace("_", " ").upper()
        return Disposition(
            "yellow",
            spoken,
            f"technical review set this test to {spoken.lower()}",
            {
                "returned_for_correction": "correct and resubmit the result",
                "retest_requested": "perform the linked retest",
                "escalated": "await the escalation decision",
            }[state.review_state],
            7,
        )

    # 8 — a deviation is still being judged.
    if state.validity_status == "minor_deviation":
        return Disposition(
            "yellow",
            "DEVIATION UNDER REVIEW",
            "the test was performed with a recorded deviation from method",
            "accept or reject the deviation in review",
            8,
        )

    # 9 — it passed, but only just.
    if (
        state.margin_percent is not None
        and state.warning_threshold is not None
        and state.margin_percent < state.warning_threshold
    ):
        return Disposition(
            "yellow",
            "PASS WITH LOW MARGIN",
            f"margin {state.margin_percent}% is below the warning threshold of "
            f"{state.warning_threshold}%",
            "review whether this margin is acceptable for the intended authority",
            9,
        )

    # 10 — the series is drifting.
    if state.trend_alert:
        return Disposition(
            "yellow",
            "TREND CONCERN",
            "this result continues an adverse trend across recent tests",
            "review the trend before relying on this result",
            10,
        )

    # 11 — approved, with a stated limitation that must travel with it.
    if state.approval_state == "conditionally_approved":
        condition = state.approval_condition or "a stated limitation applies"
        return Disposition(
            "yellow",
            f"CONDITIONAL — {condition}",
            f"approved subject to a condition: {condition}",
            "observe the stated limitation; obtain unconditional approval if "
            "this result is needed as unqualified evidence",
            11,
        )

    # 12 — 🔴 RULE 6 OF THE SEVEN NON-NEGOTIABLES.
    #
    # A technically passing test stays YELLOW until mandatory approvals
    # complete. This single rule is why a green tick in this product means
    # something, and it is the most important assertion in the golden
    # end-to-end scenario.
    if state.approval_state != "approved":
        who = state.next_approver or "the next approver"
        return Disposition(
            "yellow",
            f"AWAITING {who.upper()}",
            f"the result is technically acceptable but {who} has not yet approved it",
            f"obtain approval from {who}",
            12,
        )

    # 13 — a screening pass is preliminary evidence and says so.
    if state.test_purpose == "screening" and not state.final_confirmed:
        return Disposition(
            "green",
            "SCREENING PASSED — preliminary",
            "a screening test passed; screening is preliminary authority and is "
            "never confirmation evidence",
            "confirm with a test at the required authority before relying on this",
            13,
        )

    # 14 — confirmed, and the authority it was confirmed at is named.
    return Disposition(
        "green",
        f"{state.authority_level.upper()} CONFIRMED",
        f"confirmed at {state.authority_level} authority",
        None,
        14,
    )
