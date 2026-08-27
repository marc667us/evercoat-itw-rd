"""A wrong relationship was permanent, and the correction must not erase it.

🔴 THE DEFECT. `quality.hypothesis_evidence` carries
`UNIQUE (hypothesis_id, evidence_id)` and `link_evidence` does a plain INSERT,
so a chemist who recorded an observation as `supports` and then realised it
`contradicts` could not re-link it — the pair key refused the second row — and
nothing else could change it. Raised by the Supervisor against the Slice 6
browser, on a screen whose own header argues that hiding contradicting evidence
is what makes every hypothesis look well-founded. A relationship that cannot be
corrected is that failure with an extra step.

🔴 AND THE CORRECTION MUST LEAVE THE OLD READING RECOVERABLE. §5 forbids
destroying R&D history and an evidence link is a judgement with an author and a
timestamp. The UPDATE writes an `audit.events` row carrying `previous_state`,
so "X said supports on Tuesday, Y said contradicts on Thursday" survives in the
append-only hash-chained table this system keeps history in.

⚠️ SO THE INTERESTING ASSERTION IS NOT "THE ROW CHANGED". A test that only
checked the new value would pass against an implementation that overwrote the
old one and told nobody — which is the version §5 forbids. Each case below also
asserts what is left behind.
"""

from __future__ import annotations

import datetime as dt
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.domains.failures.service import (
    FailureError,
    FailureNotFoundError,
    get_failure,
    link_evidence,
    relabel_evidence_link,
)


@pytest.fixture
def linked(owner_session: Session) -> dict[str, uuid.UUID]:
    """An investigation with one hypothesis, one piece of evidence, one link."""
    org = uuid.uuid4()
    project = uuid.uuid4()
    failure = uuid.uuid4()
    person = uuid.uuid4()
    corrector = uuid.uuid4()
    hypothesis = uuid.uuid4()
    evidence = uuid.uuid4()

    owner_session.execute(
        text(
            "INSERT INTO core.organizations (id, name, code) VALUES (:id, 'Relabel Fixture', :code)"
        ),
        {"id": org, "code": f"RLF{str(org)[:6]}"},
    )
    owner_session.execute(
        text(
            "INSERT INTO projects.projects "
            "  (id, organization_id, project_code, name, current_stage) "
            "VALUES (:id, :org, :code, 'Fixture project', 'concept')"
        ),
        {"id": project, "org": org, "code": f"RLP-{str(project)[:8]}"},
    )
    for who, name in ((person, "First Reader"), (corrector, "Second Reader")):
        owner_session.execute(
            text(
                "INSERT INTO core.users (id, keycloak_sub, email, display_name) "
                "VALUES (:id, :sub, :email, :name)"
            ),
            {"id": who, "sub": f"rlf-{who}", "email": f"rlf-{who}@fixture.invalid", "name": name},
        )
        owner_session.execute(
            text(
                "INSERT INTO core.organization_members "
                "  (organization_id, user_id, status, email, display_name) "
                "VALUES (:org, :uid, 'active', :email, :name)"
            ),
            {"org": org, "uid": who, "email": f"rlf-{who}@fixture.invalid", "name": name},
        )
    owner_session.execute(
        text(
            "INSERT INTO quality.failures "
            "  (id, organization_id, project_id, failure_code, title, severity, "
            "   status, opened_by) "
            "VALUES (:id, :org, :pid, :code, 'Adhesion loss on cure', 'major', "
            "        'open', :who)"
        ),
        {
            "id": failure,
            "org": org,
            "pid": project,
            "code": f"FL-{str(failure)[:8]}",
            "who": person,
        },
    )
    owner_session.execute(
        text(
            "INSERT INTO quality.failure_hypotheses "
            "  (id, organization_id, project_id, failure_id, possible_cause, "
            "   confidence, origin, status, proposed_by) "
            "VALUES (:id, :org, :pid, :fid, 'Filler surface treatment', "
            "        'medium', 'human', 'proposed', :who)"
        ),
        {"id": hypothesis, "org": org, "pid": project, "fid": failure, "who": person},
    )
    owner_session.execute(
        text(
            "INSERT INTO quality.failure_evidence "
            "  (id, organization_id, project_id, failure_id, evidence_type, "
            "   summary, origin, recorded_by) "
            "VALUES (:id, :org, :pid, :fid, 'batch_deviation', "
            "        'Lot 4471 weighed 2.1% under target', 'human', :who)"
        ),
        {"id": evidence, "org": org, "pid": project, "fid": failure, "who": person},
    )
    owner_session.flush()

    link_evidence(
        owner_session,
        hypothesis_id=hypothesis,
        evidence_id=evidence,
        organization_id=org,
        actor_id=person,
        relationship="supports",
        note="the deviation is in the right direction",
    )
    owner_session.flush()

    return {
        "org": org,
        "project": project,
        "failure": failure,
        "person": person,
        "corrector": corrector,
        "hypothesis": hypothesis,
        "evidence": evidence,
    }


def _link(session: Session, ids: dict[str, uuid.UUID]) -> dict[str, object]:
    return dict(
        session.execute(
            text(
                "SELECT relationship, note, linked_by FROM quality.hypothesis_evidence "
                "WHERE hypothesis_id = :hid AND evidence_id = :eid"
            ),
            {"hid": ids["hypothesis"], "eid": ids["evidence"]},
        )
        .mappings()
        .one()
    )


def _audit(session: Session, ids: dict[str, uuid.UUID]) -> list[dict[str, object]]:
    return [
        dict(r)
        for r in session.execute(
            text(
                "SELECT action, previous_state, new_state, user_id FROM audit.events "
                "WHERE organization_id = :org AND action = 'failure.evidence_relabelled' "
                "ORDER BY id"
            ),
            {"org": ids["org"]},
        ).mappings()
    ]


def test_the_pair_key_still_refuses_a_second_link(
    owner_session: Session, linked: dict[str, uuid.UUID]
) -> None:
    """🔴 THE DEFECT ITSELF, PINNED — the reason a relabel had to exist.

    If re-linking ever starts working, this test goes red and whoever changed it
    has to decide deliberately whether a second row per pair is wanted. Without
    it, "you cannot re-link" is a claim in a docstring rather than a property.
    """
    with pytest.raises(FailureError) as caught:
        link_evidence(
            owner_session,
            hypothesis_id=linked["hypothesis"],
            evidence_id=linked["evidence"],
            organization_id=linked["org"],
            actor_id=linked["person"],
            relationship="contradicts",
        )
    assert "already linked" in str(caught.value)


def test_a_relationship_can_be_corrected(
    owner_session: Session, linked: dict[str, uuid.UUID]
) -> None:
    assert _link(owner_session, linked)["relationship"] == "supports"

    result = relabel_evidence_link(
        owner_session,
        hypothesis_id=linked["hypothesis"],
        evidence_id=linked["evidence"],
        organization_id=linked["org"],
        actor_id=linked["corrector"],
        relationship="contradicts",
        note="it is in the WRONG direction for this mechanism",
    )
    owner_session.flush()

    assert result["changed"] is True
    row = _link(owner_session, linked)
    assert row["relationship"] == "contradicts"
    assert row["note"] == "it is in the WRONG direction for this mechanism"
    # The corrector's name is on it now, which is what makes the row current
    # rather than merely different.
    assert row["linked_by"] == linked["corrector"]


def test_the_previous_reading_survives_in_the_audit_chain(
    owner_session: Session, linked: dict[str, uuid.UUID]
) -> None:
    """🔴 THE ASSERTION AN OVERWRITE CANNOT PASS.

    Everything above is satisfied by an UPDATE that tells nobody. §5 forbids
    destroying R&D history, so what makes this correction legitimate rather
    than a quiet edit is that the old reading, and who gave it, are recoverable
    afterwards.
    """
    relabel_evidence_link(
        owner_session,
        hypothesis_id=linked["hypothesis"],
        evidence_id=linked["evidence"],
        organization_id=linked["org"],
        actor_id=linked["corrector"],
        relationship="contradicts",
        note="it is in the WRONG direction",
    )
    owner_session.flush()

    events = _audit(owner_session, linked)
    assert len(events) == 1, f"expected one relabel event, found {len(events)}"

    previous = events[0]["previous_state"]
    assert isinstance(previous, dict)
    assert previous["relationship"] == "supports", (
        "the audit event does not carry the reading that was replaced, so the "
        "correction destroyed it"
    )
    assert previous["note"] == "the deviation is in the right direction"
    assert previous["linked_by"] == str(linked["person"]), (
        "the audit event does not say WHO gave the previous reading"
    )
    assert events[0]["user_id"] == linked["corrector"]


def test_a_correction_that_changes_nothing_is_not_recorded_as_one(
    owner_session: Session, linked: dict[str, uuid.UUID]
) -> None:
    """A no-op must not fill the append-only chain with entries to rule out.

    ⚠️ AND IT MUST NOT SILENTLY SUCCEED AS THOUGH IT HAD DONE SOMETHING, which
    is why `changed` comes back False rather than the call simply returning.
    """
    result = relabel_evidence_link(
        owner_session,
        hypothesis_id=linked["hypothesis"],
        evidence_id=linked["evidence"],
        organization_id=linked["org"],
        actor_id=linked["corrector"],
        relationship="supports",
        note="the deviation is in the right direction",
    )
    owner_session.flush()

    assert result["changed"] is False
    assert _audit(owner_session, linked) == []
    # And the original author is still the author — a no-op must not quietly
    # reassign the reading to whoever re-submitted it.
    assert _link(owner_session, linked)["linked_by"] == linked["person"]


def test_an_unlinked_pair_is_refused_rather_than_created(
    owner_session: Session, linked: dict[str, uuid.UUID]
) -> None:
    """🔴 PATCH IS NOT AN UPSERT.

    A relabel of something that was never linked must be a 404, not a new link.
    An upsert here would let a caller create an assertion through the endpoint
    that exists to correct one — and `link_evidence`, which requires
    `failure.investigate` and the same permission, is where a NEW claim belongs.
    """
    with pytest.raises(FailureNotFoundError):
        relabel_evidence_link(
            owner_session,
            hypothesis_id=linked["hypothesis"],
            evidence_id=uuid.uuid4(),
            organization_id=linked["org"],
            actor_id=linked["corrector"],
            relationship="contradicts",
        )


def test_an_invented_relationship_is_refused(
    owner_session: Session, linked: dict[str, uuid.UUID]
) -> None:
    """The three values are the vocabulary; a fourth is not a nuance."""
    with pytest.raises(FailureError):
        relabel_evidence_link(
            owner_session,
            hypothesis_id=linked["hypothesis"],
            evidence_id=linked["evidence"],
            organization_id=linked["org"],
            actor_id=linked["corrector"],
            relationship="probably_supports",
        )


def test_the_corrected_reading_is_what_the_screen_gets(
    owner_session: Session, linked: dict[str, uuid.UUID]
) -> None:
    """The whole point, read back through the endpoint the workspace calls.

    `get_failure` builds each hypothesis's `evidence` from the bridge table, and
    a correction that did not reach that projection would be invisible on the one
    screen it was made for — the "green in one layer, wrong in the one people
    look at" shape this project keeps finding.
    """
    relabel_evidence_link(
        owner_session,
        hypothesis_id=linked["hypothesis"],
        evidence_id=linked["evidence"],
        organization_id=linked["org"],
        actor_id=linked["corrector"],
        relationship="contradicts",
        note="wrong direction",
    )
    owner_session.flush()

    detail = get_failure(owner_session, failure_id=linked["failure"], organization_id=linked["org"])
    hypotheses = detail["hypotheses"]
    assert len(hypotheses) == 1
    evidence = hypotheses[0]["evidence"]
    assert len(evidence) == 1, "the link vanished from the projection"
    assert evidence[0]["relationship"] == "contradicts"
    assert evidence[0]["note"] == "wrong direction"


def test_the_fixture_time_is_not_used_for_anything(
    owner_session: Session, linked: dict[str, uuid.UUID]
) -> None:
    """`linked_at` moves with the correction, so "when was this last assessed"
    is answerable from the row itself.

    Kept separate because it is the one assertion about the row that is about
    TIME rather than content, and bundling it into the correction test above
    would make that test fail for two unrelated reasons.
    """
    before = owner_session.execute(
        text(
            "SELECT linked_at FROM quality.hypothesis_evidence "
            "WHERE hypothesis_id = :hid AND evidence_id = :eid"
        ),
        {"hid": linked["hypothesis"], "eid": linked["evidence"]},
    ).scalar_one()

    relabel_evidence_link(
        owner_session,
        hypothesis_id=linked["hypothesis"],
        evidence_id=linked["evidence"],
        organization_id=linked["org"],
        actor_id=linked["corrector"],
        relationship="inconclusive",
        note="linked in error; it bears on a different hypothesis",
    )
    owner_session.flush()

    after = owner_session.execute(
        text(
            "SELECT linked_at FROM quality.hypothesis_evidence "
            "WHERE hypothesis_id = :hid AND evidence_id = :eid"
        ),
        {"hid": linked["hypothesis"], "eid": linked["evidence"]},
    ).scalar_one()

    assert isinstance(after, dt.datetime)
    assert after >= before
