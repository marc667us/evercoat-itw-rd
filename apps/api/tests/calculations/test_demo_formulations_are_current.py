"""The baked demonstration figures must match the engine that produced them.

WHY THIS TEST IS THE POINT OF THE WHOLE ARRANGEMENT.

`scripts/build_demo_formulations.py` runs the real calculation engine and
writes its output into `demo-data.json`, so the static demonstration can
show a theoretical density without reimplementing the maths in TypeScript.
That buys correctness exactly once — at the moment the script is run.

Without this test, the next person edits a component percentage in the
JSON, the committed `computed` block keeps the old numbers, and the
deployed site shows a density that belongs to a formula nobody has. Baked
values with no freshness check are the "two things that cannot be checked
against each other" defect wearing a different hat.

So: recompute, and fail if the committed file disagrees.
"""

from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
import sys

import pytest

# parents[4], not [3]. This file is at
# <repo>/apps/api/tests/calculations/, so [3] resolves to <repo>/apps and
# DATA.exists() was False — every test below skipped itself and the guard
# silently protected nothing. Verified by seeding a stale figure and
# watching it NOT be caught.
REPO = pathlib.Path(__file__).resolve().parents[4]
DATA = REPO / "apps" / "web" / "lib" / "demo" / "demo-data.json"
SCRIPT = REPO / "scripts" / "build_demo_formulations.py"


def test_the_dataset_this_module_guards_actually_exists():
    """Guards the guard.

    Every other test here is skipped when the dataset is missing, which is
    reasonable — and which meant a wrong path turned the entire module into
    five green skips protecting nothing. This one fails instead.
    """
    assert DATA.exists(), f"demo dataset not found at {DATA}"
    assert SCRIPT.exists(), f"build script not found at {SCRIPT}"


@pytest.mark.skipif(not DATA.exists(), reason="demo dataset not present")
def test_committed_demo_figures_match_a_fresh_computation(tmp_path):
    """Recompute into a COPY and compare the whole document.

    🔴 THE FIRST VERSION ERASED ITS OWN EVIDENCE. It ran the build script,
    which writes `demo-data.json` in place, then compared a pre-read copy
    against the rewritten file. So it failed once on stale data and passed
    on the very next run — because the failing run had already fixed the
    file. A developer rerunning "to confirm" saw green and would have
    committed a regenerated dataset they never looked at. Demonstrated by
    the Supervisor, which seeded a stale figure and watched exactly that.

    🔴 AND IT COMPARED ONLY `formulas[].versions[].computed`. The material
    display percentages baked this round sit outside that sub-tree, so
    changing a material's solids fraction left `solids_percent` stale and
    the guard still passed. `/materials` would have rendered a percentage
    for a fraction nobody recorded.

    So: copy the repo out, recompute in the copy, diff the ENTIRE document,
    and never write a tracked file from a test.
    """
    work = tmp_path / "repo"
    shutil.copytree(
        REPO,
        work,
        ignore=shutil.ignore_patterns(
            ".git",
            "node_modules",
            ".next",
            "out",
            "__pycache__",
            ".venv",
            "playwright-report",
            "test-results",
            "tmp",
        ),
    )

    committed = json.loads(DATA.read_text(encoding="utf-8"))

    result = subprocess.run(  # noqa: S603 - fixed argv, no shell
        [sys.executable, str(work / "scripts" / "build_demo_formulations.py")],
        capture_output=True,
        text=True,
        cwd=str(work),
        check=False,
    )
    assert result.returncode == 0, result.stderr

    recomputed = json.loads(
        (work / "apps" / "web" / "lib" / "demo" / "demo-data.json").read_text(encoding="utf-8")
    )

    assert committed == recomputed, (
        "The committed demonstration dataset is STALE — recomputing it produced "
        "something different. Someone changed a formula or a material without "
        "rerunning the engine. Fix with: python scripts/build_demo_formulations.py"
    )

    # The repo file must be untouched by this test.
    assert json.loads(DATA.read_text(encoding="utf-8")) == committed, (
        "this test wrote to a tracked file"
    )


@pytest.mark.skipif(not DATA.exists(), reason="demo dataset not present")
def test_every_version_carries_a_computed_block():
    """A version with no computed block renders blank figures rather than
    wrong ones — quieter, but still a screen that cannot do its job."""
    data = json.loads(DATA.read_text(encoding="utf-8"))
    for f in data["formulas"]:
        for v in f["versions"]:
            assert "computed" in v, f"{v['version_code']} was never computed"
            for key in (
                "total_percentage",
                "theoretical_density_g_cm3",
                "solids_percent",
                "voc_g_per_l",
                "raw_material_cost_per_kg",
                "submission_blocks",
            ):
                assert key in v["computed"], f"{v['version_code']} missing {key}"


@pytest.mark.skipif(not DATA.exists(), reason="demo dataset not present")
def test_every_formula_component_names_a_real_material():
    """A component pointing at a missing material makes the whole version
    uncomputable, and the failure would surface as a KeyError in a build
    script rather than as anything a reader could act on."""
    data = json.loads(DATA.read_text(encoding="utf-8"))
    codes = {m["material_code"] for m in data["materials"]}
    for f in data["formulas"]:
        for v in f["versions"]:
            for c in v["components"]:
                assert c["material_code"] in codes, (
                    f"{v['version_code']} uses unknown material {c['material_code']}"
                )


@pytest.mark.skipif(not DATA.exists(), reason="demo dataset not present")
def test_every_material_names_a_real_supplier():
    data = json.loads(DATA.read_text(encoding="utf-8"))
    codes = {s["supplier_code"] for s in data["suppliers"]}
    for m in data["materials"]:
        for s in m["suppliers"]:
            assert s in codes, f"{m['material_code']} names unknown supplier {s}"


@pytest.mark.skipif(not DATA.exists(), reason="demo dataset not present")
def test_a_draft_that_should_be_blocked_actually_is():
    """The demonstration exists partly to show hard submission validation
    working. If the seeded 'bad' draft ever becomes valid, the screen that
    demonstrates the blocker silently shows nothing."""
    data = json.loads(DATA.read_text(encoding="utf-8"))
    drafts = [v for f in data["formulas"] for v in f["versions"] if v["status"] == "draft"]
    assert drafts, "no draft version in the dataset to demonstrate the blocker"
    assert any(v["computed"]["submission_blocks"] for v in drafts), (
        "no draft is blocked — the submission validation demonstration is empty"
    )
