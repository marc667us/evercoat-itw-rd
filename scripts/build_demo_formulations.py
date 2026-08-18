#!/usr/bin/env python
"""Compute the demonstration formulations with the REAL calculation engine.

WHY THIS SCRIPT EXISTS AT ALL.

`CLAUDE.md` rule 2: Python owns deterministic scientific calculation, and
nothing else may perform the arithmetic. The deployed demonstration is a
static export with no Python behind it, so there are only three ways it can
show a theoretical density:

  1. reimplement the maths in TypeScript — a second implementation of the
     controlled calculation, which is the rule this codebase exists to
     enforce, broken on purpose;
  2. type plausible numbers into the dataset by hand — inventing scientific
     results, which rule 3 forbids outright;
  3. run the real engine at BUILD time and bake its output in.

This is (3). Every derived figure the demonstration shows is produced by
`app.calculations.formulation`, the same module the API will call, and is
written into `demo-data.json` under a `computed` block.

`tests/calculations/test_demo_formulations_are_current.py` re-runs this and
fails if the committed JSON disagrees, so the baked numbers cannot drift
away from the engine that produced them.

Run:  python scripts/build_demo_formulations.py
"""

from __future__ import annotations

import json
import pathlib
import sys
from decimal import Decimal

REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "apps" / "api"))

from app.calculations import (  # noqa: E402
    Component,
    binder_to_filler_ratio,
    cost_per_kg,
    scale_to_batch,
    solids_content,
    theoretical_density,
    total_percentage,
    validate_for_submission,
    voc_content_g_per_l,
)

DATA = REPO / "apps" / "web" / "lib" / "demo" / "demo-data.json"
HUNDRED = Decimal("100")

# Materials restricted for use. Kept here rather than inferred from the
# material list so the submission validator is exercised against a real
# restriction rather than an empty set.
RESTRICTED = frozenset({"RM-SOLV-01"})

# The reference batch the demonstration shows a weigh-up for. A real number
# a technician would recognise, not 1 kg.
DEMO_BATCH_KG = Decimal("25")


def _components(version: dict) -> list[Component]:
    """Build engine Components from the JSON, resolving material properties."""
    materials = {m["material_code"]: m for m in _data["materials"]}
    out: list[Component] = []
    for line in version["components"]:
        m = materials[line["material_code"]]
        out.append(
            Component(
                material_code=line["material_code"],
                percentage=Decimal(line["percentage"]),
                role=m["role"],
                density_g_cm3=Decimal(m["density_g_cm3"]),
                solids_fraction=Decimal(m["solids_fraction"]),
                voc_fraction=Decimal(m["voc_fraction"]),
                cost_per_kg=Decimal(m["cost_per_kg"]),
            )
        )
    return out


def _q(value: Decimal, places: str) -> str:
    """Quantise for display and return a STRING.

    A string, not a float. The whole point of computing here is that the
    numbers stay exact; handing them to JSON as floats at the last step
    would undo it.
    """
    return str(value.quantize(Decimal(places)))


def compute(version: dict) -> dict:
    comps = _components(version)
    blocks = validate_for_submission(
        comps, restricted_materials=RESTRICTED, require_density=True
    )
    computed = {
        "total_percentage": _q(total_percentage(comps), "0.0001"),
        "theoretical_density_g_cm3": _q(theoretical_density(comps), "0.0001"),
        "binder_to_filler": _q(binder_to_filler_ratio(comps), "0.001"),
        "solids_percent": _q(solids_content(comps), "0.01"),
        "voc_g_per_l": _q(voc_content_g_per_l(comps), "0.1"),
        "raw_material_cost_per_kg": _q(cost_per_kg(comps), "0.0001"),
        "submission_blocks": [{"code": b.code, "message": b.message} for b in blocks],
        "batch": {
            "batch_mass_kg": str(DEMO_BATCH_KG),
            "masses_kg": {
                code: str(mass)
                for code, mass in scale_to_batch(comps, DEMO_BATCH_KG).items()
            },
        },
    }
    return computed


def diff_versions(parent: dict, child: dict) -> list[dict]:
    """The difference engine: old / new / delta / %delta, per component.

    IN PYTHON, like every other number on this page. A percentage delta is
    arithmetic on a controlled quantity, and `CLAUDE.md` rule 2 does not
    carve out an exception for arithmetic that happens to be easy. Doing it
    in the frontend would put a second implementation of formulation maths
    in TypeScript, which is the thing the rule forbids.

    A component present in one version and absent from the other is
    reported with the missing side as null rather than as zero. Zero says
    "we used none of it"; null says "this line did not exist" — and a
    reviewer reading a revision history needs to tell those apart.
    """
    old_pct = {c["material_code"]: Decimal(c["percentage"]) for c in parent["components"]}
    new_pct = {c["material_code"]: Decimal(c["percentage"]) for c in child["components"]}

    rows: list[dict] = []
    for code in sorted(old_pct.keys() | new_pct.keys()):
        was = old_pct.get(code)
        now = new_pct.get(code)
        if was is None:
            change = "added"
            delta = now
            pct_delta = None
        elif now is None:
            change = "removed"
            delta = -was
            pct_delta = Decimal("-100")
        else:
            delta = now - was
            change = "unchanged" if delta == 0 else "changed"
            pct_delta = (delta / was * HUNDRED) if was != 0 else None

        rows.append(
            {
                "material_code": code,
                "change": change,
                "old_percentage": None if was is None else _q(was, "0.0001"),
                "new_percentage": None if now is None else _q(now, "0.0001"),
                "delta": None if delta is None else _q(delta, "0.0001"),
                "percent_delta": None if pct_delta is None else _q(pct_delta, "0.01"),
            }
        )
    return rows


def main() -> int:
    global _data
    _data = json.loads(DATA.read_text(encoding="utf-8"))

    if "formulas" not in _data:
        print("no `formulas` in the dataset — nothing to compute", file=sys.stderr)
        return 1

    # Material display percentages, computed HERE.
    #
    # The materials table showed solids and VOC as `Number(fraction) * 100`
    # with `toFixed()` — JavaScript floating point on a controlled
    # percentage, which CLAUDE.md §5 forbids outright and which sat inside a
    # commit whose whole premise is that the frontend performs no
    # formulation arithmetic. Raised by Codex. The fraction stays in the
    # data for the engine; the percentage is baked for display.
    for material in _data.get("materials", []):
        for src, dest in (
            ("solids_fraction", "solids_percent"),
            ("voc_fraction", "voc_percent"),
        ):
            material[dest] = _q(Decimal(material[src]) * HUNDRED, "0.1")

    for formula in _data["formulas"]:
        by_code = {v["version_code"]: v for v in formula["versions"]}
        for version in formula["versions"]:
            version["computed"] = compute(version)
            parent_code = version.get("parent_version")
            parent = by_code.get(parent_code) if parent_code else None
            version["computed"]["diff_vs_parent"] = (
                diff_versions(parent, version) if parent else []
            )

    DATA.write_text(
        json.dumps(_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    n = sum(len(f["versions"]) for f in _data["formulas"])
    print(f"computed {n} formula version(s) with the real engine")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
