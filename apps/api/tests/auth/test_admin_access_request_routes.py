"""L1 — the access-request queue, over real HTTP.

🔴 THE TABLE HAD A WRITER AND NO READER, AND THAT IS WHAT THESE TESTS EXIST FOR.

`POST /api/public/access-requests` has written `public_intel.access_requests`
since migration 059. Until 2026-09-01 nothing in `apps/api/app` or `apps/web`
ever read it back. So the landing page told every visitor *"your request has
been queued for review"* and there was no path, anywhere in the product, by
which anyone could review it.

`MEMORY.md` states the rule: *"a route with no caller, a permission with no
enforcement point and a table with no writer are one defect."* A table with no
READER is the same defect from the other side, and the more misleading one,
because the writer succeeds and the visitor is thanked.

⚠️ THESE ARE ROUTE TESTS, NOT SERVICE TESTS, AND THAT IS THE POINT.
`test_admin_member_routes.py`'s own docstring records why: a classifier tested
in isolation says nothing about whether the exception ever reaches it. The same
applies here to the permission gate, the `FOR UPDATE` lock, the 422s and the
address the bind actually uses -- none of which a service-level test could see.

🔴 EVERY GUARD BELOW IS FALSIFIABLE, AND THE ONES THAT MATTER SAY HOW.
A guard that cannot fail is not a guard -- this project has counted six.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from tests.auth.conftest import ORG_HEADER

pytestmark = [pytest.mark.db]


@pytest.fixture
def client() -> TestClient:
    from app.main import app

    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def queued_request(owner_session, admin_org) -> Iterator[dict[str, object]]:
    """One `new` access request, exactly as the public route writes them.

    🔴 IT COMMITS, BECAUSE THE ROUTE RUNS ON ITS OWN CONNECTION and cannot see
    an uncommitted transaction -- and it therefore TEARS DOWN EXPLICITLY. A
    committing fixture without teardown leaks permanently, which on 2026-08-28
    made CI's seed-idempotency gate fail while naming a file two directories
    away from the defect.

    ⚠️ Teardown also removes anything an APPROVAL created. `admin_org` deletes
    every membership in its organization, but only the `core.users` rows whose
    subject matches its own prefix -- a subject bound by these tests carries a
    different one and would otherwise leak a user row per run.
    """
    sfx = uuid.uuid4().hex[:8]
    email = f"l1-applicant-{sfx}@l1probe.org"
    request_id = owner_session.execute(
        text(
            """
            INSERT INTO public_intel.access_requests
                (full_name, work_email, company, reason)
            VALUES (:n, :e, :c, :r)
            RETURNING id
            """
        ),
        {
            "n": "Dana Applicant",
            "e": email,
            "c": "Applicant Coatings Ltd",
            "r": "Evaluating the platform for a filler development programme.",
        },
    ).scalar_one()
    owner_session.commit()

    try:
        yield {"id": request_id, "email": email, "suffix": sfx}
    finally:
        owner_session.rollback()
        owner_session.execute(
            text(
                """
                DELETE FROM core.member_roles WHERE member_id IN (
                    SELECT m.id FROM core.organization_members m
                    JOIN core.users u ON u.id = m.user_id
                    WHERE u.keycloak_sub LIKE :p
                )
                """
            ),
            {"p": f"l1-bound-{sfx}%"},
        )
        owner_session.execute(
            text(
                """
                DELETE FROM core.organization_members WHERE user_id IN (
                    SELECT id FROM core.users WHERE keycloak_sub LIKE :p
                )
                """
            ),
            {"p": f"l1-bound-{sfx}%"},
        )
        owner_session.execute(
            text("DELETE FROM core.users WHERE keycloak_sub LIKE :p"),
            {"p": f"l1-bound-{sfx}%"},
        )
        owner_session.execute(
            text("DELETE FROM public_intel.access_requests WHERE id = :i"),
            {"i": request_id},
        )
        owner_session.commit()


def _headers(make_token, sub: str, org_id: object) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token(sub=sub)}", ORG_HEADER: str(org_id)}


def _status_of(owner_session, request_id: object) -> tuple[str, object]:
    owner_session.rollback()
    return owner_session.execute(
        text("SELECT status, decided_by FROM public_intel.access_requests WHERE id = :i"),
        {"i": request_id},
    ).one()


# ---------------------------------------------------------------------------
# The reader
# ---------------------------------------------------------------------------


def test_an_administrator_can_read_the_queue(client, make_token, admin_org, queued_request) -> None:
    """The reader the table never had.

    Falsified by pointing `list_access_requests` at the wrong status: the row
    is `new`, so a filter that asks for anything else returns it absent and
    this fails.
    """
    r = client.get(
        "/api/admin/access-requests",
        headers=_headers(make_token, str(admin_org["admin_sub"]), admin_org["org_id"]),
    )
    assert r.status_code == 200, f"{r.status_code}: {r.text}"
    rows = r.json()
    mine = [row for row in rows if row["id"] == str(queued_request["id"])]
    assert mine, "the queued request is not in the default queue"
    assert mine[0]["work_email"] == queued_request["email"]
    assert mine[0]["status"] == "new"
    assert mine[0]["decided_at"] is None


def test_a_member_without_admin_users_cannot_read_the_queue(
    client, make_token, admin_org, queued_request
) -> None:
    """These rows are people's names and work addresses. `admin.users` or nothing."""
    r = client.get(
        "/api/admin/access-requests",
        headers=_headers(make_token, str(admin_org["plain_sub"]), admin_org["org_id"]),
    )
    assert r.status_code == 403, f"{r.status_code}: {r.text}"


def test_an_anonymous_caller_cannot_read_the_queue(client, admin_org) -> None:
    r = client.get("/api/admin/access-requests")
    assert r.status_code in (401, 403), f"{r.status_code}: {r.text}"


# ---------------------------------------------------------------------------
# The decision
# ---------------------------------------------------------------------------


def test_approving_without_a_keycloak_subject_is_422_and_changes_nothing(
    client, make_token, owner_session, admin_org, queued_request
) -> None:
    """🔴 THE REFUSAL IS ASSERTED, AND SO IS THE ABSENCE OF A SIDE EFFECT.

    A 422 over a row that has already moved to `approved` would be the worst
    possible outcome: the caller is told it failed and the queue says it
    succeeded. The status is re-read from the database, not inferred from the
    response.
    """
    r = client.post(
        f"/api/admin/access-requests/{queued_request['id']}/decision",
        json={"decision": "approved", "reason": "looks legitimate", "roles": ["executive_viewer"]},
        headers=_headers(make_token, str(admin_org["admin_sub"]), admin_org["org_id"]),
    )
    assert r.status_code == 422, f"{r.status_code}: {r.text}"
    assert "keycloak_sub" in r.text
    status_now, decided_by = _status_of(owner_session, queued_request["id"])
    assert status_now == "new"
    assert decided_by is None


def test_approving_with_no_role_is_422_and_changes_nothing(
    client, make_token, owner_session, admin_org, queued_request
) -> None:
    """A membership with no role holds no permission.

    Approving into one produces an account that signs in and reaches nothing --
    a "yes" that behaves like a "no", and the hardest kind of failure to
    notice. Refused rather than created.
    """
    r = client.post(
        f"/api/admin/access-requests/{queued_request['id']}/decision",
        json={
            "decision": "approved",
            "reason": "looks legitimate",
            "keycloak_sub": f"l1-bound-{queued_request['suffix']}-a",
            "roles": [],
        },
        headers=_headers(make_token, str(admin_org["admin_sub"]), admin_org["org_id"]),
    )
    assert r.status_code == 422, f"{r.status_code}: {r.text}"
    status_now, _ = _status_of(owner_session, queued_request["id"])
    assert status_now == "new"


def test_approving_with_an_unknown_role_is_422_and_changes_nothing(
    client, make_token, owner_session, admin_org, queued_request
) -> None:
    r = client.post(
        f"/api/admin/access-requests/{queued_request['id']}/decision",
        json={
            "decision": "approved",
            "reason": "looks legitimate",
            "keycloak_sub": f"l1-bound-{queued_request['suffix']}-b",
            "roles": ["chief_wizard"],
        },
        headers=_headers(make_token, str(admin_org["admin_sub"]), admin_org["org_id"]),
    )
    assert r.status_code == 422, f"{r.status_code}: {r.text}"
    status_now, _ = _status_of(owner_session, queued_request["id"])
    assert status_now == "new"


def test_approving_binds_the_submitted_address_and_moves_the_request(
    client, make_token, owner_session, admin_org, queued_request
) -> None:
    """🔴 THE WHOLE POINT: an approval produces a REAL MEMBERSHIP.

    Three separate assertions, because a decision that reported success while
    creating nothing is exactly the "three success messages over failed
    operations" failure recorded on 2026-08-31:

      1. the response names a membership,
      2. that membership exists in the database and carries the role,
      3. and the queue row moved, attributed to the administrator who did it.

    ⚠️ AND THE ADDRESS IS THE ONE THAT WAS SUBMITTED. The payload deliberately
    carries no address; if the route ever started taking one from the caller,
    an approval could be redirected to a different person than the one that was
    reviewed, and the audit record would describe a decision nobody took.
    Falsified by binding a different address in the route: this assertion goes
    red while every other one still passes.
    """
    sub = f"l1-bound-{queued_request['suffix']}-c"
    r = client.post(
        f"/api/admin/access-requests/{queued_request['id']}/decision",
        json={
            "decision": "approved",
            "reason": "verified by phone with the applicant",
            "keycloak_sub": sub,
            "roles": ["executive_viewer"],
        },
        headers=_headers(make_token, str(admin_org["admin_sub"]), admin_org["org_id"]),
    )
    assert r.status_code == 200, f"{r.status_code}: {r.text}"
    body = r.json()
    assert body["status"] == "approved"
    assert body["member_id"], "an approval reported success without a membership"

    owner_session.rollback()
    stored_email, stored_org, role_count = owner_session.execute(
        text(
            """
            SELECT m.email::text, m.organization_id, count(mr.role_id)
              FROM core.organization_members m
              JOIN core.users u ON u.id = m.user_id
              LEFT JOIN core.member_roles mr ON mr.member_id = m.id
             WHERE u.keycloak_sub = :s
             GROUP BY m.email, m.organization_id
            """
        ),
        {"s": sub},
    ).one()
    assert stored_email == queued_request["email"], (
        "the bind used an address other than the one submitted and reviewed"
    )
    assert str(stored_org) == str(admin_org["org_id"])
    assert role_count == 1

    status_now, decided_by = _status_of(owner_session, queued_request["id"])
    assert status_now == "approved"
    assert str(decided_by) == str(admin_org["admin_id"])


def test_rejecting_moves_the_request_and_creates_no_membership(
    client, make_token, owner_session, admin_org, queued_request
) -> None:
    """A rejection must not be a quiet approval.

    Asserted as an ABSENCE -- no membership carrying the applicant's address --
    because a forward check that only reads the status cannot see one.
    """
    before = owner_session.execute(
        text("SELECT count(*) FROM core.organization_members WHERE organization_id = :o"),
        {"o": admin_org["org_id"]},
    ).scalar_one()

    r = client.post(
        f"/api/admin/access-requests/{queued_request['id']}/decision",
        json={"decision": "rejected", "reason": "not a business address"},
        headers=_headers(make_token, str(admin_org["admin_sub"]), admin_org["org_id"]),
    )
    assert r.status_code == 200, f"{r.status_code}: {r.text}"
    assert r.json()["member_id"] is None

    owner_session.rollback()
    after = owner_session.execute(
        text("SELECT count(*) FROM core.organization_members WHERE organization_id = :o"),
        {"o": admin_org["org_id"]},
    ).scalar_one()
    assert after == before, "a rejection created a membership"

    status_now, decided_by = _status_of(owner_session, queued_request["id"])
    assert status_now == "rejected"
    assert str(decided_by) == str(admin_org["admin_id"])


def test_deciding_twice_is_a_409(client, make_token, admin_org, queued_request) -> None:
    """The second administrator to press the button gets an answer, not a 500.

    Two people opening the same queue and approving the same row is the
    ordinary case. Without the `FOR UPDATE` re-read both would bind, and the
    loser would hit `organization_members_unique` and surface as a 500 -- a
    contention failure wearing the clothes of a server fault.
    """
    headers = _headers(make_token, str(admin_org["admin_sub"]), admin_org["org_id"])
    first = client.post(
        f"/api/admin/access-requests/{queued_request['id']}/decision",
        json={"decision": "rejected", "reason": "duplicate of an earlier request"},
        headers=headers,
    )
    assert first.status_code == 200, f"{first.status_code}: {first.text}"

    second = client.post(
        f"/api/admin/access-requests/{queued_request['id']}/decision",
        json={
            "decision": "approved",
            "reason": "changed my mind",
            "keycloak_sub": "x",
            "roles": ["executive_viewer"],
        },
        headers=headers,
    )
    assert second.status_code == 409, f"{second.status_code}: {second.text}"
    assert "already rejected" in second.text


def test_a_decided_request_leaves_the_default_queue(
    client, make_token, admin_org, queued_request
) -> None:
    """The filter is real, not decoration.

    Falsified by making `list_access_requests` ignore its parameter: the row
    would then appear in `new` after being rejected and this fails.
    """
    headers = _headers(make_token, str(admin_org["admin_sub"]), admin_org["org_id"])
    client.post(
        f"/api/admin/access-requests/{queued_request['id']}/decision",
        json={"decision": "rejected", "reason": "out of scope for this deployment"},
        headers=headers,
    )

    new_queue = client.get("/api/admin/access-requests", headers=headers).json()
    assert not [row for row in new_queue if row["id"] == str(queued_request["id"])], (
        "a decided request is still in the undecided queue"
    )

    rejected = client.get("/api/admin/access-requests?status=rejected", headers=headers).json()
    assert [row for row in rejected if row["id"] == str(queued_request["id"])]

    everything = client.get("/api/admin/access-requests?status=all", headers=headers).json()
    assert [row for row in everything if row["id"] == str(queued_request["id"])]


def test_a_member_without_admin_users_cannot_decide(
    client, make_token, owner_session, admin_org, queued_request
) -> None:
    r = client.post(
        f"/api/admin/access-requests/{queued_request['id']}/decision",
        json={"decision": "rejected", "reason": "attempting without the permission"},
        headers=_headers(make_token, str(admin_org["plain_sub"]), admin_org["org_id"]),
    )
    assert r.status_code == 403, f"{r.status_code}: {r.text}"
    status_now, _ = _status_of(owner_session, queued_request["id"])
    assert status_now == "new"


def test_an_unknown_request_is_404(client, make_token, admin_org) -> None:
    r = client.post(
        f"/api/admin/access-requests/{uuid.uuid4()}/decision",
        json={"decision": "rejected", "reason": "nothing there"},
        headers=_headers(make_token, str(admin_org["admin_sub"]), admin_org["org_id"]),
    )
    assert r.status_code == 404, f"{r.status_code}: {r.text}"
