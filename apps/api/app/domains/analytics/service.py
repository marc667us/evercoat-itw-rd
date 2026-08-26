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

---------------------------------------------------------------------------
⚠️ THE PLAN SAYS MATERIALIZED VIEWS. THIS IS DELIBERATELY NOT THAT — YET.
---------------------------------------------------------------------------

`IMPLEMENTATION_PLAN.md` §F20 specifies the analytics surface as views and
materialized views under an `analytics.*` schema, and states the hazard in the
same breath: *"Materialized views do not inherit source-table RLS"* — so each
would have to materialize `organization_id` and the resource-scope dimensions,
carry its own policy, refresh under `evercoat_worker`, and have an explicit
cross-tenant aggregate test.

That is a performance design and it is the right end state at volume. It is
also a design in which a single omitted policy publishes one tenant's
aggregates to another, permanently, in a table nothing else guards. This
module computes live on the CALLER'S OWN RLS-SCOPED SESSION instead, so there
is no second copy of the data to secure and no refresh job to get wrong.

The trade is real and it is cost, not safety: see the note below. When the
corpus justifies materialization, the §F20 checklist is the specification —
and the cross-tenant aggregate test it names is not optional.

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

__all__ = ["MAX_PROJECTS", "MAX_ROWS", "activity_analytics", "portfolio_by_project"]

# 🔴 THE PORTFOLIO IS BOUNDED IN *BOTH* DIMENSIONS. Raised by the Supervisor.
#
# `portfolio_by_project` runs one `test_results_report` per project, and each
# of those runs one `get_test` per test up to `MAX_ROWS`. Nothing bounded the
# number of projects, so an organization with N of them cost up to N x 201
# queries in ONE request, on top of the ~201 `activity_analytics` had already
# issued. A Director opening `/analytics` on a twenty-project organization
# would have held a database connection for minutes and then timed out.
#
# The per-row cap was visible and the per-project one was not, which is the
# more dangerous shape: the docstring acknowledged an O(n) cost and no number
# anywhere said what n could reach.
#
# ⚠️ AND THE CAP IS REPORTED, NOT SILENT. `portfolio_truncated` says when
# projects were left out. *No silent caps* -- a truncated portfolio that did
# not say so would read as "this organization has 25 projects" when it has
# more, which is the same class of untruth as an invented figure.
MAX_PROJECTS = 25


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
    #
    # 🔴 AND THE ROWS ARE COUNTED HERE, NEVER RETURNED. Raised by the
    # Supervisor, and it was a real authorization bypass — introduced by me in
    # the change whose whole subject is authorization bypasses.
    #
    # The first version returned `report["rows"]` verbatim "for drill-down".
    # Those rows ARE the payload of `GET /api/analysis/reports/test-results`,
    # which the conductor gates on `report.generate`. This route gates on
    # `analytics.view`. Measured against the seed, FOUR roles hold
    # `analytics.view` WITHOUT `report.generate`:
    #
    #     procurement_specialist  production_engineer
    #     executive_viewer        administrator
    #
    # So each of them was refused at the report route with a 403 and then
    # handed every `test_id`, `test_number` and disposition through this one.
    # `test_the_report_needs_report_generate_not_merely_view` pins that gate,
    # and I built a second door past it in the same commit — *two boundaries
    # answering the same question differently*, again.
    #
    # ⚠️ AND NOTHING CONSUMED THEM. `apps/web/app/analytics/page.tsx` never
    # read `rows`; it renders counts. A leak with no caller is still a leak,
    # and the absence of a consumer is what made it invisible in review.
    #
    # Counts stay: an aggregate is a different disclosure from a per-record
    # identifier, and every dashboard in this product already shows one.
    # Drill-down to source records is the REPORT's job, behind the REPORT's
    # permission — which is the distinction the two permissions exist for.
    rows: list[dict[str, Any]] = report["rows"]

    return {
        "scope": "project" if project_id else "organization",
        "project_id": str(project_id) if project_id else None,
        "testing": {
            "counted": report["counted"],
            "truncated": report["truncated"],
            # 🔴 THE CAP THE SERVER ACTUALLY APPLIED, NOT THE ONE ASKED FOR.
            #
            # This was omitted and the screen hardcoded "200" beside its
            # truncation warning. That happened to match the frontend's own
            # default request, so it looked right — and `?limit=10` would have
            # returned `truncated: true` under a notice claiming a cap of 200.
            # An invented number wearing a server's authority is worse than no
            # number, and this module's own docstring says a total that
            # silently stopped means something other than what it says.
            # Raised by Codex. `report["limit"]` is post-clamp, so it is the
            # cap that was enforced rather than the one requested.
            "limit": report["limit"],
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
    # 🔴 `is None`, NOT `or`. Raised by the Supervisor.
    #
    # `str(r.get(key) or "unknown")` maps `""`, `0` and `False` into the
    # `unknown` bucket alongside NULL — so an empty-string `authority_level`
    # would have been counted as "not derived", which is a different fact.
    # The docstring above stated the contract as "NULL on this row" and the
    # code did not implement it: a comment asserting a rule the code lacks,
    # in the function written to prevent a meaningless count.
    counts = Counter("unknown" if (value := r.get(key)) is None else str(value) for r in rows)
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
    session: Session,
    *,
    organization_id: uuid.UUID,
    limit: int = MAX_ROWS,
    max_projects: int = MAX_PROJECTS,
) -> tuple[list[dict[str, Any]], bool]:
    """Organization-wide activity by project, and whether projects were cut.

    Returns `(rows, truncated)`. The flag is returned rather than inferred
    from `len(rows) == max_projects`, which would be wrong for an organization
    holding exactly the cap.

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
            LIMIT :lim
            """
        ),
        # One more than the cap, so "were there more?" is answered by the
        # query rather than guessed from the row count.
        {"org": organization_id, "lim": max_projects + 1},
    ).mappings()

    rows = list(projects)
    truncated = len(rows) > max_projects
    out: list[dict[str, Any]] = []
    for p in rows[:max_projects]:
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
                "limit": report["limit"],
                "by_colour": report["by_colour"],
            }
        )
    return out, truncated
