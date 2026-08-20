"""A metrics label must be a route TEMPLATE, never an attacker's path.

🔴 WHAT THIS CATCHES, AND WHY NOTHING ELSE DID

`main.py`'s access-log middleware read `request.scope["route"]` at the
TOP of the middleware and fell back to `request.url.path`. Starlette's
router is what writes `route` into the scope, and the router runs
*inside* `call_next` -- so the key was never present when it was read and
the fallback fired on **every single request**. The comment above the
line said "route template, not the concrete path"; the code did the exact
opposite of what its own comment claimed.

Prometheus creates one time series per distinct label value. So:

  * `/api/projects/<uuid>` minted a new series per project, and
  * an ANONYMOUS caller could mint an unbounded number of them by
    requesting `/whatever/<nonce>`, growing the API process and the
    monitoring backend until one of them fell over.

Found by Codex during the 2026-08-20 API security audit.

This test needs no database and no Keycloak: it drives the real ASGI app
and then reads the real collector.
"""

from __future__ import annotations

import os
import uuid

import pytest

# Settings are constructed at import time and have no defaults for these
# two -- deliberately, so a missing database password stops the process
# rather than connecting somewhere unintended (`core/config.py`). CI
# supplies both; this keeps the file runnable on a developer machine.
# `127.0.0.1:1` is a port nothing listens on: no JWKS fetch is made here,
# and if one ever were, it must fail rather than reach a real realm.
os.environ.setdefault(
    "DATABASE_URL", "postgresql+psycopg://evercoat_app:unused@127.0.0.1:1/evercoat_itw_rd"
)
os.environ.setdefault("KEYCLOAK_ISSUER", "http://127.0.0.1:1/realms/evercoat")

from fastapi.testclient import TestClient

from app.main import REQUESTS, UNMATCHED_ROUTE_LABEL, app


def _path_labels() -> set[str]:
    """Every `path` label value the request counter currently holds."""
    return {
        sample.labels["path"]
        for metric in REQUESTS.collect()
        for sample in metric.samples
        if "path" in sample.labels
    }


@pytest.fixture
def client() -> TestClient:
    # Server exceptions must not be re-raised: the middleware's own
    # exception branch is one of the two places the label is computed,
    # and a test that never reaches it proves half the fix.
    return TestClient(app, raise_server_exceptions=False)


def test_unrouted_paths_collapse_into_one_label(client: TestClient) -> None:
    """Twenty distinct 404s must produce ONE new label value, not twenty."""
    nonces = [uuid.uuid4().hex for _ in range(20)]

    before = _path_labels()
    for nonce in nonces:
        response = client.get(f"/no-such-route/{nonce}")
        assert response.status_code == 404, (
            f"/no-such-route/{nonce} was routed to something; pick a path that 404s"
        )

    after = _path_labels()

    leaked = {label for label in after if any(nonce in label for nonce in nonces)}
    assert not leaked, (
        "attacker-controlled path segments became Prometheus label values, so "
        "an anonymous caller can mint unbounded time series: "
        f"{sorted(leaked)[:5]}"
    )

    assert UNMATCHED_ROUTE_LABEL in after, (
        "unrouted requests produced no label at all; they must collapse into "
        f"the single fixed value {UNMATCHED_ROUTE_LABEL!r}"
    )

    # The counter must have grown by at most the one collapsed label --
    # asserting only "no nonce leaked" would also pass if the middleware
    # stopped recording anything at all.
    new_labels = after - before
    assert new_labels <= {UNMATCHED_ROUTE_LABEL}, (
        f"unrouted requests added more than one label value: {sorted(new_labels)}"
    )


def test_a_matched_route_reports_its_template(client: TestClient) -> None:
    """The fix must not have thrown away the real labels along with the bad ones.

    A version that returned `<unmatched>` for everything would pass the
    test above while making the metrics useless, so the positive case is
    asserted too.
    """
    response = client.get("/health/live")
    assert response.status_code == 200, response.text

    assert "/health/live" in _path_labels(), (
        "a matched route did not report its own template; the label is now bounded but says nothing"
    )


def test_a_path_parameter_is_not_expanded_into_the_label(client: TestClient) -> None:
    """`/api/projects/{project_id}`, never `/api/projects/<a real uuid>`.

    This is the case that bites in NORMAL operation rather than under
    attack: one series per project, forever, with no attacker involved.
    """
    project_id = uuid.uuid4()

    # Unauthenticated, so this refuses long before touching a database --
    # 401/403 is the expected answer and is all this test needs. What
    # matters is which LABEL the middleware recorded on the way out.
    client.get(f"/api/projects/{project_id}")

    labels = _path_labels()
    assert str(project_id) not in " ".join(labels), (
        "a concrete uuid reached the metrics labels; every project would create its own time series"
    )
