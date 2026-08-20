"""A message is exactly as private as the channel it was posted in.

🔴 WHAT THIS CATCHES, AND WHY NOTHING ELSE DID

Migration 022 gave `messaging.channels` a policy carrying the PROJECT
predicate, and gave `messaging.messages` — in the same file, in a
DO-block loop over six tables — a policy carrying only
`organization_id`. `list_messages` then selected messages by
`channel_id` and **never joined `channels` at all**, so the channel's
protection was not merely weaker: it was never consulted.

Two disclosures followed, both reachable by any authenticated member of
the organization who held a channel id:

  1. every message in a RESTRICTED project's channel they are not a
     member of, and
  2. every message in a DIRECT conversation between two other people.

The second is the sharper one. 022's own policy comment says direct
messages "are governed by channel membership instead" — and that
governance existed in exactly ONE place, the `list_channels` LISTING
query. Nothing enforced it on the path that returns the words.

`tests/db/test_023_messaging.py` covered the NOTIFICATION boundary
thoroughly and never asked whether the messages themselves were
readable, which is why a suite that was green proved nothing about this.

Every test below asserts BOTH directions. A predicate that returns
nothing to everybody would close the hole and make messaging useless,
and it would pass a one-directional test.

🔴 ON NOT COMMITTING

Nothing here calls `app_session.commit()`. `SET LOCAL` dies with its
transaction, so a commit would DISCARD the RLS GUCs, `core.current_org_id()`
would go NULL, and every policy's `core.rls_permissive()` branch would
open the table completely — a negative assertion would then pass while
proving the opposite of what it claims. `_assert_scoped_as` is called
immediately before each negative assertion so that a vacuous pass is
impossible rather than merely unlikely.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.domains.messaging.service import (
    ChannelInput,
    MessageInput,
    MessagingNotFoundError,
    create_channel,
    list_messages,
    post_message,
)


def _scope(session: Session, org: uuid.UUID, user: uuid.UUID) -> None:
    """Become this user, in this organization, for this transaction."""
    session.execute(text("SELECT set_config('app.current_org', :o, true)"), {"o": str(org)})
    session.execute(text("SELECT set_config('app.current_user_id', :u, true)"), {"u": str(user)})


def _assert_scoped_as(session: Session, org: uuid.UUID, user: uuid.UUID) -> None:
    """Refuse to make a negative assertion from an unscoped session.

    With no GUC set, `core.rls_permissive()` opens every policy and a
    "the outsider saw nothing" assertion would be measuring an empty
    transaction rather than a boundary.
    """
    actual_org, actual_user = session.execute(
        text("SELECT core.current_org_id(), core.current_user_id()")
    ).one()
    # Split rather than combined, so a failure names WHICH half is wrong.
    assert actual_org == org, (
        f"the session is scoped to organization {actual_org}, not {org}; RLS "
        "would be permissive and the result would prove nothing"
    )
    assert actual_user == user, (
        f"the session is scoped to user {actual_user}, not {user}; the "
        "membership predicate would be answering about the wrong person"
    )


@pytest.fixture
def two_people(owner_session: Session, app_session: Session) -> Iterator[dict[str, uuid.UUID]]:
    """One organization, a RESTRICTED project, an insider and an outsider.

    Both are active organization members, so the ONLY thing separating
    them is the project boundary — which is the only way a difference in
    behaviour can be attributed to it.
    """
    suffix = uuid.uuid4().hex[:8]

    org = owner_session.execute(
        text("INSERT INTO core.organizations (code, name) VALUES (:c, :n) RETURNING id"),
        {"c": f"VIS-{suffix}", "n": "Visibility Org"},
    ).scalar_one()

    def _user(handle: str, name: str) -> uuid.UUID:
        uid: uuid.UUID = owner_session.execute(
            text(
                """
                INSERT INTO core.users (keycloak_sub, email, display_name)
                VALUES (:s, :e, :n) RETURNING id
                """
            ),
            {"s": f"vis-{handle}-{suffix}", "e": f"{handle}-{suffix}@example.test", "n": name},
        ).scalar_one()
        owner_session.execute(
            text(
                """
                INSERT INTO core.organization_members (organization_id, user_id, status)
                VALUES (:o, :u, 'active')
                """
            ),
            {"o": org, "u": uid},
        )
        return uid

    insider = _user("insider", "Insider")
    outsider = _user("outsider", "Outsider")

    project = owner_session.execute(
        text(
            """
            INSERT INTO projects.projects
                (organization_id, project_code, name, status, confidentiality)
            VALUES (:o, :c, 'Restricted Work', 'active', 'restricted')
            RETURNING id
            """
        ),
        {"o": org, "c": f"V-{suffix}"},
    ).scalar_one()

    owner_session.execute(
        text(
            """
            INSERT INTO projects.project_members
                (organization_id, project_id, user_id, project_role)
            VALUES (:o, :p, :u, 'lead')
            """
        ),
        {"o": org, "p": project, "u": insider},
    )
    owner_session.commit()

    _scope(app_session, org, insider)

    yield {"org": org, "insider": insider, "outsider": outsider, "project": project}

    # Nothing this suite writes through `app_session` is ever committed,
    # so only the fixture's own committed rows need removing. Children
    # before parents: every FK here is RESTRICT by design (§5, never
    # cascade-delete R&D history).
    app_session.rollback()
    owner_session.begin()
    for statement in (
        "DELETE FROM projects.project_members WHERE organization_id = :o",
        "DELETE FROM projects.projects WHERE organization_id = :o",
        "DELETE FROM core.organization_members WHERE organization_id = :o",
    ):
        owner_session.execute(text(statement), {"o": org})
    owner_session.execute(
        text("DELETE FROM core.users WHERE id IN (:a, :b)"), {"a": insider, "b": outsider}
    )
    owner_session.execute(text("DELETE FROM core.organizations WHERE id = :o"), {"o": org})
    owner_session.commit()


# ---------------------------------------------------------------------------
# A restricted project's conversation
# ---------------------------------------------------------------------------


def test_an_outsider_cannot_read_a_restricted_projects_messages(
    app_session: Session, two_people: dict[str, uuid.UUID]
) -> None:
    fx = two_people

    channel = create_channel(
        app_session,
        organization_id=fx["org"],
        actor_id=fx["insider"],
        spec=ChannelInput(channel_type="project", name="Restricted", project_id=fx["project"]),
    )
    post_message(
        app_session,
        channel_id=channel["id"],
        organization_id=fx["org"],
        actor_id=fx["insider"],
        spec=MessageInput(body="The filler shrank by 0.4 percent on the second batch."),
    )

    _scope(app_session, fx["org"], fx["outsider"])
    _assert_scoped_as(app_session, fx["org"], fx["outsider"])

    seen = list_messages(app_session, channel_id=channel["id"], organization_id=fx["org"])
    assert seen == [], (
        "a full organization member who is NOT in the restricted project read "
        f"its conversation: {seen}"
    )


def test_the_project_member_can_read_them(
    app_session: Session, two_people: dict[str, uuid.UUID]
) -> None:
    """The other direction.

    Without this, a `list_messages` that returned nothing to anybody
    would pass the test above.
    """
    fx = two_people

    channel = create_channel(
        app_session,
        organization_id=fx["org"],
        actor_id=fx["insider"],
        spec=ChannelInput(channel_type="project", name="Restricted", project_id=fx["project"]),
    )
    post_message(
        app_session,
        channel_id=channel["id"],
        organization_id=fx["org"],
        actor_id=fx["insider"],
        spec=MessageInput(body="The filler shrank by 0.4 percent on the second batch."),
    )

    _assert_scoped_as(app_session, fx["org"], fx["insider"])
    seen = list_messages(app_session, channel_id=channel["id"], organization_id=fx["org"])
    assert len(seen) == 1, f"the project member cannot read their own channel: {seen}"
    assert "0.4 percent" in seen[0]["body"]


# ---------------------------------------------------------------------------
# Somebody else's direct message
# ---------------------------------------------------------------------------


def test_a_stranger_cannot_read_a_direct_message(
    app_session: Session, two_people: dict[str, uuid.UUID]
) -> None:
    """A direct channel has no project to hide behind.

    `project_id IS NULL`, so the `channels` policy admits every member of
    the organization by design — 022 says membership governs these
    instead. This is the test that membership actually does.
    """
    fx = two_people

    channel = create_channel(
        app_session,
        organization_id=fx["org"],
        actor_id=fx["insider"],
        spec=ChannelInput(channel_type="direct", name=None),
    )
    post_message(
        app_session,
        channel_id=channel["id"],
        organization_id=fx["org"],
        actor_id=fx["insider"],
        spec=MessageInput(body="Between us: I think the supplier substituted the talc."),
    )

    _scope(app_session, fx["org"], fx["outsider"])
    _assert_scoped_as(app_session, fx["org"], fx["outsider"])

    seen = list_messages(app_session, channel_id=channel["id"], organization_id=fx["org"])
    assert seen == [], f"a stranger read a private conversation they are not part of: {seen}"


def test_a_participant_can_read_their_own_direct_message(
    app_session: Session, two_people: dict[str, uuid.UUID]
) -> None:
    fx = two_people

    channel = create_channel(
        app_session,
        organization_id=fx["org"],
        actor_id=fx["insider"],
        spec=ChannelInput(channel_type="direct", name=None),
    )
    post_message(
        app_session,
        channel_id=channel["id"],
        organization_id=fx["org"],
        actor_id=fx["insider"],
        spec=MessageInput(body="Between us: I think the supplier substituted the talc."),
    )

    _assert_scoped_as(app_session, fx["org"], fx["insider"])
    seen = list_messages(app_session, channel_id=channel["id"], organization_id=fx["org"])
    assert len(seen) == 1, f"a participant cannot read their own direct message: {seen}"


def test_a_stranger_cannot_post_into_a_direct_message(
    app_session: Session, two_people: dict[str, uuid.UUID]
) -> None:
    """The write half.

    Refused as "no such channel", deliberately: whether the conversation
    exists must not be answerable by someone outside it.
    """
    fx = two_people

    channel = create_channel(
        app_session,
        organization_id=fx["org"],
        actor_id=fx["insider"],
        spec=ChannelInput(channel_type="direct", name=None),
    )

    _scope(app_session, fx["org"], fx["outsider"])
    _assert_scoped_as(app_session, fx["org"], fx["outsider"])

    with pytest.raises(MessagingNotFoundError):
        post_message(
            app_session,
            channel_id=channel["id"],
            organization_id=fx["org"],
            actor_id=fx["outsider"],
            spec=MessageInput(body="I can see you."),
        )


# ---------------------------------------------------------------------------
# The database layer, on its own
# ---------------------------------------------------------------------------


def test_the_database_refuses_independently_of_the_service(
    app_session: Session, two_people: dict[str, uuid.UUID]
) -> None:
    """🔴 THE POINT OF MIGRATION 025.

    The service functions were fixed in the same change, so every test
    above would pass with `messaging.messages` still carrying only an
    organization-scoped policy. `SECURITY.md` §1 requires that any ONE
    layer failing must not expose data — so this one bypasses the service
    entirely and asks PostgreSQL directly, exactly as a future route,
    worker, report or psql session would.
    """
    fx = two_people

    channel = create_channel(
        app_session,
        organization_id=fx["org"],
        actor_id=fx["insider"],
        spec=ChannelInput(channel_type="project", name="Restricted", project_id=fx["project"]),
    )
    post_message(
        app_session,
        channel_id=channel["id"],
        organization_id=fx["org"],
        actor_id=fx["insider"],
        spec=MessageInput(body="Raw SQL must not reach this."),
    )

    raw = text("SELECT count(*) FROM messaging.messages WHERE channel_id = :cid")

    _assert_scoped_as(app_session, fx["org"], fx["insider"])
    assert app_session.execute(raw, {"cid": channel["id"]}).scalar_one() == 1, (
        "the project member cannot see their own message through raw SQL; "
        "the policy is too strict, not too loose"
    )

    _scope(app_session, fx["org"], fx["outsider"])
    _assert_scoped_as(app_session, fx["org"], fx["outsider"])
    assert app_session.execute(raw, {"cid": channel["id"]}).scalar_one() == 0, (
        "messaging.messages returned a restricted project's rows to a "
        "non-member over raw SQL: the database layer is not enforcing the "
        "channel's confidentiality, only the service is"
    )


# ---------------------------------------------------------------------------
# The two ways the database backstop was defeatable
# ---------------------------------------------------------------------------
# 🔴 FOUND BY ADVERSARIALLY REVIEWING MIGRATION 025 ITSELF.
#
# The first version of 025 tightened the `USING` side of
# `messaging.messages` and left the `WITH CHECK` side of the two tables
# `core.can_read_channel()` READS at organization-only. Since
# `evercoat_app` holds `GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN
# SCHEMA messaging` (022:511), the predicate could simply be fed a
# different answer.
#
# Neither attack is reachable over HTTP — `create_channel` is the only
# writer of `channel_members`, and no route updates `channels` at all.
# That is exactly why they belong here: the whole point of the database
# layer is what it does when the application layer is bypassed, and every
# test above this line goes through the service.


def _direct_channel(session: Session, fx: dict[str, uuid.UUID]) -> uuid.UUID:
    channel = create_channel(
        session,
        organization_id=fx["org"],
        actor_id=fx["insider"],
        spec=ChannelInput(channel_type="direct", name=None),
    )
    post_message(
        session,
        channel_id=channel["id"],
        organization_id=fx["org"],
        actor_id=fx["insider"],
        spec=MessageInput(body="Between us: I think the supplier substituted the talc."),
    )
    channel_id: uuid.UUID = channel["id"]
    return channel_id


def test_a_stranger_cannot_enrol_themselves_into_a_direct_channel(
    app_session: Session, two_people: dict[str, uuid.UUID]
) -> None:
    """H1 — the self-enrolment attack.

    `can_read_channel` asks whether a `channel_members` row exists. If the
    attacker can write that row, the predicate answers whatever they like.
    The `channels` policy shows every `direct` row to the whole
    organization by design, so the id is not a secret either.
    """
    fx = two_people
    channel_id = _direct_channel(app_session, fx)

    _scope(app_session, fx["org"], fx["outsider"])
    _assert_scoped_as(app_session, fx["org"], fx["outsider"])

    with pytest.raises(Exception) as exc:  # noqa: PT011 - psycopg raises its own type
        app_session.execute(
            text(
                """
                INSERT INTO messaging.channel_members
                    (organization_id, channel_id, user_id)
                VALUES (:org, :cid, :uid)
                """
            ),
            {"org": fx["org"], "cid": channel_id, "uid": fx["outsider"]},
        )
    assert "row-level security" in str(exc.value).lower(), (
        "a stranger inserted their own membership row into someone else's "
        f"direct channel, which makes core.can_read_channel() answer TRUE: {exc.value}"
    )
    app_session.rollback()


def test_a_stranger_cannot_retype_a_direct_channel(
    app_session: Session, two_people: dict[str, uuid.UUID]
) -> None:
    """H2 — retyping the channel out of `direct`.

    `can_read_channel` only demands membership for `channel_type =
    'direct'`. Everything else is governed by the `channels` policy, and
    a channel with no project is visible organization-wide — so one
    UPDATE turned a private conversation into an announcement readable by
    every colleague.
    """
    fx = two_people
    channel_id = _direct_channel(app_session, fx)

    _scope(app_session, fx["org"], fx["outsider"])
    _assert_scoped_as(app_session, fx["org"], fx["outsider"])

    with pytest.raises(Exception) as exc:  # noqa: PT011 - psycopg raises its own type
        app_session.execute(
            text("UPDATE messaging.channels SET channel_type = 'announcement' WHERE id = :cid"),
            {"cid": channel_id},
        )
    message = str(exc.value).lower()
    assert "retyped" in message or "row-level security" in message, (
        f"a direct channel was retyped, exposing the whole conversation: {exc.value}"
    )
    app_session.rollback()


def test_the_creator_can_still_open_a_direct_channel(
    app_session: Session, two_people: dict[str, uuid.UUID]
) -> None:
    """🔴 THE FIX MUST NOT BREAK THE FEATURE IT PROTECTS.

    The obvious rule — "you may only add a member to a channel you can
    already read" — cannot bootstrap a direct channel: a `WITH CHECK`
    subquery does not see the row the same command is inserting, so the
    creator's own first membership row would be refused and NO direct
    message could ever be created. That version was proposed and
    rejected; the policy admits the channel's `created_by` instead.

    This test is what distinguishes the two.
    """
    fx = two_people

    channel = create_channel(
        app_session,
        organization_id=fx["org"],
        actor_id=fx["insider"],
        spec=ChannelInput(channel_type="direct", name=None, member_ids=(fx["outsider"],)),
    )

    _assert_scoped_as(app_session, fx["org"], fx["insider"])
    members = app_session.execute(
        text("SELECT count(*) FROM messaging.channel_members WHERE channel_id = :cid"),
        {"cid": channel["id"]},
    ).scalar_one()
    assert members == 2, (
        "creating a direct channel no longer records both participants; the "
        f"membership policy has broken channel creation (got {members})"
    )


def test_a_stranger_cannot_promote_a_direct_message_into_a_task(
    app_session: Session, two_people: dict[str, uuid.UUID]
) -> None:
    """The path that COPIES the words somewhere else.

    `promote_message` writes the message body into
    `workflow.tasks.description`, where it is readable by people who were
    never in the conversation — so a leak here outlives the channel it
    came from. It was the one function in this module carrying only the
    database policy and not the service predicate; both are present now.
    """
    from app.domains.messaging.service import promote_message

    fx = two_people
    channel = create_channel(
        app_session,
        organization_id=fx["org"],
        actor_id=fx["insider"],
        spec=ChannelInput(channel_type="direct", name=None),
    )
    posted = post_message(
        app_session,
        channel_id=channel["id"],
        organization_id=fx["org"],
        actor_id=fx["insider"],
        spec=MessageInput(body="Between us: the supplier substituted the talc."),
    )

    _scope(app_session, fx["org"], fx["outsider"])
    _assert_scoped_as(app_session, fx["org"], fx["outsider"])

    with pytest.raises(MessagingNotFoundError):
        promote_message(
            app_session,
            message_id=posted["id"],
            organization_id=fx["org"],
            actor_id=fx["outsider"],
            task_type="investigation",
            title="Check the talc",
            assigned_user_id=None,
        )
