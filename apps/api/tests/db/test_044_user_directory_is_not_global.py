"""I55 / I80 — the user directory is org-scoped, and cannot be written across.

Migration 032 closed I19 for every table that had RLS enabled. `core.users`
had none, so 032 did nothing for it. Measured 2026-08-23 as `evercoat_app`
with no GUC set:

    SELECT count(*) FROM core.organization_members;   -->    0
    SELECT count(*) FROM core.users;                  -->  571

571 rows, every tenant, email addresses included.

The write half (I80) was found while measuring the read half. `invite_member`
ran ``INSERT ... ON CONFLICT (keycloak_sub) DO UPDATE SET display_name``; run
under organization A's GUC against a subject who is a member only of
organization B, it renamed that user and returned B's real email address.

These tests are written against the behaviour a connection sees, following
`test_032`. `test_the_table_is_protected_at_all` is the one exception and
exists so a failure names its cause in one line.

⚠️ Several tests here COMMIT. `app_engine` is a separate connection from
`owner_session`, and `evercoat_owner` holds no membership in `evercoat_app`
so `SET ROLE` is refused. Two connections and an RLS-bearing role leave
exactly one option: commit, assert, clean up in a `finally`. The same
reasoning is written out at length in `test_032`.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError


@pytest.fixture
def two_orgs_two_users(owner_session) -> Iterator[dict[str, uuid.UUID | str]]:
    """Organization A with one member, organization B with one member.

    Committed, because the assertions run on a different connection as a role
    that RLS applies to. Removed in the `finally` regardless of outcome.
    """
    suffix = uuid.uuid4().hex[:8]
    orgs: list[uuid.UUID] = []
    for label in ("A", "B"):
        orgs.append(
            owner_session.execute(
                text("INSERT INTO core.organizations (code, name) VALUES (:c, :n) RETURNING id"),
                {"c": f"I55-{label}-{suffix}", "n": f"I55 probe {label}"},
            ).scalar_one()
        )

    users: list[uuid.UUID] = []
    subs: list[str] = []
    for label, org in zip(("A", "B"), orgs, strict=True):
        sub = f"i55-{label.lower()}-{suffix}"
        subs.append(sub)
        uid = owner_session.execute(
            text(
                """
                INSERT INTO core.users (keycloak_sub, email, display_name)
                VALUES (:sub, :email, :name) RETURNING id
                """
            ),
            {
                "sub": sub,
                "email": f"i55-{label.lower()}-{suffix}@example.test",
                "name": f"I55 member {label}",
            },
        ).scalar_one()
        users.append(uid)
        owner_session.execute(
            text(
                """
                INSERT INTO core.organization_members (organization_id, user_id)
                VALUES (:org, :uid)
                """
            ),
            {"org": org, "uid": uid},
        )
    owner_session.commit()

    try:
        yield {
            "org_a": orgs[0],
            "org_b": orgs[1],
            "user_a": users[0],
            "user_b": users[1],
            "sub_a": subs[0],
            "sub_b": subs[1],
        }
    finally:
        owner_session.rollback()
        owner_session.execute(
            text("DELETE FROM core.organization_members WHERE user_id = ANY(:u)"),
            {"u": users},
        )
        owner_session.execute(text("DELETE FROM core.users WHERE id = ANY(:u)"), {"u": users})
        owner_session.execute(
            text("DELETE FROM core.organizations WHERE id = ANY(:o)"), {"o": orgs}
        )
        owner_session.commit()


def test_the_table_is_protected_at_all(owner_session) -> None:
    """`core.users` has RLS enabled, three policies, and NOT force.

    Not the security property — the behavioural tests below are that. This
    names the cause when they fail. FORCE is asserted OFF deliberately: both
    subject lookups are SECURITY DEFINER owned by `evercoat_owner` and run
    before an organization is chosen, so FORCE here stops sign-in. That
    cutover is I58's, and `core.users` is now inside its scope.
    """
    rls, force = owner_session.execute(
        text(
            """
            SELECT c.relrowsecurity, c.relforcerowsecurity
              FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
             WHERE n.nspname = 'core' AND c.relname = 'users'
            """
        )
    ).one()
    assert rls is True, (
        "core.users has RLS disabled. The runtime role reads every tenant's "
        "email addresses with no context set. See migration 044."
    )
    assert force is False, (
        "core.users has FORCE ROW LEVEL SECURITY. memberships_for_subject and "
        "principal_for_subject are owner-owned definers that read this table "
        "with no GUC; under FORCE they return zero rows and sign-in is dead. "
        "If this cutover is intentional, it is I58 and it must prove sign-in."
    )

    policies = owner_session.execute(
        text("SELECT count(*) FROM pg_policy WHERE polrelid = 'core.users'::regclass")
    ).scalar_one()
    assert policies == 3, (
        f"core.users carries {policies} policies; 044 creates exactly 3 "
        "(select, insert, update). A missing UPDATE policy re-opens I80."
    )


def test_no_tenant_context_means_no_users(app_engine) -> None:
    """The runtime role, with no GUC, sees no users at all.

    🔴 Proved by falsification: with `ALTER TABLE core.users DISABLE ROW LEVEL
    SECURITY`, this returns 571 on the development database instead of 0.
    """
    with app_engine.connect() as conn:
        count = conn.execute(text("SELECT count(*) FROM core.users")).scalar_one()

    assert count == 0, (
        f"core.users returned {count} rows to evercoat_app with NO organization "
        "context set. Emails and display names are cross-tenant personal data, "
        "and any path reaching a connection without session_scope() reads all "
        "of them."
    )


def test_scoping_to_one_organization_shows_its_members_and_no_others(
    app_engine, two_orgs_two_users
) -> None:
    """The positive and negative halves together.

    A fail-closed directory that shows nobody is an outage, not a security
    improvement — every screen that resolves an actor's name would blank.
    """
    f = two_orgs_two_users
    with app_engine.connect() as conn:
        conn.execute(
            text("SELECT set_config('app.current_org', :o, false)"),
            {"o": str(f["org_a"])},
        )
        visible = (
            conn.execute(
                text("SELECT id FROM core.users WHERE id = ANY(:ids)"),
                {"ids": [f["user_a"], f["user_b"]]},
            )
            .scalars()
            .all()
        )

    assert f["user_a"] in visible, (
        "the runtime role could not see a member of its OWN organization. "
        "Migration 044 has closed the directory to everyone."
    )
    assert f["user_b"] not in visible, (
        "a user belonging only to another organization was visible while "
        "scoped to the first. I55 is not closed."
    )


def test_an_email_address_does_not_cross_the_boundary(app_engine, two_orgs_two_users) -> None:
    """I55 stated as the disclosure it actually is.

    The count test above would pass against a policy that hid the row from
    `SELECT id` while some other column path still leaked. This asks for the
    personal data directly.
    """
    f = two_orgs_two_users
    with app_engine.connect() as conn:
        conn.execute(
            text("SELECT set_config('app.current_org', :o, false)"),
            {"o": str(f["org_a"])},
        )
        row = conn.execute(
            text("SELECT email::text, display_name FROM core.users WHERE id = :u"),
            {"u": f["user_b"]},
        ).one_or_none()

    assert row is None, (
        f"organization A read organization B's user record: {row}. That is the "
        "571-row cross-tenant PII disclosure I55 names."
    )


def test_a_deactivated_member_is_still_resolvable(app_engine, owner_session, two_orgs_two_users):
    """🔴 The `status` decision, asserted so it is not quietly tightened later.

    044's policy does NOT filter on `core.organization_members.status`. Adding
    that filter looks like a hardening and is a data-loss bug: eleven INNER
    joins in this codebase resolve an actor through `core.users`
    (`projects/dashboard.py`, `opportunities/service.py`,
    `messaging/service.py`, `tasks/service.py`, `pipeline/service.py`), so a
    leaver would not merely lose their name — the records they created would
    drop out of every list.

    Whether somebody may sign in is `status` and Keycloak. Whether their name
    renders on a record they made is this policy, and the answer is yes.
    """
    f = two_orgs_two_users
    owner_session.execute(
        text(
            """
            UPDATE core.organization_members SET status = 'inactive'
             WHERE user_id = :u AND organization_id = :o
            """
        ),
        {"u": f["user_a"], "o": f["org_a"]},
    )
    owner_session.commit()

    with app_engine.connect() as conn:
        conn.execute(
            text("SELECT set_config('app.current_org', :o, false)"),
            {"o": str(f["org_a"])},
        )
        name = conn.execute(
            text("SELECT display_name FROM core.users WHERE id = :u"),
            {"u": f["user_a"]},
        ).scalar_one_or_none()

    assert name == "I55 member A", (
        "a deactivated member became unresolvable. Every record they ever "
        "created now drops out of the eleven INNER joins that resolve an "
        "actor through core.users. See the policy comment in migration 044."
    )


def test_the_cross_tenant_rename_is_refused(app_engine, two_orgs_two_users) -> None:
    """I80, as the exact statement that was measured doing it.

    Run 2026-08-23 as `evercoat_app` under organization A's GUC against a
    subject belonging only to organization B, this returned::

        id            54648e11-dcdc-4a05-84db-c928a4bee28c
        email         owner-08f856f3@example.test
        display_name  PWNED BY ORG A

    A rename of another tenant's user, and a disclosure of their real email
    through `RETURNING`, from one statement behind `admin.users`.

    🔴 THIS TEST ASSERTS THE BEHAVIOUR, AND DELIBERATELY DOES NOT CLAIM WHICH
    POLICY PRODUCES IT. Its first version said "proved by falsification: with
    the UPDATE policy dropped, this fails". That was measured and it is FALSE
    — dropping the UPDATE policy denies every update, so the statement still
    errored and the test still passed, for a different reason. Making the
    UPDATE policy fully permissive ALSO left it passing. The full matrix:

        SELECT policy | UPDATE policy | result
        --------------+---------------+------------------------------------
        restrictive   | restrictive   | refused              (shipped)
        restrictive   | permissive    | refused
        permissive    | restrictive   | refused
        permissive    | permissive    | 'PWNED BY ORG A'     (pre-044)

    So the falsification that actually reddens this test is making the READ
    policy permissive, which is the pre-044 state — `core.users` had no RLS at
    all. That is what `test_no_tenant_context_means_no_users` and
    `test_an_email_address_does_not_cross_the_boundary` pin down, and this
    test rides on them rather than duplicating the claim.

    Documented rather than deleted, because the next reader will otherwise
    conclude the UPDATE policy is what refuses this. It is not; see the
    policy's COMMENT in migration 044.
    """
    f = two_orgs_two_users
    with app_engine.connect() as conn:
        conn.execute(
            text("SELECT set_config('app.current_org', :o, false)"),
            {"o": str(f["org_a"])},
        )
        with pytest.raises(ProgrammingError) as caught:
            conn.execute(
                text(
                    """
                    INSERT INTO core.users (keycloak_sub, email, display_name)
                    VALUES (:sub, 'attacker@example.test', 'PWNED BY ORG A')
                    ON CONFLICT (keycloak_sub) DO UPDATE
                        SET display_name = EXCLUDED.display_name
                    RETURNING id, email::text, display_name
                    """
                ),
                {"sub": f["sub_b"]},
            )

    assert "row-level security" in str(caught.value).lower(), (
        "the statement failed for some reason other than the RLS policy: "
        f"{caught.value}. The test must fail on the boundary, not on a typo."
    )


def test_a_rename_inside_the_organization_still_works(app_engine, two_orgs_two_users) -> None:
    """🔴 The half that was missing, and the one that catches a deny-all.

    A table with RLS enabled and no usable UPDATE policy is not hardened, it
    is read-only — and every cross-tenant assertion in this file would pass
    against it, exactly as they did when the UPDATE policy was dropped
    entirely during falsification. Display names change; an administrator must
    be able to correct one inside their own organization.

    This is the UPDATE-side equivalent of
    `test_scoping_to_one_organization_shows_its_members_and_no_others`, and
    the reason `test_the_cross_tenant_rename_is_refused` is not sufficient on
    its own.
    """
    f = two_orgs_two_users
    with app_engine.connect() as conn:
        conn.execute(
            text("SELECT set_config('app.current_org', :o, false)"),
            {"o": str(f["org_a"])},
        )
        renamed = conn.execute(
            text(
                """
                UPDATE core.users SET display_name = 'I55 member A, corrected'
                 WHERE id = :u
                RETURNING display_name
                """
            ),
            {"u": f["user_a"]},
        ).scalar_one_or_none()
        conn.rollback()

    assert renamed == "I55 member A, corrected", (
        "an administrator could not rename a member of their OWN organization "
        f"(got {renamed!r}). Migration 044 has made core.users read-only "
        "rather than org-scoped, and every cross-tenant test in this file "
        "passes vacuously against that."
    )


def test_the_row_is_unchanged_after_the_refusal(owner_session, two_orgs_two_users) -> None:
    """A refusal that still wrote would be the worst of both.

    Read as the owner so this observes the stored row rather than a policy's
    view of it.
    """
    f = two_orgs_two_users
    name = owner_session.execute(
        text("SELECT display_name FROM core.users WHERE id = :u"), {"u": f["user_b"]}
    ).scalar_one()
    assert name == "I55 member B", (
        f"organization B's user is now named {name!r}. The rename was refused and applied anyway."
    )


def test_the_binding_lookup_resolves_an_id_and_nothing_else(app_engine, two_orgs_two_users):
    """`core.user_id_for_subject` — without it, 044 would break a feature.

    044's read policy makes an existing user in another organization
    invisible, and `keycloak_sub` is globally unique, so an administrator
    could neither find nor create them: multi-organization membership would
    become impossible. That is why `core.users` has no `organization_id` in
    the first place, so removing the disclosure by removing the feature is not
    a fix.

    What the function may return is exactly one uuid. If it ever grows a
    row-returning signature, this test is where that gets caught.
    """
    f = two_orgs_two_users
    with app_engine.connect() as conn:
        conn.execute(
            text("SELECT set_config('app.current_org', :o, false)"),
            {"o": str(f["org_a"])},
        )
        resolved = conn.execute(
            text("SELECT core.user_id_for_subject(:s)"), {"s": f["sub_b"]}
        ).scalar_one()
        missing = conn.execute(
            text("SELECT core.user_id_for_subject(:s)"), {"s": f"nobody-{uuid.uuid4().hex}"}
        ).scalar_one_or_none()

    assert resolved == f["user_b"], (
        "the binding lookup could not resolve a subject in another "
        "organization, so an administrator cannot invite an existing human. "
        "044 has closed a disclosure by deleting a feature."
    )
    assert missing is None, "an unknown subject resolved to something."

    ret = None
    with app_engine.connect() as conn:
        ret = conn.execute(
            text(
                """
                SELECT pg_get_function_result(p.oid)
                  FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
                 WHERE n.nspname = 'core' AND p.proname = 'user_id_for_subject'
                """
            )
        ).scalar_one()
    assert ret == "uuid", (
        f"core.user_id_for_subject now returns {ret!r}. It is SECURITY DEFINER "
        "and therefore outside RLS; it may return an identifier and never a "
        "record. Anything wider is a cross-tenant read channel."
    )


def test_the_binding_lookup_is_not_public(owner_session) -> None:
    """A definer function granted to PUBLIC is granted to every future role.

    Same finding shape as migration 035, which had to take `principal_for_subject`
    back from PUBLIC after it shipped that way.
    """
    public_can = owner_session.execute(
        text(
            """
            SELECT has_function_privilege('public',
                'core.user_id_for_subject(text)', 'EXECUTE')
            """
        )
    ).scalar_one()
    assert public_can is False, (
        "core.user_id_for_subject is executable by PUBLIC. It is SECURITY "
        "DEFINER and reads across every tenant by design; only evercoat_app "
        "may call it."
    )


def test_sign_in_still_works(owner_session) -> None:
    """🔴 The thing 044 was shaped not to break.

    `core.memberships_for_subject` runs BEFORE an organization is chosen — it
    is what tells a signed-in browser which organizations it may ask for — and
    it reads `core.users`. It survives 044 only because it is SECURITY DEFINER
    owned by `evercoat_owner` and FORCE is off, which is the same argument
    migration 032 made and the same one I58 will have to replace.

    Builds its own subject: CI's database is migrated and not seeded, and a
    version of this test that read a seeded user would fail there reporting a
    security regression that is not present.
    """
    suffix = uuid.uuid4().hex[:8]
    sub = f"i55-signin-{suffix}"
    org = owner_session.execute(
        text("INSERT INTO core.organizations (code, name) VALUES (:c, :n) RETURNING id"),
        {"c": f"I55-SI-{suffix}", "n": "I55 sign-in probe"},
    ).scalar_one()
    uid = owner_session.execute(
        text(
            """
            INSERT INTO core.users (keycloak_sub, email, display_name)
            VALUES (:s, :e, 'I55 sign-in') RETURNING id
            """
        ),
        {"s": sub, "e": f"i55-signin-{suffix}@example.test"},
    ).scalar_one()
    owner_session.execute(
        text("INSERT INTO core.organization_members (organization_id, user_id) VALUES (:o, :u)"),
        {"o": org, "u": uid},
    )
    owner_session.flush()

    rows = owner_session.execute(
        text("SELECT * FROM core.memberships_for_subject(:s)"), {"s": sub}
    ).all()

    assert len(rows) == 1, (
        f"core.memberships_for_subject returned {len(rows)} rows for a subject "
        "with exactly one membership. GET /api/me answers 404 for every "
        "legitimate user and sign-in is dead. 044 enabled RLS on core.users; "
        "if FORCE was enabled with it, that is the cause."
    )
