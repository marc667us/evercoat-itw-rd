"""Reporting — test results, aggregated for the analysis department.

This is the link the operator asked for: test data reaching the analysis
module as a report rather than only as a dashboard panel.

🔴 IT DOES NOT DERIVE A STATUS. IT READS THE ONE TESTING ALREADY DERIVED.

§10 is categorical that `display_color` and `final_status` are server-owned
and rule-derived, and `app/calculations/testing.py` says it in the strongest
terms: *"a CASE expression in SQL computing display_color would be a second
answer"*. A report that grouped tests by re-implementing the fourteen ordered
rules would be exactly that second answer — and the first time the two
disagreed, nobody could say which was right.

So every row here comes from `testing.service.get_test`, which is the one
place that calls `derive_disposition`. This module counts; it does not judge.

⚠️ ONE `get_test` PER ROW, AND THAT IS A REAL COST.
`list_tests` returns the five stored axes but NOT the derived disposition,
so the queue alone cannot say how many tests are GREEN. Fetching each test is
the only way to read the derivation rather than copy it, and correctness wins
that trade — but it is O(n) round trips, so `limit` is bounded and the report
states what it counted. A future `list_tests` that returned the disposition
would make this a single query; until it does, this is honest rather than
fast, and the cap is visible rather than silent.

⚠️ AN EMPTY REPORT IS AN ANSWER. If the organization has no tests, this
returns zero counts and an empty list — never a placeholder, never a
demonstration figure. This project shipped "a failed read became demonstration
data" once (2026-08-19) and once was enough.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.domains.testing.service import get_test, list_tests

__all__ = ["MAX_ROWS", "test_results_report"]

# Bounded, and the report says when it hit the cap. §11's counts are of
# actionable items, and a report that silently truncated would be counting
# something other than what it claims.
MAX_ROWS = 200


def test_results_report(
    session: Session,
    *,
    organization_id: uuid.UUID,
    project_id: uuid.UUID | None = None,
    limit: int = MAX_ROWS,
) -> dict[str, Any]:
    """Tests grouped by their DERIVED disposition, with drill-down ids.

    Every row carries `test_id` and `test_number` so §2's requirement that
    analytics "drill down to real source records" is satisfiable without a
    second round trip to work out what is being looked at.

    The two evaluations are reported SEPARATELY -- `calculated_result` beside
    `disposition` -- because §10 requires it: a low-margin pass awaiting
    approval is both a pass and not final, and one field cannot say that.
    """
    capped = max(1, min(limit, MAX_ROWS))
    queue = list_tests(
        session, organization_id=organization_id, project_id=project_id, limit=capped
    )

    rows: list[dict[str, Any]] = []
    by_colour: dict[str, int] = {}
    by_rule: dict[int, int] = {}

    for entry in queue:
        detail = get_test(session, test_id=entry["id"], organization_id=organization_id)
        disposition = detail.get("final_disposition") or {}
        automatic = detail.get("automatic_evaluation") or {}
        colour = str(disposition.get("colour") or "unknown")
        rule = disposition.get("rule")

        by_colour[colour] = by_colour.get(colour, 0) + 1
        if isinstance(rule, int):
            by_rule[rule] = by_rule.get(rule, 0) + 1

        rows.append(
            {
                "test_id": entry["id"],
                "test_number": entry["test_number"],
                "project_id": entry.get("project_id"),
                "method_code": entry.get("method_code"),
                "test_purpose": entry.get("test_purpose"),
                "authority_level": entry.get("authority_level"),
                # The automatic evaluation and the final disposition, side by
                # side and never merged. See the docstring.
                "calculated_result": automatic.get("calculated_result"),
                "disposition": {
                    "colour": colour,
                    "label": disposition.get("label"),
                    "reason": disposition.get("reason"),
                    "next_action": disposition.get("next_action"),
                    "rule": rule,
                },
            }
        )

    return {
        "organization_id": str(organization_id),
        "project_id": str(project_id) if project_id else None,
        "counted": len(rows),
        # Stated rather than implied: a reader must be able to tell a complete
        # report from a truncated one without counting the rows themselves.
        "truncated": len(queue) >= capped,
        "limit": capped,
        "by_colour": by_colour,
        # Which of §10's fourteen rules fired, and how often. A traffic light
        # nobody can explain is a traffic light nobody trusts, and at the
        # portfolio level "eleven tests are YELLOW" is far less useful than
        # "eleven are YELLOW, nine of them awaiting the same approver".
        "by_rule": {str(k): v for k, v in sorted(by_rule.items())},
        "rows": rows,
    }
