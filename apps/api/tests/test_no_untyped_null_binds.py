"""An optional SQL filter must CAST its bind, or the unfiltered call 500s.

🔴 THIS DEFECT WAS DIAGNOSED, DOCUMENTED, AND FIXED IN ONE PLACE OUT OF TEN.

`app/domains/opportunities/service.py` carries this comment, written before
today:

    CAST is required, not cosmetic. An untyped NULL bind appearing only in
    `:status IS NULL` gives the planner no context to infer a type from, and
    PostgreSQL refuses the whole statement with "could not determine data type
    of parameter $2" -- but only on the unfiltered call, so a test that always
    passed a status would never see it.

Every word of that is correct. It was applied to one query. Nine other list
endpoints kept the uncast form, and on 2026-08-22 -- the first time the
application was driven through a browser against a real database --
`/api/materials`, `/api/formulations` and `/api/suppliers` returned **500 to
every signed-in user**. Three of the five wired screens.

The suite was green throughout, for exactly the reason the comment gives: the
tests pass a filter value, and the failure only occurs when the filter is
absent, which is what a browser does by default.

**A fix applied to one instance of a pattern is not a fix to the pattern.**
That is the second time today the same shape has appeared -- migration 024 left
a tripwire on one function while the same hazard sat on another -- so this time
the rule is instrumented instead of restated.

WHY A SOURCE CHECK RATHER THAN A REQUEST TEST
---------------------------------------------
A request test would need every list endpoint called with no filters, and
would only ever cover the endpoints somebody remembered. This reads the SQL,
so an endpoint added next month is covered on arrival.
"""

from __future__ import annotations

import re
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]

# `:name IS NULL` where the bind is NOT wrapped in a CAST. The negative
# lookbehind is what distinguishes `:status IS NULL` from
# `CAST(:status AS TEXT) IS NULL`.
UNCAST_BIND_IS_NULL = re.compile(r"(?<!AS TEXT\)\s)(?<!AS UUID\)\s)(?<![\w)])(:\w+)\s+IS\s+NULL")

# A comment explaining the rule is not a violation of it.
COMMENT = re.compile(r"^\s*(#|--)")


def _sql_lines(path: Path) -> list[tuple[int, str]]:
    """Every line of the file, minus comments.

    Crude on purpose: the check is a grep with a good error message, and a SQL
    parser here would be a second thing to maintain and get wrong.
    """
    out: list[tuple[int, str]] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if COMMENT.match(line):
            continue
        out.append((number, line))
    return out


def test_every_optional_filter_casts_its_bind() -> None:
    """🔴 The tenth instance must not become an eleventh.

    Proved by falsification: reverting any one site to `(:status IS NULL OR
    m.status = :status)` fails this test naming that file and line.
    """
    offenders: list[str] = []
    for path in sorted((API_ROOT / "app").rglob("*.py")):
        for number, line in _sql_lines(path):
            match = UNCAST_BIND_IS_NULL.search(line)
            if match:
                offenders.append(f"{path.relative_to(API_ROOT)}:{number}  {match.group(1)} IS NULL")

    assert not offenders, (
        "these SQL binds are compared to NULL without a CAST. PostgreSQL "
        "cannot infer the type of a bind that appears only in `:x IS NULL`, "
        "and refuses the whole statement with 'could not determine data type "
        "of parameter $n' -- but ONLY when the filter is omitted, which is "
        "what a browser does by default and what a test passing a filter "
        "value never does. Write `CAST(:x AS TEXT) IS NULL`.\n  " + "\n  ".join(offenders)
    )


def test_the_rule_is_documented_where_it_was_first_found() -> None:
    """The comment that got it right stays put.

    It is the clearest statement of the failure mode in the codebase, and it
    is load-bearing: the next person to meet `could not determine data type of
    parameter $2` finds the explanation next to a working example.
    """
    source = (API_ROOT / "app/domains/opportunities/service.py").read_text(encoding="utf-8")
    assert "could not determine data type" in source, (
        "the explanation of the untyped-NULL-bind failure has been removed "
        "from opportunities/service.py. It is the only place the failure mode "
        "is written down next to a correct example."
    )
