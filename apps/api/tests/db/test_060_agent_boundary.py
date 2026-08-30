"""Migration 060 — an agent may draft, and may never publish.

🔴 DRIVEN AS THE AGENT ROLE, AGAINST A REAL DATABASE.

`tests/test_agent_pool_boundary.py` reads the source and proves the conductor
NAMES the agent connection. This proves the connection actually refuses. Both
are needed and neither is the other: a correct call to a trigger that stopped
refusing passes the first; a refusing trigger nothing calls passes the second.

Every case here runs on `agent_engine`. Running them as the owner would find
the boundary absent — the trigger reads `session_user` — and report that as a
pass, which is the same trap `auth_engine` and `public_engine` exist to avoid.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import InternalError, ProgrammingError

pytestmark = pytest.mark.db


def _name() -> str:
    return f"__t_agent_{uuid.uuid4()}__"


@pytest.mark.parametrize("status", ["published", "withdrawn"])
def test_an_agent_cannot_write_a_manufacturer_that_is_not_a_draft(
    agent_engine, status: str
) -> None:
    """The whole point of 060.

    An agent that could publish could put an invented price or an invented SDS
    link in front of anonymous readers as fact, with no human in between.
    """
    with (
        agent_engine.begin() as conn,
        pytest.raises((InternalError, ProgrammingError), match="only write drafts"),
    ):
        conn.execute(
            text(
                """
                INSERT INTO public_intel.manufacturers
                    (name, content_origin, publication_status,
                     is_demonstration_data)
                VALUES (:n, 'synthetic', cast(:s AS public_intel.publication_status),
                        true)
                """
            ),
            {"n": _name(), "s": status},
        )


def test_an_agent_cannot_publish_a_product(agent_engine, owner_engine) -> None:
    marker = _name()
    with owner_engine.begin() as conn:
        manufacturer = conn.execute(
            text(
                "INSERT INTO public_intel.manufacturers "
                "(name, content_origin, publication_status) "
                "VALUES (:n, 'source_derived', 'draft') RETURNING id"
            ),
            {"n": marker},
        ).scalar_one()
    try:
        with (
            agent_engine.begin() as conn,
            pytest.raises((InternalError, ProgrammingError), match="only write drafts"),
        ):
            conn.execute(
                text(
                    """
                    INSERT INTO public_intel.products
                        (manufacturer_id, product_name, content_origin,
                         publication_status, is_demonstration_data)
                    VALUES (:m, 'probe', 'synthetic', 'published', true)
                    """
                ),
                {"m": manufacturer},
            )
    finally:
        with owner_engine.begin() as conn:
            conn.execute(
                text("DELETE FROM public_intel.manufacturers WHERE name = :n"),
                {"n": marker},
            )


def test_an_agent_cannot_record_a_review(agent_engine) -> None:
    """`reviewed_by`/`reviewed_at` is the evidence the publication invariant reads.

    An agent able to set it could manufacture the grounds for a later
    `verified` publication — the review would exist and no human would have
    done one.
    """
    with (
        agent_engine.begin() as conn,
        pytest.raises((InternalError, ProgrammingError), match="may not record a review"),
    ):
        conn.execute(
            text(
                """
                INSERT INTO public_intel.manufacturers
                    (name, content_origin, publication_status, reviewed_at)
                VALUES (:n, 'source_derived', 'draft', clock_timestamp())
                """
            ),
            {"n": _name()},
        )


def test_an_agent_can_write_a_draft_which_is_the_positive_case(agent_engine, owner_engine) -> None:
    """The other direction, without which every refusal above is vacuous.

    A trigger that refused every agent write would pass all three tests above
    and leave the agent tier unable to do the job it exists for.
    """
    marker = _name()
    with agent_engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO public_intel.manufacturers
                    (name, content_origin, publication_status, generated_by)
                VALUES (:n, 'source_derived', 'draft', 'test')
                """
            ),
            {"n": marker},
        )
    try:
        with owner_engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT publication_status, generated_by "
                    "FROM public_intel.manufacturers WHERE name = :n"
                ),
                {"n": marker},
            ).one()
        assert row.publication_status == "draft"
        assert row.generated_by == "test"
    finally:
        with owner_engine.begin() as conn:
            conn.execute(
                text("DELETE FROM public_intel.manufacturers WHERE name = :n"),
                {"n": marker},
            )


def test_an_agent_cannot_promote_an_existing_draft(agent_engine, owner_engine) -> None:
    """The trigger is on UPDATE too, and that is not incidental.

    A rule enforced on INSERT only would let an agent write a draft and then
    promote it a moment later — this repository has already shipped a rule
    enforced on UPDATE only, in the other direction.
    """
    marker = _name()
    with owner_engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO public_intel.manufacturers "
                "(name, content_origin, publication_status) "
                "VALUES (:n, 'source_derived', 'draft')"
            ),
            {"n": marker},
        )
    try:
        with (
            agent_engine.begin() as conn,
            pytest.raises((InternalError, ProgrammingError), match="only write drafts"),
        ):
            conn.execute(
                text(
                    "UPDATE public_intel.manufacturers "
                    "SET publication_status = 'published' WHERE name = :n"
                ),
                {"n": marker},
            )
    finally:
        with owner_engine.begin() as conn:
            conn.execute(
                text("DELETE FROM public_intel.manufacturers WHERE name = :n"),
                {"n": marker},
            )


def test_an_agent_cannot_read_the_access_request_queue(agent_engine) -> None:
    """Those rows are names and work addresses submitted by members of the public."""
    with (
        agent_engine.connect() as conn,
        pytest.raises(ProgrammingError, match="permission denied"),
    ):
        conn.execute(text("SELECT count(*) FROM public_intel.access_requests"))


@pytest.mark.parametrize("table", ["manufacturers", "products", "news_items", "product_documents"])
def test_an_agent_cannot_delete(agent_engine, table: str) -> None:
    """No DELETE anywhere: the drafts ARE the record of what it proposed."""
    with (
        agent_engine.connect() as conn,
        pytest.raises(ProgrammingError, match="permission denied"),
    ):
        conn.execute(text(f"DELETE FROM public_intel.{table}"))  # noqa: S608


def test_an_agent_cannot_reach_a_tenant_table(agent_engine) -> None:
    for table in ("competitors.products", "materials.materials", "core.users"):
        with (
            agent_engine.connect() as conn,
            pytest.raises(ProgrammingError, match="permission denied"),
        ):
            conn.execute(text(f"SELECT count(*) FROM {table}"))  # noqa: S608
