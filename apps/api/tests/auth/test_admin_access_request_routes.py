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
    # 🔴 THE OWNER IS SUBJECT TO 064'S PREDICATE AND MUST SAY WHICH TENANT IT IS
    # ACTING AS.
    #
    # `access_requests` is FORCE RLS and its tenant policy carries no `TO`
    # clause, so `evercoat_owner` — NOBYPASSRLS since 001 — is governed by
    # `organization_id = core.current_org_id()` exactly like the runtime role.
    # Without this the INSERT below raises *"new row violates row-level security
    # policy"*, which is how this fixture caught the first draft of migration 064
    # locking the owner out of the table entirely.
    #
    # Session-scoped rather than `SET LOCAL`, because this fixture COMMITS and a
    # transaction-scoped setting would be gone by the time teardown runs.
    owner_session.execute(
        text("SELECT set_config('app.current_org', :org, false)"),
        {"org": str(admin_org["org_id"])},
    )
    # 🔴 THE REQUEST HAS AN OWNER (migration 064). Before it, this table had no
    # `organization_id`, so the queue was platform-wide and every tenant's
    # administrator could read every applicant.
    request_id = owner_session.execute(
        text(
            """
            INSERT INTO public_intel.access_requests
                (organization_id, full_name, work_email, company, reason)
            VALUES (:org, :n, :e, :c, :r)
            RETURNING id
            """
        ),
        {
            "org": admin_org["org_id"],
            "n": "Dana Applicant",
            "e": email,
            "c": "Applicant Coatings Ltd",
            "r": "Evaluating the platform for a filler development programme.",
        },
    ).scalar_one()
    owner_session.commit()

    try:
        yield {
            "id": request_id,
            "email": email,
            "suffix": sfx,
            "organization_id": admin_org["org_id"],
        }
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
        # 🔴 NAME THE TENANT, THEN ASSERT THE DELETE ACTUALLY HAPPENED.
        #
        # This row is behind FORCE RLS and the owner is governed by the same
        # predicate as everyone else, so a teardown that has lost the GUC
        # deletes NOTHING and says nothing about it — and the next fixture up
        # then fails on `access_requests_decided_by_fkey` while deleting the
        # user that decided it. That is a confusing error two fixtures away
        # from its cause, and it is what happened.
        #
        # Re-setting it here rather than relying on the value from setup is the
        # same discipline `_status_of` applies: `app.current_org` is a property
        # of a CONNECTION, and a pooled connection is not a durable place to
        # keep one.
        owner_session.execute(
            text("SELECT set_config('app.current_org', :org, false)"),
            {"org": str(admin_org["org_id"])},
        )
        removed = owner_session.execute(
            text("DELETE FROM public_intel.access_requests WHERE id = :i"),
            {"i": request_id},
        ).rowcount
        owner_session.commit()
        assert removed == 1, (
            f"teardown deleted {removed} access requests, not 1 — the row is "
            "still there and the next fixture will fail on its foreign key"
        )


def _headers(make_token, sub: str, org_id: object) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token(sub=sub)}", ORG_HEADER: str(org_id)}


def _status_of(owner_session, request_id: object, org: object) -> tuple[str, object]:
    """Read one request back as the owner, NAMING THE TENANT EVERY TIME.

    🔴 `app.current_org` IS A CONNECTION PROPERTY AND THE POOL HANDS
    CONNECTIONS AROUND.

    An earlier version set the GUC once in the fixture and let every later read
    inherit it. That is exactly the connection-pool tenant-context trap
    `IMPLEMENTATION_PLAN.md` §J names as *"the classic way RLS silently
    fails"*: `pool_reset_on_return="rollback"` does not clear a session-level
    `set_config(..., false)`, tests that repoint it do not always put it back,
    and the failure surfaces as `NoResultFound` in a test that has nothing to
    do with the one that moved it.

    Setting it here makes each read state which tenant it is asking as, which
    is what the production code does at `db.py:514` for the same reason.
    """
    owner_session.rollback()
    owner_session.execute(
        text("SELECT set_config('app.current_org', :org, false)"), {"org": str(org)}
    )
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
    status_now, decided_by = _status_of(owner_session, queued_request["id"], admin_org["org_id"])
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
    status_now, _ = _status_of(owner_session, queued_request["id"], admin_org["org_id"])
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
    status_now, _ = _status_of(owner_session, queued_request["id"], admin_org["org_id"])
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
    # 🔴 THE EXACT ROLE, NOT A COUNT. Raised by Codex: asserting
    # `count(...) == 1` passes if the approval granted `administrator` instead
    # of the role that was asked for, which is the single worst thing this
    # route could get wrong. The code is asserted, and so is the absence of any
    # other role.
    stored_email, stored_org, granted = owner_session.execute(
        text(
            """
            SELECT m.email::text, m.organization_id,
                   coalesce(array_agg(r.code ORDER BY r.code)
                            FILTER (WHERE r.code IS NOT NULL), '{}') AS roles
              FROM core.organization_members m
              JOIN core.users u ON u.id = m.user_id
              LEFT JOIN core.member_roles mr ON mr.member_id = m.id
              LEFT JOIN core.roles r ON r.id = mr.role_id
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
    assert list(granted) == ["executive_viewer"], (
        f"the approval granted {list(granted)!r} rather than the role it was "
        "asked for. A count would have accepted 'administrator' here."
    )

    status_now, decided_by = _status_of(owner_session, queued_request["id"], admin_org["org_id"])
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

    status_now, decided_by = _status_of(owner_session, queued_request["id"], admin_org["org_id"])
    assert status_now == "rejected"
    assert str(decided_by) == str(admin_org["admin_id"])


def test_deciding_twice_is_a_409(client, make_token, admin_org, queued_request) -> None:
    """A decided request refuses a second decision.

    THIS TEST DOES **NOT** PROVE THE `FOR UPDATE` LOCK, AND ITS FIRST DOCSTRING
    CLAIMED IT DID. Raised by Codex.

    The two requests here are strictly sequential: the first transaction has
    committed before the second begins, so the status re-read alone is enough
    and this passes with the lock removed. What it actually proves is that a
    decided row is not decidable again -- worth having, and not the concurrency
    property. `test_the_row_lock_serialises_two_deciders` below is the one that
    needs two connections to observe it.

    A test that names a mechanism it cannot see is how a guard ends up trusted
    for the wrong reason.
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
    status_now, _ = _status_of(owner_session, queued_request["id"], admin_org["org_id"])
    assert status_now == "new"


def test_an_unknown_request_is_404(client, make_token, admin_org) -> None:
    r = client.post(
        f"/api/admin/access-requests/{uuid.uuid4()}/decision",
        json={"decision": "rejected", "reason": "nothing there"},
        headers=_headers(make_token, str(admin_org["admin_sub"]), admin_org["org_id"]),
    )
    assert r.status_code == 404, f"{r.status_code}: {r.text}"


# ---------------------------------------------------------------------------
# The boundary migration 064 added, and the lock the sequential test cannot see
# ---------------------------------------------------------------------------


def test_another_organizations_administrator_cannot_see_the_request(
    client, make_token, owner_session, admin_org, queued_request
) -> None:
    """THE CROSS-TENANT DISCLOSURE CODEX REFUSED, ASSERTED CLOSED.

    Before migration 064 `public_intel.access_requests` had no
    `organization_id`, no RLS and no predicate, so this queue was platform-wide
    and an administrator of any organization could read every applicant's name,
    work address and company. The first version of these routes wrote that down
    as an issue; Codex's reply was that a comment acknowledging a breach is not
    a rule.

    Falsified by removing `AND organization_id = :org` from
    `list_access_requests`: the RLS policy still filters the row, so making
    this go red then needs the policy dropped as well -- which is exactly why
    both exist.
    """
    sfx = uuid.uuid4().hex[:8]
    other_org = owner_session.execute(
        text("INSERT INTO core.organizations (code, name) VALUES (:c, :n) RETURNING id"),
        {"c": f"L1-OTHER-{sfx}", "n": "A different tenant"},
    ).scalar_one()
    other_uid = owner_session.execute(
        text(
            "INSERT INTO core.users (keycloak_sub, email, display_name)"
            " VALUES (:s, :e, 'Other Admin') RETURNING id"
        ),
        {"s": f"l1-other-{sfx}", "e": f"l1-other-{sfx}@l1probe.org"},
    ).scalar_one()
    other_mid = owner_session.execute(
        text(
            "INSERT INTO core.organization_members"
            " (organization_id, user_id, email, display_name)"
            " VALUES (:o, :u, :e, 'Other Admin') RETURNING id"
        ),
        {"o": other_org, "u": other_uid, "e": f"l1-other-{sfx}@l1probe.org"},
    ).scalar_one()
    owner_session.execute(
        text(
            "INSERT INTO core.member_roles (member_id, role_id)"
            " SELECT :m, id FROM core.roles WHERE code = 'administrator'"
        ),
        {"m": other_mid},
    )
    owner_session.commit()

    # 🔴 SWITCH TENANT FOR THE OWNER'S OWN READS, AND SWITCH BACK IN teardown.
    # `_status_of` at the end of this test reads the ORIGINAL request, which
    # belongs to `admin_org`, so leaving the GUC pointed at the other tenant
    # would make that read return nothing and the test fail for a reason that
    # has nothing to do with what it is testing.
    try:
        rows = client.get(
            "/api/admin/access-requests?status=all",
            headers=_headers(make_token, f"l1-other-{sfx}", other_org),
        )
        assert rows.status_code == 200, f"{rows.status_code}: {rows.text}"
        assert not [r for r in rows.json() if r["id"] == str(queued_request["id"])], (
            "an administrator of another organization can read this applicant"
        )

        # And cannot decide it either -- 404, because to them it does not exist.
        decision = client.post(
            f"/api/admin/access-requests/{queued_request['id']}/decision",
            json={"decision": "rejected", "reason": "reaching across a boundary"},
            headers=_headers(make_token, f"l1-other-{sfx}", other_org),
        )
        assert decision.status_code == 404, f"{decision.status_code}: {decision.text}"

        status_now, _ = _status_of(owner_session, queued_request["id"], admin_org["org_id"])
        assert status_now == "new"
    finally:
        owner_session.rollback()
        owner_session.execute(
            text("DELETE FROM core.member_roles WHERE member_id = :m"), {"m": other_mid}
        )
        owner_session.execute(
            text("DELETE FROM core.organization_members WHERE id = :m"), {"m": other_mid}
        )
        owner_session.execute(text("DELETE FROM core.users WHERE id = :u"), {"u": other_uid})
        owner_session.execute(
            text("DELETE FROM core.organizations WHERE id = :o"), {"o": other_org}
        )
        owner_session.commit()


# ---------------------------------------------------------------------------
# 🔴 THE `FOR UPDATE` SERIALISATION HAS NO TEST, AND THAT IS RECORDED RATHER
#    THAN PAPERED OVER. Issue I114.
# ---------------------------------------------------------------------------
#
# `decide_access_request` re-reads the request's status inside a `FOR UPDATE`
# lock so two administrators deciding the same request cannot both proceed.
# Codex raised, correctly, that `test_deciding_twice_is_a_409` cannot prove it:
# the two requests are sequential, so the 409 comes from the committed status
# alone and the test stays green with the lock deleted.
#
# THREE attempts at a real one were written and ALL THREE were green with
# `FOR UPDATE` removed — each verified by deleting it and re-running, which is
# the only reason this is known:
#
#   1. Take a competing `FOR UPDATE NOWAIT` on a second connection. Proves
#      PostgreSQL implements row locks; never calls the route.
#   2. Hold the row, drive the real route, watch `pg_locks` for a waiter
#      blocked by the holder. Green either way — WITHOUT the lock the route
#      still blocks, just later, at the `UPDATE`. It observed "the request
#      blocks somewhere", which is not the property.
#   3. Hold the row, drive TWO real decisions, assert the outcomes are
#      {200, 409} rather than {200, 200}. Still green: Starlette's
#      `TestClient` drives requests through one anyio portal, and giving each
#      thread its own client did not separate them either — the second
#      decision still ran after the first had committed.
#
# What is actually needed is two requests genuinely in flight at once against
# a real server — the `tests/e2e/api` project runs the app under uvicorn and is
# the right home — or a test-only synchronisation point inside the route, which
# is app code added for a test and needs its own decision.
#
# Until then the lock is UNTESTED. It is not "covered by" the sequential test,
# and a fourth guard that cannot fail would be worse than this comment, because
# it would read as coverage. `MEMORY.md`: *a test that has only ever PASSED has
# not been shown to detect anything.*


@pytest.fixture
def binder_only(owner_session, admin_org) -> Iterator[str]:
    """Somebody holding `admin.users` and NOT `admin.roles`.

    🔴 A REAL ROLE, NOT A PATCHED PRINCIPAL. No seeded role has this shape --
    only `administrator` holds either permission and it holds both -- so the
    role is created here and granted exactly one permission. Patching
    `Principal.permissions` would have tested the patch: the whole question is
    whether the REAL chain (token -> principal -> require_permission -> the
    branch check) arrives at the right answer, and a stubbed principal skips
    most of it.
    """
    sfx = uuid.uuid4().hex[:8]
    sub = f"l1-binder-{sfx}"
    role_code = f"l1_binder_only_{sfx}"

    role_id = owner_session.execute(
        text(
            "INSERT INTO core.roles (code, name, description, is_seeded)"
            " VALUES (:c, 'Binder only', 'admin.users without admin.roles', false)"
            " RETURNING id"
        ),
        {"c": role_code},
    ).scalar_one()
    owner_session.execute(
        text(
            "INSERT INTO core.role_permissions (role_id, permission_id)"
            " SELECT :r, id FROM core.permissions WHERE code = 'admin.users'"
        ),
        {"r": role_id},
    )
    uid = owner_session.execute(
        text(
            "INSERT INTO core.users (keycloak_sub, email, display_name)"
            " VALUES (:s, :e, 'Binder Only') RETURNING id"
        ),
        {"s": sub, "e": f"{sub}@l1probe.org"},
    ).scalar_one()
    mid = owner_session.execute(
        text(
            "INSERT INTO core.organization_members"
            " (organization_id, user_id, email, display_name)"
            " VALUES (:o, :u, :e, 'Binder Only') RETURNING id"
        ),
        {"o": admin_org["org_id"], "u": uid, "e": f"{sub}@l1probe.org"},
    ).scalar_one()
    owner_session.execute(
        text("INSERT INTO core.member_roles (member_id, role_id) VALUES (:m, :r)"),
        {"m": mid, "r": role_id},
    )
    owner_session.commit()

    try:
        yield sub
    finally:
        owner_session.rollback()
        # 🔴 THIS USER MAY HAVE DECIDED AN ACCESS REQUEST, AND THE FK IS
        # RESTRICT. Whether that request has already been cleaned up depends
        # on fixture teardown ORDER, which is a fragile thing for a teardown
        # to rely on -- it produced a ForeignKeyViolation reported two
        # fixtures away from its cause. Releasing the reference first makes
        # this teardown correct on its own, in any order.
        # ⚠️ AND IT NAMES THE TENANT. Under FORCE RLS this UPDATE matches
        # nothing without `app.current_org`, silently -- which is how the fix
        # above failed the first time it was written. Third occurrence of the
        # same trap in this file: the GUC is a property of a CONNECTION, and a
        # pooled connection is not a durable place to keep one.
        owner_session.execute(
            text("SELECT set_config('app.current_org', :org, false)"),
            {"org": str(admin_org["org_id"])},
        )
        owner_session.execute(
            text("UPDATE public_intel.access_requests SET decided_by = NULL WHERE decided_by = :u"),
            {"u": uid},
        )
        owner_session.execute(
            text("DELETE FROM core.member_roles WHERE member_id = :m"), {"m": mid}
        )
        owner_session.execute(
            text("DELETE FROM core.organization_members WHERE id = :m"), {"m": mid}
        )
        owner_session.execute(text("DELETE FROM core.users WHERE id = :u"), {"u": uid})
        owner_session.execute(
            text("DELETE FROM core.role_permissions WHERE role_id = :r"), {"r": role_id}
        )
        owner_session.execute(text("DELETE FROM core.roles WHERE id = :r"), {"r": role_id})
        owner_session.commit()


def test_approving_needs_admin_roles_and_rejecting_does_not(
    client, make_token, owner_session, admin_org, queued_request, binder_only
) -> None:
    """APPROVING grants a role. REJECTING grants nothing. They differ.

    🔴 CODEX: the first version gated the whole route on `admin.users` while the
    approval branch called `_grant_role` -- so a caller holding only the
    person-binding permission could approve an applicant straight into
    `administrator`. `members.tsx` states the rule that breaks: *"collapsing
    them would make 'can add a colleague' and 'can grant them every permission
    in the product' the same decision."*

    🔴 SUPERVISOR: the fix over-corrected by putting both on the dependency,
    which made REJECTING an applicant require the role-granting permission too.
    A rejection grants nothing and no part of the justification covers it.

    Both directions are asserted, because a test that only checked the refusal
    would have passed against the over-correction exactly as happily as against
    the right answer.
    """
    headers = _headers(make_token, binder_only, admin_org["org_id"])

    refused = client.post(
        f"/api/admin/access-requests/{queued_request['id']}/decision",
        json={
            "decision": "approved",
            "reason": "approving without the role permission",
            "keycloak_sub": f"l1-bound-{queued_request['suffix']}-d",
            "roles": ["executive_viewer"],
        },
        headers=headers,
    )
    assert refused.status_code == 403, f"{refused.status_code}: {refused.text}"
    assert "admin.roles" in refused.text
    status_now, _ = _status_of(owner_session, queued_request["id"], admin_org["org_id"])
    assert status_now == "new", "a refused approval still moved the request"

    # The same caller may still REJECT -- that is the Supervisor's half.
    allowed = client.post(
        f"/api/admin/access-requests/{queued_request['id']}/decision",
        json={"decision": "rejected", "reason": "not a business address"},
        headers=headers,
    )
    assert allowed.status_code == 200, (
        "rejecting was refused for want of admin.roles, which grants nothing: "
        f"{allowed.status_code}: {allowed.text}"
    )


def test_sign_up_refuses_when_the_deployment_names_no_organization(monkeypatch) -> None:
    """🔴 FAIL CLOSED: no configured owner means no request is taken.

    Raised by the Supervisor as the deployment half of the same finding:
    `public_landing_organization_id` existed in `config.py` and was set nowhere
    in the repository, so this route would have answered 503 on every
    deployment the moment it shipped. It is now set in `scripts/demo-up.ps1`,
    and this pins the behaviour when it is absent.

    Writing the row with a NULL owner instead would put it where no tenant
    predicate can reach it -- recreating, one layer down, the exact "table with
    no reader" defect this whole change exists to close.
    """
    from fastapi.testclient import TestClient

    from app.api import public as public_module

    real = public_module.get_settings()

    class _NoOwner:
        """Everything the real settings say, except who owns the landing page."""

        def __getattr__(self, name: str):
            return getattr(real, name)

        public_landing_organization_id = None

    monkeypatch.setattr(public_module, "get_settings", _NoOwner)

    from app.main import app

    probe = TestClient(app, raise_server_exceptions=False)
    response = probe.post(
        "/api/public/access-requests",
        json={
            "full_name": "Nobody",
            "work_email": "nobody@l1probe.org",
            "company": "Nowhere",
        },
    )
    assert response.status_code == 503, f"{response.status_code}: {response.text}"
    assert "not been configured" in response.text
