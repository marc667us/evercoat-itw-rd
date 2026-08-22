"""I69 — every table holding recipe data has a classification DECISION.

🔴 THE POINT OF THIS FILE IS THAT THE GAP CANNOT WIDEN SILENTLY.

Codex's BLOCKER against migration 039: *"Formula identity carries the label
while the actual recipe lives in child tables. This makes the lattice largely
decorative outside the one export query."*

Migration 041 makes the label RESOLVABLE for the recipe subtree, by
inheritance. That closes the half that can be closed today. The other half --
tests, samples, messages, MSD transcripts -- is real, open, and tracked.

So the risk this file addresses is not the current gap, which is written down.
It is the NEXT table: a `formulations.formula_attachments`, a
`quality.root_causes`, a `laboratory.batch_photographs` added in six weeks by
someone who never read I69, carrying recipe-derived content and no decision
about its sensitivity. `test_every_formula_derived_table_has_a_decision`
discovers those from the CATALOGUE rather than from a list somebody
maintains, so it fails on arrival.

⚠️ THE LIMIT OF THIS INSTRUMENT, STATED SO IT IS NOT MISTAKEN FOR MORE.
Discovery is by FOREIGN KEY into `formulations`. A table that holds recipe
information without referencing it -- a free-text message quoting a
composition, an MSD transcript, a report blob -- is NOT discoverable this way
and is not covered. That is precisely why `DEFERRED` below lists such tables by
hand, and why I69 stays open rather than being marked closed by this file.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

# ---------------------------------------------------------------------------
# The map. Every entry is a DECISION, and the reason is part of the entry.
# ---------------------------------------------------------------------------

# Resolve their classification from the parent formula, via
# `formulations.effective_classification`. No column of their own, because a
# child that disagrees with its parent is a disclosure and not a distinction.
INHERITS: dict[str, str] = {
    "formulations.formula_versions": "a version IS the formula at a point in time",
    "formulations.formula_components": "the composition -- the recipe itself",
    "formulations.formula_version_drivers": "names the failure or objective behind a revision",
    "laboratory.batches": "a batch is the formula made physical; its charge sheet is the recipe",
    "quality.failures": "a failure investigation quotes the composition it is about",
}

# Carry their own label, set deliberately (migration 039).
LABELLED: dict[str, str] = {
    "formulations.formulas": "the root of the inheritance chain",
    "materials.material_documents": "supplier documents are classified per document",
}

# 🔴 KNOWN, OPEN, AND TRACKED AS I69. Listed rather than discovered, because
# these hold recipe-derived content WITHOUT a foreign key into formulations --
# which is exactly the class this file's discovery cannot see.
DEFERRED: dict[str, str] = {
    "testing.tests": "I69 -- a result is evidence about a formula",
    "testing.test_replicates": "I69 -- raw measurements of a formula's performance",
    "laboratory.samples": "I69 -- a sample is a physical piece of the formula",
    "messaging.messages": "I69 -- free text routinely quotes compositions",
    "ai.msd_turns": "I69 -- MSD answers carry evidence packs verbatim",
}


def _formula_derived_tables(session) -> set[str]:
    """Every table with a foreign key into the formulations subtree.

    Read from `pg_constraint` rather than from a hand-kept list, because a list
    is what fails to mention the table added last Tuesday.
    """
    rows = session.execute(
        text(
            """
            SELECT DISTINCT n.nspname || '.' || c.relname
            FROM pg_constraint k
            JOIN pg_class c      ON c.oid = k.conrelid
            JOIN pg_namespace n  ON n.oid = c.relnamespace
            JOIN pg_class t      ON t.oid = k.confrelid
            JOIN pg_namespace tn ON tn.oid = t.relnamespace
            WHERE k.contype = 'f'
              AND tn.nspname = 'formulations'
              AND t.relname IN ('formulas', 'formula_versions')
            """
        )
    ).scalars()
    return set(rows)


def test_every_formula_derived_table_has_a_decision(owner_session) -> None:
    """🔴 A NEW TABLE HOLDING RECIPE DATA MUST NOT ARRIVE UNCLASSIFIED.

    This is the whole instrument. Add a table with a foreign key into
    `formulations` and this fails until somebody decides whether it inherits,
    carries its own label, or is deliberately deferred -- and says why.

    Proved by falsification: creating a `formulations.probe` with an FK to
    `formula_versions` fails this test naming that table.
    """
    discovered = _formula_derived_tables(owner_session)
    decided = set(INHERITS) | set(LABELLED) | set(DEFERRED)

    undecided = discovered - decided
    assert not undecided, (
        "these tables hold formula-derived data and no decision has been made "
        f"about their classification: {sorted(undecided)}. Add each to "
        "INHERITS, LABELLED or DEFERRED in this file, with the reason. A "
        "recipe's sensitivity does not stop at the table boundary."
    )


def test_the_map_does_not_describe_tables_that_no_longer_exist(owner_session) -> None:
    """The other direction: a stale entry hides a real gap.

    An entry for a dropped table makes the map look more complete than it is,
    and this repository has twice found a comment claiming a safety net that
    did not exist.
    """
    existing = set(
        owner_session.execute(
            text(
                "SELECT table_schema || '.' || table_name "
                "FROM information_schema.tables WHERE table_type = 'BASE TABLE'"
            )
        ).scalars()
    )
    named = set(INHERITS) | set(LABELLED) | set(DEFERRED)
    missing = named - existing
    assert not missing, f"the classification map names tables that do not exist: {sorted(missing)}"


@pytest.mark.parametrize("table", sorted(LABELLED))
def test_a_labelled_table_really_carries_the_column(owner_session, table: str) -> None:
    schema, name = table.split(".")
    has_column = owner_session.execute(
        text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = :s AND table_name = :t "
            "AND column_name = 'classification')"
        ),
        {"s": schema, "t": name},
    ).scalar_one()
    assert has_column, (
        f"{table} is listed as carrying its own classification and has no such "
        "column, so the map is describing an intention rather than the schema"
    )


@pytest.mark.parametrize("table", sorted(INHERITS))
def test_an_inheriting_table_does_not_carry_its_own_column(owner_session, table: str) -> None:
    """🔴 Two sources of truth for one fact is the defect, not the fix.

    If a child ever gains its own `classification`, the two can disagree --
    and whichever query happens to read the child wins. That is a disclosure
    wearing the clothes of a feature, so it fails here.
    """
    schema, name = table.split(".")
    has_column = owner_session.execute(
        text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = :s AND table_name = :t "
            "AND column_name = 'classification')"
        ),
        {"s": schema, "t": name},
    ).scalar_one()
    assert not has_column, (
        f"{table} inherits its classification from its formula but has grown "
        "its own column. The two can now disagree, and a child that says "
        "INTERNAL while its formula says FORMULA_RESTRICTED is a disclosure. "
        "Either remove the column or move the table to LABELLED deliberately."
    )


def test_a_version_resolves_the_classification_of_its_formula(owner_session) -> None:
    """The inheritance itself, end to end."""
    row = owner_session.execute(
        text(
            """
            SELECT v.id, f.classification
            FROM formulations.formula_versions v
            JOIN formulations.formulas f
              ON f.id = v.formula_id AND f.organization_id = v.organization_id
            LIMIT 1
            """
        )
    ).one_or_none()
    if row is None:
        pytest.skip("no formula version seeded on this database")

    resolved = owner_session.execute(
        text("SELECT formulations.effective_classification(:v)"), {"v": row[0]}
    ).scalar()
    assert resolved == row[1]


def test_reclassifying_the_formula_reclassifies_the_recipe(owner_session) -> None:
    """🔴 The property inheritance exists to provide.

    A per-table column would need five updates and could half-succeed. One
    parent means the recipe, its genealogy, its batches and its failure
    investigations all move together, in the same instant -- which is also what
    makes I49's purge-on-reclassification implementable later.
    """
    row = owner_session.execute(
        text(
            """
            SELECT v.id, f.id
            FROM formulations.formula_versions v
            JOIN formulations.formulas f
              ON f.id = v.formula_id AND f.organization_id = v.organization_id
            LIMIT 1
            """
        )
    ).one_or_none()
    if row is None:
        pytest.skip("no formula version seeded on this database")
    version_id, formula_id = row

    before = owner_session.execute(
        text("SELECT formulations.effective_classification(:v)"), {"v": version_id}
    ).scalar()
    target = "DIRECTOR_CONTROLLED" if before != "DIRECTOR_CONTROLLED" else "PUBLIC"

    owner_session.execute(
        text("UPDATE formulations.formulas SET classification = :c WHERE id = :f"),
        {"c": target, "f": formula_id},
    )
    owner_session.flush()

    after = owner_session.execute(
        text("SELECT formulations.effective_classification(:v)"), {"v": version_id}
    ).scalar()
    assert after == target, (
        "reclassifying the formula did not reclassify its version. The "
        "inheritance is not resolving through the parent."
    )


def test_the_resolver_is_not_a_cross_tenant_oracle(owner_session) -> None:
    """Invoker rights, asserted rather than assumed.

    A SECURITY DEFINER version would answer for every tenant -- the shape
    recorded as I56, and the one 037's `security_invoker=true` exists to avoid.
    """
    secdef = owner_session.execute(
        text(
            "SELECT prosecdef FROM pg_proc p JOIN pg_namespace n "
            "ON n.oid = p.pronamespace WHERE n.nspname = 'formulations' "
            "AND p.proname = 'effective_classification'"
        )
    ).scalar_one()
    assert secdef is False, (
        "formulations.effective_classification is SECURITY DEFINER, so it "
        "resolves classifications across tenant boundaries"
    )


def test_an_unknown_version_resolves_to_null_which_callers_deny(owner_session) -> None:
    import uuid

    resolved = owner_session.execute(
        text("SELECT formulations.effective_classification(:v)"), {"v": uuid.uuid4()}
    ).scalar()
    assert resolved is None
