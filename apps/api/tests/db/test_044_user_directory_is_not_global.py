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
                SELECT om.id, u.display_name
                  FROM core.organization_members om
                  JOIN core.users u ON u.id = om.user_id
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

    This drives the same boundary with a plain UPDATE of `display_name`,
    which 047 leaves granted, so the ONLY thing that can stop it is the
    policy. Measured: 0 rows cross-tenant, 1 row inside your own
    organization, and organization B's stored name unchanged.

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
            text("UPDATE core.users SET display_name = 'PWNED BY ORG A' WHERE id = :u"),
            {"u": f["user_b"]},
        ).rowcount
        conn.rollback()

    assert affected == 0, (
        f"organization A updated {affected} row(s) belonging to organization B. "
        "The read policy is what refuses this -- see migration 044's COMMENT -- "
        "so a non-zero count means core.users is not org-scoped."
    )
    stored = owner_session.execute(
        text("SELECT display_name FROM core.users WHERE id = :u"), {"u": f["user_b"]}
    ).scalar_one()
    assert stored == "I55 member B", (
        f"organization B's user is now named {stored!r}. The update reported "
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


def test_the_binding_lookup_runs_as_a_non_superuser_and_only_for_the_app(owner_session):
    """🔴 THE DEFECT THIS MIGRATION ALMOST SHIPPED, PINNED AS A TEST.

    `core.user_id_for_subject` is SECURITY DEFINER, which means it runs as its
    OWNER. The owner is whoever executed `CREATE FUNCTION` unless it is pinned,
    and this database applies migrations as `postgres`. Measured after the
    first apply: the function was owned by **postgres**, `rolsuper = true`,
    `rolbypassrls = true` -- outside RLS permanently, including after the I58
    FORCE cutover. That is I56, and migration 044's comment claimed
    `evercoat_owner` the whole time. Migration 033 had already written the rule
    three migrations earlier.

    Neither reviewer found it; `pg_proc` did.

    The privilege half was raised by Codex separately: asserting only that
    PUBLIC cannot execute passes while `evercoat_worker` or `evercoat_report`
    can. Assert the WHOLE access list.
    """
    owner, secdef, volatility, config = owner_session.execute(
        text(
            """
            SELECT pg_get_userbyid(p.proowner), p.prosecdef, p.provolatile,
                   COALESCE(array_to_string(p.proconfig, ','), '')
              FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
             WHERE n.nspname = 'core' AND p.proname = 'user_id_for_subject'
            """
        )
    ).one()

    assert owner == "evercoat_owner", (
        f"core.user_id_for_subject is owned by {owner!r}. SECURITY DEFINER runs "
        "as the owner; migration 044 must pin it with ALTER FUNCTION ... OWNER TO."
    )

    is_super = owner_session.execute(
        text("SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname = :r"),
        {"r": owner},
    ).scalar_one()
    assert is_super is False, (
        f"core.user_id_for_subject runs as {owner!r}, which is a superuser or "
        "holds BYPASSRLS. A definer owned by such a role is outside RLS "
        "permanently -- I56, and the reason I58 has to re-owner all four."
    )

    assert secdef is True, "the function is no longer SECURITY DEFINER"
    assert volatility == "s", (
        f"volatility is {volatility!r}, not STABLE. A VOLATILE definer can be "
        "given side effects without this test noticing."
    )
    assert "search_path=core, pg_temp" in config, (
        f"proconfig is {config!r}. A SECURITY DEFINER function without a pinned "
        "search_path can be redirected by a caller-controlled schema."
    )

    # The COMPLETE access list, not just PUBLIC. Only the owner and the runtime
    # role may execute it; `evercoat_worker`, `evercoat_report` and
    # `evercoat_breakglass` must not.
    grantees = set(
        owner_session.execute(
            text(
                """
                SELECT r.rolname
                  FROM pg_roles r
                 WHERE has_function_privilege(
                           r.rolname, 'core.user_id_for_subject(text)', 'EXECUTE')
                   AND NOT r.rolsuper
                """
            )
        )
        .scalars()
        .all()
    )
    assert grantees == {"evercoat_owner", "evercoat_app"}, (
        f"core.user_id_for_subject is executable by {sorted(grantees)}. It is "
        "SECURITY DEFINER and reads across every tenant by design; only the "
        "runtime role may call it."
    )

    public_can = owner_session.execute(
        text("SELECT has_function_privilege('public', 'core.user_id_for_subject(text)', 'EXECUTE')")
    ).scalar_one()
    assert public_can is False, (
        "core.user_id_for_subject is executable by PUBLIC -- the same finding "
        "migration 035 had to fix for principal_for_subject after it shipped."
    )


def test_sign_in_still_works(app_engine, owner_session) -> None:
    """🔴 The thing 044 was shaped not to break — AS THE ROLE THAT SIGNS IN.

    `core.memberships_for_subject` runs BEFORE an organization is chosen — it
    is what tells a signed-in browser which organizations it may ask for — and
    it reads `core.users`. It survives 044 only because it is SECURITY DEFINER
    owned by `evercoat_owner` and FORCE is off, which is the same argument
    migration 032 made and the same one I58 will have to replace.

    🔴 THE FIRST VERSION CALLED IT THROUGH `owner_session` AND PROVED NOTHING.
    Raised by Codex: the owner bypasses non-forced RLS anyway, so that version
    stayed green even if the function were changed to SECURITY INVOKER — while
    the real sign-in path, `evercoat_app` with no tenant GUC, would return zero
    rows and 404 every user. It now runs on `app_engine`, with no GUC, which is
    exactly what `GET /api/me` does.

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
        text("INSERT INTO core.organization_members (organization_id, user_id) VALUES (:o, :u)"),
        {"o": org, "u": uid},
    )
    owner_session.commit()

    try:
        with app_engine.connect() as conn:
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
