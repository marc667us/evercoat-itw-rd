"""A NUMERIC must reach the browser as a string, not as a float.

🔴 WHAT THIS CATCHES, AND WHY NOTHING ELSE DID

`_with_percentages` stringified the two DERIVED percentages and left every
stored quantity as a `Decimal`. FastAPI's `jsonable_encoder` maps
`Decimal` to **float**:

    jsonable_encoder(Decimal("1.1000"))  ->  1.1        (a float)

So a density recorded to four decimal places went out as a JSON number
carrying one — the exact round trip `CLAUDE.md` §5 and this module's own
docstrings say the Decimal discipline exists to prevent. The web client,
which correctly types these as strings, rejected every live material row
with a parse error.

**The end-to-end test could not catch it**, because it STUBS the response
with the shape the client wants. A test that supplies its own contract
cannot detect a contract mismatch — it proves the client parses what the
client believes, which is never in doubt.

This test asserts the SERVER's side of the same contract, needs no
database, and fails the moment a NUMERIC column is added to the row
without being added to `_QUANTITY_KEYS`.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from fastapi.encoders import jsonable_encoder

from app.domains.materials.service import (
    _QUANTITY_KEYS,
    _stringify_quantities,
    _with_percentages,
)


def _row(**overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": "00000000-0000-0000-0000-000000000001",
        "material_code": "RM-001",
        "name": "A resin",
        "density_g_cm3": Decimal("1.1000"),
        "solids_fraction": Decimal("0.6500"),
        "voc_fraction": Decimal("0.3500"),
        "cost_per_kg": Decimal("2.8000"),
    }
    row.update(overrides)
    return row


def test_every_quantity_leaves_as_a_string() -> None:
    out = _with_percentages(_row())
    for key in ("density_g_cm3", "solids_fraction", "voc_fraction", "cost_per_kg"):
        assert isinstance(out[key], str), (
            f"{key} left the service as {type(out[key]).__name__}. FastAPI encodes "
            "Decimal as float, so the stored scale is lost and the web client "
            "rejects the row."
        )


def test_the_stored_scale_survives() -> None:
    """1.1000 must not become 1.1.

    Four decimal places is a recorded measurement precision, not
    decoration. A density that arrives as `1.1` has silently claimed a
    coarser measurement than the laboratory made.
    """
    out = _with_percentages(_row())
    assert out["density_g_cm3"] == "1.1000"
    assert jsonable_encoder(out["density_g_cm3"]) == "1.1000"


def test_the_encoded_payload_contains_no_floats() -> None:
    """The end-to-end property, asserted through the real encoder."""
    encoded = jsonable_encoder(_with_percentages(_row()))
    floats = {k: v for k, v in encoded.items() if isinstance(v, float)}
    assert not floats, (
        "these fields reached the wire as JSON numbers: "
        f"{sorted(floats)}. A NUMERIC must be a string — see this file's header."
    )


def test_an_unknown_quantity_stays_null_and_does_not_become_zero() -> None:
    """`None` means UNMEASURED, and it is not zero.

    This project has already shipped a defect where a blank measurement
    rendered a green PASS, and `Number("")` is 0. A null that became
    `"0"` here would be that defect again, one layer down.
    """
    out = _with_percentages(_row(density_g_cm3=None, solids_fraction=None))
    assert out["density_g_cm3"] is None
    assert out["solids_percent"] is None


def test_percentages_are_still_derived_by_the_engine() -> None:
    """The fractions are stored 0-1; the browser must never multiply."""
    out = _with_percentages(_row())
    assert out["solids_percent"] == "65.0000"
    assert out["voc_percent"] == "35.0000"


def test_the_quantity_list_covers_every_numeric_the_row_can_carry() -> None:
    """A NUMERIC column added without being listed goes out as a float.

    The list is the single point of failure for this whole contract, so
    name the columns it must contain rather than trusting a reader to
    remember. These are the NUMERIC columns of `materials.materials`
    plus the supplier price that joins the row elsewhere.
    """
    expected = {
        "density_g_cm3",
        "solids_fraction",
        "voc_fraction",
        "cost_per_kg",
        "epoxy_equivalent_weight",
        "amine_hydrogen_equivalent_weight",
        "quoted_price_per_kg",
    }
    assert set(_QUANTITY_KEYS) == expected, (
        "the quantity list and this test disagree. If a NUMERIC column was "
        "added, add it to BOTH; if one was removed, remove it from both."
    )


# ---------------------------------------------------------------------------
# 🔴 THE HELPER WAS RIGHT AND A CALLER STILL SHIPPED FLOATS.
#
# Everything above tests `_with_percentages`, and `_with_percentages` has been
# correct since the day it was fixed. `get_material` -- the detail endpoint the
# material edit form loads from -- assembled its response by hand and called
# neither helper. It returned raw `Decimal`s, FastAPI encoded them as floats,
# and every material carrying a density, cost or fraction failed the client's
# parse. Testing the helper cannot see that: the defect is a caller that does
# not use it.
#
# ⚠️ THE FIRST VERSION OF THAT TEST COULD NOT FAIL, AND WAS DELETED.
#
# It scraped the service source and asserted `_with_percentages` appeared
# somewhere in `get_material`. Reverting the fix left the helper's name in the
# NEXT line -- the one handling the nested supplier rows -- so it went on
# passing over the broken code. The same went for the `update_material` check,
# which read the LAST `return` in the body and so read the wrong one.
#
# The replacements live in `tests/db/test_015_material_row_contract.py` and
# CALL the functions against a real database, because what is being asserted
# is what the function RETURNS, and only the function can answer that.
# ---------------------------------------------------------------------------


def test_the_quantity_stringifier_is_reachable_on_its_own() -> None:
    """`_stringify_quantities` exists so a row can be fixed WITHOUT the
    percentages -- a supplier row carries `quoted_price_per_kg` and no
    fractions, and running the percentage half over it would attach
    `solids_percent: null` to a supplier."""
    supplier = {"supplier_code": "SUP-1", "quoted_price_per_kg": Decimal("12.3400")}
    encoded = jsonable_encoder(_stringify_quantities(dict(supplier)))
    assert encoded["quoted_price_per_kg"] == "12.3400"
    assert not isinstance(encoded["quoted_price_per_kg"], float)
    assert "solids_percent" not in encoded
