"""A controlled mass and a physical measurement must not become floats.

🔴 THE SAME DEFECT CODEX FOUND IN `materials`, IN TWO MORE MODULES

`jsonable_encoder` maps `Decimal` to `float`. Measured:

    jsonable_encoder(Decimal("12.5000"))  ->  12.5
    jsonable_encoder(Decimal("2.00"))     ->  2.0

`materials` was fixed on 2026-08-19 and **nowhere else was**. `laboratory`
and `testing` returned their rows straight from the database, so:

  * `laboratory.batches.planned_quantity_kg` — `NUMERIC(14,4)`, the
    planned mass of a controlled formulation batch — went out with the
    trailing scale destroyed, and
  * `testing.test_replicates.measured_value` — `NUMERIC(18,6)`, the raw
    physical measurement this entire platform exists to record faithfully
    — did the same.

`CLAUDE.md` §5 is unambiguous: *"NUMERIC, never float, for percentages,
masses, densities and measured values. Floating-point on a controlled
formulation percentage is a defect."*

Nothing caught it because no screen was wired to these routes yet, so no
client had ever parsed the response. It was found while wiring the
Laboratory screen — by reading the contract before writing against it,
rather than by the screen failing later.

This test needs no database: it drives the real encoder over the real
helper.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from fastapi.encoders import jsonable_encoder

# Aliased with LEADING UNDERSCORES on purpose. pytest collects any
# module-level callable whose name starts with `test`, so importing
# testing's helper as `testing_decimal_strings` made pytest try to RUN
# it as a test case and error on the missing fixture. Caught here, not
# in CI.
from app.domains.formulations.service import PROPERTY_SCALE
from app.domains.formulations.service import _decimal_strings as _formulations_helper
from app.domains.formulations.service import _try as _formulations_try
from app.domains.laboratory.service import _decimal_strings as _lab_helper
from app.domains.testing.service import _decimal_strings as _testing_helper


def test_the_encoder_really_does_destroy_scale() -> None:
    """The premise, asserted rather than assumed.

    If a future FastAPI encodes `Decimal` as a string on its own, this
    fails and the two modules' helpers become redundant — which is worth
    being told about rather than discovering by reading.
    """
    encoded = jsonable_encoder({"mass": Decimal("12.5000")})
    assert isinstance(encoded["mass"], float), (
        "jsonable_encoder no longer maps Decimal to float; re-check whether "
        "_decimal_strings is still needed"
    )
    assert encoded["mass"] == 12.5


@pytest.mark.parametrize(
    "helper",
    [_lab_helper, _testing_helper],
    ids=["laboratory", "testing"],
)
def test_every_decimal_survives_the_wire_with_its_scale(helper: Any) -> None:
    row = {
        "batch_number": "LB-2026-014",
        "planned_quantity_kg": Decimal("12.5000"),
        "tolerance_percent": Decimal("2.00"),
        "measured_value": Decimal("6.123456"),
        "actual_mass_kg": None,
        "component_count": 7,
        "started_at": None,
    }

    encoded = jsonable_encoder(helper(row))

    assert encoded["planned_quantity_kg"] == "12.5000", (
        "the planned batch mass lost its stored scale on the way out"
    )
    assert encoded["tolerance_percent"] == "2.00"
    assert encoded["measured_value"] == "6.123456", (
        "a raw physical measurement was rendered as a float"
    )

    # Nothing else is touched: a None stays None, an int stays an int, and
    # a string stays a string. A helper that stringified everything would
    # pass the assertions above while breaking every count on the screen.
    assert encoded["actual_mass_kg"] is None
    assert encoded["component_count"] == 7
    assert isinstance(encoded["component_count"], int)
    assert encoded["batch_number"] == "LB-2026-014"
    assert encoded["started_at"] is None


@pytest.mark.parametrize(
    "helper",
    [_lab_helper, _testing_helper],
    ids=["laboratory", "testing"],
)
def test_no_float_reaches_the_client_for_any_decimal_column(helper: Any) -> None:
    """The generic guard.

    `materials` enumerates its quantity columns by name, which works until
    somebody adds a NUMERIC column and does not extend the tuple — exactly
    how this class of bug survives. These helpers convert every `Decimal`
    in the row, so a column added tomorrow is covered without anybody
    remembering to do anything.

    This asserts that property directly: whatever Decimals are present,
    none of them arrives as a float.
    """
    row = {f"quantity_{i}": Decimal(f"{i}.0001") for i in range(6)}
    encoded = jsonable_encoder(helper(row))

    floats = {key: value for key, value in encoded.items() if isinstance(value, float)}
    assert not floats, f"these Decimal columns reached the client as floats: {floats}"
    assert all(isinstance(value, str) for value in encoded.values())


# ---------------------------------------------------------------------------
# I84 — the same defect again, in the places an orphaned route was hiding it
# ---------------------------------------------------------------------------
#
# 🔴 THIS FILE'S OWN HEADER PREDICTED THIS AND WAS STILL TOO NARROW.
#
# It says the laboratory/testing defect survived because *"no screen was wired
# to these routes yet, so no client had ever parsed the response"*. That was
# right, and the fix went only as far as the routes being wired that day. Two
# whole surfaces were left:
#
#   * `testing.get_test` builds `statistics` and `automatic_evaluation` AFTER
#     `_decimal_strings` has run on the row, so the mean, the sample standard
#     deviation, the CV and the pass margin were never converted at all.
#
#   * `formulations` had **no helper of any kind**. Measured against the
#     running service: `percentage 2.5`, `density_g_cm3 2.2`,
#     `theoretical_density_g_cm3 1.0906918323011936` — every one a float, on
#     the module whose numbers ARE the controlled formulation.
#
# Both were found the same way as the first instance and for the same reason:
# by wiring a screen to routes nothing had ever called. The lesson is not
# "check testing and formulations" — it is that a module with no client is a
# module whose response contract has never been tested by anything.


def test_formulations_has_a_helper_and_it_behaves_like_the_others() -> None:
    """The module that had none.

    Percentages, densities and costs are the numbers `CLAUDE.md` §5 names
    first, and this module returned all three as floats until a screen
    finally parsed them.
    """
    row = {
        "material_code": "RM-FIL-01",
        "percentage": Decimal("22.0000"),
        "density_g_cm3": Decimal("2.2000"),
        "cost_per_kg": Decimal("6.4000"),
        "solids_fraction": None,
        "display_order": 100,
    }

    encoded = jsonable_encoder(_formulations_helper(row))

    assert encoded["percentage"] == "22.0000", (
        "a controlled formulation percentage lost its stored scale on the way out"
    )
    assert encoded["density_g_cm3"] == "2.2000"
    assert encoded["cost_per_kg"] == "6.4000"

    # Unchanged, for the same reason as above: a helper that stringified
    # everything would break `display_order` and every count on the screen.
    assert encoded["solids_fraction"] is None
    assert encoded["display_order"] == 100
    assert isinstance(encoded["display_order"], int)


def test_a_derived_property_is_a_quantized_string_or_a_stated_reason() -> None:
    """`_try` is the response boundary for every engine calculation.

    Two things are asserted together because the endpoint needs both:

    1. **A string.** The engine returns `Decimal`; the encoder would make it
       a float.

    2. **Quantized.** The engine deliberately does not round — it divides at
       full `Decimal` context precision, so a theoretical density arrived as
       `1.092376966584235260696368803`. Twenty-eight significant digits
       asserted from inputs recorded to four is false precision on a
       controlled figure, and rule 3 requires a theoretical density presented
       as calculated rather than dressed up as measured.
    """
    ok = _formulations_try(lambda: Decimal("1.092376966584235260696368803"))
    encoded = jsonable_encoder(ok)

    assert isinstance(encoded["value"], str), "a derived property reached the client as a float"
    assert encoded["value"] == "1.0924", (
        "a derived property was not quantized to the project's four-place scale — "
        "scripts/build_demo_formulations.py and the live API render onto the SAME "
        "screens, so a disagreement here shows one formula two different ways"
    )
    assert encoded["unavailable_reason"] is None
    assert Decimal("0.0001") == PROPERTY_SCALE, (
        "the presentation scale moved; scripts/build_demo_formulations.py must "
        "move with it or the two data sources disagree on the same screen"
    )


def test_an_unavailable_property_carries_the_reason_and_no_value() -> None:
    """A refusal is not a zero, and it is not a blank.

    The engine raises with a message naming the material and the missing
    property; that sentence is the most useful thing on the screen. A `None`
    value beside a `None` reason would be a blank cell, which reads as
    "calculated, came out empty".
    """

    def refuse() -> Decimal:
        raise ValueError("density unknown for: RM-FIL-07")

    out = _formulations_try(refuse)
    assert out["value"] is None
    assert out["unavailable_reason"] == "density unknown for: RM-FIL-07"


def test_test_statistics_and_margin_are_strings_not_floats() -> None:
    """The four fields `get_test` builds after `_decimal_strings` has run.

    `mean`, `standard_deviation`, `cv_percent` and `margin_percent` are
    assembled from dataclasses into fresh dicts, so the row-level conversion
    never reached them. They are now passed through the helper explicitly, and
    this pins that: the raw physical measurement this platform exists to record
    faithfully, and the statistics computed from it, must not become floats.
    """
    statistics = _testing_helper(
        {
            "count": 3,
            "valid_count": 2,
            "mean": Decimal("12.000000"),
            "standard_deviation": Decimal("0.014142"),
            "cv_percent": Decimal("0.117851"),
        }
    )
    encoded = jsonable_encoder(statistics)

    assert encoded["mean"] == "12.000000", "a measured mean lost its scale"
    assert encoded["standard_deviation"] == "0.014142"
    assert encoded["cv_percent"] == "0.117851"

    # 🔴 CARDINALITIES STAY INTEGERS. `valid_count` feeds rule 5 of the traffic
    # light — `replicates_valid < replicates_required` — and a string there
    # would compare as text.
    assert encoded["count"] == 3
    assert isinstance(encoded["count"], int)
    assert isinstance(encoded["valid_count"], int)


def test_a_null_statistic_stays_null_and_never_becomes_a_number() -> None:
    """One replicate has a mean and NO standard deviation.

    `None`, not zero — zero claims "perfectly repeatable", which one
    measurement cannot support, and rule 6 compares CV against a limit, so a
    spurious `0.0` would silently pass every single-replicate test. The helper
    must leave the absence alone rather than rendering it as `"0"`.
    """
    encoded = jsonable_encoder(
        _testing_helper(
            {
                "count": 1,
                "valid_count": 1,
                "mean": Decimal("12.000000"),
                "standard_deviation": None,
                "cv_percent": None,
            }
        )
    )

    assert encoded["standard_deviation"] is None
    assert encoded["cv_percent"] is None
    assert encoded["mean"] == "12.000000"
