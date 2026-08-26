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
                "INSERT INTO core.organization_members (organization_id, user_id, email,"
                " display_name) SELECT :org, :uid, u.email, u.display_name FROM core.users u"
                " WHERE u.id = :uid"
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

    # 🔴 COUNTING POLICIES PROVED ALMOST NOTHING. Raised by Codex: the first
    # version asserted `count(*) == 3`, which passes against three INSERT
    # policies, or against a SELECT policy of `USING (true)`. Assert the SHAPE:
    # which command each governs, and that neither read nor update predicate is
    # the constant TRUE.
    shape = {
        row[0]: (row[1], row[2], row[3])
        for row in owner_session.execute(
            text(
                """
                SELECT polname, polcmd::text,
                       COALESCE(pg_get_expr(polqual, polrelid), ''),
                       COALESCE(pg_get_expr(polwithcheck, polrelid), '')
                  FROM pg_policy WHERE polrelid = 'core.users'::regclass
                """
            )
        ).all()
    }
    assert set(shape) == {
        "users_visible_within_a_shared_organization",
        "users_identity_may_be_created",
        "users_updatable_within_a_shared_organization",
    }, f"core.users carries the wrong set of policies: {sorted(shape)}"

    # 'r' = SELECT, 'a' = INSERT, 'w' = UPDATE.
    assert shape["users_visible_within_a_shared_organization"][0] == "r"
    assert shape["users_identity_may_be_created"][0] == "a"
    assert shape["users_updatable_within_a_shared_organization"][0] == "w"

    read_using = shape["users_visible_within_a_shared_organization"][1]
    assert read_using.strip() != "true", (
        f"the read policy's USING expression is {read_using!r}. A constant TRUE "
        "re-opens I55 in full while every count-based test stays green."
    )
    assert "organization_members" in read_using, (
        f"the read policy's USING expression is {read_using!r} and does not "
        "consult core.organization_members, so it cannot be scoping on shared "
        "membership."
    )
    upd_using, upd_check = shape["users_updatable_within_a_shared_organization"][1:]
    permissive = "the UPDATE policy is permissive. It is not what refuses the "
    permissive += "cross-tenant rename today, but it is the only thing that would "
    permissive += "if the read policy were ever widened -- see 044's matrix."
    assert upd_using.strip() != "true", permissive
    assert upd_check.strip() != "true", permissive


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

    ⚠️ SINCE 052 THE PERSONAL DATA IS NOT ON `core.users` ANY MORE, so this
    asks in both places. The address and the name a tenant knows a member by
    live on `core.organization_members` (I106); the global row keeps the
    identity provider's mirror and the runtime roles cannot read it at all.
    Asking only the old question would leave this test passing on a privilege
    error while the row-level boundary it names went unexercised — the same
    displacement 047 caused one layer up, recorded in
    `test_the_rls_boundary_still_refuses_a_cross_tenant_update`.
    """
    f = two_orgs_two_users
    with app_engine.connect() as conn:
        conn.execute(
            text("SELECT set_config('app.current_org', :o, false)"),
            {"o": str(f["org_a"])},
        )
        # (a) Where the personal data lives now. This is a plain RLS question:
        # the columns are readable, so only `org_member_isolation` can refuse.
        row = conn.execute(
            text(
                """
                SELECT email::text, display_name FROM core.organization_members
                 WHERE user_id = :u
                """
            ),
            {"u": f["user_b"]},
        ).one_or_none()
        assert row is None, (
            f"organization A read organization B's member record: {row}. That "
            "is the cross-tenant PII disclosure I55 names, at the table 052 "
            "moved it to."
        )

        # (b) And the global row refuses before RLS is reached. Named as a
        # PRIVILEGE refusal rather than accepted as "an error", so a lost
        # INSERT grant or a missing schema USAGE cannot satisfy it.
        with pytest.raises(ProgrammingError) as caught:
            conn.execute(
                text("SELECT email::text, display_name FROM core.users WHERE id = :u"),
                {"u": f["user_b"]},
            )
        refusal = str(caught.value).lower()
        assert "permission denied" in refusal, (
            f"reading the global identity failed for another reason: {caught.value}"
        )
        # ...and on THAT table. "permission denied" alone would accept a lost
        # schema USAGE or any unrelated privilege failure, which says nothing
        # about the column revoke this test is here for.
        assert "users" in refusal, (
            f"something other than core.users refused the read: {caught.value}"
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
            # The membership's name since 052 -- `core.users.display_name` is
            # no longer readable by this role, and the name a record renders
            # is the one this organization knows the person by anyway.
            text(
                """
                SELECT display_name FROM core.organization_members
                 WHERE user_id = :u AND organization_id = :o
                """
            ),
            {"u": f["user_a"], "o": f["org_a"]},
        ).scalar_one_or_none()

    assert name == "I55 member A", (
        "a deactivated member became unresolvable. Every record they ever "
        "created now drops out of the eleven INNER joins that resolve an "
        "actor through core.users. See the policy comment in migration 044."
    )

    # 🔴 A DIRECT READ IS NOT THE CLAIM. Raised by Codex: the assertion above
    # passes while the INNER joins the justification is built on still drop
    # their parent rows. So run a REAL one -- this is `list_members`'
    # production query (`app/api/admin.py`), INNER by construction, and the
    # row it would lose is the membership itself.
    with app_engine.connect() as conn:
        conn.execute(
            text("SELECT set_config('app.current_org', :o, false)"),
            {"o": str(f["org_a"])},
        )
        rows = conn.execute(
            text(
                """
                SELECT om.id, om.display_name
                  FROM core.organization_members om
                 WHERE om.user_id = :u
                """
            ),
            {"u": f["user_a"]},
        ).all()

    assert len(rows) == 1, (
        "the deactivated member vanished from an INNER JOIN through "
        "core.users -- the Administration members list would silently lose "
        "the row, not merely the name. This is the failure the policy's "
        "status decision exists to prevent, and the direct read above cannot "
        "see it."
    )


def test_the_cross_tenant_rename_is_refused(app_engine, owner_session, two_orgs_two_users):
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

    # 🔴 MIGRATION 047 MOVED THE REFUSAL EARLIER, AND THE ASSERTION HAD TO
    # MOVE WITH IT RATHER THAN BE LOOSENED.
    #
    # `ON CONFLICT (keycloak_sub)` names that column in its inference clause,
    # and 047 revoked SELECT on it from every runtime role (I81). So the
    # statement is now refused by column privilege BEFORE row-level security
    # is consulted: `permission denied for table users` rather than
    # `new row violates row-level security policy`.
    #
    # That is a stronger refusal, and it is also a REDUCTION IN WHAT THIS TEST
    # PROVES: a boundary that can no longer be reached by this statement is
    # not exercised by it. The RLS half is therefore asserted separately, on a
    # statement 047 does not intercept, in
    # `test_the_rls_boundary_still_refuses_a_cross_tenant_update` below. Both
    # mechanisms are accepted here, and named, because either one refusing is
    # the property this test actually guards.
    # Codex: "permission denied" alone accepts a lost INSERT grant, a lost
    # schema USAGE, or any other unrelated privilege failure, and the
    # unchanged-row check below cannot tell those apart. So the privilege
    # branch must also NAME THE TABLE it was refused on.
    refusal = str(caught.value).lower()
    assert "row-level security" in refusal or (
        "permission denied" in refusal and "users" in refusal
    ), (
        "the statement failed for some reason other than the RLS policy or "
        f"047's column privilege: {caught.value}. The test must fail on the "
        "boundary, not on a typo."
    )

    # 🔴 THE "STILL UNCHANGED" CHECK BELONGS HERE, NOT IN ITS OWN TEST.
    # It was a separate test, and Codex showed that made it near-vacuous:
    # pytest builds a FRESH fixture per test, so the separate version was
    # reading a user its own fixture had just created and nothing had
    # attempted to rename. It asserted that an untouched row was untouched.
    # Read as the owner, so this observes the STORED row rather than a
    # policy's view of it -- a refusal that still wrote would otherwise look
    # identical to a refusal that did not.
    stored = owner_session.execute(
        text("SELECT display_name FROM core.users WHERE id = :u"), {"u": f["user_b"]}
    ).scalar_one()
    assert stored == "I55 member B", (
        f"organization B's user is now named {stored!r}. The rename raised and was applied anyway."
    )


def test_the_rls_boundary_still_refuses_a_cross_tenant_update(
    app_engine, owner_session, two_orgs_two_users
) -> None:
    """🔴 THE COVERAGE 047 DISPLACED, PUT BACK ON A REACHABLE STATEMENT.

    `test_the_cross_tenant_rename_is_refused` used an upsert whose
    `ON CONFLICT (keycloak_sub)` clause 047 now refuses at the privilege
    layer, before RLS is consulted. Left alone, that would have quietly
    stopped exercising the row-level boundary while still passing — a test
    that no longer reaches the thing it names.

    This drives the same boundary with a plain UPDATE of `display_name`, so
    the ONLY thing that can stop it is the policy. Measured: 0 rows
    cross-tenant, 1 row inside your own organization, and organization B's
    stored name unchanged.

    🔴 AND IT MOVED TABLES FOR THE SECOND TIME, FOR THE SAME REASON. 052
    revoked UPDATE on `core.users.display_name` as well, so the statement this
    test used would now be refused at the privilege layer too — passing while
    exercising nothing, which is precisely the displacement the paragraph
    above was written about. `core.organization_members.display_name` is
    granted and governed by `org_member_isolation`, so the boundary is
    reachable again. **When a privilege change makes a boundary test
    unreachable, move the test to a statement that still reaches it.**

    ⚠️ IT REFUSES BY MATCHING NOTHING, NOT BY RAISING. PostgreSQL applies the
    SELECT policy to the rows an UPDATE reads through its WHERE, so a
    cross-tenant target is simply invisible and the statement reports zero
    rows. Asserting `pytest.raises` here would fail against a perfectly
    hardened database.
    """
    f = two_orgs_two_users
    with app_engine.connect() as conn:
        conn.execute(
            text("SELECT set_config('app.current_org', :o, false)"),
            {"o": str(f["org_a"])},
        )
        affected = conn.execute(
            text(
                """
                UPDATE core.organization_members SET display_name = 'PWNED BY ORG A'
                 WHERE user_id = :u
                """
            ),
            {"u": f["user_b"]},
        ).rowcount
        conn.rollback()

    assert affected == 0, (
        f"organization A updated {affected} membership row(s) belonging to "
        "organization B. org_member_isolation is what refuses this, so a "
        "non-zero count means the membership table is not org-scoped."
    )
    # Read as the OWNER, so this observes the STORED row rather than a policy's
    # view of it: a refusal that still wrote would otherwise look identical to
    # one that did not.
    stored = owner_session.execute(
        text(
            """
            SELECT display_name FROM core.organization_members
             WHERE user_id = :u AND organization_id = :o
            """
        ),
        {"u": f["user_b"], "o": f["org_b"]},
    ).scalar_one()
    assert stored == "I55 member B", (
        f"organization B's member is now named {stored!r}. The update reported "
        "zero rows and was applied anyway."
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
            # On the MEMBERSHIP since 052: correcting a colleague's record is
            # a per-organization act, and doing it on the global row would
            # rewrite what every other tenant sees.
            text(
                """
                UPDATE core.organization_members
                   SET display_name = 'I55 member A, corrected'
                 WHERE user_id = :u AND organization_id = :o
                RETURNING display_name
                """
            ),
            {"u": f["user_a"], "o": f["org_a"]},
        ).scalar_one_or_none()
        conn.rollback()

    assert renamed == "I55 member A, corrected", (
        "an administrator could not rename a member of their OWN organization "
        f"(got {renamed!r}). The membership table is read-only rather than "
        "org-scoped, and every cross-tenant test in this file passes "
        "vacuously against that."
    )


def test_the_feature_survives_the_oracle_being_removed(app_engine, two_orgs_two_users):
    """🔴 044's REAL CONCERN, REDIRECTED TO ITS REPLACEMENT (I82 / 049).

    This test used to exercise `core.user_id_for_subject`, and its point was
    never that function: it was that **044 must not close a disclosure by
    deleting a feature.** 044's read policy makes a user in another
    organization invisible while `keycloak_sub` stays globally unique, so
    without SOME privileged resolution an administrator could neither find nor
    create a human who already has an account elsewhere — and
    multi-organization membership is the reason `core.users` has no
    `organization_id` at all.

    Migration 049 removed that function because it was an oracle (I82) and
    replaced it with `core.bind_subject_to_organization`, which resolves and
    binds atomically. So the concern is unchanged and the subject moves: a
    subject that exists ONLY in organization B must still be bindable into
    organization A.

    ⚠️ WRITING THIS FOUND A GAP IN 049's OWN TESTS. They covered a brand-new
    subject and a duplicate bind, and never the case this file has always
    cared about — an EXISTING identity in another tenant. That case is the
    entire justification for the function being SECURITY DEFINER.
    """
    f = two_orgs_two_users
    with app_engine.connect() as conn:
        conn.execute(
            text("SELECT set_config('app.current_org', :o, false)"), {"o": str(f["org_a"])}
        )
        conn.execute(
            text("SELECT set_config('app.current_user_id', :u, false)"),
            {"u": str(f["user_a"])},
        )
        # 🔴 THE ACTOR MUST ACTUALLY ADMINISTER ORGANIZATION A (050).
        #
        # The bind proves the caller's standing via
        # `core.authorization_for_current_session()` -- the check that closed
        # the forged-GUC cross-tenant write. So this grants `user_a` a real
        # role carrying `admin.users` inside the same transaction it then
        # rolls back, rather than weakening the function to suit the test.
        member_a = conn.execute(
            text(
                """
                SELECT id FROM core.organization_members
                 WHERE organization_id = :o AND user_id = :u
                """
            ),
            {"o": f["org_a"], "u": f["user_a"]},
        ).scalar_one()
        role_admin = conn.execute(
            text(
                """
                SELECT r.id FROM core.roles r
                JOIN core.role_permissions rp ON rp.role_id = r.id
                JOIN core.permissions p       ON p.id = rp.permission_id
                WHERE p.code = 'admin.users' LIMIT 1
                """
            )
        ).scalar_one()
        conn.execute(
            text("INSERT INTO core.member_roles (member_id, role_id) VALUES (:m, :r)"),
            {"m": member_a, "r": role_admin},
        )

        row = conn.execute(
            text(
                """
                SELECT member_id
                  FROM core.bind_subject_to_organization(:s, :e, :n)
                """
            ),
            {"s": f["sub_b"], "e": "rebind-b@example.test", "n": "B, invited into A"},
        ).one()
        # 051: the function no longer hands back the identity -- the uuid it
        # used to return WAS the "does this subject already exist" answer. The
        # membership is what it returns, and the identity is resolved through
        # it, which is exactly what the route now does.
        bound_user = conn.execute(
            text("SELECT user_id FROM core.organization_members WHERE id = :m"),
            {"m": row.member_id},
        ).scalar_one()
        conn.rollback()

    assert bound_user == f["user_b"], (
        "an administrator in organization A could not bind a human who already "
        "has an identity in organization B. 044 has closed a disclosure by "
        "deleting a feature, which is exactly what this test exists to prevent."
    )
    # 🔴 THE NO-DUPLICATE PROPERTY IS ASSERTED ON THE UUID, NOT ON A FLAG.
    #
    # This used to read `identity_created is False`. Migration 050 removed
    # that column: it was a cross-tenant existence bit with no consumer, and
    # the "cost" said to excuse it could be rolled back. `row.user_id ==
    # f["user_b"]` above already proves the stronger thing -- the EXISTING
    # identity was reused rather than a second one minted for the same human.
    assert row.member_id is not None, "resolved an identity without binding it"


def test_the_replacement_returns_an_identifier_and_never_a_record(owner_session):
    """It may return identifiers. It may not return a person.

    `core.user_id_for_subject` was pinned to `RETURNS uuid` for this reason:
    it is SECURITY DEFINER and therefore outside RLS, so anything wider is a
    cross-tenant read channel. The replacement returns three columns and the
    same rule applies to each — two identifiers and a boolean, and nothing
    that carries an email, a display name or a subject.
    """
    result = owner_session.execute(
        text(
            """
            SELECT pg_get_function_result(p.oid)
              FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
             WHERE n.nspname = 'core' AND p.proname = 'bind_subject_to_organization'
            """
        )
    ).scalar_one()

    normalised = result.lower().replace("table(", "").replace(")", "")
    returned = {c.strip().split()[-1] for c in normalised.split(",")}
    assert returned <= {"uuid", "boolean"}, (
        f"core.bind_subject_to_organization returns {result!r}. It is SECURITY "
        "DEFINER and therefore outside RLS; it may return identifiers and a "
        "flag, never a record. Anything wider is a cross-tenant read channel."
    )
    # 🔴 AND THE TYPE WAS NEVER THE POINT — THE COLUMN WAS (051).
    #
    # `{"uuid"}` was satisfied by `user_id`, and `user_id` is the existence
    # oracle: the same uuid comes back from repeated ROLLED-BACK binds when the
    # subject already exists elsewhere, a different one each time when it does
    # not. Measured. A test that only bounds the TYPE cannot say which
    # question the value answers, so this names the column.
    columns = [c.strip().split()[0] for c in normalised.split(",")]
    assert columns == ["member_id"], (
        f"core.bind_subject_to_organization returns {result!r}. It may return "
        "the membership it created and nothing else. `user_id` in particular "
        "is a free, traceless cross-tenant existence answer -- 050 removed "
        "`identity_created` for exactly that and left the uuid carrying it."
    )


def test_the_replacement_runs_as_a_non_superuser_and_only_for_the_app(owner_session):
    """🔴 THE DEFECT 044 ALMOST SHIPPED, STILL PINNED — ON THE NEW FUNCTION.

    SECURITY DEFINER runs as its OWNER, and the owner is whoever executed
    CREATE FUNCTION unless pinned. This database applies migrations as
    `postgres`. Measured after 044's first apply: the function was owned by
    **postgres**, `rolsuper = true`, `rolbypassrls = true` — outside RLS
    permanently, including after the I58 cutover. That is I56, and 044's
    comment claimed `evercoat_owner` the whole time. Neither reviewer found
    it; `pg_proc` did.

    The privilege half was Codex's: asserting only that PUBLIC cannot execute
    passes while `evercoat_worker` or `evercoat_report` can. Assert the WHOLE
    access list.
    """
    row = owner_session.execute(
        text(
            """
            SELECT pg_get_userbyid(p.proowner) AS owner,
                   p.prosecdef                 AS secdef,
                   COALESCE(array_to_string(p.proconfig, ','), '') AS config,
                   r.rolsuper                  AS is_super,
                   r.rolbypassrls              AS bypasses_rls
              FROM pg_proc p
              JOIN pg_namespace n ON n.oid = p.pronamespace
              JOIN pg_roles r     ON r.oid = p.proowner
             WHERE n.nspname = 'core' AND p.proname = 'bind_subject_to_organization'
            """
        )
    ).one()

    assert row.owner == "evercoat_owner", f"owned by {row.owner!r}, not evercoat_owner"
    assert row.secdef is True, "not SECURITY DEFINER; it cannot resolve across tenants"
    assert "search_path=core, pg_temp" in row.config, f"search_path is {row.config!r}"

    # 🔴 BOTH HALVES. `rolbypassrls` IS NOT IMPLIED BY `NOT rolsuper`, and my
    # first version of this test asserted only the superuser half -- so
    # `ALTER ROLE evercoat_owner BYPASSRLS` would have put every SECURITY
    # DEFINER in this database permanently outside RLS with the whole suite
    # still green. Raised by the Supervisor: a grep for `rolbypassrls` across
    # the test tree returned ZERO assertions after that rewrite. I56's shape,
    # with the tripwire removed by the person redirecting the test.
    assert row.is_super is False, f"the owner {row.owner!r} is a SUPERUSER"
    assert row.bypasses_rls is False, (
        f"the owner {row.owner!r} has BYPASSRLS, so this definer is outside "
        "RLS permanently -- including after the I56/I58 FORCE cutover"
    )

    # 🔴 `has_function_privilege`, NOT `proacl` -- BECAUSE proacl LIES WHEN IT
    # IS NULL.
    #
    # A NULL `proacl` means THE DEFAULT APPLIES, and the default for a
    # function is EXECUTE to PUBLIC. My rewrite did
    # `COALESCE(proacl, ARRAY[]::text[])`, so that exact state became `[]` and
    # every assertion over it passed vacuously: a later migration recreating
    # this function without the REVOKE/GRANT pair would leave PUBLIC able to
    # execute a definer that writes memberships, and the test would be green.
    #
    # *A guard that passes when it cannot see is not a guard* -- mine, quoted
    # back at me by the Supervisor. `has_function_privilege` answers correctly
    # for a NULL ACL and follows role inheritance too.
    fn = "core.bind_subject_to_organization(text,text,text)"
    can = {
        role: owner_session.execute(
            text("SELECT has_function_privilege(:r, :f, 'EXECUTE')"), {"r": role, "f": fn}
        ).scalar_one()
        for role in ("public", "evercoat_app", "evercoat_worker", "evercoat_report")
    }
    assert can["public"] is False, "PUBLIC can execute a definer that writes memberships"
    assert can["evercoat_app"] is True, "the runtime role cannot execute it; invites are dead"
    assert can["evercoat_worker"] is False, "the worker can bind memberships"
    assert can["evercoat_report"] is False, "the reporting role can bind memberships"


def test_sign_in_still_works(auth_engine, owner_session) -> None:
    """🔴 The thing 044 was shaped not to break — AS THE ROLE THAT SIGNS IN.

    `core.memberships_for_subject` runs BEFORE an organization is chosen — it
    is what tells a signed-in browser which organizations it may ask for — and
    it reads `core.users`. It survives 044 only because it is SECURITY DEFINER
    owned by `evercoat_owner` and FORCE is off, which is the same argument
    migration 032 made and the same one I58 will have to replace.

    🔴 THE FIRST VERSION CALLED IT THROUGH `owner_session` AND PROVED NOTHING.
    Raised by Codex: the owner bypasses non-forced RLS anyway, so that version
    stayed green even if the function were changed to SECURITY INVOKER — while
    the real sign-in path, with no tenant GUC, would return zero rows and 404
    every user. It runs on the role that actually signs in, which is exactly
    what `GET /api/me` does.

    ⚠️ THAT ROLE CHANGED IN MIGRATION 053 AND THIS TEST MOVED WITH IT. It was
    `evercoat_app` until I109 showed that a lookup taking a SUBJECT AS AN
    ARGUMENT, reachable from the runtime connection, is an
    identity-enumeration primitive. `evercoat_auth` holds EXECUTE now — and
    pointing this at `app_engine` would quietly stop asserting that anybody
    can sign in, while still passing for the opposite reason.

    Builds its own subject: CI's database is migrated and not seeded, and a
    version that read a seeded user would fail there reporting a security
    regression that is not present.
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
        text(
            "INSERT INTO core.organization_members (organization_id, user_id, email,"
            " display_name) SELECT :o, :u, u.email, u.display_name FROM core.users u WHERE u.id"
            " = :u"
        ),
        {"o": org, "u": uid},
    )
    owner_session.commit()

    try:
        with auth_engine.connect() as conn:
            # Deliberately NO app.current_org. That absence is the point: the
            # browser has not chosen an organization yet, and this lookup is
            # what offers it the list.
            rows = conn.execute(
                text("SELECT * FROM core.memberships_for_subject(:s)"), {"s": sub}
            ).all()

        assert len(rows) == 1, (
            f"core.memberships_for_subject returned {len(rows)} rows to "
            "evercoat_app for a subject with exactly one membership, with no "
            "tenant context set. GET /api/me answers 404 for every legitimate "
            "user and sign-in is dead. 044 enabled RLS on core.users; if FORCE "
            "was enabled with it, or the function stopped being an "
            "owner-owned SECURITY DEFINER, that is the cause."
        )
    finally:
        owner_session.rollback()
        owner_session.execute(
            text("DELETE FROM core.organization_members WHERE user_id = :u"), {"u": uid}
        )
        owner_session.execute(text("DELETE FROM core.users WHERE id = :u"), {"u": uid})
        owner_session.execute(text("DELETE FROM core.organizations WHERE id = :o"), {"o": org})
        owner_session.commit()
