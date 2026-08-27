"""`has_root_cause` answers the question its name asks.

🔴 FOUND 2026-08-27 WHILE WRITING THE FIRST BROWSER CLIENT FOR THIS MODULE.

`list_failures` selected

    (SELECT count(*) FROM quality.failure_hypotheses h
      WHERE h.failure_id = f.id AND h.status = 'accepted') AS has_root_cause

— a column whose NAME asks a yes/no question and whose VALUE was a number.

It had survived because it had no consumer. Slice 6's backend shipped without a
browser, so nothing had ever validated the payload; every reader of a `has_*`
field would have used it in a truthiness test and been right by accident, since
0 is falsy and 2 is truthy in both Python and JavaScript. The first client that
declared a TYPE for it — `z.boolean()`, written from the name, as anybody
would — would have rejected every response the endpoint produced.

*Ask what a returned value ANSWERS, not what the column is CALLED.* This
platform has the lesson recorded from I82, where removing a flag did not remove
the bit because it had moved into `user_id`. Same shape, opposite direction: the
name promised a boolean the query never produced.

🔴 WHY THE SERVICE WAS CHANGED RATHER THAN THE CLIENT.

Modelling it as `z.number()` would have been the smaller edit and the wrong one.
It leaves a field called `has_root_cause` returning 2, so the NEXT consumer —
a report, a dashboard tile, an agent tool — meets the same trap, and the trap is
one that fails silently in the direction that looks correct. The column now says
`> 0`, and this test is what stops it going back.

⚠️ ASSERTED IN BOTH DIRECTIONS, AND ON THE TYPE — WHICH IS THE ONLY THING
THAT DISTINGUISHES THE TWO.

🔴 AND ONE ARGUMENT IN THE FIRST DRAFT OF THIS FILE WAS WRONG. It said a count
could come back as 2 and that this file would catch it. It cannot:
`failure_hypotheses_one_accepted_idx` is a partial unique index on
`(failure_id) WHERE status = 'accepted'`, so a failure has **at most one**
accepted hypothesis and the count could only ever be 0 or 1. The test written
to prove otherwise failed against the database, which is how the claim was
found — and the claim is corrected here rather than the wording softened.

So the defect was never about MAGNITUDE. It was about TYPE: `count(*)` returns
an integer, a consumer that validates its payload declares `boolean` from the
name, and `0`/`1` are not `true`/`false` in zod or in `is` comparisons. Every
loose reader was right by accident; every strict one was refused. That is
enough to fix, and the assertions below use `is False` / `is True` — identity,
which `0` and `1` fail — rather than equality, which they pass.
"""

from __future__ import annotations

import datetime as dt
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domains.failures.service import list_failures


@pytest.fixture
def investigation(owner_session: Session) -> dict[str, uuid.UUID]:
    """One organization, one project, one open failure, two hypotheses.

    Built with raw INSERTs rather than through the service, because the point
    here is the SHAPE of a read and not the behaviour of a write — and going
    through `open_investigation` would tie this test to a workflow that has its
    own tests and its own reasons to change.
    """
    org = uuid.uuid4()
    project = uuid.uuid4()
    failure = uuid.uuid4()
    # `quality.failures.opened_by` is NOT NULL -- an investigation is always
    # opened BY somebody, which is the right constraint and the reason this
    # fixture has to mint an identity rather than leave the column out.
    person = uuid.uuid4()

    owner_session.execute(
        text(
            "INSERT INTO core.organizations (id, name, code) "
            "VALUES (:id, 'Root Cause Fixture', :code)"
        ),
        {"id": org, "code": f"RCF{str(org)[:6]}"},
    )
    owner_session.execute(
        text(
            "INSERT INTO projects.projects "
            "  (id, organization_id, project_code, name, current_stage) "
            "VALUES (:id, :org, :code, 'Fixture project', 'concept')"
        ),
        {"id": project, "org": org, "code": f"RCP-{str(project)[:8]}"},
    )
    owner_session.execute(
        text(
            "INSERT INTO core.users (id, keycloak_sub, email, display_name) "
            "VALUES (:id, :sub, :email, 'Root Cause Fixture Person')"
        ),
        {
            "id": person,
            "sub": f"rcf-{person}",
            "email": f"rcf-{person}@fixture.invalid",
        },
    )
    owner_session.execute(
        text(
            # 🔴 `email` AND `display_name` LIVE ON THE MEMBERSHIP, NOT ON THE
            # IDENTITY. Migration 052 (I106/ADR-031) moved a tenant's view of a
            # member here and made the GLOBAL `core.users.email` unreadable by
            # the runtime roles. Both columns are NOT NULL, which is why a
            # fixture cannot get away with naming only the ids.
            "INSERT INTO core.organization_members "
            "  (organization_id, user_id, status, email, display_name) "
            "VALUES (:org, :uid, 'active', :email, 'Root Cause Fixture Person')"
        ),
        {"org": org, "uid": person, "email": f"rcf-{person}@fixture.invalid"},
    )
    owner_session.execute(
        text(
            "INSERT INTO quality.failures "
            "  (id, organization_id, project_id, failure_code, title, severity, status, opened_by) "
            "VALUES (:id, :org, :pid, :code, 'Adhesion loss on cure', 'major', 'open', :who)"
        ),
        {
            "id": failure,
            "org": org,
            "pid": project,
            "code": f"FL-{str(failure)[:8]}",
            "who": person,
        },
    )
    owner_session.flush()
    return {"org": org, "project": project, "failure": failure, "person": person}


def _add_hypothesis(session: Session, ids: dict[str, uuid.UUID], status: str) -> uuid.UUID:
    """Insert one hypothesis in the given state.

    🔴 AN `accepted` HYPOTHESIS MUST NAME A HUMAN, AND THE DATABASE SAYS SO.
    `failure_hypotheses_accepted_names_a_human` refuses a row whose status is
    `accepted` while `accepted_by` is NULL — §7's *"only a human moves anything
    to accepted"* enforced as a CHECK rather than left to the service. Writing
    this fixture is how one meets it: there is no way to fabricate an accepted
    root cause with nobody's name on it, not even from the owner role.
    """
    hypothesis = uuid.uuid4()
    accepted = status == "accepted"
    session.execute(
        text(
            # `project_id` is NOT NULL and carried on the hypothesis as well as
            # on the failure -- §5's tenant-scoped composite keys, so a
            # hypothesis cannot drift onto another tenant's project.
            "INSERT INTO quality.failure_hypotheses "
            "  (id, organization_id, project_id, failure_id, possible_cause, "
            "   confidence, origin, status, proposed_by, accepted_by, accepted_at) "
            "VALUES (:id, :org, :pid, :fid, 'Filler surface treatment', "
            "        'medium', 'human', :status, :who, :accepted_by, :accepted_at)"
        ),
        {
            "id": hypothesis,
            "org": ids["org"],
            "pid": ids["project"],
            "fid": ids["failure"],
            "status": status,
            # NOT NULL, and rightly so: §7 turns on a hypothesis carrying who
            # proposed it, which is what makes `origin = 'msd'` mean something.
            "who": ids["person"],
            "accepted_by": ids["person"] if accepted else None,
            "accepted_at": dt.datetime.now(dt.UTC) if accepted else None,
        },
    )
    session.flush()
    return hypothesis


def _row(session: Session, ids: dict[str, uuid.UUID]) -> dict[str, object]:
    rows = list_failures(session, organization_id=ids["org"])
    assert len(rows) == 1, (
        "the fixture's own investigation is not visible to list_failures, so "
        "nothing below is measuring the column this test is about"
    )
    return rows[0]


def test_has_root_cause_is_false_with_no_accepted_hypothesis(
    owner_session: Session, investigation: dict[str, uuid.UUID]
) -> None:
    _add_hypothesis(owner_session, investigation, "proposed")
    row = _row(owner_session, investigation)

    # 🔴 `is False`, NOT `== False`. A bare count returns 0, and `0 == False`
    # is True in Python — so an equality assertion here would pass against the
    # exact defect this test exists to catch.
    assert row["has_root_cause"] is False, (
        f"has_root_cause is {row['has_root_cause']!r} ({type(row['has_root_cause']).__name__}); "
        "a column whose name asks a yes/no question must answer one"
    )
    assert row["hypothesis_count"] == 1


def test_has_root_cause_answers_the_question_its_name_asks(
    owner_session: Session, investigation: dict[str, uuid.UUID]
) -> None:
    """The positive half, and the half that catches a count coming back."""
    _add_hypothesis(owner_session, investigation, "accepted")
    row = _row(owner_session, investigation)

    assert row["has_root_cause"] is True, (
        f"has_root_cause is {row['has_root_cause']!r} "
        f"({type(row['has_root_cause']).__name__}) rather than True — it has "
        "gone back to being a count"
    )


def test_the_database_permits_at_most_one_accepted_hypothesis(
    owner_session: Session, investigation: dict[str, uuid.UUID]
) -> None:
    """🔴 THE INVARIANT THAT MADE THE FIRST VERSION OF THIS TEST IMPOSSIBLE.

    This started life as *"a second accepted hypothesis does not make the answer
    two"* — an assertion a bare `count(*)` could not survive, and the reason the
    file claimed the fix was about magnitude. It cannot be written:
    `failure_hypotheses_one_accepted_idx` refuses the second row outright.

    Rather than delete the case, it is inverted into the fact that displaced it.
    That fact is load-bearing in its own right and had no test: it is why
    `get_failure` can say `accepted_root_cause` in the SINGULAR and take
    `next(h for h in hypotheses if h["status"] == "accepted")` without deciding
    between candidates, and it is §7's *"only a human moves anything to
    accepted"* given a second guarantee — that a human moves exactly one.

    ⚠️ It also fixes the type argument in place. With at most one accepted row
    the count is 0 or 1, so `has_root_cause` as a count carried the right
    INFORMATION and the wrong TYPE — which is precisely what a schema catches
    and a truthiness check does not.
    """
    _add_hypothesis(owner_session, investigation, "accepted")

    with pytest.raises(IntegrityError) as caught:
        _add_hypothesis(owner_session, investigation, "accepted")

    assert "failure_hypotheses_one_accepted_idx" in str(caught.value), (
        "a second accepted hypothesis was refused by something OTHER than the "
        f"one-accepted index, so this test is not measuring it: {caught.value}"
    )


def test_has_root_cause_is_still_true_after_the_second_is_refused(
    owner_session: Session, investigation: dict[str, uuid.UUID]
) -> None:
    """And the read still answers correctly once the transaction recovers.

    Separate test, separate transaction: the refusal above ABORTS the one it
    happens in, so any query after it in the same test would fail with
    `InFailedSqlTransaction` rather than tell us anything about the column.
    """
    _add_hypothesis(owner_session, investigation, "accepted")
    row = _row(owner_session, investigation)

    assert row["has_root_cause"] is True
    assert row["hypothesis_count"] == 1
