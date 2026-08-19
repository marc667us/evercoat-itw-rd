"""MSD's authorization boundary.

🔴 THE ONE AI RULE THAT CANNOT BE TAKEN ON TRUST.

`CLAUDE.md` §7: "MSD operates under EXACTLY the calling user's
authorization boundary... Filter retrieval before the model sees
anything — never filter after generation. AI must never become a
permission-bypass channel."

Every test here runs on `app_session` — the runtime role, subject to
RLS — and NOT on `owner_session`. That is not a stylistic preference: the
owner is exempt from RLS while `relforcerowsecurity` is FALSE, so this
entire file would pass against a system with no boundary at all if it
used the owner. The distinction is the test.

The fixture COMMITS, because `app_session` is a different connection and
cannot see uncommitted rows — a suite that forgot that would report the
boundary working when the data was simply never there.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.domains.msd.retrieval import (
    retrieve_for_question,
    verify_evidence_within_boundary,
)


@pytest.fixture
def two_projects(owner_session: Session, app_session: Session) -> Iterator[dict[str, uuid.UUID]]:
    """One organization, two projects — one NORMAL and one RESTRICTED —
    each holding a formula whose name contains the same search term.

    The same term on purpose. A retrieval that returned only the normal
    project's row because the search happened not to match the other
    would prove nothing; both must match, so the only thing that can
    exclude one is the boundary.
    """
    suffix = uuid.uuid4().hex[:8]
    term = f"lightweight{suffix}"

    org = owner_session.execute(
        text("INSERT INTO core.organizations (code, name) VALUES (:c, :n) RETURNING id"),
        {"c": f"MSD-{suffix}", "n": "MSD Boundary Org"},
    ).scalar_one()

    outsider = owner_session.execute(
        text(
            """
            INSERT INTO core.users (keycloak_sub, email, display_name)
            VALUES (:s, :e, 'Outsider') RETURNING id
            """
        ),
        {"s": str(uuid.uuid4()), "e": f"outsider-{suffix}@example.test"},
    ).scalar_one()
    owner_session.execute(
        text(
            """
            INSERT INTO core.organization_members (organization_id, user_id, status)
            VALUES (:o, :u, 'active')
            """
        ),
        {"o": org, "u": outsider},
    )

    ids: dict[str, uuid.UUID] = {"org": org, "outsider": outsider}

    for label, confidentiality in (("normal", "normal"), ("restricted", "restricted")):
        project = owner_session.execute(
            text(
                """
                INSERT INTO projects.projects
                    (organization_id, project_code, name, confidentiality)
                VALUES (:o, :c, :n, :conf) RETURNING id
                """
            ),
            {
                "o": org,
                "c": f"RDP-{label[:1].upper()}-{suffix}",
                "n": f"{label} project",
                "conf": confidentiality,
            },
        ).scalar_one()

        formula = owner_session.execute(
            text(
                """
                INSERT INTO formulations.formulas
                    (organization_id, project_id, formula_code, name, owner_user_id,
                     created_by)
                VALUES (:o, :p, :c, :n, :u, :u) RETURNING id
                """
            ),
            {
                "o": org,
                "p": project,
                "c": f"FRM-{label[:1].upper()}-{suffix}",
                # Both names carry the search term.
                "n": f"{term} putty",
                "u": outsider,
            },
        ).scalar_one()

        version = owner_session.execute(
            text(
                """
                INSERT INTO formulations.formula_versions
                    (organization_id, project_id, formula_id, version_number,
                     version_code, status, created_by)
                VALUES (:o, :p, :f, 1, :vc, 'draft', :u) RETURNING id
                """
            ),
            {
                "o": org,
                "p": project,
                "f": formula,
                "vc": f"FRM-{label[:1].upper()}-{suffix}-V1",
                "u": outsider,
            },
        ).scalar_one()

        ids[f"{label}_project"] = project
        ids[f"{label}_version"] = version

    owner_session.commit()
    ids["term"] = term  # type: ignore[assignment]

    yield ids

    app_session.rollback()
    owner_session.begin()
    owner_session.execute(
        text("DELETE FROM ai.msd_evidence WHERE organization_id = :o"), {"o": org}
    )
    owner_session.execute(text("DELETE FROM ai.msd_turns WHERE organization_id = :o"), {"o": org})
    owner_session.execute(text("DELETE FROM ai.msd_threads WHERE organization_id = :o"), {"o": org})
    owner_session.execute(
        text("DELETE FROM formulations.formula_versions WHERE organization_id = :o"), {"o": org}
    )
    owner_session.execute(
        text("DELETE FROM formulations.formulas WHERE organization_id = :o"), {"o": org}
    )
    owner_session.execute(
        text("DELETE FROM projects.projects WHERE organization_id = :o"), {"o": org}
    )
    owner_session.execute(
        text("DELETE FROM core.organization_members WHERE organization_id = :o"), {"o": org}
    )
    owner_session.execute(text("DELETE FROM core.users WHERE id = :u"), {"u": outsider})
    owner_session.execute(text("DELETE FROM core.organizations WHERE id = :o"), {"o": org})
    owner_session.commit()


def _scope(session: Session, org: uuid.UUID, user: uuid.UUID) -> None:
    session.execute(text("SELECT set_config('app.current_org', :o, true)"), {"o": str(org)})
    session.execute(text("SELECT set_config('app.current_user_id', :u, true)"), {"u": str(user)})


def test_msd_cannot_retrieve_a_restricted_project_the_asker_is_not_in(
    app_session: Session, two_projects: dict[str, uuid.UUID]
) -> None:
    """🔴 THE TEST THIS WHOLE MODULE EXISTS FOR.

    Two formulas match the search term identically. One is in a normal
    project, one in a restricted project the asker does not belong to.
    Retrieval must return the first and never the second — and not
    because this code filtered it, but because the database never handed
    it over.

    If this fails, MSD is a permission-bypass channel and §7 is violated
    at its most important point.
    """
    fx = two_projects
    _scope(app_session, fx["org"], fx["outsider"])

    found = retrieve_for_question(
        app_session,
        organization_id=fx["org"],
        question=str(fx["term"]),
        entity_types=("formula_version",),
    )

    returned = {r.entity_id for r in found}

    assert fx["normal_version"] in returned, (
        "retrieval returned nothing from the project the asker CAN see — the search "
        "term is wrong and this test proves nothing"
    )
    assert fx["restricted_version"] not in returned, (
        "MSD retrieved a formula version from a restricted project the asker is not a "
        "member of. This is the permission-bypass channel §7 forbids."
    )


def test_membership_makes_the_restricted_project_visible(
    owner_session: Session, app_session: Session, two_projects: dict[str, uuid.UUID]
) -> None:
    """Verified in BOTH directions.

    A retrieval that returned nothing at all would pass the test above
    while making MSD useless. Adding the asker to the restricted project
    must make its formula retrievable — the boundary is the user's, not a
    blanket exclusion.
    """
    fx = two_projects

    owner_session.begin()
    owner_session.execute(
        text(
            """
            INSERT INTO projects.project_members
                (organization_id, project_id, user_id, project_role)
            -- 'chemist', not 'contributor'. The allowed roles are
            -- ('lead','chemist','engineer','technician','qa','director',
            -- 'observer') -- migration 001 line 300. Read this time
            -- rather than guessed: the same guess cost a full CI round
            -- trip on `criticality` an hour ago.
            VALUES (:o, :p, :u, 'chemist')
            ON CONFLICT DO NOTHING
            """
        ),
        {"o": fx["org"], "p": fx["restricted_project"], "u": fx["outsider"]},
    )
    owner_session.commit()

    _scope(app_session, fx["org"], fx["outsider"])
    found = retrieve_for_question(
        app_session,
        organization_id=fx["org"],
        question=str(fx["term"]),
        entity_types=("formula_version",),
    )

    assert fx["restricted_version"] in {r.entity_id for r in found}, (
        "a project member could not retrieve their own project's formula; the "
        "boundary is excluding too much"
    )


def test_retrieval_takes_no_user_id_it_could_impersonate() -> None:
    """The signature is part of the guarantee.

    `retrieve_for_question` takes a SESSION and no `user_id`. A user
    parameter would invite a caller to pass somebody else's, and there is
    no honest reason to retrieve as one person on behalf of another — so
    the parameter does not exist.

    Asserted against the signature rather than trusted from the
    docstring, because a later convenience argument would be exactly the
    kind of change that looks harmless.
    """
    import inspect

    parameters = set(inspect.signature(retrieve_for_question).parameters)

    assert "user_id" not in parameters
    assert "as_user" not in parameters
    assert "on_behalf_of" not in parameters
    assert "session" in parameters


def test_an_unknown_source_is_refused_rather_than_skipped(
    app_session: Session, two_projects: dict[str, uuid.UUID]
) -> None:
    """A typo must not silently narrow the search.

    Skipping an unrecognised source would produce a confident, incomplete
    answer — which is worse than an error, because nothing on the screen
    would say the search had been narrower than asked for.
    """
    fx = two_projects
    _scope(app_session, fx["org"], fx["outsider"])

    with pytest.raises(ValueError, match="not a retrievable source"):
        retrieve_for_question(
            app_session,
            organization_id=fx["org"],
            question="anything",
            entity_types=("formula_verison",),  # deliberate typo
        )


def test_cited_evidence_outside_the_boundary_is_detectable(
    owner_session: Session, app_session: Session, two_projects: dict[str, uuid.UUID]
) -> None:
    """🔴 WHY `ai.msd_evidence` EXISTS.

    The boundary is correct by construction at retrieval time, and that
    makes it unverifiable afterwards unless something recorded what was
    used. This writes a turn citing the RESTRICTED version — the shape a
    leak would take — and asserts the checker reports it.

    A checker that returned nothing here would mean an actual leak left
    no trace, and "MSD respected the boundary" would be a claim about
    code that nobody could ever test.
    """
    fx = two_projects

    owner_session.begin()
    thread = owner_session.execute(
        text(
            """
            INSERT INTO ai.msd_threads (organization_id, owner_id, title)
            VALUES (:o, :u, 'boundary probe') RETURNING id
            """
        ),
        {"o": fx["org"], "u": fx["outsider"]},
    ).scalar_one()
    turn = owner_session.execute(
        text(
            """
            INSERT INTO ai.msd_turns
                (organization_id, thread_id, turn_number, role, body, disclaimer, asked_by)
            VALUES (:o, :t, 1, 'assistant', 'an answer',
                    'AI-generated recommendation — requires technical review', :u)
            RETURNING id
            """
        ),
        {"o": fx["org"], "t": thread, "u": fx["outsider"]},
    ).scalar_one()
    owner_session.execute(
        text(
            """
            INSERT INTO ai.msd_evidence
                (organization_id, turn_id, entity_type, entity_id, excerpt)
            VALUES (:o, :turn, 'formula_version', :v, 'cited from outside the boundary')
            """
        ),
        {"o": fx["org"], "turn": turn, "v": fx["restricted_version"]},
    )
    owner_session.commit()

    _scope(app_session, fx["org"], fx["outsider"])
    unreadable = verify_evidence_within_boundary(
        app_session, organization_id=fx["org"], turn_id=turn
    )

    assert len(unreadable) == 1
    assert unreadable[0]["entity_id"] == fx["restricted_version"]


def test_an_assistant_turn_without_its_label_is_refused(
    owner_session: Session, two_projects: dict[str, uuid.UUID]
) -> None:
    """§7: AI recommendations are labelled, always.

    Enforced by a CHECK constraint rather than by a template, so a turn
    read through the API, exported or printed carries the label too — a
    template only decorates one rendering of it.
    """
    from sqlalchemy.exc import IntegrityError

    fx = two_projects
    owner_session.begin()
    thread = owner_session.execute(
        text(
            """
            INSERT INTO ai.msd_threads (organization_id, owner_id, title)
            VALUES (:o, :u, 'label probe') RETURNING id
            """
        ),
        {"o": fx["org"], "u": fx["outsider"]},
    ).scalar_one()

    with pytest.raises(IntegrityError) as caught:
        owner_session.execute(
            text(
                """
                INSERT INTO ai.msd_turns
                    (organization_id, thread_id, turn_number, role, body, asked_by)
                VALUES (:o, :t, 1, 'assistant', 'an unlabelled answer', :u)
                """
            ),
            {"o": fx["org"], "t": thread, "u": fx["outsider"]},
        )

    assert "assistant_is_labelled" in str(caught.value.orig)
    owner_session.rollback()


def test_an_msd_thread_cannot_be_reassigned(
    owner_session: Session, two_projects: dict[str, uuid.UUID]
) -> None:
    """A thread's owner IS its authorization scope.

    Handing it to another user would silently re-scope every future
    retrieval against a different boundary, while the earlier turns —
    built under the first user's scope — stayed in it.
    """
    from sqlalchemy.exc import DBAPIError

    fx = two_projects
    owner_session.begin()
    thread = owner_session.execute(
        text(
            """
            INSERT INTO ai.msd_threads (organization_id, owner_id, title)
            VALUES (:o, :u, 'reassignment probe') RETURNING id
            """
        ),
        {"o": fx["org"], "u": fx["outsider"]},
    ).scalar_one()
    other = owner_session.execute(
        text(
            """
            INSERT INTO core.users (keycloak_sub, email, display_name)
            VALUES (:s, :e, 'Somebody else') RETURNING id
            """
        ),
        {"s": str(uuid.uuid4()), "e": f"other-{uuid.uuid4().hex[:8]}@example.test"},
    ).scalar_one()

    with pytest.raises(DBAPIError) as caught:
        owner_session.execute(
            text("UPDATE ai.msd_threads SET owner_id = :u WHERE id = :t"),
            {"u": other, "t": thread},
        )

    assert "authorization boundary" in str(caught.value.orig)
    owner_session.rollback()
