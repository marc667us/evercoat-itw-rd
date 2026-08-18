"""`mass_deviation` — the weighing reconciliation.

Property-based where the property is the point, example-based where a
specific number carries the meaning. `CLAUDE.md` §15 requires Hypothesis
for scientific code, and a reconciliation a technician acts on at the
bench qualifies.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.calculations.formulation import mass_deviation

# Realistic bench masses: a gram to a hundred kilograms, to the milligram.
masses = st.decimals(
    min_value=Decimal("0.001"),
    max_value=Decimal("100.000"),
    places=3,
    allow_nan=False,
    allow_infinity=False,
)


def test_the_percentage_is_relative_to_the_plan_and_not_the_batch() -> None:
    """THE DECISION THIS FUNCTION EXISTS TO GET RIGHT.

    5 g astray on a 10 g addition is a 50% error and matters enormously.
    The same 5 g on a 20 kg addition is noise. Dividing by the batch mass
    would make every minor component look perfect — and minor components
    are catalysts and hardeners, where a proportional error does the most
    damage.
    """
    small = mass_deviation(Decimal("0.010"), Decimal("0.015"))
    large = mass_deviation(Decimal("20.000"), Decimal("20.005"))

    assert small.delta_percent == Decimal("50")
    assert small.within_tolerance is False

    assert large.delta_percent < Decimal("0.03")
    assert large.within_tolerance is True


def test_the_sign_is_preserved() -> None:
    """Over- and under-charging fail in opposite directions.

    Too much hardener and too little hardener are different faults with
    different consequences; reporting a magnitude would collapse them.
    """
    over = mass_deviation(Decimal("10.000"), Decimal("10.500"))
    under = mass_deviation(Decimal("10.000"), Decimal("9.500"))

    assert over.delta_kg > 0
    assert under.delta_kg < 0
    assert over.delta_percent == -under.delta_percent


def test_the_tolerance_is_a_band_not_a_ceiling() -> None:
    """Under-charging by 3% is as far out as over-charging by 3%.

    A naive `percent <= tolerance` passes every under-charge, however
    large, because a negative number is always below the limit. That bug
    would be invisible in any test that only weighs too much.
    """
    over = mass_deviation(Decimal("10.0"), Decimal("10.4"), tolerance_percent=Decimal("3"))
    under = mass_deviation(Decimal("10.0"), Decimal("9.6"), tolerance_percent=Decimal("3"))

    assert over.within_tolerance is False
    assert under.within_tolerance is False


def test_a_planned_mass_of_zero_is_refused() -> None:
    """Not reported as an infinite deviation.

    A component planned at zero is not a component, and the weigh-up
    sheet should never have produced the line. Returning infinity would
    push a meaningless figure onto a screen; raising says where the fault
    actually is.
    """
    with pytest.raises(ValueError, match="positive"):
        mass_deviation(Decimal("0"), Decimal("1.0"))


def test_a_negative_weight_is_refused() -> None:
    with pytest.raises(ValueError, match="negative"):
        mass_deviation(Decimal("1.0"), Decimal("-0.5"))


def test_a_float_is_refused_at_the_boundary() -> None:
    """The engine's standing rule, restated for the new entry point.

    `0.1` is not representable in binary floating point, and a weighing
    reconciliation is precisely where that error becomes a decision about
    whether a batch is acceptable.
    """
    with pytest.raises(TypeError, match="float"):
        mass_deviation(1.0, Decimal("1.0"))  # type: ignore[arg-type]


@given(planned=masses, actual=masses)
def test_the_delta_always_reconstructs_the_actual_mass(planned: Decimal, actual: Decimal) -> None:
    """planned + delta == actual, exactly, for any pair.

    The invariant a technician relies on when reading the sheet: the two
    numbers and the difference between them must agree. Exact under
    `Decimal`; in float this fails for ordinary values.
    """
    result = mass_deviation(planned, actual)
    assert result.planned_kg + result.delta_kg == result.actual_kg


@given(planned=masses)
def test_weighing_exactly_to_plan_is_always_in_tolerance(planned: Decimal) -> None:
    """Zero deviation passes at every tolerance, including zero.

    Guards the boundary: `abs(0) <= 0` must hold, or a perfectly weighed
    line would be flagged under a zero-tolerance batch.
    """
    result = mass_deviation(planned, planned, tolerance_percent=Decimal("0"))
    assert result.delta_kg == 0
    assert result.delta_percent == 0
    assert result.within_tolerance is True
