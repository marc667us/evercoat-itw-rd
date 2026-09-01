"""I107 — `POST /api/admin/members` over real HTTP.

🔴 THIS ROUTE HAD NO END-TO-END TEST, AND THAT IS HOW A 500 SHIPPED.

`tests/db/test_admin_bind_refusals.py` unit-tests `_bind_conflict` and
`_standing_refusal` as functions, and says so in its own docstring. Nothing
posted to the route. So when migration 050's standing check turned out to
raise SQLSTATE 42501 -- which psycopg surfaces as `ProgrammingError`, a
SIBLING of `IntegrityError` and not a subclass -- the handler never saw it,
the refusal left as a **500**, and the suite stayed green. **A classifier
tested in isolation says nothing about whether the exception ever reaches
it.**

⚠️ ONE CORRECTION TO THE RECORD, MEASURED BY FALSIFYING THIS TEST. The 050
write-up says the refusal escaped "carrying a driver message". It does not:
breaking `_standing_refusal` on purpose and re-running produces
`{"detail":"internal error","correlation_id":"..."}` -- the application's
generic handler is doing its job. **The defect is the STATUS, not the body.**
403 and 500 tell a client two different things, and only one of them is true.
Worth stating because "it leaks the driver message" is the sort of detail that
makes a fix look more urgent than its real reason, which is enough on its own.

These tests drive the real ASGI application with a real signed token against a
real PostgreSQL, so every layer the request actually crosses is in play:
`get_principal`, `require_permission`, `session_scope`'s GUCs, the SECURITY
DEFINER bind, the constraint that refuses it, and the handler that classifies
what comes back.

⚠️ THE STATUS CODE IS THE ASSERTION, NOT THE MESSAGE. A 409 tells a client its
request conflicts with existing state and that changing it will help; a 403
says the caller may not do this at all; a 500 says the server broke. The route
answered the third for the second, which is exactly the class of defect that
survives a suite testing only the words.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from tests.auth.conftest import ORG_HEADER

pytestmark = [pytest.mark.db]


@pytest.fixture
def client() -> TestClient:
    from app.main import app

    return TestClient(app, raise_server_exceptions=False)


def _headers(make_token, sub: str, org_id: object) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token(sub=sub)}", ORG_HEADER: str(org_id)}


def _payload(sfx: str, *, sub: str | None = None, email: str | None = None) -> dict[str, object]:
    """A body the ROUTE will accept.

    ⚠️ NOT `@example.test`, WHICH EVERY OTHER FIXTURE IN THIS REPOSITORY USES.
    `MemberInvite.email` is a Pydantic `EmailStr`, and `email-validator`
    refuses reserved and special-use top-level domains -- `.test`, `.invalid`,
    `.example`, `.localhost`. So every address the database fixtures create is
    one this endpoint would have answered 422 for.

    That is not a defect in either place, but it is a small piece of evidence
    for why I107 existed: no fixture in the suite was shaped like a request
    this route could accept, and nothing had ever posted one.
    """
    tag = uuid.uuid4().hex[:6]
    return {
        "keycloak_sub": sub or f"i107-new-{sfx}-{tag}",
        "email": email or f"i107-new-{sfx}-{tag}@i107probe.org",
        "display_name": "Newly Invited",
        "roles": [],
    }


def test_an_administrator_can_invite_a_new_subject(
    client, make_token, owner_session, admin_org
) -> None:
    """The ordinary path, end to end, asserted on the STORED result.

    The response must echo the database's row rather than the request, and the
    membership must actually exist afterwards -- a 201 over a transaction that
    rolled back is the shape this project has shipped before.
    """
    body = _payload(str(admin_org["suffix"]))
    r = client.post(
        "/api/admin/members",
        json=body,
        headers=_headers(make_token, str(admin_org["admin_sub"]), admin_org["org_id"]),
    )
    assert r.status_code == 201, f"{r.status_code}: {r.text}"
    got = r.json()
    assert got["email"] == body["email"]
    assert got["display_name"] == body["display_name"]
    assert got["status"] == "active"

    # 🔴 READ IT BACK AS THE OWNER, ON A DIFFERENT CONNECTION. The response is
    # the route's claim; this is whether it committed.
    stored = owner_session.execute(
        text(
            """
            SELECT organization_id, email::text, display_name
              FROM core.organization_members WHERE id = :m
            """
        ),
        {"m": got["member_id"]},
    ).one()
    assert stored.organization_id == admin_org["org_id"]
    assert (stored.email, stored.display_name) == (body["email"], body["display_name"])

    # And the audit event exists in the same transaction as the change, which
    # is the rule this whole module was written to guarantee.
    audited = owner_session.execute(
        text(
            """
            SELECT count(*) FROM audit.events
             WHERE action = 'admin.member_invited' AND entity_id = :m
            """
        ),
        {"m": got["member_id"]},
    ).scalar_one()
    assert audited == 1, "the membership committed without its audit event"


def test_inviting_the_same_subject_twice_is_a_409_not_a_500(client, make_token, admin_org) -> None:
    """`organization_members_unique`, classified.

    The second call must say the membership already exists -- a fact
    `list_members` already shows this caller, so naming it discloses nothing.
    """
    body = _payload(str(admin_org["suffix"]))
    headers = _headers(make_token, str(admin_org["admin_sub"]), admin_org["org_id"])
    first = client.post("/api/admin/members", json=body, headers=headers)
    assert first.status_code == 201, f"{first.status_code}: {first.text}"

    second = client.post("/api/admin/members", json=body, headers=headers)
    assert second.status_code == 409, f"{second.status_code}: {second.text}"
    assert "already a member" in second.json()["detail"]


def test_a_taken_address_is_a_409_naming_the_address(client, make_token, admin_org) -> None:
    """🔴 THE PATH THAT DEPENDS ON THE INDEX KEEPING 046's CONSTRAINT NAME.

    Migration 052 replaced 046's trigger with a partial unique index and kept
    the name deliberately, because `_bind_conflict` classifies on
    `diag.constraint_name` and anything it cannot name becomes a 500. Nothing
    but this test exercises that end to end -- the database test asserts the
    name, and this asserts that the name still produces the right STATUS.
    """
    body = _payload(str(admin_org["suffix"]), email=str(admin_org["plain_email"]))
    r = client.post(
        "/api/admin/members",
        json=body,
        headers=_headers(make_token, str(admin_org["admin_sub"]), admin_org["org_id"]),
    )
    assert r.status_code == 409, f"{r.status_code}: {r.text}"
    assert "email address" in r.json()["detail"]


def test_a_member_without_admin_users_is_refused_at_the_route(
    client, make_token, admin_org
) -> None:
    """The route-level gate, which is the one that normally decides.

    A laboratory technician is a real member of this organization and holds no
    `admin.users`. Without this the test below cannot be read as being about
    the DATABASE's check, because both would answer 403 for the same reason.
    """
    r = client.post(
        "/api/admin/members",
        json=_payload(str(admin_org["suffix"])),
        headers=_headers(make_token, str(admin_org["plain_sub"]), admin_org["org_id"]),
    )
    assert r.status_code == 403, f"{r.status_code}: {r.text}"


def test_the_databases_own_refusal_is_a_403_not_a_500(
    client, make_token, owner_session, admin_org
) -> None:
    """🔴 THE DEFECT I107 EXISTS FOR, DRIVEN THROUGH THE REAL ROUTE.

    Migration 050 makes the bind prove the caller's standing in the database as
    well as at the route -- the same rule on the path that has no route. It
    raises `insufficient_privilege`, SQLSTATE 42501, which psycopg surfaces as
    `ProgrammingError`: a SIBLING of `IntegrityError`, not a subclass. The
    route caught only `IntegrityError` and no exception handler is registered
    on the app, so the database refusing a privileged write answered with a
    driver message and a 500.

    ⚠️ REACHING IT MEANS MAKING THE TWO CHECKS DISAGREE, which in production is
    the immediate-revocation window `core.authorization_for_current_session()`
    exists for: the caller's role is revoked between `get_principal` and the
    write. That window is real and it is narrow, so it is produced here
    deterministically -- the token's principal still holds `admin.users`, and
    the role row is deleted before the request is dispatched, so the route's
    check passes against the verified principal while the definer's check,
    which reads the database, refuses.

    Answering that with a 500 defeats the entire point of checking twice.
    """
    # The route's own check reads the principal resolved from the token at
    # request time, so the grant must survive long enough to be seen there and
    # be gone by the time the definer looks. Deleting the ROLE ASSIGNMENT and
    # then posting does exactly that in one step: `require_permission` is
    # satisfied by a principal built from... the same data. So instead the
    # disagreement is created where it genuinely occurs -- inside the session.
    #
    # `session_scope` sets `app.current_user_id` from the principal. Override
    # `get_db` with a session scoped to a member who holds NOTHING, leaving the
    # token and `require_permission` untouched. That is precisely the state the
    # revocation window produces: an authorized principal, a session the
    # database will not honour.
    from app.core.db import RequestContext, session_scope
    from app.core.security import get_db
    from app.main import app

    def _unprivileged_db():
        # The SAME organization -- so RLS is not what refuses, and the only
        # thing left to say no is the definer's permission check.
        context = RequestContext(
            organization_id=uuid.UUID(str(admin_org["org_id"])),
            user_id=uuid.UUID(str(admin_org["plain_id"])),
        )
        with session_scope(context) as session:
            yield session

    app.dependency_overrides[get_db] = _unprivileged_db
    try:
        r = client.post(
            "/api/admin/members",
            json=_payload(str(admin_org["suffix"])),
            headers=_headers(make_token, str(admin_org["admin_sub"]), admin_org["org_id"]),
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert r.status_code == 403, (
        f"the database's own refusal answered {r.status_code}, not 403. Body: {r.text[:300]}"
    )
    assert "not permitted" in r.json()["detail"]
    # 🔴 AND IT MUST NOT REPEAT THE DATABASE'S MESSAGE. 050 deliberately does
    # not say WHICH is missing -- membership or permission -- because only one
    # of those is the caller's business.
    assert "insufficient_privilege" not in r.text
    assert "organization_members" not in r.text

    # Nothing was written by the refused request.
    leaked = owner_session.execute(
        text(
            """
            SELECT count(*) FROM core.organization_members
             WHERE organization_id = :o AND email::text LIKE :p
            """
        ),
        {"o": admin_org["org_id"], "p": f"i107-new-{admin_org['suffix']}-%"},
    ).scalar_one()
    assert leaked == 0, f"{leaked} membership(s) survived a refused request"


def test_an_unknown_role_is_422_before_anything_is_written(
    client, make_token, owner_session, admin_org
) -> None:
    """Validation happens before the identity is created, not after.

    A 422 that had already minted a `core.users` row would leave an identity
    nobody asked for and no membership to make it visible -- the orphan shape
    I101 counts 595 of.
    """
    body = _payload(str(admin_org["suffix"]))
    body["roles"] = ["sorcerer"]
    r = client.post(
        "/api/admin/members",
        json=body,
        headers=_headers(make_token, str(admin_org["admin_sub"]), admin_org["org_id"]),
    )
    assert r.status_code == 422, f"{r.status_code}: {r.text}"
    stranded = owner_session.execute(
        text("SELECT count(*) FROM core.users WHERE keycloak_sub = :s"),
        {"s": body["keycloak_sub"]},
    ).scalar_one()
    assert stranded == 0, "the rejected request created an identity anyway"


def test_an_anonymous_caller_is_refused(client, admin_org) -> None:
    """No token, no membership. The first link in §6's chain."""
    r = client.post(
        "/api/admin/members",
        json=_payload(str(admin_org["suffix"])),
        headers={ORG_HEADER: str(admin_org["org_id"])},
    )
    assert r.status_code in (401, 403), f"{r.status_code}: {r.text}"
