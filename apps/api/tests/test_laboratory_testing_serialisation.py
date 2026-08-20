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
