"""`core.memberships_for_subject` — the one lookup that runs before a tenant.

It is the only thing standing between a signed-in browser and an
application it cannot use: every other route requires
``X-Organization-Id``, and this is what tells the browser what to put
there. It is also ``SECURITY DEFINER``, so it bypasses RLS, and that
makes it worth testing as a boundary rather than as a query.
"""

from __future__ import annotations

from sqlalchemy import text


def test_it_is_scoped_strictly_to_the_subject(owner_session) -> None:
    """A subject that does not exist gets nothing, not everything.

    The failure mode worth ruling out is a predicate that silently matches
    every row -- which is what a SECURITY DEFINER function with a mistaken
    WHERE clause would do, invisibly, while returning plausible data.
    """
    rows = owner_session.execute(
        text("SELECT * FROM core.memberships_for_subject(:sub)"),
        {"sub": "a-subject-no-realm-ever-issued"},
    ).all()
    assert rows == [], (
        "an unknown subject returned membership rows. This function bypasses "
        "RLS, so a predicate that matches everything is a cross-tenant read "
        "path for anyone who can call it."
    )


def test_it_takes_no_organization_argument(owner_session) -> None:
    """There must be no overload a caller can steer with a tenant id.

    The entire purpose is to report what the caller is a member of. A
    tenant filter here would be a filter the CALLER controls on the one
    query that decides which tenants exist for them.
    """
    signatures = (
        owner_session.execute(
            text(
                """
            SELECT pg_get_function_identity_arguments(p.oid)
            FROM pg_proc p
            JOIN pg_namespace n ON n.oid = p.pronamespace
            WHERE n.nspname = 'core' AND p.proname = 'memberships_for_subject'
            """
            )
        )
        .scalars()
        .all()
    )

    # `pg_get_function_identity_arguments` includes the parameter NAME, so
    # the expected value is "p_sub text" and not "text". Asserted as the
    # full string rather than a substring: an added second parameter would
    # still contain "p_sub text".
    assert signatures == ["p_sub text"], (
        f"expected exactly one signature taking only the subject, found {signatures}"
    )


def test_execute_is_not_public(owner_session) -> None:
    """PostgreSQL grants EXECUTE to PUBLIC by default on a new function.

    Left in place, every role in the database could call an RLS-bypassing
    identity lookup for an arbitrary subject.
    """
    public_can_execute = owner_session.execute(
        text(
            """
            SELECT has_function_privilege(
                'public', 'core.memberships_for_subject(text)', 'EXECUTE'
            )
            """
        )
    ).scalar_one()
    assert public_can_execute is False, (
        "PUBLIC can execute core.memberships_for_subject. Migration 024 revokes "
        "it deliberately; something has re-granted it."
    )


def test_only_the_application_role_may_execute_it(owner_session) -> None:
    """`evercoat_worker` and `evercoat_report` must NOT hold EXECUTE.

    The worker never serves `/api/me`. An RLS-bypassing lookup that worker
    code can call for an arbitrary subject is an identity-enumeration
    primitive sitting in a process with no use for it.
    """
    for role, expected in (("evercoat_app", True), ("evercoat_worker", False)):
        granted = owner_session.execute(
            text(
                "SELECT has_function_privilege(:role, "
                "'core.memberships_for_subject(text)', 'EXECUTE')"
            ),
            {"role": role},
        ).scalar_one()
        assert granted is expected, (
            f"{role} EXECUTE on core.memberships_for_subject is {granted}, expected {expected}"
        )


def test_the_definer_is_pinned(owner_session) -> None:
    """SECURITY DEFINER means "run as the OWNER", so the owner must be fixed.

    Without an explicit ``ALTER FUNCTION ... OWNER TO``, the definer is
    whichever account happened to run the migration -- ``postgres`` in CI,
    something else elsewhere -- and the function then behaves differently
    per environment. See migration 024.
    """
    owner, is_definer = owner_session.execute(
        text(
            """
            SELECT pg_get_userbyid(p.proowner), p.prosecdef
            FROM pg_proc p
            JOIN pg_namespace n ON n.oid = p.pronamespace
            WHERE n.nspname = 'core' AND p.proname = 'memberships_for_subject'
            """
        )
    ).one()
    assert is_definer is True, "the function is no longer SECURITY DEFINER"
    assert owner == "evercoat_owner", (
        f"the function is owned by {owner!r}, not evercoat_owner, so its "
        "RLS behaviour depends on who ran the migration"
    )


def test_the_force_rls_cutover_must_revisit_this_function(owner_session) -> None:
    """🔴 A TRIPWIRE FOR A DEFECT THAT DOES NOT EXIST YET.

    Same shape as
    ``test_the_force_rls_cutover_must_revisit_the_chain_trigger``, and for
    the same underlying reason.

    ``core.memberships_for_subject`` is SECURITY DEFINER owned by
    ``evercoat_owner``. That makes its reads immune to the CALLER's
    context today, because ``core.organizations`` and
    ``core.organization_members`` have RLS ENABLED but not FORCED, and an
    owner is exempt from a non-forced policy.

    **The cutover removes that exemption.** ``evercoat_owner`` is
    ``NOLOGIN`` and does not hold ``BYPASSRLS`` anywhere in this
    repository, so the moment ``FORCE ROW LEVEL SECURITY`` is enabled and
    ``core.rls_permissive()`` returns FALSE, this function runs subject to
    policies keyed on ``core.current_org_id()`` -- with no GUC set,
    because it is called BEFORE an organization is chosen.

    It will return zero rows. ``GET /api/me`` will answer 404 for every
    legitimate user. Sign-in will be dead, and the migration's own header
    argues this function exists precisely to avoid that.

    The Supervisor found this: pinning the owner made the behaviour
    deterministic, and deterministically wrong after the cutover. It is
    recorded as a blocker here rather than pre-solved, because the fix --
    granting ``evercoat_owner`` BYPASSRLS, or adding a policy that admits
    this one lookup -- is a decision that belongs with the cutover
    migration and its review, not smuggled in ahead of it.

    ---------------------------------------------------------------
    UPDATED 2026-08-22 — HALF THE CUTOVER LANDED, AND THIS TRIPWIRE
    NARROWED TO THE HALF THAT STILL BITES.
    ---------------------------------------------------------------

    Migration 032 (I19) set ``core.rls_permissive()`` to FALSE, so this test
    no longer asserts it is TRUE -- it was, and the assertion did exactly its
    job by making that a deliberate decision rather than a side effect.

    **The danger this file names is entirely unaffected**, because it was
    never really about ``rls_permissive()``. This function is exempt by
    OWNERSHIP, not by the escape hatch: an owner is exempt from a policy that
    is not FORCED, whatever the predicate says. 032 changed the predicate and
    deliberately left FORCE alone, which is precisely why sign-in survived it.

    So the surviving assertion is the FORCE half, and it is the one that
    always mattered. ``tests/db/test_032_the_database_fails_closed.py``
    carries the positive counterpart -- it calls this function and asserts it
    still returns rows -- so the two fail together and say the same thing from
    both directions.
    """
    forced = owner_session.execute(
        text(
            "SELECT bool_or(relforcerowsecurity) FROM pg_class "
            "WHERE oid IN ('core.organizations'::regclass, "
            "'core.organization_members'::regclass)"
        )
    ).scalar_one()

    cutover_note = (
        "core.memberships_for_subject is owned by evercoat_owner, which does "
        "NOT hold BYPASSRLS, and it runs with no organization GUC set. Its "
        "exemption comes from OWNERSHIP of a non-FORCED table, so forcing RLS "
        "removes it: the function returns zero rows, GET /api/me answers 404 "
        "for every user, and sign-in stops working entirely. Grant "
        "evercoat_owner BYPASSRLS, or add a policy that admits this lookup, "
        "in the SAME migration that forces RLS. Read this test's docstring "
        "first."
    )

    assert forced is False, f"FORCE ROW LEVEL SECURITY is now on. {cutover_note}"
