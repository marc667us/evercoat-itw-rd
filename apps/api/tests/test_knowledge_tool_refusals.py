"""The knowledge tool's two refusals: too poor to quote, and too broken to run.

Both exist because routing MSD's fallback into a search put a database query
in front of a refusal that used to be pure Python. That change is only safe if
the search declines to answer as readily as the refusal it replaced.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from sqlalchemy.exc import OperationalError

import app.agents.tools.knowledge as knowledge_tool
from app.agents.tools.knowledge import MAX_DISTANCE, search_knowledge


class _FakeSavepoint:
    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True


class _FakeSession:
    """Only the one method the tool uses. A real Session is not needed to show
    that a failing query does not escape as a 500."""

    def __init__(self) -> None:
        self.savepoint = _FakeSavepoint()

    def begin_nested(self) -> _FakeSavepoint:
        return self.savepoint


def _row(distance: float) -> dict[str, Any]:
    return {
        "content": "Cure at 60 C for 30 minutes.",
        "title": "Cure schedule",
        "source": "procedure",
        "document_id": uuid.uuid4(),
        "ordinal": 1,
        "classification": "INTERNAL",
        "distance": distance,
    }


def test_a_poor_match_is_not_quoted(monkeypatch: pytest.MonkeyPatch) -> None:
    """🔴 `distance` WAS COMPUTED, CARRIED OUT, AND READ BY NOBODY.

    `retrieve` orders by distance and returns the top rows, so it returns
    something whenever the library is non-empty. Its comment claimed the value
    was surfaced "so the composer can decline to quote a poor match" and no
    caller ever declined anything -- the codebase's own "comment claims a
    capability that does not exist" pattern, found by the Supervisor.

    With the fallback now routing every unrouted question here, the effect was
    that "thoughts on the weather" was answered with four quoted passages from
    real -- possibly CONFIDENTIAL-tier -- documents, presented as responsive.
    """
    monkeypatch.setattr(knowledge_tool, "retrieve", lambda *a, **k: [_row(MAX_DISTANCE + 0.01)])
    assert search_knowledge(_FakeSession(), organization_id=uuid.uuid4(), question="q") == []


def test_a_good_match_still_is(monkeypatch: pytest.MonkeyPatch) -> None:
    """The falsification of the test above.

    A threshold that rejected everything would make it pass while deleting the
    feature -- and an empty knowledge search is indistinguishable from a
    working one that found nothing, so nothing else would have complained.

    ⚠️ THE QUESTION USED TO BE `"q"`, AND THAT STOPPED BEING ENOUGH.
    A second condition now guards this path -- the question must share a
    content word with the passage -- so a one-letter placeholder is refused for
    a reason that has nothing to do with the distance this test is about. The
    question below overlaps the passage on "cure", which is what a real caller
    would look like.
    """
    monkeypatch.setattr(knowledge_tool, "retrieve", lambda *a, **k: [_row(MAX_DISTANCE - 0.01)])
    found = search_knowledge(
        _FakeSession(), organization_id=uuid.uuid4(), question="what is the cure schedule"
    )
    assert len(found) == 1
    assert found[0]["title"] == "Cure schedule"


def test_a_close_passage_about_something_else_is_not_quoted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """🔴 THE THRESHOLD ALONE STOPPED SEPARATING RELEVANT FROM IRRELEVANT.

    Re-measured 2026-08-23 against a five-document library -- four times the
    corpus `MAX_DISTANCE` was derived on, and still small. The related and
    unrelated distance ranges OVERLAP:

        related    0.554 .. 0.716
        unrelated  0.664 .. 0.859

    "my favourite colour is blue" scored **0.664**, better than a genuinely
    related question at 0.716, and was quoted four passages of body-filler
    procedure as though responsive. No value of MAX_DISTANCE separates those
    two sets, so retuning it would be choosing a number that looks decisive
    and decides nothing.

    The guard is shared vocabulary, which is the only thing a LEXICAL embedder
    can actually attest to. This test pins the case the threshold missed: a
    passage well inside the distance cut, on a subject the question never
    mentions.
    """
    monkeypatch.setattr(knowledge_tool, "retrieve", lambda *a, **k: [_row(0.60)])
    found = search_knowledge(
        _FakeSession(),
        organization_id=uuid.uuid4(),
        question="my favourite colour is blue",
    )
    assert found == [], (
        "a passage about a cure schedule was quoted in answer to a question "
        "about a favourite colour, at a distance well inside MAX_DISTANCE. "
        "The distance cut cannot catch this; shared subject matter can."
    )


def test_a_question_of_pure_filler_words_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ "why?" is a question the knowledge base cannot answer.

    Distinct from the test above: there is nothing to overlap WITH, rather
    than an overlap that fails. Both must refuse, and for a caller the two are
    the same answer -- but a future change that made empty questions match
    everything would only be caught here.
    """
    monkeypatch.setattr(knowledge_tool, "retrieve", lambda *a, **k: [_row(0.10)])
    assert (
        search_knowledge(_FakeSession(), organization_id=uuid.uuid4(), question="why? is it") == []
    )


def test_a_broken_knowledge_tier_is_a_refusal_not_a_500(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """🔴 A FEATURE THAT IS ABSENT MUST NOT TAKE THE CONVERSATION WITH IT.

    Before the fallback change an unrecognised question touched no database at
    all. Afterwards every one of them runs a query, and migration 042 may
    simply not be applied in a given environment -- so the failure mode is not
    exotic. Unhandled, it escaped `answer()` as a 500 AND poisoned the caller's
    transaction, so `record_exchange` could not even store the user's turn.
    """

    def _boom(*a: object, **k: object) -> None:
        raise OperationalError(
            "SELECT 1", {}, Exception('relation "knowledge.chunks" does not exist')
        )

    monkeypatch.setattr(knowledge_tool, "retrieve", _boom)
    session = _FakeSession()

    assert search_knowledge(session, organization_id=uuid.uuid4(), question="q") == []
    assert session.savepoint.rolled_back, (
        "the savepoint was not rolled back, so the enclosing transaction is "
        "still poisoned and the turn cannot be recorded"
    )
