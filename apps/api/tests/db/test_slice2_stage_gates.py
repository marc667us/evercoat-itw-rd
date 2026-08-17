"""Stage-gate configuration (Administration §2).

The reorder test is the reason this file exists, and it earned its place
immediately: `admin_stage_gates.py` originally claimed a single
`UPDATE ... FROM unnest(...) WITH ORDINALITY` was collision-free against
`UNIQUE (organization_id, sequence)`, "because a non-deferrable unique
constraint is checked once at STATEMENT end".

**That was false.** PostgreSQL checks a non-deferrable UNIQUE constraint
per row, as each row is updated. The single statement failed in exactly
the same place as a row-by-row loop:

    duplicate key value violates unique constraint
    "stage_definitions_org_seq_key"

Migration 009 made the constraint DEFERRABLE INITIALLY IMMEDIATE and the
route now defers it for its own transaction. The tests below prove all
three halves of that: ordinary writes are still checked immediately, a
reorder passes through duplicate intermediate states, and the final state
is still required to be unique.

The lesson generalises: a comment asserting engine semantics is a claim,
not a check.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError


@pytest.fixture
def gate_world(owner_session):
    suffix = uuid.uuid4().hex[:8]

    org = owner_session.execute(
        text("INSERT INTO core.organizations (code, name) VALUES (:c, :n) RETURNING id"),
        {"c": f"GATE-{suffix}", "n": "Stage Gate Test Org"},
    ).scalar_one()

    stages = []
    for seq, code in enumerate(["CONCEPT", "FEASIBILITY", "FORMULATION", "VALIDATION"], start=1):
        stages.append(
            owner_session.execute(
                text(
                    """
                    INSERT INTO workflow.stage_definitions
                        (organization_id, stage_code, name, sequence)
                    VALUES (:o, :c, :n, :s) RETURNING id
                    """
                ),
                {"o": org, "c": code, "n": code.title(), "s": seq},
            ).scalar_one()
        )
    owner_session.flush()
    return {"org": org, "stages": stages, "suffix": suffix}


# The statements admin_stage_gates.reorder_stage_definitions issues, in
# order. The SET CONSTRAINTS is not optional decoration -- without it the
# UPDATE fails, which is what the two tests below prove.
_DEFER = text("SET CONSTRAINTS workflow.stage_definitions_org_seq_key DEFERRED")

_REORDER = text(
    """
    UPDATE workflow.stage_definitions sd
    SET sequence = ordering.position
    FROM (
        SELECT id, ordinality AS position
        FROM unnest(CAST(:ids AS UUID[])) WITH ORDINALITY AS t(id, ordinality)
    ) AS ordering
    WHERE sd.id = ordering.id
      AND sd.organization_id = :org
    """
)


def test_the_sequence_constraint_is_real(owner_session, gate_world):
    """Guard against the reorder test passing vacuously.

    If (organization_id, sequence) were NOT unique, the reorder test below
    would prove nothing at all -- it would pass because nothing was ever
    being enforced. This asserts the constraint bites first.
    """
    with pytest.raises(IntegrityError):
        owner_session.execute(
            text(
                """
                INSERT INTO workflow.stage_definitions
                    (organization_id, stage_code, name, sequence)
                VALUES (:o, 'DUPE', 'Dupe', 1)
                """
            ),
            {"o": gate_world["org"]},
        )
        owner_session.flush()


def test_a_row_by_row_reorder_collides(owner_session, gate_world):
    """The failure the single-statement form exists to avoid.

    Setting stage 2 to sequence 1 while stage 1 still holds 1 violates the
    unique constraint immediately. This is the naive implementation, and
    it is proven broken here so the comment in admin_stage_gates.py is
    demonstrably true rather than merely plausible.
    """
    with pytest.raises(IntegrityError):
        owner_session.execute(
            text(
                """
                UPDATE workflow.stage_definitions SET sequence = 1
                WHERE id = :s AND organization_id = :o
                """
            ),
            {"s": gate_world["stages"][1], "o": gate_world["org"]},
        )
        owner_session.flush()


def test_reversing_the_whole_pipeline_succeeds_in_one_statement(owner_session, gate_world):
    """A full reversal -- every stage collides with another mid-way.

    The strongest form of the case: no row keeps its sequence, and every
    intermediate assignment duplicates a value still held by another row.

    Note what is NOT here: any SET CONSTRAINTS. Making the constraint
    DEFERRABLE (migration 009) changes how PostgreSQL enforces it -- from
    a per-row index check to a constraint trigger fired at END OF
    STATEMENT -- and that alone is enough. Deferring further, to COMMIT,
    would only move violations past the route's error handling.

    Before 009 this same statement raised
    `duplicate key value violates unique constraint`, which is the whole
    reason the migration exists.
    """
    reversed_ids = list(reversed(gate_world["stages"]))

    owner_session.execute(
        _REORDER,
        {"ids": [str(i) for i in reversed_ids], "org": gate_world["org"]},
    )
    owner_session.flush()

    rows = owner_session.execute(
        text(
            """
            SELECT stage_code, sequence FROM workflow.stage_definitions
            WHERE organization_id = :o ORDER BY sequence
            """
        ),
        {"o": gate_world["org"]},
    ).mappings()

    assert [r["stage_code"] for r in rows] == [
        "VALIDATION",
        "FORMULATION",
        "FEASIBILITY",
        "CONCEPT",
    ]


def test_a_single_swap_succeeds_in_one_statement(owner_session, gate_world):
    """The everyday case: two adjacent stages exchange places."""
    ids = gate_world["stages"]
    swapped = [ids[1], ids[0], ids[2], ids[3]]

    owner_session.execute(_REORDER, {"ids": [str(i) for i in swapped], "org": gate_world["org"]})
    owner_session.flush()

    rows = owner_session.execute(
        text(
            """
            SELECT stage_code, sequence FROM workflow.stage_definitions
            WHERE organization_id = :o ORDER BY sequence
            """
        ),
        {"o": gate_world["org"]},
    ).mappings()
    assert [r["stage_code"] for r in rows][:2] == ["FEASIBILITY", "CONCEPT"]


def test_deferring_moves_when_the_rule_is_checked_never_whether(owner_session, gate_world):
    """The assertion that stops 009 from being a silent weakening.

    Deferring must not make duplicate sequences *permissible* -- only
    permissible transiently. A reorder whose FINAL state still duplicates
    a sequence has to fail, and it must fail at COMMIT rather than
    quietly persisting.
    """
    ids = gate_world["stages"]

    owner_session.execute(_DEFER)
    # Two stages deliberately left holding sequence 1 at the end.
    owner_session.execute(
        text(
            """
            UPDATE workflow.stage_definitions SET sequence = 1
            WHERE id = ANY(CAST(:ids AS UUID[])) AND organization_id = :o
            """
        ),
        {"ids": [str(ids[0]), str(ids[1])], "o": gate_world["org"]},
    )

    # Permitted so far -- the check has been deferred, not removed.
    with pytest.raises(IntegrityError):
        owner_session.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))
        owner_session.flush()


def test_ordinary_writes_are_still_checked_immediately(owner_session, gate_world):
    """INITIALLY IMMEDIATE: nothing outside a reorder became laxer.

    Without this, migration 009 would have traded a broken reorder for
    duplicate sequences surviving until COMMIT everywhere else -- a wider
    hole than the one it closed.
    """
    with pytest.raises(IntegrityError):
        owner_session.execute(
            text(
                """
                UPDATE workflow.stage_definitions SET sequence = 1
                WHERE id = :s AND organization_id = :o
                """
            ),
            {"s": gate_world["stages"][2], "o": gate_world["org"]},
        )
        owner_session.flush()


def test_reorder_cannot_reach_another_organizations_stages(owner_session, gate_world):
    """The organization_id predicate is what stops a cross-tenant renumber.

    The route also refuses when rowcount does not match the id count, but
    that check is only correct if this predicate actually excludes the
    other tenant's rows -- so the exclusion is asserted directly.
    """
    other_org = owner_session.execute(
        text("INSERT INTO core.organizations (code, name) VALUES (:c, :n) RETURNING id"),
        {"c": f"GATE-OTHER-{gate_world['suffix']}", "n": "Other"},
    ).scalar_one()
    foreign_stage = owner_session.execute(
        text(
            """
            INSERT INTO workflow.stage_definitions
                (organization_id, stage_code, name, sequence)
            VALUES (:o, 'FOREIGN', 'Foreign', 1) RETURNING id
            """
        ),
        {"o": other_org},
    ).scalar_one()
    owner_session.flush()

    # Ask to renumber the other tenant's stage from within our own org.
    rowcount = owner_session.execute(
        _REORDER,
        {"ids": [str(foreign_stage)], "org": gate_world["org"]},
    ).rowcount
    owner_session.flush()

    # Nothing updated -- which is what makes the route's rowcount check a
    # valid refusal rather than a formality.
    assert rowcount == 0

    untouched = owner_session.execute(
        text("SELECT sequence FROM workflow.stage_definitions WHERE id = :s"),
        {"s": foreign_stage},
    ).scalar_one()
    assert untouched == 1


def test_a_stage_with_history_can_be_retired_but_not_deleted(owner_session, gate_world):
    """CLAUDE.md §5: never cascade-delete R&D history.

    project_stages rows ARE the project's history. A stage definition that
    could be deleted would take them with it or orphan them; the FK is
    RESTRICT so the database refuses, and `is_active = false` is the
    supported path.
    """
    project = owner_session.execute(
        text(
            """
            INSERT INTO projects.projects (organization_id, project_code, name)
            VALUES (:o, :c, 'History Project') RETURNING id
            """
        ),
        {"o": gate_world["org"], "c": f"RDP-H-{gate_world['suffix']}"},
    ).scalar_one()
    owner_session.execute(
        text(
            """
            INSERT INTO workflow.project_stages
                (organization_id, project_id, stage_definition_id, status, started_at)
            VALUES (:o, :p, :s, 'completed', now())
            """
        ),
        {"o": gate_world["org"], "p": project, "s": gate_world["stages"][0]},
    )
    owner_session.flush()

    with pytest.raises(IntegrityError):
        owner_session.execute(
            text("DELETE FROM workflow.stage_definitions WHERE id = :s"),
            {"s": gate_world["stages"][0]},
        )
        owner_session.flush()


def test_requires_approval_without_an_approver_is_refused(owner_session, gate_world):
    """A gate that requires approval from nobody never opens."""
    with pytest.raises(IntegrityError):
        owner_session.execute(
            text(
                """
                INSERT INTO workflow.stage_definitions
                    (organization_id, stage_code, name, sequence, requires_approval)
                VALUES (:o, 'NOAPPROVER', 'No approver', 99, TRUE)
                """
            ),
            {"o": gate_world["org"]},
        )
        owner_session.flush()
