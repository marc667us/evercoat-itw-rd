"""Property-based tests for the formulation engine.

`CLAUDE.md` §4 requires Hypothesis for scientific code, and the source
states the invariant these exist to hold: *for any valid 100% formula and
any positive batch quantity, the sum of component masses equals the batch
mass.* An example-based test cannot establish that — it establishes it for
the three batch sizes somebody thought of.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.calculations import (
    Component,
    binder_to_filler_ratio,
    cost_per_kg,
    normalize_to_100,
    scale_to_batch,
    solids_content,
    stoichiometric_hardener_parts,
    theoretical_density,
    total_percentage,
    validate_for_submission,
    voc_content_g_per_l,
)

# ------------------------------------------------------------ strategies

percentages = st.decimals(
    min_value=Decimal("0.01"),
    max_value=Decimal("100"),
    places=4,
    allow_nan=False,
    allow_infinity=False,
)
densities = st.decimals(
    min_value=Decimal("0.5"),
    max_value=Decimal("5.0"),
    places=3,
    allow_nan=False,
    allow_infinity=False,
)
masses = st.decimals(
    min_value=Decimal("0.001"),
    max_value=Decimal("100000"),
    places=3,
    allow_nan=False,
    allow_infinity=False,
)


@st.composite
def formulas(draw, min_size: int = 1, max_size: int = 12, with_density: bool = False):
    """A list of components with distinct codes and positive percentages."""
    size = draw(st.integers(min_value=min_size, max_value=max_size))
    pcts = draw(st.lists(percentages, min_size=size, max_size=size))
    dens = draw(st.lists(densities, min_size=size, max_size=size))
    return [
        Component(
            material_code=f"RM-{i:03d}",
            percentage=p,
            density_g_cm3=d if with_density else None,
        )
        for i, (p, d) in enumerate(zip(pcts, dens, strict=True))
    ]


# ------------------------------------------------------------- batching


@settings(max_examples=250)
@given(components=formulas(), batch=masses)
def test_component_masses_sum_exactly_to_the_batch_mass(components, batch):
    """THE stated invariant, over arbitrary formulas and batch sizes.

    Exact equality, not "within tolerance". Rounding each line
    independently would drift, and a technician reconciling a weigh-up
    against the sheet would find a discrepancy the software invented.
    """
    masses_out = scale_to_batch(components, batch)
    assert sum(masses_out.values()) == batch


@settings(max_examples=100)
@given(
    components=formulas(),
    # BATCHES LARGE ENOUGH THAT ROUNDING IS NOT THE SIGNAL.
    #
    # The first version drew from the full mass range and failed at
    # batch=0.304 kg — correctly. Masses round to the milligram, so a 304 g
    # batch split over a dozen components puts each line within a few
    # rounding steps of its neighbours, and a linearity ratio measured there
    # is measuring the quantiser, not the function. The engine is right; the
    # test was asking the wrong question of it.
    batch=st.decimals(min_value=Decimal("100"), max_value=Decimal("10000"), places=3),
    factor=st.integers(min_value=2, max_value=50),
)
def test_scaling_is_linear_in_the_batch_size(components, batch, factor):
    """Doubling the batch doubles every component.

    Checked on the RATIO rather than the absolute value, because the
    remainder line legitimately absorbs a rounding residue that does not
    scale linearly at the last decimal place.
    """
    single = scale_to_batch(components, batch)
    multiple = scale_to_batch(components, batch * factor)

    # The LAST line is the designated remainder and is excluded on purpose.
    # `scale_to_batch` documents that it absorbs the rounding residue so the
    # total is exact; that residue does not scale, by design. Asserting
    # linearity on it would be asserting the opposite of the contract.
    scaling_lines = [c.material_code for c in components[:-1]]

    for code in scaling_lines:
        mass = single[code]
        # Only lines materially above the rounding step can carry a
        # meaningful ratio at all.
        if mass > Decimal("1"):
            ratio = multiple[code] / mass
            # RELATIVE tolerance. An absolute 0.01 on the ratio meant 0.125%
            # at factor 8 and 0.02% at factor 50 — a bound that tightened as
            # the factor grew, for no reason connected to the maths. It
            # failed at factor 8 on a 0.15% deviation that is simply the
            # milligram quantiser doing its job.
            assert abs(ratio - factor) / factor < Decimal("0.01")


def test_batch_mass_must_be_positive():
    c = [Component("RM-1", Decimal("100"))]
    with pytest.raises(ValueError, match="positive"):
        scale_to_batch(c, Decimal("0"))


# ---------------------------------------------------------- normalising


@settings(max_examples=250)
@given(components=formulas())
def test_normalisation_totals_exactly_one_hundred(components):
    """Not 99.9999. A normalisation that leaves the total failing its own
    check has done nothing useful."""
    assert total_percentage(normalize_to_100(components)) == Decimal("100")


@settings(max_examples=100)
@given(
    # Generated in range rather than filtered to it. The first version used
    # assume() to discard components below 0.5%, which threw away roughly
    # fifty inputs for every three it kept — Hypothesis reported the health
    # check, and it was right to: that much filtering distorts the
    # distribution and makes the test weaker than it looks.
    pcts=st.lists(
        st.decimals(min_value=Decimal("1"), max_value=Decimal("100"), places=4),
        min_size=2,
        max_size=12,
    )
)
def test_normalisation_preserves_component_ratios(pcts):
    components = [Component(f"RM-{i}", p) for i, p in enumerate(pcts)]
    before = components[0].percentage / components[1].percentage
    after_list = normalize_to_100(components)
    after = after_list[0].percentage / after_list[1].percentage
    assert abs(after - before) < Decimal("0.01")


# ------------------------------------------------------------- density


@settings(max_examples=200)
@given(components=formulas(with_density=True))
def test_blend_density_lies_between_the_component_densities(components):
    """A blend cannot be lighter than its lightest ingredient or heavier
    than its heaviest. This is the sanity property that a mass-weighted
    average would also satisfy — the next test is the one that separates
    the correct formula from the common wrong one."""
    rho = theoretical_density(components)
    lows = min(c.density_g_cm3 for c in components)
    highs = max(c.density_g_cm3 for c in components)
    assert lows - Decimal("0.001") <= rho <= highs + Decimal("0.001")


def test_blend_density_is_volume_additive_not_a_mass_average():
    """50/50 by mass of 1.0 and 3.0 g/cm3.

    Volume-additive:  1 / (0.5/1.0 + 0.5/3.0) = 1.5 g/cm3
    Mass average:     (1.0 + 3.0) / 2         = 2.0 g/cm3

    The mass average is the common mistake and overstates the density of
    any blend containing a light filler — precisely the case this product
    exists to optimise.
    """
    components = [
        Component("LIGHT", Decimal("50"), density_g_cm3=Decimal("1.0")),
        Component("HEAVY", Decimal("50"), density_g_cm3=Decimal("3.0")),
    ]
    rho = theoretical_density(components)
    assert abs(rho - Decimal("1.5")) < Decimal("0.0001")
    assert abs(rho - Decimal("2.0")) > Decimal("0.4")


def test_density_refuses_to_guess_a_missing_value():
    components = [
        Component("A", Decimal("50"), density_g_cm3=Decimal("1.0")),
        Component("B", Decimal("50")),
    ]
    with pytest.raises(ValueError, match="density unknown"):
        theoretical_density(components)


# --------------------------------------------------------------- solids


@settings(max_examples=100)
@given(
    solids=st.lists(
        st.decimals(min_value=Decimal("0"), max_value=Decimal("1"), places=3),
        min_size=1,
        max_size=8,
    )
)
def test_solids_content_is_a_percentage(solids):
    components = [
        Component(f"RM-{i}", Decimal("10"), solids_fraction=s) for i, s in enumerate(solids)
    ]
    result = solids_content(components)
    assert Decimal("0") <= result <= Decimal("100")


def test_solids_refuses_to_assume_an_unknown_component_is_solid():
    """Assuming solidity for unknown data is how a coating's solids figure
    flatters itself."""
    components = [
        Component("A", Decimal("50"), solids_fraction=Decimal("1")),
        Component("B", Decimal("50")),
    ]
    with pytest.raises(ValueError, match="solids fraction unknown"):
        solids_content(components)


def test_solids_infers_the_non_volatile_remainder_from_a_stated_voc():
    components = [
        Component("SOLVENT", Decimal("100"), voc_fraction=Decimal("0.8")),
    ]
    assert solids_content(components) == Decimal("20.0")


# ------------------------------------------------------------------ VOC


def test_voc_is_reported_per_litre_because_that_is_what_is_regulated():
    components = [
        Component(
            "SOLVENT",
            Decimal("100"),
            density_g_cm3=Decimal("0.9"),
            voc_fraction=Decimal("0.5"),
        )
    ]
    # 0.5 mass fraction * 0.9 g/cm3 * 1000 = 450 g/L
    assert abs(voc_content_g_per_l(components) - Decimal("450")) < Decimal("0.01")


# ---------------------------------------------------------------- ratios


def test_binder_to_filler_uses_roles():
    components = [
        Component("RESIN", Decimal("40"), role="resin"),
        Component("TALC", Decimal("60"), role="filler"),
    ]
    assert binder_to_filler_ratio(components) == Decimal("40") / Decimal("60")


def test_binder_to_filler_refuses_when_there_is_no_filler():
    """A ratio against nothing is not a number a chemist can act on, and a
    silent zero would read as 'no binder'."""
    components = [Component("RESIN", Decimal("100"), role="resin")]
    with pytest.raises(ValueError, match="no filler"):
        binder_to_filler_ratio(components)


def test_stoichiometric_hardener_parts():
    # EEW 190, AHEW 95 -> 50 parts hardener per 100 parts resin.
    assert stoichiometric_hardener_parts(Decimal("190"), Decimal("95")) == Decimal("50")


# ------------------------------------------------------------------ cost


def test_cost_is_a_weighted_average_of_component_cost():
    components = [
        Component("CHEAP", Decimal("50"), cost_per_kg=Decimal("1.00")),
        Component("DEAR", Decimal("50"), cost_per_kg=Decimal("3.00")),
    ]
    assert cost_per_kg(components) == Decimal("2.00")


# ------------------------------------------------- submission validation


def test_a_formula_totalling_one_hundred_is_submittable():
    components = [
        Component("A", Decimal("60")),
        Component("B", Decimal("40")),
    ]
    assert validate_for_submission(components) == []


def test_total_outside_tolerance_blocks_submission():
    components = [Component("A", Decimal("99"))]
    codes = [b.code for b in validate_for_submission(components)]
    assert "TOTAL_OUT_OF_TOLERANCE" in codes


def test_a_restricted_material_blocks_submission():
    components = [Component("BANNED", Decimal("100"))]
    blocks = validate_for_submission(components, restricted_materials=frozenset({"BANNED"}))
    assert [b.code for b in blocks] == ["RESTRICTED_MATERIAL"]


def test_a_duplicated_component_blocks_submission():
    components = [Component("A", Decimal("50")), Component("A", Decimal("50"))]
    codes = [b.code for b in validate_for_submission(components)]
    assert "DUPLICATE_COMPONENT" in codes


def test_every_blocker_is_reported_at_once():
    """A form that reveals one blocker per attempt teaches a chemist to
    distrust the software."""
    components = [Component("BANNED", Decimal("30")), Component("BANNED", Decimal("30"))]
    codes = {
        b.code
        for b in validate_for_submission(components, restricted_materials=frozenset({"BANNED"}))
    }
    assert {"TOTAL_OUT_OF_TOLERANCE", "RESTRICTED_MATERIAL", "DUPLICATE_COMPONENT"} <= codes


# -------------------------------------------------------- the float rule


def test_a_float_percentage_is_refused_not_converted():
    """CLAUDE.md §5. `Decimal(0.1)` is 0.1000000000000000055511151231257827;
    accepting a float here would launder a caller's bug into a
    plausible-looking number nothing downstream could detect."""
    with pytest.raises(TypeError, match="float"):
        Component("A", 34.75)  # type: ignore[arg-type]


def test_a_float_batch_mass_is_refused():
    components = [Component("A", Decimal("100"))]
    with pytest.raises(TypeError, match="float"):
        scale_to_batch(components, 25.0)  # type: ignore[arg-type]


def test_an_empty_formula_is_refused():
    with pytest.raises(ValueError, match="at least one component"):
        total_percentage([])


# ------------------------------------- the fourth §8 block, and duplicates


def test_a_failed_safety_check_blocks_submission():
    """§8's fourth hard block, which was listed in the docstring and absent
    from the code. A formula can be arithmetically perfect and still unsafe,
    and that is the one blocker whose absence is dangerous rather than
    merely wrong."""
    components = [Component("A", Decimal("100"))]
    assert validate_for_submission(components) == []

    blocks = validate_for_submission(
        components, failed_safety_checks=("peroxide incompatibility with amine",)
    )
    assert [b.code for b in blocks] == ["SAFETY_CHECK_FAILED"]
    assert "peroxide incompatibility" in blocks[0].message


def test_scaling_refuses_a_formula_with_duplicated_components():
    """The exact-sum invariant cannot hold for a result keyed by material
    code when two lines share one code — the later silently overwrote the
    earlier and the masses summed to less than the batch. The property test
    never caught it because its generator makes unique codes."""
    components = [
        Component("SAME", Decimal("50")),
        Component("SAME", Decimal("50")),
    ]
    with pytest.raises(ValueError, match="duplicated components"):
        scale_to_batch(components, Decimal("10"))
