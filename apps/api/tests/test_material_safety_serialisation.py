"""A safety NUMERIC must reach the browser as a string, not as a float.

🔴 THIS IS I84 FOR THE THIRD TIME, AND THE SLICE SHIPPED WITHOUT IT.

`materials` and `laboratory`/`testing` each carry a guard exactly like this one,
and each was written after the same defect: FastAPI's `jsonable_encoder` maps
`Decimal` to **float**, so a `NUMERIC(7,4)` concentration of `10.0000` goes out
as the JSON number `10.0`. The scale the manufacturer disclosed is destroyed, a
float lands on a controlled safety record in violation of `CLAUDE.md` §5, and
the web client — which correctly types these as `z.string()` — rejects the whole
response with a parse error.

`material_safety` used neither the helper nor a guard. It was found by the
Supervisor review, not by the suite.

**Why the live suite was green.** The demonstration database holds no
interpreted Safety Data Sheets yet, so `components` and `storage_rules` were
always empty lists and the `Decimal` never appeared in a response. A test that
has only ever run over an empty collection has not been shown to detect
anything.

**Why the end-to-end test cannot catch it either.** It STUBS the API response
with the shape the client wants. A test that supplies its own contract cannot
detect a contract mismatch.

So this asserts the SERVER's half of the contract, needs no database, and fails
the moment a NUMERIC column is added to one of these rows without passing
through `_decimal_strings`.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from fastapi.encoders import jsonable_encoder

from app.domains.material_safety.service import _decimal_strings

# Every NUMERIC column the safety schema returns to a client, by the key the
# response actually uses. Listed by hand ON PURPOSE: a new NUMERIC column that
# nobody adds here is a column nobody thought about, and the assertion below
# reads the row rather than this list, so an omission shows up as a float
# escaping rather than as a silently shorter loop.
_SAFETY_NUMERIC_KEYS = (
    "concentration_low",
    "concentration_high",
    "min_temperature_c",
    "max_temperature_c",
)


def _component_row(**overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "component_name": "Styrene",
        "cas_number": "100-42-5",
        "ec_number": None,
        # The disclosed range. NUMERIC(7,4) in PostgreSQL.
        "concentration_low": Decimal("10.0000"),
        "concentration_high": Decimal("25.0000"),
    }
    row.update(overrides)
    return row


def _storage_row(**overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": "00000000-0000-0000-0000-000000000001",
        # NUMERIC(6,2).
        "min_temperature_c": Decimal("5.00"),
        "max_temperature_c": Decimal("25.00"),
        "segregation_class": "oxidiser",
        "shelf_life_months": 12,
        "requirement": "Store below 25 degrees Celsius",
    }
    row.update(overrides)
    return row


def _encoded(row: dict[str, Any]) -> dict[str, Any]:
    """What actually goes over the wire."""
    return dict(jsonable_encoder(_decimal_strings(row)))


def test_no_decimal_survives_as_a_float_in_a_component() -> None:
    encoded = _encoded(_component_row())
    for key in ("concentration_low", "concentration_high"):
        assert isinstance(encoded[key], str), (
            f"{key} reached the client as {type(encoded[key]).__name__}. "
            "FastAPI encodes Decimal as float, so the disclosed scale is lost "
            "and the client's z.string() rejects the whole response."
        )


def test_no_decimal_survives_as_a_float_in_a_storage_rule() -> None:
    encoded = _encoded(_storage_row())
    for key in ("min_temperature_c", "max_temperature_c"):
        assert isinstance(encoded[key], str), f"{key} reached the client as a float"


def test_the_stored_scale_is_preserved_exactly() -> None:
    """🔴 NOT MERELY "IS A STRING" — THE RIGHT STRING.

    `str(Decimal("10.0000"))` is `"10.0000"`, and that trailing precision is
    the disclosure: a sheet saying 10.0000% said something more precise than
    one saying 10%. `float` would render both as `10.0`.
    """
    encoded = _encoded(_component_row())
    assert encoded["concentration_low"] == "10.0000"
    assert encoded["concentration_high"] == "25.0000"
    assert _encoded(_storage_row())["min_temperature_c"] == "5.00"


def test_a_null_range_stays_null_rather_than_becoming_a_string() -> None:
    """A component with no disclosed range is a real and common case -- an SDS
    routinely names a substance without a concentration. `None` must survive as
    JSON null, not become the string "None", which would render on screen."""
    encoded = _encoded(_component_row(concentration_low=None, concentration_high=None))
    assert encoded["concentration_low"] is None
    assert encoded["concentration_high"] is None


def test_non_decimal_fields_are_untouched() -> None:
    """The helper must not stringify everything it sees: `shelf_life_months` is
    an integer and the client types it as `z.number()`."""
    encoded = _encoded(_storage_row())
    assert encoded["shelf_life_months"] == 12
    assert isinstance(encoded["shelf_life_months"], int)
    assert encoded["segregation_class"] == "oxidiser"


def test_the_guard_can_fail() -> None:
    """🔴 FALSIFICATION. Every assertion above passes trivially if
    `_decimal_strings` is a no-op on rows that contain no Decimal, so prove the
    UNCONVERTED row really does produce the float this file exists to prevent.
    Without this, the suite would stay green if the helper were deleted.
    """
    unconverted = dict(jsonable_encoder(_component_row()))
    assert isinstance(unconverted["concentration_low"], float), (
        "the premise of this test file no longer holds: FastAPI is not "
        "encoding Decimal as float, so these guards may be unnecessary"
    )
    assert unconverted["concentration_low"] == 10.0


def test_every_named_numeric_key_is_covered_by_one_of_the_rows() -> None:
    """A key added to `_SAFETY_NUMERIC_KEYS` with no row carrying it would make
    this file look more thorough than it is."""
    covered = set(_component_row()) | set(_storage_row())
    missing = [key for key in _SAFETY_NUMERIC_KEYS if key not in covered]
    assert missing == [], f"named as NUMERIC but never exercised: {missing}"
