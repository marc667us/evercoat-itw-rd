"""Explaining a test result. Concept Note §17, TODO I23.

🔴 THIS TOOL COMPUTES NOTHING. IT READS WHAT THE ENGINE ALREADY DERIVED.

That is not a simplification, it is the rule. §10's disposition is produced by
an ordered fourteen-rule algorithm in `app/calculations/testing.py`, and
`get_test` runs it on every read from the five stored axes plus the method's
limits and the requirement's threshold. There is no `display_color` column,
deliberately, so that a stored answer cannot go stale.

A tool that re-derived any of it -- recomputing a mean, re-deciding a colour,
re-reading a threshold -- would be a **second implementation of the safety
algorithm**, reachable from a chat box. When the two disagreed, the one a user
had been told would be the one nobody could account for. So this asks
`get_test` and reports.

WHAT AN EXPLANATION HAS TO CARRY
--------------------------------
§10 requires the automatic evaluation and the final disposition to be shown as
TWO SEPARATE THINGS -- a low-margin pass awaiting approval is both a pass and
not final, and one sentence cannot say that. So both are returned, plus:

  * the raw replicates, because §10 says raw measurements are the record and
    an aggregate alone is not;
  * the mean, standard deviation and CV the engine computed from them;
  * **the rule number** that decided the colour, so "why is this yellow" has a
    checkable answer rather than a plausible one;
  * the next action the disposition names, because a YELLOW with no stated
    next step is a defect §10 calls out by name.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.domains.testing.service import TestNotFoundError, get_test

__all__ = ["explain_test", "find_test_by_number"]


def find_test_by_number(
    session: Session, *, organization_id: uuid.UUID, query: str
) -> uuid.UUID | None:
    """Resolve a test number to an id, within the caller's boundary.

    Matches on the number only -- not on a method name or a formula code. A
    fuzzy match across several columns would let "the flexure test" resolve to
    whichever row sorted first, and answering a question about the wrong test
    result is worse than answering none.

    The session carries the caller's RLS context, so a test in a project they
    are not a member of resolves to `None` exactly as it would be absent.
    """
    cleaned = query.strip()
    if not cleaned:
        return None
    return session.execute(
        text(
            """
            SELECT id FROM testing.tests
            WHERE organization_id = :org AND test_number ILIKE :q
            ORDER BY test_number
            LIMIT 1
            """
        ),
        {"org": organization_id, "q": f"%{cleaned}%"},
    ).scalar_one_or_none()


def explain_test(
    session: Session, *, organization_id: uuid.UUID, query: str
) -> dict[str, Any] | None:
    """The derived facts about one test. `None` when it cannot be resolved.

    `None` rather than an empty dict so a caller cannot accidentally render an
    explanation of nothing -- the conductor must say "I could not find that
    test", which is a different statement from "that test has no result".
    """
    test_id = find_test_by_number(session, organization_id=organization_id, query=query)
    if test_id is None:
        return None

    try:
        test = get_test(session, test_id=test_id, organization_id=organization_id)
    except TestNotFoundError:
        return None

    return {
        "test_number": test.get("test_number"),
        "test_purpose": test.get("test_purpose"),
        "authority_level": test.get("authority_level"),
        "execution_status": test.get("execution_status"),
        "validity_status": test.get("validity_status"),
        "review_state": test.get("review_state"),
        "approval_state": test.get("approval_state"),
        # The two fields §10 requires shown separately.
        "automatic_evaluation": test.get("automatic_evaluation"),
        "final_disposition": test.get("final_disposition"),
        # Raw first, aggregate second -- that is the order §10 puts them in.
        "replicates": test.get("replicates"),
        "statistics": test.get("statistics"),
        "requirement": _requirement_of(
            session, organization_id=organization_id, requirement_id=test.get("requirement_id")
        ),
    }


def _requirement_of(
    session: Session, *, organization_id: uuid.UUID, requirement_id: uuid.UUID | None
) -> dict[str, Any] | None:
    """The acceptance criterion the result was measured against.

    Fetched separately because `get_test` returns `requirement_id` and not the
    requirement -- checked, not assumed. Without it an explanation can say
    "2.0 MPa" and not "2.0 MPa against a 5.0 MPa minimum", and the second is
    the half that answers "why".

    Same session, so the same row visibility: a requirement the caller cannot
    see comes back None and the explanation simply omits the comparison rather
    than inventing one.
    """
    if requirement_id is None:
        return None
    row = (
        session.execute(
            text(
                """
                SELECT name, minimum_value, maximum_value, canonical_unit,
                       warning_threshold, criticality
                FROM projects.requirements
                WHERE id = :r AND organization_id = :org
                """
            ),
            {"r": requirement_id, "org": organization_id},
        )
        .mappings()
        .one_or_none()
    )
    return dict(row) if row else None
