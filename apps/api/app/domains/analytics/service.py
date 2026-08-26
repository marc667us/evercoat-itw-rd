"""Analytics — testing and laboratory activity, counted.

🔴 WHY THIS EXISTS: TWO PERMISSIONS THAT ENFORCED NOTHING.

Measured against `migrations/002_seed_roles_permissions.sql` before a line of
this was written:

    analytics.view       held by 9 of 10 roles   read by NO application code
    analytics.portfolio  held by 2 of 10 roles   read by NO application code

`report.generate` was the third of that set and got its first enforcement
point on 2026-08-25. These two did not. A permission no production path reads
is the same defect as a route with no caller and a table with no writer — it
looks like governance in the catalogue and grants nothing, refuses nothing,
and cannot be audited. *Ask of every permission which production path
enforces it, not only of every role.*

---------------------------------------------------------------------------
THE TWO TIERS ARE THE CATALOGUE'S OWN WORDS, NOT AN INVENTION
---------------------------------------------------------------------------

    ('analytics.view',      'analytics', 'View analytics in scope')
    ('analytics.portfolio', 'analytics', 'View organization-wide portfolio analytics')

So: `analytics.view` answers "how does the work I can see stand", and
`analytics.portfolio` adds the organization-wide breakdown by project. The
split is the reason two permissions exist, and holding both is the Director
and the Executive Viewer — exactly the two roles the seed grants
`analytics.portfolio`, measured, not assumed.

⚠️ THE PORTFOLIO SECTION IS ABSENT, NOT EMPTY, WITHOUT THE PERMISSION.
`by_project` is `None` for a caller without `analytics.portfolio`, and the
response says `portfolio_included: false`. A zero-length list would claim
"there are no projects", which is a different statement and a false one —
this is the *"a dashboard's failure mode is an EMPTY PANEL"* lesson, and the
08-19 incident where a failed read became demonstration data.

---------------------------------------------------------------------------
🔴 IT DOES NOT DERIVE A STATUS. NOT ONCE.
---------------------------------------------------------------------------

§10's traffic light is server-owned and produced by ONE ordered algorithm in
`app/calculations/testing.py`. Every disposition counted here comes from
`app/domains/reporting/service.py::test_results_report`, which reads
`testing.service.get_test`, which is the single caller of `derive_disposition`.

A `CASE` expression in SQL grouping tests by colour would be a second answer
to "is this test GREEN", and the first time the two disagreed nobody could
say which was right. `app/calculations/testing.py` says exactly that. This
module counts what testing concluded; it never concludes.

⚠️ THE COST IS INHERITED AND SO IS THE CAP. `test_results_report` costs one
`get_test` per row and bounds itself at `MAX_ROWS`. Counting over it inherits
both. The response repeats the report's `truncated` flag rather than hiding
it: a total that silently stopped at 200 is a number that means something
other than what it says.
"""

from __future__ import annotations

import uuid
from collections import Counter
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.domains.reporting.service import MAX_ROWS, test_results_report

__all__ = ["MAX_ROWS", "activity_analytics", "portfolio_by_project"]


def activity_analytics(
    session: Session,
    *,
    organization_id: uuid.UUID,
    project_id: uuid.UUID | None = None,
    limit: int = MAX_ROWS,
) -> dict[str, Any]:
    """Testing and laboratory activity in the caller's scope.

    "In scope" is RLS's answer, not a WHERE clause this module invents: the
    session is the caller's own and the policies decide which rows exist. An
    optional `project_id` narrows further, for the drill-down §2 requires.
    """
    report = test_results_report(
        session,
        organization_id=organization_id,
        project_id=project_id,
        limit=limit,
    )

    # 🔴 READ, DO NOT RE-DERIVE. `by_colour` and `by_rule` are the report's,
    # which are testing's, which are `derive_disposition`'s. Recomputing them
    # from `rows` with a different tie-break would be the second answer.
    rows: list[dict[str, Any]] = report["rows"]

    return {
        "scope": "project" if project_id else "organization",
        "project_id": str(project_id) if project_id else None,
        "testing": {
            "counted": report["counted"],
            "truncated": report["truncated"],
            "by_colour": report["by_colour"],
            "by_rule": report["by_rule"],
            # 🔴 COUNTED FROM WHAT THE ROWS ACTUALLY CARRY.
            #
            # The first draft of this counted `review_state` and
            # `validity_status`. `test_results_report` does not return either
            # — its rows are `test_id`, `test_number`, `project_id`,
            # `method_code`, `test_purpose`, `authority_level`,
            # `calculated_result` and `disposition`. Both counts would have
            # come back as `{"unknown": n}`: correct-looking, plausible, and
            # meaningless. `.get()` returning a default is exactly how that
            # kind of wrong number survives review.
            #
            # These three are present on every row.
            #
            # `by_calculated_result` beside `by_colour` is §10's rule that the
            # automatic evaluation and the final disposition are shown
            # SEPARATELY, applied at portfolio scale: "nine passed, four of
            # them not yet final" is the sentence one field cannot say.
            "by_calculated_result": _count(rows, "calculated_result"),
            # §10: a green SCREENING test is never qualification evidence.
            # A GREEN count that did not say at what authority would invite
            # exactly that misreading.
            "by_authority_level": _count(rows, "authority_level"),
            "by_test_purpose": _count(rows, "test_purpose"),
        },
        "laboratory": _laboratory_activity(
            session, organization_id=organization_id, project_id=project_id
        ),
        # Every count above is traceable: the report's rows carry `test_id`
        # and `test_number`, so a figure here drills down to real records
        # rather than being an aggregate nobody can open (§2).
        "rows": rows,
    }


def _count(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    """Count one field of the report's rows.

    ⚠️ `unknown` MEANS "NULL ON THIS ROW", AND IT MUST NEVER MEAN "NO SUCH
    FIELD". `calculated_result` is legitimately NULL until a test has been
    evaluated, and that is a real bucket worth counting — but the same
    default would silently absorb a key this function was called with by
    mistake, which is precisely how the first draft of the caller produced
    two meaningless counts. So a key absent from EVERY row is a programming
    error and raises, while a key present and NULL counts as `unknown`.

    The check is cheap and it is the difference between a number that is
    missing and a number that is wrong.
    """
    if rows and not any(key in r for r in rows):
        raise KeyError(
            f"analytics tried to count {key!r}, which no report row carries — "
            "that would have counted every row as 'unknown' and looked right"
        )
    counts = Counter(str(r.get(key) or "unknown") for r in rows)
    return dict(sorted(counts.items()))


def _laboratory_activity(
    session: Session, *, organization_id: uuid.UUID, project_id: uuid.UUID | None
) -> dict[str, Any]:
    """Lab batches by status.

    ⚠️ `status` HERE IS A STORED COLUMN, NOT A TRAFFIC LIGHT. Batches have a
    lifecycle status (`authorized`, `in_progress`, `completed`, …) and no
    §10 disposition — nothing is being derived, so grouping in SQL is
    legitimate here in a way it never is for a test.

    Parameterised, and `organization_id` is bound rather than interpolated.
    RLS scopes this anyway; the explicit predicate is the second of the two
    independent barriers, not a substitute for either.
    """
    # 🔴 THE CAST IS REQUIRED, NOT COSMETIC — AND THE SUITE CAUGHT ME.
    #
    # An untyped NULL bind appearing only in `:project IS NULL` gives the
    # planner no context to infer a type from, and PostgreSQL refuses the
    # WHOLE statement with "could not determine data type of parameter $2".
    # It fails only on the UNFILTERED call, which is exactly the call a
    # browser makes by default — so a test that always passes a project id
    # would never see it, and the screen would 500 for every signed-in user.
    #
    # That is not hypothetical: on 2026-08-22 this same omission returned 500
    # from `/api/materials`, `/api/formulations` and `/api/suppliers` — three
    # of the five wired screens — under a green suite.
    # `tests/test_no_untyped_null_binds.py` exists because of it, it read this
    # query, and it failed. *A fix applied to one instance of a pattern is not
    # a fix to the pattern* — instrumenting the rule is what made it catch the
    # eleventh instance on the day it was written.
    sql = """
        SELECT status, COUNT(*) AS n
        FROM laboratory.batches
        WHERE organization_id = :org
          AND (CAST(:project AS UUID) IS NULL OR project_id = CAST(:project AS UUID))
        GROUP BY status
        ORDER BY status
    """
    rows = session.execute(text(sql), {"org": organization_id, "project": project_id}).mappings()
    by_status = {r["status"]: int(r["n"]) for r in rows}
    return {"total": sum(by_status.values()), "by_status": by_status}


def portfolio_by_project(
    session: Session, *, organization_id: uuid.UUID, limit: int = MAX_ROWS
) -> list[dict[str, Any]]:
    """Organization-wide activity, broken down by project.

    🔴 THIS IS THE `analytics.portfolio` HALF AND THE CONDUCTOR GATES IT
    SEPARATELY. It deliberately ignores any project filter: a portfolio view
    scoped to one project is not a portfolio view, and offering the parameter
    would invite a caller to believe they had narrowed something.

    ⚠️ IT IS STILL RLS-SCOPED. "Organization-wide" means every project this
    session can see, which is what the policies decide — never a privileged
    read. A caller holding `analytics.portfolio` in an organization they are
    not a member of sees nothing, and that is correct.
    """
    projects = session.execute(
        text(
            """
            SELECT id, project_code, name, current_stage, status
            FROM projects.projects
            WHERE organization_id = :org
            ORDER BY project_code
            """
        ),
        {"org": organization_id},
    ).mappings()

    out: list[dict[str, Any]] = []
    for p in projects:
        # One report per project, and that is the O(n) cost this inherits
        # from reading the derivation instead of copying it. `limit` bounds
        # each, and `truncated` is carried out rather than swallowed.
        report = test_results_report(
            session, organization_id=organization_id, project_id=p["id"], limit=limit
        )
        out.append(
            {
                "project_id": str(p["id"]),
                "project_code": p["project_code"],
                "name": p["name"],
                "current_stage": p["current_stage"],
                "status": p["status"],
                "tests": report["counted"],
                "truncated": report["truncated"],
                "by_colour": report["by_colour"],
            }
        )
    return out
