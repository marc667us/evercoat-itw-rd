"""The proxy and the API must agree about the `/api` prefix.

🔴 WHAT THIS CATCHES

`infrastructure/compose/Caddyfile` carried `uri strip_prefix /api` inside
its `handle /api/*` block, while `app/main.py` mounts every router UNDER
`/api` and `apps/web/lib/api/client.test.ts` asserts the client asks for
`/api/materials` unstripped.

So the proxy rewrote `/api/projects` to `/projects`, which the API does
not serve. **Every API route would have 404'd through the reverse proxy.**

Nothing caught it, and nothing could have:

  * CI talks to uvicorn directly, never through Caddy;
  * the full compose stack has never been up at once (`CLAUDE.md` §15);
  * `tsc`, `ruff` and `mypy` cannot see across a Caddyfile.

This is the platform's recurring shape — *two literals in two files
cannot be type-checked into agreement* — applied to the one hop where a
mismatch takes the entire API offline. The rule was copied from the
`/auth` block, where stripping IS correct because Keycloak serves
`/realms/...` at its root.

It needs no database, no network and no running proxy.
"""

from __future__ import annotations

import re
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = API_ROOT.parents[1]
CADDYFILE = REPO_ROOT / "infrastructure" / "compose" / "Caddyfile"
MAIN_PY = API_ROOT / "app" / "main.py"


def _caddyfile() -> str:
    assert CADDYFILE.exists(), f"the reverse-proxy config is missing: {CADDYFILE}"
    return CADDYFILE.read_text(encoding="utf-8")


def _block(source: str, opener: str) -> str:
    """The body of one `handle ... {` block, by brace matching."""
    start = source.index(opener)
    depth = 0
    for index in range(start, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
    raise AssertionError(f"unterminated block starting at {opener!r}")


def test_the_api_still_mounts_under_the_api_prefix() -> None:
    """The premise of every assertion below.

    If the API is ever re-mounted at the root, this test fails FIRST and
    says so, rather than the proxy assertions silently becoming wrong in
    the other direction.
    """
    source = MAIN_PY.read_text(encoding="utf-8")
    mounts = re.findall(r'include_router\([^)]*prefix="(/[^"]*)"', source, re.S)
    api_mounts = [prefix for prefix in mounts if prefix.startswith("/api")]

    assert api_mounts, (
        "no router is mounted under /api any more. If that is deliberate, "
        "the Caddyfile's /api handling must change with it -- and this test "
        "is the reminder that the two files have to move together."
    )


def test_the_proxy_does_not_strip_the_prefix_the_api_expects() -> None:
    block = _block(_caddyfile(), "handle /api/*")

    assert "strip_prefix /api" not in block, (
        "the reverse proxy strips /api while the API mounts its routers "
        "UNDER /api, so every route 404s through the proxy. This is the "
        "defect the file's own comment now documents; do not reinstate it."
    )
    assert "reverse_proxy api:8000" in block, (
        "the /api block no longer forwards to the API service at all"
    )


def test_the_auth_block_still_strips_because_keycloak_serves_at_its_root() -> None:
    """The positive case, so the rule is understood rather than obeyed.

    A blanket "never strip_prefix" would break identity: Keycloak serves
    `/realms/...` at its root, so `/auth/realms/x` MUST become
    `/realms/x`. The difference between the two blocks is the point.
    """
    block = _block(_caddyfile(), "handle /auth/*")

    assert "strip_prefix /auth" in block, (
        "the /auth block stopped stripping its prefix; Keycloak serves "
        "/realms/... at its root, so /auth/realms/x would 404"
    )


def test_metrics_are_refused_at_the_edge() -> None:
    """`/metrics` is unauthenticated in the API and must not be public.

    It enumerates every route template and its traffic — free
    reconnaissance. The Caddyfile previously CLAIMED metrics were kept off
    the internet while providing no `/metrics` handler at all, and the
    `/api/*` strip_prefix meant `/api/metrics` reached it regardless.
    """
    source = _caddyfile()
    assert "handle /metrics" in source, (
        "there is no /metrics handler, so the request falls through to the "
        "catch-all. Refuse it explicitly: a route that is private by "
        "accident is not private."
    )

    block = _block(source, "handle /metrics")
    assert "respond 404" in block, f"the /metrics block does not refuse the request: {block!r}"
    assert "reverse_proxy" not in block, (
        "the /metrics block forwards to a backend; the API's Prometheus "
        "endpoint has no authentication of its own"
    )
