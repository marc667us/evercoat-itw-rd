"""Messaging: the notification boundary, and promotion by hand only.

Two rules carry this module, and both are the kind that pass a code
review and fail in production.

**A notification must not disclose what its recipient cannot see.** The
channel's own RLS protects the MESSAGES and does nothing about a
notification row addressed to an outsider. My first version of this check
reused `list_channels`'s predicate, which evaluates in the AUTHOR's
session -- so a restricted project's channel read as reachable for
everyone, and the mention notification would have named the project to
somebody with no access to it. The test below is the one that would have
caught it.

**Informal chat never becomes authoritative knowledge automatically**
(§7). Promotion exists, is explicit, produces a TASK rather than a
conclusion, and links back to the message it came from.

Everything here runs on `app_session` where the boundary is the subject,
because the owner is exempt from RLS while `relforcerowsecurity` is FALSE
and an owner-run version of this file would pass against a system with no
boundary at all.
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
    create_channel,
    list_messages,
    my_notifications,
    post_message,
    promote_message,
)


@pytest.fixture
def channel_fixture(owner_session: Session, app_session: Session) -> Iterator[dict[str, uuid.UUID]]:
    """One org, one RESTRICTED project, an author inside it and an
    outsider who is not.

    Both are active organization members, so nothing but the project
    boundary separates them -- which is the only way the test can
    attribute a difference in behaviour to that boundary.
    """
    suffix = uuid.uuid4().hex[:8]

    org = owner_session.execute(
        text("INSERT INTO core.organizations (code, name) VALUES (:c, :n) RETURNING id"),
        {"c": f"MSG-{suffix}", "n": "Messaging Org"},
    ).scalar_one()

    def _user(handle: str, name: str) -> uuid.UUID:
        uid: uuid.UUID = owner_session.execute(
            text(
                """
                INSERT INTO core.users (keycloak_sub, email, display_name)
                VALUES (:s, :e, :n) RETURNING id
                """
            ),
            {"s": f"msg-{handle}-{suffix}", "e": f"{handle}@example.test", "n": name},
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

    author = _user(f"author{suffix}", "Author")
    outsider = _user(f"outsider{suffix}", "Outsider")
    # A THIRD person, INSIDE the restricted project and not its author. Needed
    # because §7's rule about notifications turns on whether the RECIPIENT can
    # see the thing -- and with only an author and an outsider, "notified" and
    # "in the project" could never be told apart from "is the actor".
    member = _user(f"member{suffix}", "Member")

    project = owner_session.execute(
        text(
            """
            -- Columns read from migration 001, not guessed. There is no
            -- `project_type` and no `created_by` on projects.projects;
            -- naming them cost a full CI round trip, which is the same
            -- price the same mistake charged for `criticality` and for
            -- `project_role`.
            INSERT INTO projects.projects
                (organization_id, project_code, name, status, confidentiality)
            VALUES (:o, :c, 'Restricted Work', 'active', 'restricted')
            RETURNING id
            """
        ),
        {"o": org, "c": f"P-{suffix}"},
    ).scalar_one()

    owner_session.execute(
        text(
            """
            INSERT INTO projects.project_members
                (organization_id, project_id, user_id, project_role)
            VALUES (:o, :p, :u, 'lead')
            """
        ),
        {"o": org, "p": project, "u": author},
    )
    owner_session.execute(
        text(
            """
            INSERT INTO projects.project_members
                (organization_id, project_id, user_id, project_role)
            VALUES (:o, :p, :u, 'chemist')
            """
        ),
        {"o": org, "p": project, "u": member},
    )
    owner_session.commit()

    _scope(app_session, org, author)

    yield {
        "org": org,
        "author": author,
        "member": member,
        "outsider": outsider,
        "project": project,
    }

    app_session.rollback()
    owner_session.begin()
    # 🔴 CHILDREN BEFORE PARENTS, AND MESSAGES ARE A CHILD OF CHANNELS.
    #
    # The first version deleted channels first and messages last, because
    # messages need the append-only trigger disabled and that felt like a
    # special case to handle at the end. `messages_channel_fk` is
    # RESTRICT by design (§5: never cascade-delete R&D history), so the
    # parent cannot go first no matter how the special case is arranged.
    #
    # Messages carry `deny_message_rewrite`. Disabling it to clean up is
    # itself proof the mechanism is real -- a fixture that could simply
    # delete would mean the guard was decorative.
    owner_session.execute(
        text("ALTER TABLE messaging.messages DISABLE TRIGGER messages_are_a_record")
    )
    for statement in (
        "DELETE FROM messaging.notifications WHERE organization_id = :o",
        "DELETE FROM messaging.message_links WHERE organization_id = :o",
        "DELETE FROM workflow.tasks WHERE organization_id = :o",
        "DELETE FROM messaging.messages WHERE organization_id = :o",
        "DELETE FROM messaging.channel_members WHERE organization_id = :o",
        "DELETE FROM messaging.channels WHERE organization_id = :o",
        "DELETE FROM projects.project_members WHERE organization_id = :o",
        "DELETE FROM projects.projects WHERE organization_id = :o",
        "DELETE FROM core.organization_members WHERE organization_id = :o",
    ):
        owner_session.execute(text(statement), {"o": org})
    owner_session.execute(
        text("ALTER TABLE messaging.messages ENABLE TRIGGER messages_are_a_record")
    )
    owner_session.execute(
        text("DELETE FROM core.users WHERE id IN (:a, :b)"), {"a": author, "b": outsider}
    )
    owner_session.execute(text("DELETE FROM core.organizations WHERE id = :o"), {"o": org})
    owner_session.commit()


def _scope(session: Session, org: uuid.UUID, user: uuid.UUID) -> None:
    session.execute(text("SELECT set_config('app.current_org', :o, true)"), {"o": str(org)})
    session.execute(text("SELECT set_config('app.current_user_id', :u, true)"), {"u": str(user)})


def test_a_mention_does_not_notify_someone_outside_the_project(
    app_session: Session, channel_fixture: dict[str, uuid.UUID]
) -> None:
    """🔴 THE NOTIFICATION IS THE LEAK, IF YOU LET IT BE.

    The outsider is a full organization member and is mentioned by name
    in a RESTRICTED project's channel. They must get no notification --
    because the notification would name a project they cannot open, and
    the channel's RLS cannot stop a row addressed to them.
    """
    fx = channel_fixture

    channel = create_channel(
        app_session,
        organization_id=fx["org"],
        actor_id=fx["author"],
        spec=ChannelInput(channel_type="project", name="Restricted", project_id=fx["project"]),
    )

    outsider_handle = app_session.execute(
        text("SELECT split_part(email, '@', 1) FROM core.users WHERE id = :u"),
        {"u": fx["outsider"]},
    ).scalar_one()

    result = post_message(
        app_session,
        channel_id=channel["id"],
        organization_id=fx["org"],
        actor_id=fx["author"],
        spec=MessageInput(body=f"@{outsider_handle} can you look at this?"),
    )
    app_session.commit()

    # The MENTION is recorded -- the message said what it said.
    assert result["mentions"], "the mention was not resolved at all"
    assert result["mentions"][0]["user_id"] == fx["outsider"]
    assert result["mentions"][0]["notified"] is False, (
        "a user outside a restricted project was notified about its channel; "
        "the notification discloses the project's existence"
    )

    delivered = my_notifications(
        app_session, organization_id=fx["org"], recipient_id=fx["outsider"]
    )
    assert delivered == [], f"a notification reached an outsider: {delivered}"


def test_a_mention_notifies_a_project_member(
    app_session: Session, owner_session: Session, channel_fixture: dict[str, uuid.UUID]
) -> None:
    """Verified in BOTH directions.

    A check that notified nobody would pass the test above while making
    mentions useless. Adding the outsider to the project must make the
    mention deliver.
    """
    fx = channel_fixture

    owner_session.begin()
    owner_session.execute(
        text(
            """
            INSERT INTO projects.project_members
                (organization_id, project_id, user_id, project_role)
            VALUES (:o, :p, :u, 'chemist')
            """
        ),
        {"o": fx["org"], "p": fx["project"], "u": fx["outsider"]},
    )
    owner_session.commit()

    channel = create_channel(
        app_session,
        organization_id=fx["org"],
        actor_id=fx["author"],
        spec=ChannelInput(channel_type="project", name="Restricted", project_id=fx["project"]),
    )
    handle = app_session.execute(
        text("SELECT split_part(email, '@', 1) FROM core.users WHERE id = :u"),
        {"u": fx["outsider"]},
    ).scalar_one()

    result = post_message(
        app_session,
        channel_id=channel["id"],
        organization_id=fx["org"],
        actor_id=fx["author"],
        spec=MessageInput(body=f"@{handle} please review"),
    )
    app_session.commit()

    assert result["mentions"][0]["notified"] is True, (
        "a project member was not notified of their own mention; the check is excluding too much"
    )
    delivered = my_notifications(
        app_session, organization_id=fx["org"], recipient_id=fx["outsider"]
    )
    assert len(delivered) == 1
    assert delivered[0]["is_actionable"] is True


def test_promotion_creates_a_task_and_links_back_to_the_message(
    app_session: Session, channel_fixture: dict[str, uuid.UUID]
) -> None:
    """§7: conclusions become controlled records only by explicit human
    promotion -- and what they become is a TASK, not a decision.

    The link back is the digital thread's rule applied to conversation:
    the task can always answer "where did this come from?".
    """
    fx = channel_fixture

    channel = create_channel(
        app_session,
        organization_id=fx["org"],
        actor_id=fx["author"],
        spec=ChannelInput(channel_type="project", name="Restricted", project_id=fx["project"]),
    )
    message = post_message(
        app_session,
        channel_id=channel["id"],
        organization_id=fx["org"],
        actor_id=fx["author"],
        spec=MessageInput(body="We should re-run the adhesion test at 5 degrees."),
    )

    promoted = promote_message(
        app_session,
        message_id=message["id"],
        organization_id=fx["org"],
        actor_id=fx["author"],
        task_type="experiment",
        title="Re-run adhesion at 5 C",
    )
    app_session.commit()

    source = (
        app_session.execute(
            text(
                """
            SELECT source_event, entity_type, entity_id
            FROM workflow.tasks WHERE id = :t AND organization_id = :o
            """
            ),
            {"t": promoted["task_id"], "o": fx["org"]},
        )
        .mappings()
        .one()
    )

    assert source["source_event"] == "message.promoted"
    assert source["entity_id"] == message["id"], (
        "the task does not point back at the message it came from"
    )

    link = (
        app_session.execute(
            text(
                """
            SELECT link_type, entity_type, entity_id FROM messaging.message_links
            WHERE message_id = :m AND link_type = 'promotion'
            """
            ),
            {"m": message["id"]},
        )
        .mappings()
        .one()
    )
    assert link["entity_id"] == promoted["task_id"]


def test_nothing_is_promoted_without_being_asked(
    app_session: Session, channel_fixture: dict[str, uuid.UUID]
) -> None:
    """Posting a message must create no controlled record at all.

    The rule is that informal chat never becomes authoritative knowledge
    AUTOMATICALLY. A service that helpfully opened a task for any message
    containing "we should" would violate it while looking like a feature.
    """
    fx = channel_fixture

    channel = create_channel(
        app_session,
        organization_id=fx["org"],
        actor_id=fx["author"],
        spec=ChannelInput(channel_type="project", name="Restricted", project_id=fx["project"]),
    )
    post_message(
        app_session,
        channel_id=channel["id"],
        organization_id=fx["org"],
        actor_id=fx["author"],
        spec=MessageInput(body="We should probably reformulate and open a corrective action."),
    )
    app_session.commit()

    tasks = app_session.execute(
        text("SELECT count(*) FROM workflow.tasks WHERE organization_id = :o"), {"o": fx["org"]}
    ).scalar_one()
    assert tasks == 0, "a message created a controlled record on its own"


def test_a_withdrawn_message_leaves_the_conversation_readable(
    app_session: Session, owner_session: Session, channel_fixture: dict[str, uuid.UUID]
) -> None:
    """A withdrawn message is replaced, not omitted.

    Omitting it would leave replies pointing at nothing, and a
    conversation with holes cannot be read at all.
    """
    fx = channel_fixture

    channel = create_channel(
        app_session,
        organization_id=fx["org"],
        actor_id=fx["author"],
        spec=ChannelInput(channel_type="project", name="Restricted", project_id=fx["project"]),
    )
    first = post_message(
        app_session,
        channel_id=channel["id"],
        organization_id=fx["org"],
        actor_id=fx["author"],
        spec=MessageInput(body="Original claim."),
    )
    post_message(
        app_session,
        channel_id=channel["id"],
        organization_id=fx["org"],
        actor_id=fx["author"],
        spec=MessageInput(body="Agreed.", reply_to_id=first["id"]),
    )
    app_session.commit()

    owner_session.begin()
    owner_session.execute(
        text("UPDATE messaging.messages SET is_deleted = TRUE WHERE id = :m"), {"m": first["id"]}
    )
    owner_session.commit()

    thread = list_messages(app_session, channel_id=channel["id"], organization_id=fx["org"])
    assert len(thread) == 2, "the withdrawn message vanished and took the thread with it"
    assert thread[0]["body"] == "(this message was withdrawn)"
    assert thread[1]["reply_to_id"] == first["id"]


def test_a_channel_past_its_limit_shows_the_newest_messages(
    app_session: Session, channel_fixture: dict[str, uuid.UUID]
) -> None:
    """🔴 THE WINDOW MUST BE ANCHORED TO THE END OF THE CONVERSATION.

    Raised by the Supervisor. `list_messages` ordered ASCENDING with a LIMIT,
    which returns the OLDEST `limit` rows. There is no offset or cursor
    parameter, so once a channel passed `limit` messages every message posted
    afterwards was unreachable through this API — a reader was pinned to the
    opening of the conversation permanently, and the newest thing they could
    see never changed no matter how much was said.

    Five messages with a limit of three. The correct answer is the LAST three,
    in reading order. The old implementation returned the FIRST three, which
    is what this asserts against.
    """
    fx = channel_fixture

    channel = create_channel(
        app_session,
        organization_id=fx["org"],
        actor_id=fx["author"],
        spec=ChannelInput(channel_type="project", name="Busy", project_id=fx["project"]),
    )
    for n in range(1, 6):
        post_message(
            app_session,
            channel_id=channel["id"],
            organization_id=fx["org"],
            actor_id=fx["author"],
            spec=MessageInput(body=f"message {n}"),
        )

    page = list_messages(app_session, channel_id=channel["id"], organization_id=fx["org"], limit=3)

    bodies = [m["body"] for m in page]
    assert bodies == ["message 3", "message 4", "message 5"], (
        "the window is anchored to the START of the conversation - a busy channel "
        f"can never show what was said most recently. Got {bodies}"
    )


def test_promoting_a_message_notifies_the_person_it_is_assigned_to(
    app_session: Session, channel_fixture: dict[str, uuid.UUID]
) -> None:
    """I36 -- A TASK NOBODY IS TOLD ABOUT IS NOT AN ASSIGNMENT.

    `promote_message` wrote `workflow.tasks` with its own INSERT rather than
    calling `create_task`, so it silently missed the assignee notification
    that I33 added there. A decision promoted out of a conversation landed in
    somebody's queue with nothing telling them it was there -- which is the
    whole point of promoting it.

    The duplication was held in place by an import cycle (`tasks` imported
    `notify` from `messaging`), not by a decision. Moving `notify` to
    `app/core` removed the obstacle.
    """
    fx = channel_fixture

    channel = create_channel(
        app_session,
        organization_id=fx["org"],
        actor_id=fx["author"],
        spec=ChannelInput(channel_type="project", name="Promotion", project_id=fx["project"]),
    )
    message = post_message(
        app_session,
        channel_id=channel["id"],
        organization_id=fx["org"],
        actor_id=fx["author"],
        spec=MessageInput(body="We should re-run the adhesion series at 40C."),
    )

    promote_message(
        app_session,
        message_id=message["id"],
        organization_id=fx["org"],
        actor_id=fx["author"],
        task_type="experiment",
        title="Re-run the adhesion series at 40C",
        assigned_user_id=fx["member"],
    )

    notified = (
        app_session.execute(
            text(
                """
            SELECT notification_type, is_actionable
            FROM messaging.notifications
            WHERE organization_id = :o AND recipient_id = :u
              AND notification_type = 'task_assigned'
            """
            ),
            {"o": fx["org"], "u": fx["member"]},
        )
        .mappings()
        .all()
    )

    assert len(notified) == 1, "promoting a message assigned a task to someone and never told them"
    assert notified[0]["is_actionable"] is True, (
        "an assigned task is actionable; §11's badge counts items needing action"
    )


def test_promoting_to_someone_outside_a_restricted_project_does_not_notify_them(
    app_session: Session, channel_fixture: dict[str, uuid.UUID]
) -> None:
    """§7 -- THE NOTIFICATION MUST NOT BE THE LEAK.

    `create_task` proves ORGANIZATION membership, which is not the same as
    being able to see the project. A task on a RESTRICTED project can be
    assigned to an organization member who is not on it, and the
    notification's TITLE would name work they have no access to.

    Found in my own I33 change while writing the test above: the mention path
    had this guard from the start and the task path did not.

    The task is still CREATED -- refusing the assignment is a larger decision.
    Withholding the notification is the narrow thing §7 requires.
    """
    fx = channel_fixture

    channel = create_channel(
        app_session,
        organization_id=fx["org"],
        actor_id=fx["author"],
        spec=ChannelInput(channel_type="project", name="Leaky", project_id=fx["project"]),
    )
    message = post_message(
        app_session,
        channel_id=channel["id"],
        organization_id=fx["org"],
        actor_id=fx["author"],
        spec=MessageInput(body="The catalyst supplier substitution is confidential."),
    )

    promote_message(
        app_session,
        message_id=message["id"],
        organization_id=fx["org"],
        actor_id=fx["author"],
        task_type="experiment",
        title="Confidential catalyst substitution follow-up",
        assigned_user_id=fx["outsider"],
    )

    leaked = app_session.execute(
        text(
            "SELECT count(*) FROM messaging.notifications "
            "WHERE organization_id = :o AND recipient_id = :u"
        ),
        {"o": fx["org"], "u": fx["outsider"]},
    ).scalar_one()

    assert leaked == 0, (
        "somebody outside a restricted project was sent a notification naming its work"
    )
